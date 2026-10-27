"""实战项目 01：温湿度同时越界时点亮 D23 报警灯。"""
import dht
import network
import socket
import time
import ujson
from machine import Pin
from wifi_config import WIFI_SSID, WIFI_PASSWORD

SENSOR_PIN = 2                 # D2 / GPIO2
ALARM_LED_PIN = 23             # D23 / GPIO23
LED_ON_LEVEL = 1               # 本项目接法为高电平点亮
LED_OFF_LEVEL = 0
TEMP_THRESHOLD_C = 25
HUMIDITY_THRESHOLD_RH = 60
SAMPLE_INTERVAL_MS = 2500      # DHT11 采样周期需大于 2 秒

sensor = dht.DHT11(Pin(SENSOR_PIN))
alarm_led = Pin(ALARM_LED_PIN, Pin.OUT, value=LED_OFF_LEVEL)
latest = {
    'sensor_ok': False,
    'has_reading': False,
    'temperature': None,
    'humidity': None,
    'alarm': False,
    'updated_ms': None,
    'error': '等待首次采样',
}
control_mode = 'auto'
manual_led_on = False

PAGE = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>温湿度报警系统 · ESP32 实战项目</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#edf2f7;color:#182b44;font-family:system-ui,-apple-system,sans-serif}
main{width:min(94vw,620px);padding:30px;background:white;border-radius:24px;
box-shadow:0 18px 50px #18304a18}h1{margin:0 0 8px;font-size:clamp(25px,7vw,36px)}
.subtitle{margin:0;color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:13px;margin:24px 0}
.card{padding:19px 14px;border-radius:18px;background:#f4f7fb;text-align:center}
.label{font-size:14px;color:#64748b}.value{margin:7px 0;font-size:clamp(36px,9vw,50px);font-weight:700;color:#1769e0}
.unit{font-size:15px;color:#64748b}.alarm{padding:18px;border-radius:16px;background:#edf2f7;text-align:center}
.alarm.active{background:#fff1f0;color:#b42318}.alarm-title{font-size:21px;font-weight:700}
.controls{margin:18px 0;padding:18px;border:1px solid #e2e8f0;border-radius:16px}
.mode-row,.button-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
[hidden]{display:none!important}
button{border:0;border-radius:10px;padding:11px 15px;background:#e5edf8;color:#20334c;font:inherit;font-weight:600;cursor:pointer}
button.selected{background:#1769e0;color:#fff}button:disabled{opacity:.5;cursor:wait}
.control-note{margin:12px 0 0;color:#64748b;font-size:13px}
.status{min-height:24px;margin-top:14px;color:#52647c;font-size:14px}.status.error{color:#b42318}
.rule{margin:16px 0 0;padding:14px;border-left:4px solid #1769e0;background:#f4f7fb;color:#40536d;font-size:14px}
.foot{margin-top:18px;color:#94a3b8;font-size:12px}
@media(max-width:380px){main{padding:21px}.grid{gap:9px}.card{padding:16px 9px}}
</style></head><body><main>
<h1>温湿度报警系统</h1><p class="subtitle">ESP32 · DHT11 · LED：D23 / GPIO23</p>
<div class="grid"><section class="card"><div class="label">温度</div>
<div class="value" id="temperature">--</div><span class="unit">°C</span></section>
<section class="card"><div class="label">相对湿度</div>
<div class="value" id="humidity">--</div><span class="unit">% RH</span></section></div>
<section class="alarm" id="alarmBox"><div class="label">报警灯状态</div>
<div class="alarm-title" id="alarmState">等待传感器读数</div></section>
<section class="controls"><strong>LED 控制</strong><div id="modeState" class="control-note">当前模式：自动</div>
<div class="mode-row"><button type="button" data-action="mode_auto">自动模式</button>
<button type="button" data-action="mode_manual">手动模式</button></div>
<div id="manualControls" class="button-row" hidden>
<button type="button" data-action="led_on">点亮 LED</button>
<button type="button" data-action="led_off">关闭 LED</button></div>
<p id="controlNote" class="control-note">自动模式按照温湿度阈值控制 LED。</p></section>
<div class="status" id="status">正在读取传感器…</div>
<p class="rule"><strong>触发条件：</strong>温度 &gt; 25°C <strong>且</strong>湿度 &gt; 60% RH；两个条件必须同时满足。</p>
<p class="foot">浏览器每秒刷新；DHT11 每 2.5 秒采样。自动模式读数异常时保留上次有效灯状态；手动模式仍由网页控制。</p>
</main><script>
const temperature=document.getElementById('temperature');
const humidity=document.getElementById('humidity');
const alarmState=document.getElementById('alarmState');
const alarmBox=document.getElementById('alarmBox');
const statusText=document.getElementById('status');
const modeState=document.getElementById('modeState');
const manualControls=document.getElementById('manualControls');
const controlNote=document.getElementById('controlNote');
const controlButtons=[...document.querySelectorAll('[data-action]')];
let controlBusy=false;
function renderControls(data){
  const manual=data.mode==='manual';
  modeState.textContent='当前模式：'+(manual?'手动':'自动');
  manualControls.hidden=!manual;
  controlNote.textContent=manual?'手动模式下自动报警暂停；使用下方按钮直接控制 LED。':'自动模式按照温湿度阈值控制 LED。';
  controlButtons.forEach(button=>{
    button.disabled=controlBusy||((button.dataset.action==='led_on'||button.dataset.action==='led_off')&&!manual);
    button.classList.toggle('selected',button.dataset.action===(manual?'mode_manual':'mode_auto'));
  });
}
async function sendAction(action){
  if(controlBusy) return;
  controlBusy=true;
  controlButtons.forEach(button=>button.disabled=true);
  try{
    const response=await fetch('/api/control',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'action='+encodeURIComponent(action)});
    const result=await response.json();
    if(!response.ok||!result.ok) throw new Error(result.error||'HTTP '+response.status);
  }catch(error){
    statusText.textContent='控制失败：'+error.message;
    statusText.className='status error';
  }finally{
    controlBusy=false;
    await refresh();
  }
}
controlButtons.forEach(button=>button.addEventListener('click',()=>sendAction(button.dataset.action)));
async function refresh(){
  try{
    const response=await fetch('/api/readings',{cache:'no-store'});
    if(!response.ok) throw new Error('HTTP '+response.status);
    const data=await response.json();
    renderControls(data);
    alarmState.textContent=data.led_on?'LED 已点亮':'LED 已关闭';
    alarmBox.className=data.led_on?'alarm active':'alarm';
    if(data.has_reading){
      temperature.textContent=data.temperature;
      humidity.textContent=data.humidity;
    }else{
      temperature.textContent='--';
      humidity.textContent='--';
    }
    if(data.sensor_ok){
      const age=(data.age_ms/1000).toFixed(1);
      const condition=data.alarm_condition?'温湿度同时越界':'自动报警条件未满足';
      statusText.textContent=condition+' · '+(data.mode==='manual'?'自动报警暂停':'自动控制中')+' · 数据更新于 '+age+' 秒前';
      statusText.className='status';
    }else if(data.has_reading){
      statusText.textContent=(data.error||'传感器读取失败')+(data.mode==='manual'?'；手动 LED 状态仍有效':'；当前 LED 状态沿用上次有效读数');
      statusText.className='status error';
    }else{
      statusText.textContent=data.mode==='manual'?'尚无有效传感器读数；手动 LED 控制仍可用':(data.error||'尚未取得有效读数，自动报警状态不可用');
      statusText.className='status error';
    }
  }catch(error){
    statusText.textContent='无法连接 ESP32，请检查 Wi-Fi 网络';
    statusText.className='status error';
  }
}
refresh();
setInterval(refresh,1000);
</script></body></html>'''


def connect_wifi():
    if not WIFI_SSID:
        raise ValueError('Fill in wifi_config.py first')
    wlan = network.WLAN(network.WLAN.IF_STA)
    wlan.active(True)
    wlan.config(reconnects=-1)
    if not wlan.isconnected():
        print('Connecting to Wi-Fi...')
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    start = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), start) > 30000:
            status = wlan.status()
            wlan.disconnect()
            raise RuntimeError('Wi-Fi timeout; check 2.4 GHz SSID/password. Status: %s' % status)
        time.sleep_ms(200)
    print('Open in browser: http://%s/' % wlan.ifconfig()[0])
    return wlan


def respond(client, status, body, content_type='text/html; charset=utf-8'):
    body = body.encode('utf-8')
    header = ('HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
              'Connection: close\r\nCache-Control: no-store\r\n\r\n'
              % (status, content_type, len(body)))
    client.write(header.encode('utf-8'))
    client.write(body)


def readings_json():
    result = dict(latest)
    updated_ms = result.pop('updated_ms')
    result['age_ms'] = (time.ticks_diff(time.ticks_ms(), updated_ms)
                        if updated_ms is not None else None)
    result['mode'] = control_mode
    result['alarm_condition'] = bool(latest['alarm'])
    result['led_on'] = bool(alarm_led.value())
    return ujson.dumps(result)


def set_control(action):
    global control_mode, manual_led_on
    if action == b'mode_manual':
        if control_mode != 'manual':
            manual_led_on = bool(alarm_led.value())
        control_mode = 'manual'
        alarm_led.value(LED_ON_LEVEL if manual_led_on else LED_OFF_LEVEL)
    elif action == b'mode_auto':
        control_mode = 'auto'
        if latest['has_reading']:
            alarm_led.value(LED_ON_LEVEL if latest['alarm'] else LED_OFF_LEVEL)
        else:
            alarm_led.value(LED_OFF_LEVEL)
    elif action == b'led_on' or action == b'led_off':
        if control_mode != 'manual':
            return False
        manual_led_on = action == b'led_on'
        alarm_led.value(LED_ON_LEVEL if manual_led_on else LED_OFF_LEVEL)
    else:
        return False
    return True


def control_json(ok, error=None):
    return ujson.dumps({
        'ok': ok,
        'error': error,
        'mode': control_mode,
        'alarm_condition': bool(latest['alarm']),
        'led_on': bool(alarm_led.value()),
    })


def handle(client):
    client.settimeout(3)
    request = b''
    while b'\r\n\r\n' not in request:
        chunk = client.recv(256)
        if not chunk:
            return
        request += chunk
        if len(request) > 2048:
            respond(client, '431 Request Header Fields Too Large', 'Request too large')
            return
    header, body = request.split(b'\r\n\r\n', 1)
    lines = header.split(b'\r\n')
    parts = lines[0].split()
    content_length = 0
    for line in lines[1:]:
        if line.lower().startswith(b'content-length:'):
            try:
                content_length = int(line.split(b':', 1)[1].strip())
            except ValueError:
                respond(client, '400 Bad Request', 'Invalid Content-Length')
                return
    if content_length < 0 or content_length > 256:
        respond(client, '413 Payload Too Large', 'Request body too large')
        return
    while len(body) < content_length:
        chunk = client.recv(256)
        if not chunk:
            respond(client, '400 Bad Request', 'Incomplete request body')
            return
        body += chunk
    if len(parts) != 3:
        respond(client, '400 Bad Request', 'Bad request')
    elif parts[0] == b'GET' and parts[1] == b'/':
        respond(client, '200 OK', PAGE)
    elif parts[0] == b'GET' and parts[1] == b'/api/readings':
        respond(client, '200 OK', readings_json(), 'application/json; charset=utf-8')
    elif parts[1] == b'/api/control' and parts[0] != b'POST':
        respond(client, '405 Method Not Allowed', 'Use POST')
    elif parts[0] == b'POST' and parts[1] == b'/api/control':
        if not body.startswith(b'action='):
            respond(client, '400 Bad Request', control_json(False, 'Expected action'),
                    'application/json; charset=utf-8')
        else:
            action = body[7:content_length]
            if action in (b'mode_auto', b'mode_manual'):
                set_control(action)
                respond(client, '200 OK', control_json(True),
                        'application/json; charset=utf-8')
            elif action in (b'led_on', b'led_off'):
                if set_control(action):
                    respond(client, '200 OK', control_json(True),
                            'application/json; charset=utf-8')
                else:
                    respond(client, '409 Conflict', control_json(False, 'Switch to manual mode first'),
                            'application/json; charset=utf-8')
            else:
                respond(client, '400 Bad Request', control_json(False, 'Unknown action'),
                        'application/json; charset=utf-8')
    else:
        respond(client, '404 Not Found', 'Not found')


def sample_sensor():
    global latest
    try:
        sensor.measure()
        temperature = sensor.temperature()
        humidity = sensor.humidity()
        alarm = temperature > TEMP_THRESHOLD_C and humidity > HUMIDITY_THRESHOLD_RH
        if control_mode == 'auto':
            alarm_led.value(LED_ON_LEVEL if alarm else LED_OFF_LEVEL)
        latest = {
            'sensor_ok': True,
            'has_reading': True,
            'temperature': temperature,
            'humidity': humidity,
            'alarm': alarm,
            'updated_ms': time.ticks_ms(),
            'error': None,
        }
        print('Temperature: %s C, humidity: %s %%RH, automatic alarm: %s, mode: %s, LED: %s'
              % (temperature, humidity, 'ON' if alarm else 'OFF', control_mode,
                 'ON' if alarm_led.value() else 'OFF'))
    except OSError as error:
        latest['sensor_ok'] = False
        latest['error'] = 'DHT11 读取失败，请检查接线和供电'
        print('DHT11 read error:', error)


def main():
    print('Alarm LED GPIO23 initialized off')
    wlan = connect_wifi()
    sample_sensor()
    last_sample_ms = time.ticks_ms()

    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 80))
    server.listen(2)
    server.settimeout(1)
    try:
        while True:
            now = time.ticks_ms()
            if time.ticks_diff(now, last_sample_ms) >= SAMPLE_INTERVAL_MS:
                sample_sensor()
                last_sample_ms = time.ticks_ms()
            if not wlan.isconnected():
                wlan = connect_wifi()
            try:
                client, _ = server.accept()
            except OSError:
                continue
            try:
                handle(client)
            except OSError as error:
                print('Client error:', error)
            finally:
                client.close()
    finally:
        server.close()
        alarm_led.value(LED_OFF_LEVEL)


if __name__ == '__main__':
    main()
