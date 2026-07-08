# probe_budget.py — persisted probe cooldowns using RTC memory

import machine
import time

class ProbeBudget:
    """
    Stores last-probe timestamps in RTC memory.
    Prevents scan storms across deep sleep cycles.
    """
    def __init__(self, key=b"PB:"):
        self._rtc = machine.RTC()
        self._key = key
        self._last = {"wifi": 0, "ble": 0}
        self._load()

    def _load(self):
        raw = self._rtc.memory()
        if not raw or not raw.startswith(self._key):
            return
        try:
            s = raw[len(self._key):].decode()
            # format: wifi_ts,ble_ts
            w, b = s.split(",")
            self._last["wifi"] = int(w)
            self._last["ble"] = int(b)
        except Exception:
            pass

    def _save(self):
        s = f'{self._last["wifi"]},{self._last["ble"]}'
        self._rtc.memory(self._key + s.encode())

    def can_probe(self, iface: str, cooldown_s: int) -> bool:
        now = int(time.time())
        last = self._last.get(iface, 0)
        return (now - last) >= int(cooldown_s)

    def mark_probed(self, iface: str):
        self._last[iface] = int(time.time())
        self._save()