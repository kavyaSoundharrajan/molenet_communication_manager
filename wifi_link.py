# wifi_link.py — Real WiFi UDP + ACK-confirmed delivery

import network
import socket
import time

import config


class WiFiLink:

    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

        self.last_rtt_ms = None
        self.last_ack_success = 0

    def _ensure_connected(self):
        if self.wlan.isconnected():
            return True

        print("[WiFi] Connecting to:", config.WIFI_SSID)
        self.wlan.connect(config.WIFI_SSID, config.WIFI_PASS)

        t0 = time.ticks_ms()

        while not self.wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), t0) > config.WIFI_CONNECT_TIMEOUT_MS:
                print("[WiFi] Connection timeout")
                return False
            time.sleep_ms(250)

        print("[WiFi] Connected:", self.wlan.ifconfig())
        return True

    def send_with_ack(self, pkt, seq, node_id, timeout_ms=None):
        """
        WiFi success means:
            UDP packet sent AND WIFI_ACK:<seq> received.
        """

        if timeout_ms is None:
            timeout_ms = config.WIFI_ACK_WAIT_MS

        self.last_rtt_ms = None
        self.last_ack_success = 0

        if not self._ensure_connected():
            return {
                "status": config.OUTCOME_FAILED,
                "reason": "wifi_not_connected",
                "seq": int(seq),
                "rtt_ms": None,
                "ack_success": 0
            }

        sock = None

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(timeout_ms / 1000.0)

            addr = (config.WIFI_UDP_HOST, config.WIFI_UDP_PORT)

            # Send text wrapper so laptop can parse seq easily.
            payload_hex = pkt.hex() if hasattr(pkt, "hex") else "".join(["%02x" % b for b in pkt])
            msg = "DATA|%d|%d|%s" % (int(node_id), int(seq), payload_hex)

            expected_ack = "WIFI_ACK:%d" % int(seq)

            t0 = time.ticks_ms()

            sock.sendto(msg.encode(), addr)
            print("[WiFi TX]", msg)

            data, _ = sock.recvfrom(256)
            rtt = time.ticks_diff(time.ticks_ms(), t0)

            try:
                ack = data.decode()
            except:
                ack = str(data)

            print("[WiFi RX]", ack)
            print("[WiFi RTT]", rtt)

            if ack == expected_ack:
                self.last_rtt_ms = rtt
                self.last_ack_success = 1

                return {
                    "status": config.OUTCOME_SUCCESS,
                    "seq": int(seq),
                    "rtt_ms": rtt,
                    "ack_success": 1
                }

            return {
                "status": config.OUTCOME_FAILED,
                "reason": "wrong_wifi_ack",
                "seq": int(seq),
                "rtt_ms": rtt,
                "ack_success": 0
            }

        except Exception as e:
            print("[WiFi ERROR]", e)
            return {
                "status": config.OUTCOME_FAILED,
                "reason": "wifi_ack_timeout_or_error",
                "seq": int(seq),
                "rtt_ms": None,
                "ack_success": 0
            }

        finally:
            try:
                if sock:
                    sock.close()
            except:
                pass