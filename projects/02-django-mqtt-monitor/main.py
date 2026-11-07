"""Project 02: DHT11 + SSD1315 OLED + MQTT and GPIO4/15 alarms."""
import dht
import framebuf
import network
import socket
import time
import ujson
from machine import I2C, Pin, PWM
from project_config import MQTT_HOST, MQTT_PORT, DEVICE_ID
from wifi_config import WIFI_SSID, WIFI_PASSWORD

SENSOR_PIN = 2
LED_PIN = 4                         # D4 / GPIO4 on the user's board
BUZZER_PIN = 15                     # D15 / GPIO15; passive buzzer via PWM
BUTTON_PIN = 21                     # D21 / GPIO21; switch connects to 3.3 V
I2C_SCL_PIN = 18
I2C_SDA_PIN = 19
OLED_ADDRESS = 0x3C
TEMP_THRESHOLD_C = 25
HUMIDITY_THRESHOLD_RH = 60
SAMPLE_INTERVAL_MS = 2500
LED_ON_LEVEL = 1
LED_OFF_LEVEL = 0
BUZZER_FREQUENCY_HZ = 2000
BUZZER_DUTY_U16 = 32768
BUZZER_ON_MS = 250
BUZZER_OFF_MS = 250
ROOT_TOPIC = 'esp32/%s' % DEVICE_ID


class SSD1315:
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(128 * 64 // 8)
        self.frame = framebuf.FrameBuffer(self.buffer, 128, 64, framebuf.MONO_VLSB)
        for command in (0xAE, 0x20, 0x00, 0x40, 0xA1, 0xC8, 0x81, 0x7F,
                        0xA6, 0xA8, 0x3F, 0xD3, 0x00, 0xD5, 0x80, 0xD9,
                        0xF1, 0xDA, 0x12, 0xDB, 0x40, 0x8D, 0x14, 0xAF):
            self.command(command)

    def command(self, value):
        self.i2c.writeto(self.address, bytes((0x00, value)))

    def show(self):
        self.command(0x21)
        self.command(0)
        self.command(127)
        self.command(0x22)
        self.command(0)
        self.command(7)
        self.i2c.writeto(self.address, b'\x40' + self.buffer)


def draw_scaled_text(frame, scratch, value, x, y, scale):
    """Draw large numeric text with MicroPython's built-in 8x8 font."""
    font = framebuf.FrameBuffer(scratch, 8, 8, framebuf.MONO_VLSB)
    for char in value:
        font.fill(0)
        font.text(char, 0, 0, 1)
        for row in range(8):
            for column in range(8):
                if font.pixel(column, row):
                    frame.fill_rect(x + column * scale, y + row * scale,
                                    scale, scale, 1)
        x += 8 * scale


def remaining_length(value):
    encoded = bytearray()
    while True:
        digit = value % 128
        value //= 128
        if value:
            digit |= 0x80
        encoded.append(digit)
        if not value:
            return encoded


def mqtt_string(value):
    value = value.encode()
    return bytes((len(value) >> 8, len(value) & 255)) + value


class MQTT:
    """Small MQTT 3.1.1 QoS 0 client for this single-device learning project."""
    def __init__(self):
        self.sock = None
        self.buffer = b''
        self.packet_id = 1

    def _send(self, header, body):
        pending = bytes((header,)) + remaining_length(len(body)) + body
        while pending:
            sent = self.sock.write(pending)
            if not sent:
                raise OSError('MQTT socket write failed')
            pending = pending[sent:]

    def _read_exactly(self, count):
        result = b''
        while len(result) < count:
            chunk = self.sock.read(count - len(result))
            if not chunk:
                raise OSError('MQTT broker closed the connection')
            result += chunk
        return result

    def connect(self):
        self.close()
        sock = socket.socket()
        sock.settimeout(0.5)
        self.sock = sock
        sock.connect((MQTT_HOST, MQTT_PORT))
        client_id = 'e32-' + DEVICE_ID
        body = mqtt_string('MQTT') + bytes((4, 2, 0, 30)) + mqtt_string(client_id)
        self._send(0x10, body)
        if self._read_exactly(4) != b'\x20\x02\x00\x00':
            raise OSError('MQTT broker rejected the connection')
        topic = ROOT_TOPIC + '/command'
        body = bytes((self.packet_id >> 8, self.packet_id & 255)) + mqtt_string(topic) + b'\x00'
        self._send(0x82, body)
        self.packet_id = self.packet_id % 65535 + 1
        self.sock.settimeout(0.05)

    def publish(self, topic, payload):
        body = mqtt_string(topic) + payload.encode()
        self._send(0x30, body)

    def poll(self):
        try:
            chunk = self.sock.read(256)
            if chunk:
                self.buffer += chunk
        except OSError:
            return None
        if len(self.buffer) < 2:
            return None
        header = self.buffer[0]
        remaining = 0
        multiplier = 1
        index = 1
        while True:
            if index >= len(self.buffer):
                return None
            digit = self.buffer[index]
            remaining += (digit & 127) * multiplier
            index += 1
            if not digit & 128:
                break
            multiplier *= 128
        if len(self.buffer) < index + remaining:
            return None
        packet = self.buffer[index:index + remaining]
        self.buffer = self.buffer[index + remaining:]
        if header >> 4 != 3 or len(packet) < 4:
            return None
        topic_length = packet[0] * 256 + packet[1]
        topic = packet[2:2 + topic_length]
        payload = packet[2 + topic_length:]
        if topic == (ROOT_TOPIC + '/command').encode():
            return payload
        return None

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self.buffer = b''


def start_wifi():
    wlan = network.WLAN(network.WLAN.IF_STA)
    wlan.active(True)
    wlan.config(reconnects=-1)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    return wlan


def main():
    i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
    if OLED_ADDRESS not in i2c.scan():
        raise OSError('SSD1315 OLED not found at 0x%02X' % OLED_ADDRESS)
    oled = SSD1315(i2c, OLED_ADDRESS)
    font_scratch = bytearray(8)
    sensor = dht.DHT11(Pin(SENSOR_PIN))
    led = Pin(LED_PIN, Pin.OUT, value=LED_OFF_LEVEL)
    buzzer = PWM(Pin(BUZZER_PIN))
    buzzer.freq(BUZZER_FREQUENCY_HZ)
    buzzer.duty_u16(0)
    button = Pin(BUTTON_PIN, Pin.IN, Pin.PULL_DOWN)
    wlan = start_wifi()
    client = MQTT()
    mode = 'auto'
    manual_on = False
    temperature = humidity = None
    sensor_ok = False
    alarm = False
    buzzer_silenced = False
    button_was_pressed = False
    buzzer_phase_on = False
    buzzer_phase_started = time.ticks_ms()
    error = 'Waiting for first reading'
    last_sample = time.ticks_ms() - SAMPLE_INTERVAL_MS
    last_wifi_attempt = time.ticks_ms()
    last_mqtt_attempt = time.ticks_ms() - 5000
    print('MQTT broker:', MQTT_HOST, 'device:', DEVICE_ID,
          'LED: GPIO4, buzzer: GPIO15, mute button: GPIO21')

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_sample) >= SAMPLE_INTERVAL_MS:
            try:
                sensor.measure()
                temperature = sensor.temperature()
                humidity = sensor.humidity()
                sensor_ok = True
                error = ''
            except OSError as exc:
                sensor_ok = False
                error = 'DHT11 read error'
                print(error, exc)
            if sensor_ok:
                alarm = temperature > TEMP_THRESHOLD_C and humidity > HUMIDITY_THRESHOLD_RH
                if not alarm:
                    buzzer_silenced = False
            if mode == 'auto' and sensor_ok:
                led.value(LED_ON_LEVEL if alarm else LED_OFF_LEVEL)
            last_sample = time.ticks_ms()
            if client.sock:
                try:
                    record = {'type': 'reading', 'device_id': DEVICE_ID,
                              'temperature': temperature, 'humidity': humidity,
                              'sensor_ok': sensor_ok, 'error': error,
                              'alarm_condition': alarm, 'mode': mode,
                              'led_on': led.value() == LED_ON_LEVEL,
                              'threshold_temperature': TEMP_THRESHOLD_C,
                              'threshold_humidity': HUMIDITY_THRESHOLD_RH}
                    client.publish(ROOT_TOPIC + '/telemetry', ujson.dumps(record))
                except OSError as exc:
                    print('MQTT publish failed:', exc)
                    client.close()
            print('T:', temperature, 'H:', humidity, 'mode:', mode,
                  'LED:', led.value() == LED_ON_LEVEL)
        if not wlan.isconnected():
            client.close()
            wifi_status = wlan.status()
            if wifi_status != 1 and time.ticks_diff(now, last_wifi_attempt) >= 5000:
                try:
                    wlan.disconnect()
                    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
                    print('Wi-Fi reconnect; status:', wifi_status)
                except OSError as exc:
                    print('Wi-Fi reconnect failed:', exc)
                last_wifi_attempt = now
        elif client.sock is None and time.ticks_diff(now, last_mqtt_attempt) >= 5000:
            try:
                client.connect()
                print('Wi-Fi:', wlan.ifconfig()[0], 'MQTT connected')
            except OSError as exc:
                print('MQTT connect failed:', exc)
                client.close()
            last_mqtt_attempt = now
        if client.sock:
            try:
                message = client.poll()
                if message:
                    command = ujson.loads(message)
                    if command.get('mode') == 'auto':
                        mode = 'auto'
                    elif command.get('mode') == 'manual':
                        mode = 'manual'
                    if mode == 'manual' and command.get('led') in ('on', 'off'):
                        manual_on = command.get('led') == 'on'
                        led.value(LED_ON_LEVEL if manual_on else LED_OFF_LEVEL)
                    elif mode == 'auto' and sensor_ok:
                        alarm = temperature > TEMP_THRESHOLD_C and humidity > HUMIDITY_THRESHOLD_RH
                        led.value(LED_ON_LEVEL if alarm else LED_OFF_LEVEL)
                    ack = {'type': 'command_ack', 'device_id': DEVICE_ID,
                           'command_id': command.get('command_id'), 'mode': mode,
                           'led_on': led.value() == LED_ON_LEVEL}
                    client.publish(ROOT_TOPIC + '/status', ujson.dumps(ack))
            except (OSError, ValueError, KeyError) as exc:
                print('MQTT command error:', exc)
                client.close()
        button_pressed = button.value() == 1
        if button_pressed and not button_was_pressed and alarm:
            buzzer_silenced = True
        button_was_pressed = button_pressed
        if alarm and led.value() == LED_ON_LEVEL and not buzzer_silenced:
            phase_duration = BUZZER_ON_MS if buzzer_phase_on else BUZZER_OFF_MS
            if time.ticks_diff(now, buzzer_phase_started) >= phase_duration:
                buzzer_phase_on = not buzzer_phase_on
                buzzer_phase_started = now
            buzzer.duty_u16(BUZZER_DUTY_U16 if buzzer_phase_on else 0)
        else:
            buzzer.duty_u16(0)
            buzzer_phase_on = False
            buzzer_phase_started = now
        frame = oled.frame
        frame.fill(0)
        frame.text('TEMP', 16, 1, 1)
        frame.text('HUMIDITY', 64, 1, 1)
        frame.hline(0, 10, 128, 1)
        frame.vline(63, 0, 51, 1)

        temp_text = str(temperature) if temperature is not None else '--'
        humidity_text = str(humidity) if humidity is not None else '--'
        temp_scale = 3 if len(temp_text) <= 2 else 2
        humidity_scale = 3 if len(humidity_text) <= 2 else 2
        temp_width = len(temp_text) * 8 * temp_scale
        humidity_width = len(humidity_text) * 8 * humidity_scale
        draw_scaled_text(frame, font_scratch, temp_text,
                         (64 - temp_width) // 2, 14 if temp_scale == 3 else 18,
                         temp_scale)
        draw_scaled_text(frame, font_scratch, humidity_text,
                         64 + (64 - humidity_width) // 2,
                         14 if humidity_scale == 3 else 18, humidity_scale)
        frame.text('C', 28, 42, 1)
        frame.text('% RH', 80, 42, 1)
        frame.hline(0, 51, 128, 1)
        led_label = 'ON' if led.value() == LED_ON_LEVEL else 'OFF'
        mode_label = 'AUTO' if mode == 'auto' else 'MAN'
        state_label = 'ERR' if not sensor_ok else ('ALARM' if alarm else 'OK')
        footer = 'LED %s %s %s' % (led_label, mode_label, state_label)
        frame.text(footer, max(0, (128 - len(footer) * 8) // 2), 56, 1)
        oled.show()
        time.sleep_ms(250)


if __name__ == '__main__':
    main()
