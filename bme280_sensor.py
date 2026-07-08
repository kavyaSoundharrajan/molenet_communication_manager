# bme280_sensor.py — robust MoleNet BME280 wrapper (auto I2C bus + scan)

import machine
from config import PIN_I2C_SCL, PIN_I2C_SDA
from bme280 import BME280


class BME280Sensor:
    def __init__(self, freq=100_000):
        self.dev = None
        self.i2c = None
        self.addr = None

        # Try I2C bus 0 then 1 (ESP32 commonly uses either)
        for i2c_id in (0, 1):
            try:
                i2c = machine.I2C(
                    i2c_id,
                    scl=machine.Pin(PIN_I2C_SCL),
                    sda=machine.Pin(PIN_I2C_SDA),
                    freq=freq
                )
                addrs = i2c.scan()
                if 0x76 in addrs:
                    self.i2c = i2c
                    self.addr = 0x76
                    break
                if 0x77 in addrs:
                    self.i2c = i2c
                    self.addr = 0x77
                    break
            except Exception:
                pass

        if self.i2c is None:
            # For debugging: do one more scan print attempt on both buses
            scans = {}
            for i2c_id in (0, 1):
                try:
                    i2c = machine.I2C(
                        i2c_id,
                        scl=machine.Pin(PIN_I2C_SCL),
                        sda=machine.Pin(PIN_I2C_SDA),
                        freq=freq
                    )
                    scans[i2c_id] = i2c.scan()
                except Exception as e:
                    scans[i2c_id] = str(e)
            raise OSError("BME280 not found. I2C scans: %r" % scans)

        self.dev = BME280(self.i2c, address=self.addr)

    def read(self):
        # returns (temp_c, hum_pct, press_hpa)
        return self.dev.read_compensated()