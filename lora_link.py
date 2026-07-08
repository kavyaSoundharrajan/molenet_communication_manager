# lora_link.py — ACK-confirmed LoRa link
VERSION = "4.0.0"

import time
from config import *


class RollingHistory:

    def __init__(self, n):
        self.n = n
        self.hist = []

    def update(self, success):
        self.hist.append(1 if success else 0)
        if len(self.hist) > self.n:
            self.hist.pop(0)

    def success_ratio(self):
        if not self.hist:
            return LORA_SR_PRIOR
        return sum(self.hist) / float(len(self.hist))


class RawLoRaLink:

    def __init__(self, radio=None):
        self.radio = radio
        self.stats = RollingHistory(LORA_HIST_N)

        self._last_rssi = None
        self._last_snr = None
        self._last_rtt_ms = None

        self.last_attempts = 0
        self.last_ack_success = 0

    def send_with_ack(self, pkt, node_id, seq, ack_wait_ms=3000, retries=2):
        """
        Success means:
            packet sent AND matching ACK:<seq> received.
        """

        self.last_attempts = 0
        self.last_ack_success = 0
        self._last_rtt_ms = None

        expected_ack = "ACK:%d" % int(seq)

        attempt = 0

        while attempt <= retries:
            attempt += 1
            self.last_attempts += 1

            if DEBUG_LORA:
                print("\n[LoRa TX attempt %d]" % attempt)
                print("[LoRa TX seq]", seq)
                print("[LoRa expected ACK]", expected_ack)

            try:
                tx_ok = self.radio.send(pkt, timeout_ms=LORA_TX_TIMEOUT_MS)
            except Exception as e:
                print("[LoRa ERROR send]", e)
                tx_ok = False

            if not tx_ok:
                print("[LoRa TX failed before ACK wait]")
                continue

            t0 = time.ticks_ms()

            while time.ticks_diff(time.ticks_ms(), t0) < ack_wait_ms:

                try:
                    resp = self.radio.recv(timeout_ms=300)
                except Exception as e:
                    print("[LoRa ERROR recv]", e)
                    resp = None

                if not resp:
                    continue

                try:
                    msg = resp.decode()
                except:
                    msg = str(resp)

                try:
                    self._last_rssi = self.radio.get_rssi()
                except:
                    self._last_rssi = None

                try:
                    self._last_snr = self.radio.get_snr()
                except:
                    self._last_snr = None

                if DEBUG_LORA:
                    print("[LoRa RX while waiting]", msg)

                if msg == expected_ack:
                    self._last_rtt_ms = time.ticks_diff(time.ticks_ms(), t0)
                    self.stats.update(True)
                    self.last_ack_success = 1

                    return {
                        "status": OUTCOME_SUCCESS,
                        "seq": int(seq),
                        "attempts": self.last_attempts,
                        "ack_success": 1,
                        "rtt_ms": self._last_rtt_ms,
                        "rssi": self._last_rssi,
                        "snr": self._last_snr
                    }

            print("[LoRa ACK timeout] seq =", seq)

        self.stats.update(False)
        self.last_ack_success = 0

        return {
            "status": OUTCOME_FAILED,
            "reason": "lora_ack_timeout",
            "seq": int(seq),
            "attempts": self.last_attempts,
            "ack_success": 0,
            "rtt_ms": None,
            "rssi": self._last_rssi,
            "snr": self._last_snr
        }

    def success_ratio(self):
        return self.stats.success_ratio()

    def get_last_rssi(self):
        return self._last_rssi

    def get_last_snr(self):
        return self._last_snr

    def get_last_rtt_ms(self):
        return self._last_rtt_ms