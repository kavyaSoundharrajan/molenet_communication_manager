# sx1276_raw.py — SX1276 raw LoRa driver
# Polling-based stable version for MoleNet v6.3

import time
import machine
from config import (
    SPI_ID, PIN_SCK, PIN_MOSI, PIN_MISO,
    PIN_NSS, PIN_RST, PIN_DIO0,
    LORA_FREQ_HZ, LORA_BW, LORA_SF, LORA_CR,
    LORA_SYNC_WORD, LORA_TX_POWER_DBM
)

REG_FIFO                 = 0x00
REG_OP_MODE              = 0x01
REG_FRF_MSB              = 0x06
REG_FRF_MID              = 0x07
REG_FRF_LSB              = 0x08
REG_PA_CONFIG            = 0x09
REG_LNA                  = 0x0C
REG_FIFO_ADDR_PTR        = 0x0D
REG_FIFO_TX_BASE_ADDR    = 0x0E
REG_FIFO_RX_BASE_ADDR    = 0x0F
REG_FIFO_RX_CURRENT      = 0x10
REG_IRQ_FLAGS            = 0x12
REG_RX_NB_BYTES          = 0x13
REG_PKT_SNR_VALUE        = 0x19
REG_PKT_RSSI_VALUE       = 0x1A
REG_MODEM_CONFIG_1       = 0x1D
REG_MODEM_CONFIG_2       = 0x1E
REG_PREAMBLE_MSB         = 0x20
REG_PREAMBLE_LSB         = 0x21
REG_PAYLOAD_LENGTH       = 0x22
REG_MODEM_CONFIG_3       = 0x26
REG_SYNC_WORD            = 0x39
REG_DIO_MAPPING_1        = 0x40
REG_VERSION              = 0x42

IRQ_RX_DONE              = 0x40
IRQ_PAYLOAD_CRC_ERR      = 0x20
IRQ_TX_DONE              = 0x08

MODE_LONG_RANGE          = 0x80
MODE_SLEEP               = 0x00
MODE_STDBY               = 0x01
MODE_TX                  = 0x03
MODE_RX_CONTINUOUS       = 0x05


def _freq_to_frf(freq_hz):
    return int((freq_hz << 19) // 32000000)


def _bw_bits(bw):
    mapping = {
        7800: 0, 10400: 1, 15600: 2, 20800: 3,
        31250: 4, 41700: 5, 62500: 6,
        125000: 7, 250000: 8, 500000: 9
    }
    return (mapping.get(int(bw), 7) & 0x0F) << 4


def _cr_bits(cr):
    return ((int(cr) - 4) & 0x07) << 1


class SX1276Raw:

    def __init__(self):
        self.spi = machine.SPI(
            SPI_ID,
            baudrate=2_000_000,
            polarity=0,
            phase=0,
            sck=machine.Pin(PIN_SCK),
            mosi=machine.Pin(PIN_MOSI),
            miso=machine.Pin(PIN_MISO)
        )

        self.nss = machine.Pin(PIN_NSS, machine.Pin.OUT)
        self.nss.value(1)

        self.rst = machine.Pin(PIN_RST, machine.Pin.OUT)
        self.rst.value(1)

        self.dio0 = machine.Pin(PIN_DIO0, machine.Pin.IN)

        self._last_rssi = None
        self._last_snr = None

        self._init_radio()

    def _select(self):
        self.nss.value(0)

    def _deselect(self):
        self.nss.value(1)

    def _read_reg(self, addr):
        self._select()
        self.spi.write(bytearray([addr & 0x7F]))
        val = self.spi.read(1)[0]
        self._deselect()
        return val

    def _write_reg(self, addr, val):
        self._select()
        self.spi.write(bytearray([addr | 0x80, val & 0xFF]))
        self._deselect()

    def _write_fifo(self, data):
        self._select()
        self.spi.write(bytearray([REG_FIFO | 0x80]))
        self.spi.write(data)
        self._deselect()

    def _read_fifo(self, n):
        self._select()
        self.spi.write(bytearray([REG_FIFO & 0x7F]))
        data = self.spi.read(n)
        self._deselect()
        return data

    def _reset(self):
        self.rst.value(0)
        time.sleep_ms(20)
        self.rst.value(1)
        time.sleep_ms(50)

    def _set_mode(self, mode):
        self._write_reg(REG_OP_MODE, MODE_LONG_RANGE | mode)
        time.sleep_ms(2)

    def _clear_irqs(self):
        self._write_reg(REG_IRQ_FLAGS, 0xFF)

    def _set_fifo_base(self):
        self._write_reg(REG_FIFO_TX_BASE_ADDR, 0x00)
        self._write_reg(REG_FIFO_RX_BASE_ADDR, 0x00)
        self._write_reg(REG_FIFO_ADDR_PTR, 0x00)

    def _start_rx_continuous(self):
        self._set_mode(MODE_STDBY)
        self._write_reg(REG_FIFO_ADDR_PTR, 0x00)
        self._clear_irqs()
        self._write_reg(REG_DIO_MAPPING_1, 0x00)
        self._set_mode(MODE_RX_CONTINUOUS)
        time.sleep_ms(5)

    def _init_radio(self):
        self._reset()

        version = self._read_reg(REG_VERSION)
        if version in (0x00, 0xFF):
            raise RuntimeError("SX1276 not detected, version=%s" % hex(version))

        self._set_mode(MODE_SLEEP)
        self._set_mode(MODE_STDBY)

        self._set_fifo_base()

        frf = _freq_to_frf(LORA_FREQ_HZ)
        self._write_reg(REG_FRF_MSB, (frf >> 16) & 0xFF)
        self._write_reg(REG_FRF_MID, (frf >> 8) & 0xFF)
        self._write_reg(REG_FRF_LSB, frf & 0xFF)

        self._write_reg(REG_MODEM_CONFIG_1, _bw_bits(LORA_BW) | _cr_bits(LORA_CR))
        self._write_reg(REG_MODEM_CONFIG_2, (int(LORA_SF) << 4) | 0x04)
        self._write_reg(REG_MODEM_CONFIG_3, 0x04)
        self._write_reg(REG_SYNC_WORD, LORA_SYNC_WORD)

        self._write_reg(REG_PREAMBLE_MSB, 0x00)
        self._write_reg(REG_PREAMBLE_LSB, 0x08)

        tx_power = int(LORA_TX_POWER_DBM)
        if tx_power < 2:
            tx_power = 2
        if tx_power > 17:
            tx_power = 17

        self._write_reg(REG_PA_CONFIG, 0x80 | (tx_power - 2))
        self._write_reg(REG_LNA, self._read_reg(REG_LNA) | 0x03)

        self._start_rx_continuous()

    def send(self, payload, timeout_ms=3000):
        if isinstance(payload, str):
            payload = payload.encode()

        self._set_mode(MODE_STDBY)
        self._clear_irqs()

        self._write_reg(REG_FIFO_ADDR_PTR, 0x00)
        self._write_reg(REG_PAYLOAD_LENGTH, len(payload))
        self._write_fifo(payload)

        self._write_reg(REG_DIO_MAPPING_1, 0x40)
        self._set_mode(MODE_TX)

        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            irq = self._read_reg(REG_IRQ_FLAGS)

            if irq & IRQ_TX_DONE:
                self._clear_irqs()
                self._start_rx_continuous()
                return True

            time.sleep_ms(2)

        self._clear_irqs()
        self._start_rx_continuous()
        return False

    def recv(self, timeout_ms=5000):
        self._start_rx_continuous()

        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
            irq = self._read_reg(REG_IRQ_FLAGS)

            if irq & IRQ_PAYLOAD_CRC_ERR:
                self._clear_irqs()
                self._start_rx_continuous()
                return None

            if irq & IRQ_RX_DONE:
                self._last_snr = self._read_snr()
                self._last_rssi = self._read_rssi()

                length = self._read_reg(REG_RX_NB_BYTES)
                current_addr = self._read_reg(REG_FIFO_RX_CURRENT)

                if length <= 0 or length > 255:
                    self._clear_irqs()
                    self._start_rx_continuous()
                    return None

                self._write_reg(REG_FIFO_ADDR_PTR, current_addr)
                data = self._read_fifo(length)

                self._clear_irqs()
                self._start_rx_continuous()

                return data

            time.sleep_ms(2)

        return None

    def _read_snr(self):
        raw = self._read_reg(REG_PKT_SNR_VALUE)
        if raw > 127:
            raw -= 256
        return raw / 4.0

    def _read_rssi(self):
        raw = self._read_reg(REG_PKT_RSSI_VALUE)
        return raw - 157

    def get_rssi(self):
        return self._last_rssi

    def get_snr(self):
        return self._last_snr

    def dump_radio_config(self):
        print("VERSION:", hex(self._read_reg(REG_VERSION)))
        print("OPMODE:", hex(self._read_reg(REG_OP_MODE)))
        print("SYNC:", hex(self._read_reg(REG_SYNC_WORD)))
        print("IRQ:", hex(self._read_reg(REG_IRQ_FLAGS)))
        print("MODEM1:", hex(self._read_reg(REG_MODEM_CONFIG_1)))
        print("MODEM2:", hex(self._read_reg(REG_MODEM_CONFIG_2)))
        print(
            "FRF:",
            hex(self._read_reg(REG_FRF_MSB)),
            hex(self._read_reg(REG_FRF_MID)),
            hex(self._read_reg(REG_FRF_LSB))
        )