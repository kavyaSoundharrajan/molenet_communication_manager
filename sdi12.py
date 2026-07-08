from machine import UART, Pin
import utime


class SDI12:
    def __init__(self, tx=17, rx=18, marking=37, rx_enable=36, tx_enable=35, uart_id=1):
        print("Init SDI12")

        self.TX = Pin(tx)
        self.RX = Pin(rx)
        self.SDI_MARKING = Pin(marking, Pin.OUT, value=1)
        self.RX_ENABLE = Pin(rx_enable, Pin.OUT, value=0)
        self.TX_ENABLE = Pin(tx_enable, Pin.OUT, value=0)

        self.uart = UART(
            uart_id,
            baudrate=1200,
            bits=7,
            parity=0,
            stop=1,
            tx=self.TX,
            rx=self.RX,
            invert=UART.INV_RX,
            timeout=1000
        )

        utime.sleep_ms(300)
        self.uart.read()

    def _enter_tx(self):
        self.RX_ENABLE.value(0)
        self.TX_ENABLE.value(0)

    def _enter_rx(self):
        self.RX_ENABLE.value(1)
        self.TX_ENABLE.value(1)

    def _break_and_mark(self):
        self.SDI_MARKING.value(0)
        utime.sleep_ms(13)
        self.SDI_MARKING.value(1)
        utime.sleep_ms(9)

    def write(self, msg):
        self._enter_tx()
        self._break_and_mark()
        self.uart.write(msg)
        self.uart.flush()

    def read(self, wait_ms=500):
        self._enter_rx()
        utime.sleep_ms(wait_ms)
        return self.uart.read()

    def command(self, cmd, wait_ms=500):
        print("CMD:", cmd)
        self.write(cmd)
        resp = self.read(wait_ms)
        print("RESP:", resp)
        return resp

    def identify(self, addr="0"):
        return self.command(f"{addr}I!", wait_ms=800)

    def start_measurement(self, addr="0"):
        return self.command(f"{addr}M!", wait_ms=800)

    def read_data(self, addr="0", d_index=0):
        return self.command(f"{addr}D{d_index}!", wait_ms=800)