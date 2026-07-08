# bme280.py — minimal BME280 driver for MicroPython (I2C)
# Returns temperature (C), pressure (hPa), humidity (%)

import time
import struct


class BME280:
    def __init__(self, i2c, address=0x76):
        self.i2c = i2c
        self.addr = address
        self._load_calibration()
        self._configure()

    def _read8(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _read16(self, reg):
        b = self.i2c.readfrom_mem(self.addr, reg, 2)
        return b[0] | (b[1] << 8)

    def _readS16(self, reg):
        r = self._read16(reg)
        return r - 65536 if r > 32767 else r

    def _write8(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _load_calibration(self):
        # Temp
        self.dig_T1 = self._read16(0x88)
        self.dig_T2 = self._readS16(0x8A)
        self.dig_T3 = self._readS16(0x8C)
        # Pressure
        self.dig_P1 = self._read16(0x8E)
        self.dig_P2 = self._readS16(0x90)
        self.dig_P3 = self._readS16(0x92)
        self.dig_P4 = self._readS16(0x94)
        self.dig_P5 = self._readS16(0x96)
        self.dig_P6 = self._readS16(0x98)
        self.dig_P7 = self._readS16(0x9A)
        self.dig_P8 = self._readS16(0x9C)
        self.dig_P9 = self._readS16(0x9E)
        # Humidity
        self.dig_H1 = self._read8(0xA1)
        self.dig_H2 = self._readS16(0xE1)
        self.dig_H3 = self._read8(0xE3)
        e4 = self._read8(0xE4)
        e5 = self._read8(0xE5)
        e6 = self._read8(0xE6)
        self.dig_H4 = (e4 << 4) | (e5 & 0x0F)
        self.dig_H5 = (e6 << 4) | (e5 >> 4)
        self.dig_H6 = self._read8(0xE7)
        if self.dig_H6 > 127:
            self.dig_H6 -= 256
        self.t_fine = 0

    def _configure(self):
        # Humidity oversampling x1
        self._write8(0xF2, 0x01)
        # Normal mode, temp/press oversampling x1, standby 0.5ms, filter off
        self._write8(0xF4, 0x27)
        self._write8(0xF5, 0x00)
        time.sleep_ms(10)

    def _read_raw(self):
        data = self.i2c.readfrom_mem(self.addr, 0xF7, 8)
        pres = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum  = (data[6] << 8)  | data[7]
        return temp, pres, hum

    def read_compensated(self):
        adc_T, adc_P, adc_H = self._read_raw()

        # Temperature
        var1 = (((adc_T >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = (((((adc_T >> 4) - self.dig_T1) * ((adc_T >> 4) - self.dig_T1)) >> 12) * self.dig_T3) >> 14
        self.t_fine = var1 + var2
        T = (self.t_fine * 5 + 128) >> 8  # 0.01 C
        temp_c = T / 100.0

        # Pressure
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
        if var1 == 0:
            press_hpa = 0.0
        else:
            p = 1048576 - adc_P
            p = (((p << 31) - var2) * 3125) // var1
            var1p = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
            var2p = (self.dig_P8 * p) >> 19
            p = ((p + var1p + var2p) >> 8) + (self.dig_P7 << 4)
            press_pa = p / 256.0
            press_hpa = press_pa / 100.0

        # Humidity
        h = self.t_fine - 76800
        h = (((((adc_H << 14) - (self.dig_H4 << 20) - (self.dig_H5 * h)) + 16384) >> 15) *
             (((((((h * self.dig_H6) >> 10) * (((h * self.dig_H3) >> 11) + 32768)) >> 10) + 2097152) *
               self.dig_H2 + 8192) >> 14))
        h = h - (((((h >> 15) * (h >> 15)) >> 7) * self.dig_H1) >> 4)
        h = 0 if h < 0 else h
        h = 419430400 if h > 419430400 else h
        hum = (h >> 12) / 1024.0  # %
        return temp_c, hum, press_hpa