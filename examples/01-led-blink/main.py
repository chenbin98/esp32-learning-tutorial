"""案例 01：D2 / GPIO2 LED 亮 1 秒，灭 1 秒。"""
from machine import Pin
from time import sleep

LED_PIN = 2             # 本板 D2 对应 GPIO2；其他板请核对引脚图
LED_ON = 1              # 高电平点亮；低电平点亮的 LED 改为 0
INTERVAL_SECONDS = 1    # 每次亮 / 灭持续的时间，完整周期为它的两倍

led = Pin(LED_PIN, Pin.OUT, value=1 - LED_ON)

try:
    while True:
        led.value(LED_ON)
        sleep(INTERVAL_SECONDS)
        led.value(1 - LED_ON)
        sleep(INTERVAL_SECONDS)
finally:
    led.value(1 - LED_ON)
