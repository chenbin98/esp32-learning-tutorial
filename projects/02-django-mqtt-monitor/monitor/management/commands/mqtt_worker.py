import json

import paho.mqtt.client as mqtt
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from monitor.models import DeviceState, Reading


class Command(BaseCommand):
    help = 'Subscribe to this device MQTT topics and save telemetry in SQLite.'

    def handle(self, *args, **options):
        device_id = settings.MQTT_DEVICE_ID
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                             client_id='django-monitor-' + device_id,
                             protocol=mqtt.MQTTv311)

        def on_connect(mqtt_client, userdata, flags, reason_code, properties):
            if reason_code == 0:
                mqtt_client.subscribe([
                    ('esp32/%s/telemetry' % device_id, 0),
                    ('esp32/%s/status' % device_id, 0),
                ])
                self.stdout.write('MQTT connected; subscribed for %s' % device_id)

        def on_message(mqtt_client, userdata, message):
            try:
                payload = json.loads(message.payload.decode('utf-8'))
                if message.topic.endswith('/telemetry') and payload.get('type') == 'reading':
                    Reading.objects.create(
                        device_id=device_id,
                        temperature=payload.get('temperature'),
                        humidity=payload.get('humidity'),
                        sensor_ok=bool(payload.get('sensor_ok')),
                        alarm_condition=bool(payload.get('alarm_condition')),
                        mode=payload.get('mode', 'auto'),
                        led_on=bool(payload.get('led_on')),
                        error=str(payload.get('error') or '')[:200],
                    )
                    state, _ = DeviceState.objects.get_or_create(device_id=device_id)
                    state.last_seen = timezone.now()
                    state.mode = payload.get('mode', state.mode)
                    state.led_on = bool(payload.get('led_on'))
                    state.save()
                elif message.topic.endswith('/status') and payload.get('type') == 'command_ack':
                    state, _ = DeviceState.objects.get_or_create(device_id=device_id)
                    state.last_seen = timezone.now()
                    state.mode = payload.get('mode', state.mode)
                    state.led_on = bool(payload.get('led_on'))
                    if payload.get('command_id') == state.pending_command_id:
                        state.last_command_result = 'acknowledged by device'
                        state.pending_command_id = ''
                        state.pending_command_at = None
                    state.save()
            except (ValueError, TypeError, KeyError) as exc:
                self.stderr.write('Ignored invalid MQTT message: %s' % exc)

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=30)
        self.stdout.write('Waiting for MQTT messages at %s:%s' %
                          (settings.MQTT_HOST, settings.MQTT_PORT))
        client.loop_forever()
