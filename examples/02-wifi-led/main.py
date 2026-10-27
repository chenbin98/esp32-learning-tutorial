"""ESP32 D2 / GPIO2 web LED control."""
import network
import socket
import time
from machine import Pin
from wifi_config import WIFI_SSID, WIFI_PASSWORD

led = Pin(2, Pin.OUT, value=0)
PAGE = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ESP32 LED</title><style>
body{font-family:system-ui;background:#edf2f7;display:grid;place-items:center;min-height:90vh;color:#182b44}
main{background:white;padding:36px;border-radius:24px;text-align:center;width:min(78vw,360px)}
button{font-size:20px;padding:16px 28px;margin:8px;border:0;border-radius:12px;background:#1769e0;color:white;cursor:pointer}
.lamp{width:64px;height:64px;border-radius:50%%;background:%s;margin:24px auto}
p{color:#52647c}</style><main><h1>ESP32 LED</h1><p>D2 · GPIO2</p>
<div class="lamp"></div><h2>当前状态：%s</h2>
<form method="post" action="/on" style="display:inline"><button>点亮</button></form>
<form method="post" action="/off" style="display:inline"><button style="background:#49576a">熄灭</button></form>
<p>连接同一局域网即可控制</p></main></html>'''


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


def respond(client, status, body='', content_type='text/html; charset=utf-8', extra=''):
    body = body.encode('utf-8')
    header = ('HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n'
              'Connection: close\r\nCache-Control: no-store\r\n%s\r\n'
              % (status, content_type, len(body), extra))
    client.write(header.encode('utf-8'))
    client.write(body)


def handle(client):
    client.settimeout(3)
    request = b''
    while b'\r\n\r\n' not in request:
        chunk = client.recv(256)
        if not chunk:
            return
        request += chunk
        if len(request) > 2048:
            respond(client, '431 Request Header Fields Too Large')
            return
    parts = request.split(b'\r\n', 1)[0].split()
    if len(parts) != 3:
        respond(client, '400 Bad Request')
        return
    method, path, _ = parts
    if method == b'POST' and path in (b'/on', b'/off'):
        led.value(1 if path == b'/on' else 0)
        respond(client, '303 See Other', extra='Location: /\r\n')
    elif method == b'GET' and path == b'/':
        on = bool(led.value())
        respond(client, '200 OK', PAGE % ('#ffcb45' if on else '#c9d2de', '点亮' if on else '熄灭'))
    elif method == b'GET' and path == b'/api/state':
        respond(client, '200 OK', '{"on":%s}' % ('true' if led.value() else 'false'), 'application/json')
    else:
        respond(client, '404 Not Found', 'Not found')


def main():
    wlan = connect_wifi()
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', 80))
    server.listen(2)
    server.settimeout(1)
    try:
        while True:
            if not wlan.isconnected():
                connect_wifi()
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
        led.value(0)


if __name__ == '__main__':
    main()
