# ansa_lite.py — QoS-aware ANSA-lite with high-backlog WiFi efficiency policy
VERSION = "5.1.1"


class ANSALite:

    def __init__(self):
        self.w_reliability = 0.35
        self.w_latency = 0.20
        self.w_throughput = 0.15
        self.w_signal = 0.10
        self.w_backlog = 0.10
        self.w_energy = 0.10

    def _clamp01(self, x):
        if x is None:
            return 0.0
        if x < 0.0:
            return 0.0
        if x > 1.0:
            return 1.0
        return x

    def _norm_latency(self, rtt_ms):
        if rtt_ms is None:
            return 0.5
        return self._clamp01(1.0 - (rtt_ms / 2000.0))

    def _norm_throughput(self, bps):
        if bps is None:
            return 0.4
        return self._clamp01(bps / 5000.0)

    def _norm_rssi(self, rssi):
        if rssi is None:
            return 0.5
        return self._clamp01((rssi + 120.0) / 80.0)

    def _norm_snr(self, snr):
        if snr is None:
            return 0.5
        return self._clamp01((snr + 20.0) / 30.0)

    def _safe_attr(self, obj, name, default):
        try:
            value = getattr(obj, name)
            if value is None:
                return default
            return value
        except:
            return default

    def _signal_score(self, iface, metric):
        if iface == "lora":
            rssi_score = self._norm_rssi(self._safe_attr(metric, "avg_rssi", None))
            snr_score = self._norm_snr(self._safe_attr(metric, "avg_snr", None))
            return 0.5 * rssi_score + 0.5 * snr_score

        if iface == "ble":
            return self._norm_rssi(self._safe_attr(metric, "avg_rssi", None))

        return 0.5

    def _backlog_score(self, iface, backlog):
        pressure = self._clamp01(backlog / 10.0)

        if iface == "wifi":
            return pressure
        if iface == "ble":
            return 0.65 * pressure
        if iface == "lora":
            return 0.45 * pressure

        return 0.0

    def _energy_score(self, iface, energy_state):
        if energy_state == "CRITICAL":
            return 0.0

        if energy_state == "LOW":
            if iface == "wifi":
                return 0.1
            if iface == "lora":
                return 0.75
            if iface == "ble":
                return 0.85

        if iface == "wifi":
            return 0.45
        if iface == "lora":
            return 0.85
        if iface == "ble":
            return 0.90

        return 0.5

    def _failure_penalty(self, metric):
        failures = self._safe_attr(metric, "consecutive_failures", 0)
        return self._clamp01(failures / 5.0)

    def _metric_total_tx(self, metric):
        return self._safe_attr(metric, "total_tx", 0)

    def _metric_success_ratio(self, metric):
        try:
            return self._clamp01(metric.success_ratio())
        except:
            return 0.0

    def _score_iface(self, iface, metric, backlog, energy_state):
        reliability = self._metric_success_ratio(metric)
        latency = self._norm_latency(self._safe_attr(metric, "avg_rtt_ms", None))
        throughput = self._norm_throughput(
            self._safe_attr(metric, "avg_throughput_bps", None)
        )
        signal = self._signal_score(iface, metric)
        backlog_s = self._backlog_score(iface, backlog)
        energy = self._energy_score(iface, energy_state)
        failure_penalty = self._failure_penalty(metric)

        score = (
            self.w_reliability * reliability +
            self.w_latency * latency +
            self.w_throughput * throughput +
            self.w_signal * signal +
            self.w_backlog * backlog_s +
            self.w_energy * energy -
            0.15 * failure_penalty
        )

        score = self._clamp01(score)

        return score, {
            "rel": round(reliability, 3),
            "lat": round(latency, 3),
            "thr": round(throughput, 3),
            "sig": round(signal, 3),
            "buf": round(backlog_s, 3),
            "eng": round(energy, 3),
            "fail": round(failure_penalty, 3),
            "score": round(score, 3)
        }

    def choose_interface(
        self,
        energy_state,
        backlog,
        lora_metrics,
        wifi_metrics,
        ble_metrics
    ):

        if energy_state == "CRITICAL":
            print("  ANSA: energy CRITICAL -> no flush")
            return "none"

    
        # Efficiency policy:
        # high backlog + OK energy -> prefer WiFi for bulk recovery
    
        try:
            import config

            wifi_enabled = getattr(config, "ANSA_WIFI_ENABLED", True)
            wifi_threshold = getattr(config, "ANSA_WIFI_BACKLOG_THRESHOLD", 0.50)
            dtn_max = getattr(config, "DTN_MAX_ITEMS", 50)

            usage = backlog / float(dtn_max)

            if (
                wifi_enabled and
                energy_state == "OK" and
                usage >= wifi_threshold
            ):
                print(
                    "  ANSA efficiency policy: high backlog %.2f >= %.2f -> wifi"
                    % (usage, wifi_threshold)
                )
                return "wifi"

        except Exception as e:
            print("  ANSA efficiency policy skipped:", e)

        # Bootstrap policy: no interface history yet
        no_lora_history = self._metric_total_tx(lora_metrics) == 0
        no_wifi_history = self._metric_total_tx(wifi_metrics) == 0
        no_ble_history = self._metric_total_tx(ble_metrics) == 0

        if no_lora_history and no_wifi_history and no_ble_history:
            if backlog >= 7 and energy_state == "OK":
                print("  ANSA bootstrap: no history + high backlog -> wifi")
                return "wifi"

            print("  ANSA bootstrap: no history -> lora")
            return "lora"

        # Normal QoS-aware ANSA scoring
        scores = {}
        debug = {}

        scores["lora"], debug["lora"] = self._score_iface(
            "lora", lora_metrics, backlog, energy_state
        )

        scores["wifi"], debug["wifi"] = self._score_iface(
            "wifi", wifi_metrics, backlog, energy_state
        )

        scores["ble"], debug["ble"] = self._score_iface(
            "ble", ble_metrics, backlog, energy_state
        )

        best_iface = max(scores, key=scores.get)

        print("  ANSA QoS scores:", debug)
        print("  ANSA selected:", best_iface)

        return best_iface
