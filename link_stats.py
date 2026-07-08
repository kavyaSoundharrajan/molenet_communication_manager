# link_stats.py — locked rolling LoRa history (N attempts), persisted in RTC.memory()

import machine
import time

class RollingLinkStats:
    def __init__(self, n: int = 10, rtc_key: bytes = b"LS:"):
        self.n = int(n)
        self._rtc = machine.RTC()
        self._key = rtc_key
        self.attempts = 0
        self.successes = 0
        self.last_success_ts_s = 0
        self._ring = [0] * self.n
        self._idx = 0
        self._load()

    def _load(self):
        raw = self._rtc.memory()
        if not raw or not raw.startswith(self._key):
            return
        try:
            s = raw[len(self._key):].decode()
            meta, bits = s.split("|", 1)
            a, su, last_ts, idx = meta.split(",")
            self.attempts = int(a)
            self.successes = int(su)
            self.last_success_ts_s = int(last_ts)
            self._idx = int(idx) % self.n
            bits = bits.strip()
            if len(bits) >= self.n:
                self._ring = [1 if ch == "1" else 0 for ch in bits[:self.n]]
        except Exception:
            pass

    def _save(self):
        bits = "".join("1" if b else "0" for b in self._ring)
        s = f"{self.attempts},{self.successes},{self.last_success_ts_s},{self._idx}|{bits}"
        self._rtc.memory(self._key + s.encode())

    def update(self, success: bool, latency_ms: int | None = None):
        old = self._ring[self._idx]
        if old == 1:
            self.successes -= 1

        v = 1 if success else 0
        self._ring[self._idx] = v
        if v == 1:
            self.successes += 1
            self.last_success_ts_s = int(time.time())

        self._idx = (self._idx + 1) % self.n
        self.attempts += 1
        self._save()

    def success_ratio(self) -> float:
        return self.successes / float(self.n)

    def last_success_age_s(self) -> int:
        if self.last_success_ts_s <= 0:
            return 10**9
        return max(0, int(time.time()) - self.last_success_ts_s)