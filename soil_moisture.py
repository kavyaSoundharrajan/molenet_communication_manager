import time
from sdi12 import SDI12


class SoilMoisture:
    def __init__(self, addr="1"):
        self.addr = addr
        self.bus = SDI12()

        # temporary normalization range
        self.raw_min = 0.0
        self.raw_max = 3000.0

    def _normalize(self, value):
        if value < self.raw_min:
            value = self.raw_min
        if value > self.raw_max:
            value = self.raw_max
        return (value - self.raw_min) / (self.raw_max - self.raw_min)

    def _parse_values(self, text):
        if isinstance(text, bytes):
            text = text.decode().strip()

        vals = []
        buf = ""

        for ch in text[1:]:   # skip first address character
            if ch in "+-":
                if buf:
                    try:
                        vals.append(float(buf))
                    except:
                        pass
                buf = ch
            else:
                buf += ch

        if buf:
            try:
                vals.append(float(buf))
            except:
                pass

        return vals

    def read_all(self):
        resp = self.bus.start_measurement(self.addr)
        if not resp:
            raise OSError("No response to measurement command")

        time.sleep(1.5)

        data = self.bus.read_data(self.addr, 0)
        if not data:
            raise OSError("No response to data request")

        values = self._parse_values(data)
        if not values:
            raise ValueError("No numeric values parsed from SDI-12 response")

        return values

    def read_sample(self):
        values = self.read_all()

        raw = values[0]
        temperature = values[1] if len(values) > 1 else None
        status = values[2] if len(values) > 2 else None
        normalized = self._normalize(raw)

        return {
            "raw": raw,
            "temperature": temperature,
            "status": status,
            "normalized": normalized
        }

    def read_raw(self):
        return self.read_sample()["raw"]

    def read_normalized(self):
        return self.read_sample()["normalized"]