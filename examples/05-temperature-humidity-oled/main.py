"""案例 05：将 DHT11 温湿度显示在 I2C SSD1306 OLED 上。"""
import dht
import framebuf
import time
from machine import I2C, Pin

SENSOR_PIN = 2             # D2 / GPIO2
I2C_SCL_PIN = 18            # D18 / GPIO18
I2C_SDA_PIN = 19            # D19 / GPIO19
OLED_ADDRESS = 0x3C         # 常见 SSD1306 地址；部分模块为 0x3D
SAMPLE_INTERVAL_MS = 2500   # DHT11 采样间隔需大于 2 秒


class SSD1306:
    """128x64 SSD1306 最小驱动，使用 MicroPython 内置 framebuf。"""
    def __init__(self, i2c, address):
        self.i2c = i2c
        self.address = address
        self.buffer = bytearray(128 * 64 // 8)
        self.frame = framebuf.FrameBuffer(self.buffer, 128, 64,
                                          framebuf.MONO_VLSB)
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


def text_scaled(display, scratch, value, x, y, scale=2):
    """把 8x8 内置字体逐像素放大，避免依赖外部字体文件。"""
    font = framebuf.FrameBuffer(scratch, 8, 8, framebuf.MONO_VLSB)
    for char in value:
        font.fill(0)
        font.text(char, 0, 0, 1)
        for row in range(8):
            for column in range(8):
                if font.pixel(column, row):
                    display.frame.fill_rect(x + column * scale,
                                            y + row * scale,
                                            scale, scale, 1)
        x += 8 * scale


def main():
    i2c = I2C(0, scl=Pin(I2C_SCL_PIN), sda=Pin(I2C_SDA_PIN), freq=400000)
    devices = i2c.scan()
    print('I2C devices:', [hex(device) for device in devices])
    if OLED_ADDRESS not in devices:
        raise OSError('SSD1306 not found at 0x%02X; check wiring/address' % OLED_ADDRESS)
    display = SSD1306(i2c, OLED_ADDRESS)
    scratch = bytearray(8)
    sensor = dht.DHT11(Pin(SENSOR_PIN))
    last_sample = time.ticks_ms() - SAMPLE_INTERVAL_MS
    temperature = None
    humidity = None
    error = '等待传感器采样'

    while True:
        now = time.ticks_ms()
        if time.ticks_diff(now, last_sample) >= SAMPLE_INTERVAL_MS:
            try:
                sensor.measure()
                temperature = sensor.temperature()
                humidity = sensor.humidity()
                error = ''
                print('Temperature: %s C, humidity: %s %%RH'
                      % (temperature, humidity))
            except OSError as exc:
                error = 'DHT11 读取失败'
                print(error, exc)
            last_sample = time.ticks_ms()

        display.frame.fill(0)
        display.frame.text('TEMP / HUMIDITY', 0, 0, 1)
        display.frame.hline(0, 10, 128, 1)
        text_scaled(display, scratch,
                    'T: %sC' % (temperature if temperature is not None else '--'),
                    0, 14)
        text_scaled(display, scratch,
                    'H: %s%%' % (humidity if humidity is not None else '--'),
                    0, 34)
        display.frame.text(error[:21], 0, 56, 1)
        display.show()
        time.sleep_ms(250)


if __name__ == '__main__':
    main()
