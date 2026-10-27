"""案例 03：手机通过 BLE GATT 写入指令控制 D2 / GPIO2 LED。"""
import bluetooth
import time
from machine import Pin

LED_PIN = 2
DEVICE_NAME = "ESP32-LED-03"
SERVICE_UUID = bluetooth.UUID(0xFFF0)
LED_CHARACTERISTIC_UUID = bluetooth.UUID(0xFFF1)
IRQ_CENTRAL_CONNECT = 1
IRQ_CENTRAL_DISCONNECT = 2
IRQ_GATTS_WRITE = 3
ADV_INTERVAL_US = 100_000

led = Pin(LED_PIN, Pin.OUT, value=0)
ble = bluetooth.BLE()
ble.active(True)
ble.config(gap_name=DEVICE_NAME)

service = (
    SERVICE_UUID,
    ((LED_CHARACTERISTIC_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_WRITE),),
)
(led_state_handle,) = ble.gatts_register_services((service,))[0]
ble.gatts_write(led_state_handle, b"off")

name_bytes = DEVICE_NAME.encode()
advertisement = bytearray((2, 0x01, 0x06))
advertisement.extend((len(name_bytes) + 1, 0x09))
advertisement.extend(name_bytes)
connected = False
last_reported_connection = False


def start_advertising():
    ble.gap_advertise(ADV_INTERVAL_US, adv_data=advertisement)


def on_ble_event(event, data):
    global connected

    if event == IRQ_CENTRAL_CONNECT:
        connected = True
    elif event == IRQ_CENTRAL_DISCONNECT:
        connected = False
        start_advertising()
    elif event == IRQ_GATTS_WRITE:
        _, value_handle = data
        if value_handle != led_state_handle:
            return

        value = bytes(ble.gatts_read(led_state_handle))
        command = value.strip().lower()
        if command in (b"on", b"1") or value == b"\x01":
            led.on()
            ble.gatts_write(led_state_handle, b"on")
        elif command in (b"off", b"0") or value == b"\x00":
            led.off()
            ble.gatts_write(led_state_handle, b"off")
        else:
            state = b"on" if led.value() else b"off"
            ble.gatts_write(led_state_handle, state)


ble.irq(on_ble_event)
start_advertising()
print("BLE ready; scan for %s" % DEVICE_NAME)
print("Service UUID: 0000fff0-0000-1000-8000-00805f9b34fb")
print("LED characteristic UUID: 0000fff1-0000-1000-8000-00805f9b34fb")
print("Write on / off; read the characteristic to check the LED state.")

try:
    while True:
        if connected != last_reported_connection:
            print("Phone connected" if connected else "Phone disconnected; advertising again")
            last_reported_connection = connected
        time.sleep_ms(100)
finally:
    ble.gap_advertise(None)
    ble.active(False)
    led.off()
