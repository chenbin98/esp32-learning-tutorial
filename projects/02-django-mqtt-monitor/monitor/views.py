import json
import uuid
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from paho.mqtt import publish

from .models import DeviceState, Reading


def dashboard(request):
    return render(request, 'dashboard.html')


def _state_json():
    state = DeviceState.objects.filter(device_id=settings.MQTT_DEVICE_ID).first()
    latest_record = Reading.objects.filter(device_id=settings.MQTT_DEVICE_ID).first()
    now = timezone.now()
    pending = bool(state and state.pending_command_id and state.pending_command_at and
                   now - state.pending_command_at < timedelta(seconds=8))
    command_result = state.last_command_result if state else ''
    if state and state.pending_command_id and not pending:
        command_result = 'acknowledgement timeout'
    return {
        'device_id': settings.MQTT_DEVICE_ID,
        'online': bool(state and state.last_seen and now - state.last_seen < timedelta(seconds=15)),
        'last_seen': state.last_seen.isoformat() if state and state.last_seen else None,
        'mode': state.mode if state else 'auto',
        'led_on': state.led_on if state else False,
        'pending_command': pending,
        'command_result': command_result,
        'reading': {
            'temperature': latest_record.temperature,
            'humidity': latest_record.humidity,
            'sensor_ok': latest_record.sensor_ok,
            'alarm_condition': latest_record.alarm_condition,
            'received_at': latest_record.received_at.isoformat(),
            'error': latest_record.error,
        } if latest_record else None,
    }


@require_GET
def latest(request):
    return JsonResponse(_state_json())


@require_GET
def history(request):
    try:
        hours = max(1, min(int(request.GET.get('hours', '24')), 168))
    except ValueError:
        return JsonResponse({'error': 'hours must be an integer'}, status=400)
    since = timezone.now() - timedelta(hours=hours)
    records = list(Reading.objects.filter(device_id=settings.MQTT_DEVICE_ID,
                                          sensor_ok=True, received_at__gte=since)
                   .order_by('received_at'))
    stride = max(1, (len(records) + 1499) // 1500)
    sampled = records[::stride]
    if records and sampled[-1] is not records[-1]:
        sampled.append(records[-1])
    points = [{'time': item.received_at.isoformat(), 'temperature': item.temperature,
               'humidity': item.humidity} for item in sampled]
    return JsonResponse({'hours': hours, 'points': points})


@csrf_exempt
@require_POST
def control(request):
    try:
        payload = json.loads(request.body or b'{}')
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({'ok': False, 'error': 'Invalid JSON'}, status=400)
    mode = payload.get('mode')
    led = payload.get('led')
    if mode not in ('auto', 'manual'):
        return JsonResponse({'ok': False, 'error': 'mode must be auto or manual'}, status=400)
    if mode == 'manual' and led not in ('on', 'off'):
        return JsonResponse({'ok': False, 'error': 'manual mode requires led=on or off'}, status=400)
    command_id = uuid.uuid4().hex[:12]
    topic = 'esp32/%s/command' % settings.MQTT_DEVICE_ID
    body = json.dumps({'command_id': command_id, 'mode': mode, 'led': led})
    state, _ = DeviceState.objects.get_or_create(device_id=settings.MQTT_DEVICE_ID)
    state.pending_command_id = command_id
    state.pending_command_at = timezone.now()
    state.last_command_result = 'waiting for device acknowledgement'
    state.save()
    try:
        publish.single(topic, body, hostname=settings.MQTT_HOST, port=settings.MQTT_PORT,
                       qos=0, retain=False)
    except Exception as exc:
        state.pending_command_id = ''
        state.pending_command_at = None
        state.last_command_result = 'publish failed'
        state.save()
        return JsonResponse({'ok': False, 'error': 'MQTT publish failed: %s' % exc}, status=503)
    return JsonResponse({'ok': True, 'command_id': command_id,
                         'message': 'Command sent; waiting for device status'})
