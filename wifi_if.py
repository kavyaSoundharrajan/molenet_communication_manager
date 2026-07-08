# wifi_if.py — real Wi-Fi probe + UDP send (budget handled by CM)

import time
import network
import socket
from config import WIFI_SSID, WIFI_PASS, WIFI_UDP_HOST, WIFI_UDP_PORT, WIFI_CONNECT_TIMEOUT_MS, WIFI_SEND_TIMEOUT_MS

class WiFiIF:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)

    def probe(self) -> bool:
        """
        Opportunistic availability check.
        Try to connect quickly within timeout budget.
        """
        self.wlan.active(True)
        self.wlan.connect(WIFI_SSID, WIFI_PASS)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < WIFI_CONNECT_TIMEOUT_MS:
            if self.wlan.isconnected():
                 return True
            time.sleep_ms(100)

        return False

    def connect(self) -> bool:
        if self.wlan.isconnected():
            return True

        self.wlan.active(True)
        self.wlan.connect(WIFI_SSID, WIFI_PASS)

        t0 = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), t0) < WIFI_CONNECT_TIMEOUT_MS:
            if self.wlan.isconnected():
                return True
            time.sleep_ms(100)
        return False

    def send_udp(self, payload: bytes) -> bool:
        """
        Real transport: UDP datagram.
        Success = sendto() succeeds (best-effort; no ACK).
        """
        if not self.connect():
            self.shutdown()
            return False

        ok = False
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(WIFI_SEND_TIMEOUT_MS / 1000.0)
            s.sendto(payload, (WIFI_UDP_HOST, WIFI_UDP_PORT))
            ok = True
        except Exception:
            ok = False
        finally:
            try:
                if s:
                    s.close()
            except Exception:
                pass

        self.shutdown()
        return ok

    def shutdown(self):
        # Make Wi-Fi radio go quiet between cycles (energy intent)
        try:
            if self.wlan.isconnected():
                self.wlan.disconnect()
        except Exception:
            pass
        try:
            self.wlan.active(False)
        except Exception:
            pass