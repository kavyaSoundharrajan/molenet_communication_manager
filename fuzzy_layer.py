# fuzzy_layer.py — FuzDeMa-inspired Sugeno fuzzy SEND/STORE decision
VERSION = "4.1.1"

try:
    import config
except ImportError:
    config = None


class FuzzyLayer:

    def __init__(self):
        self.send_threshold = self._cfg("FUZZY_SEND_THRESHOLD", 0.55)

    def _cfg(self, name, default):
        if config is not None and hasattr(config, name):
            return getattr(config, name)
        return default

    def _clamp01(self, x):
        if x < 0.0:
            return 0.0
        if x > 1.0:
            return 1.0
        return x

    def _mst_low(self, x):
        if 0.0 <= x <= 15.0:
            return self._clamp01(1.0 - x / 15.0)
        return 0.0

    def _mst_average(self, x):
        if 10.0 <= x <= 30.0:
            return self._clamp01(x / 20.0 - 0.5)
        if 30.0 < x <= 50.0:
            return self._clamp01(2.5 - x / 20.0)
        return 0.0

    def _mst_high(self, x):
        if 40.0 <= x <= 100.0:
            return self._clamp01(x / 15.0 - 2.0 / 3.0)
        return 0.0

    def _energy_ok(self, state):
        return 1.0 if state == "OK" else 0.0

    def _energy_low(self, state):
        return 1.0 if state == "LOW" else 0.0

    def _energy_critical(self, state):
        return 1.0 if state == "CRITICAL" else 0.0

    def _lora_poor(self, x):
        if 0.0 <= x <= 0.3:
            return self._clamp01(1.0 - x / 0.3)
        return 0.0

    def _lora_moderate(self, x):
        if 0.2 <= x <= 0.5:
            return self._clamp01((x - 0.2) / 0.3)
        if 0.5 < x <= 0.8:
            return self._clamp01((0.8 - x) / 0.3)
        return 0.0

    def _lora_good(self, x):
        if 0.7 <= x <= 1.0:
            return self._clamp01((x - 0.7) / 0.3)
        return 0.0

    def _fuzzify(self, mst_percent, energy_state, lora_ratio):
        return {
            "mst_low": self._mst_low(mst_percent),
            "mst_average": self._mst_average(mst_percent),
            "mst_high": self._mst_high(mst_percent),
            "eng_ok": self._energy_ok(energy_state),
            "eng_low": self._energy_low(energy_state),
            "eng_critical": self._energy_critical(energy_state),
            "lora_poor": self._lora_poor(lora_ratio),
            "lora_moderate": self._lora_moderate(lora_ratio),
            "lora_good": self._lora_good(lora_ratio),
        }

    def _rule_loss(self, mst_label, eng_label, lora_label):
        loss = 0.0

        if mst_label == "low":
            loss += 0.05
        elif mst_label == "average":
            loss += 0.25
        elif mst_label == "high":
            loss += 0.50

        if eng_label == "ok":
            loss += 0.00
        elif eng_label == "low":
            loss += 0.25
        elif eng_label == "critical":
            loss += 0.50

        if lora_label == "good":
            loss += 0.00
        elif lora_label == "moderate":
            loss += 0.20
        elif lora_label == "poor":
            loss += 0.45

        return self._clamp01(loss)

    def _sugeno_defuzz(self, f):
        mst_sets = [
            ("low", f["mst_low"]),
            ("average", f["mst_average"]),
            ("high", f["mst_high"]),
        ]

        eng_sets = [
            ("ok", f["eng_ok"]),
            ("low", f["eng_low"]),
            ("critical", f["eng_critical"]),
        ]

        lora_sets = [
            ("good", f["lora_good"]),
            ("moderate", f["lora_moderate"]),
            ("poor", f["lora_poor"]),
        ]

        numerator = 0.0
        denominator = 0.0

        for mst_label, mst_mu in mst_sets:
            for eng_label, eng_mu in eng_sets:
                for lora_label, lora_mu in lora_sets:
                    alpha = min(mst_mu, eng_mu, lora_mu)

                    if alpha <= 0.0:
                        continue

                    z_i = self._rule_loss(mst_label, eng_label, lora_label)
                    numerator += alpha * z_i
                    denominator += alpha

        if denominator <= 0.0:
            return 0.5

        return self._clamp01(numerator / denominator)

    def evaluate(
        self,
        soil_moisture,
        energy_state="OK",
        lora_success_ratio=1.0,
        backlog=0
    ):
        mst_percent = self._clamp01(soil_moisture) * 100.0
        lora_ratio = self._clamp01(lora_success_ratio)

        f = self._fuzzify(mst_percent, energy_state, lora_ratio)

        loss_probability = self._sugeno_defuzz(f)
        send_confidence = self._clamp01(1.0 - loss_probability)

        decision = "SEND" if send_confidence >= self.send_threshold else "STORE"

        return {
            "send_confidence": round(send_confidence, 3),
            "loss_probability": round(loss_probability, 3),
            "decision": decision,
            "inputs": {
                "mst_percent": round(mst_percent, 1),
                "energy_state": energy_state,
                "lora_success_ratio": round(lora_ratio, 3),
                "mst_low": round(f["mst_low"], 3),
                "mst_average": round(f["mst_average"], 3),
                "mst_high": round(f["mst_high"], 3),
                "eng_ok": round(f["eng_ok"], 3),
                "eng_low": round(f["eng_low"], 3),
                "eng_critical": round(f["eng_critical"], 3),
                "lora_poor": round(f["lora_poor"], 3),
                "lora_moderate": round(f["lora_moderate"], 3),
                "lora_good": round(f["lora_good"], 3),
            }
        }
