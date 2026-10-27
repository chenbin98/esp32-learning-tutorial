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
<div class="status" id="status">正在读取传感器…</div>
<p class="rule"><strong>触发条件：</strong>温度 &gt; 25°C <strong>且</strong>湿度 &gt; 60% RH；两个条件必须同时满足。</p>
<p class="foot">浏览器每秒刷新；DHT11 每 2.5 秒采样。读数异常时保留上次有效灯状态并标记数据陈旧。</p>
</main><script>
const temperature=document.getElementById('temperature');
const humidity=document.getElementById('humidity');
const alarmState=document.getElementById('alarmState');
const alarmBox=document.getElementById('alarmBox');
const statusText=document.getElementById('status');
async function refresh(){
  try{
    const response=await fetch('/api/readings',{cache:'no-store'});
    if(!response.ok) throw new Error('HTTP '+response.status);
    const data=await response.json();
    if(data.has_reading){
      temperature.textContent=data.temperature;
      humidity.textContent=data.humidity;
      alarmState.textContent=data.alarm?'报警灯已点亮':'报警灯熄灭';
      alarmBox.className=data.alarm?'alarm active':'alarm';
    }else{
      alarmState.textContent='等待有效传感器读数';
      alarmBox.className='alarm';
    }
    if(data.sensor_ok){
      const age=(data.age_ms/1000).toFixed(1);
      statusText.textContent=(data.alarm?'温湿度同时越界':'条件未同时满足')+' · 数据更新于 '+age+' 秒前';
      statusText.className='status';
    }else if(data.has_reading){
      statusText.textContent=(data.error||'传感器读取失败')+'；当前灯状态沿用上次有效读数';
      statusText.className='status error';
    }else{
      statusText.textContent=data.error||'尚未取得有效读数，报警状态不可用';
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
    return ujson.dumps(result)


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
    parts = request.split(b'\r\n', 1)[0].split()
    if len(parts) != 3:
        respond(client, '400 Bad Request', 'Bad request')
    elif parts[0] == b'GET' and parts[1] == b'/':
        respond(client, '200 OK', PAGE)
    elif parts[0] == b'GET' and parts[1] == b'/api/readings':
        respond(client, '200 OK', readings_json(), 'application/json; charset=utf-8')
    else:
        respond(client, '404 Not Found', 'Not found')


def sample_sensor():
    global latest
    try:
        sensor.measure()
        temperature = sensor.temperature()
        humidity = sensor.humidity()
        alarm = temperature > TEMP_THRESHOLD_C and humidity > HUMIDITY_THRESHOLD_RH
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
        print('Temperature: %s C, humidity: %s %%RH, alarm: %s'
              % (temperature, humidity, 'ON' if alarm else 'OFF'))
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
