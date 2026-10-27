"""案例 04：通过 Wi-Fi 网页实时显示 DHT11 温湿度。"""
import dht
import network
import socket
import time
import ujson
from machine import Pin
from wifi_config import WIFI_SSID, WIFI_PASSWORD

SENSOR_PIN = 2             # 本板 D2 对应 GPIO2
SAMPLE_INTERVAL_MS = 2500   # DHT11 采样间隔需大于 2 秒

sensor = dht.DHT11(Pin(SENSOR_PIN))
latest = {
    "ok": False,
    "temperature": None,
    "humidity": None,
    "updated_ms": None,
    "error": "等待首次采样",
}

PAGE = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light">
<title>ESP32 温湿度监测</title>
<style>
*{box-sizing:border-box}body{margin:0;min-height:100vh;display:grid;place-items:center;
background:#edf2f7;color:#182b44;font-family:system-ui,-apple-system,sans-serif}
main{width:min(92vw,520px);padding:32px;background:white;border-radius:24px;
box-shadow:0 18px 50px #18304a18}h1{margin:0 0 8px;font-size:clamp(26px,7vw,36px)}
.subtitle{margin:0;color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:28px 0}
.card{padding:22px 16px;border-radius:18px;background:#f4f7fb;text-align:center}
.label{font-size:14px;color:#64748b}.value{margin:8px 0;font-size:clamp(38px,10vw,54px);font-weight:700;color:#1769e0}
.unit{font-size:16px;color:#64748b}.status{min-height:24px;color:#52647c;font-size:14px}
.status.error{color:#b42318}.foot{margin-top:20px;color:#94a3b8;font-size:12px}
@media(max-width:380px){main{padding:22px}.grid{gap:9px}.card{padding:18px 10px}}
</style></head><body><main>
<h1>温湿度监测</h1><p class="subtitle">ESP32 · DHT11 · D2 / GPIO2</p>
<div class="grid"><section class="card"><div class="label">温度</div>
<div class="value" id="temperature">--</div><span class="unit">°C</span></section>
<section class="card"><div class="label">相对湿度</div>
<div class="value" id="humidity">--</div><span class="unit">% RH</span></section></div>
<div class="status" id="status">正在读取传感器…</div>
<p class="foot">页面每秒检查一次；DHT11 约每 2.5 秒采集一次。</p>
</main><script>
const temperature=document.getElementById('temperature');
const humidity=document.getElementById('humidity');
const statusText=document.getElementById('status');
async function refresh(){
  try{
    const response=await fetch('/api/readings',{cache:'no-store'});
    if(!response.ok) throw new Error('HTTP '+response.status);
    const data=await response.json();
    if(data.temperature!==null) temperature.textContent=data.temperature;
    if(data.humidity!==null) humidity.textContent=data.humidity;
    if(data.ok){
      const age=(data.age_ms/1000).toFixed(1);
      statusText.textContent='采集正常 · 数据更新于 '+age+' 秒前';
      statusText.className='status';
    }else{
      statusText.textContent=data.error||'传感器读取失败，显示上次成功数据';
      statusText.className='status error';
    }
  }catch(error){
    statusText.textContent='无法读取 ESP32 数据，请检查网络连接后重试';
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


def sensor_json():
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
        respond(client, '200 OK', sensor_json(), 'application/json; charset=utf-8')
    else:
        respond(client, '404 Not Found', 'Not found')


def sample_sensor():
    global latest
    try:
        sensor.measure()
        latest = {
            'ok': True,
            'temperature': sensor.temperature(),
            'humidity': sensor.humidity(),
            'updated_ms': time.ticks_ms(),
            'error': '',
        }
        print('Temperature: %s C, humidity: %s %%RH'
              % (latest['temperature'], latest['humidity']))
    except OSError as error:
        latest['ok'] = False
        latest['error'] = 'DHT11 读取失败，请检查接线和供电'
        print('DHT11 read error:', error)


def main():
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


if __name__ == '__main__':
    main()
