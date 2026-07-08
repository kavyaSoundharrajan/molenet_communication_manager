# link_metrics.py — lightweight per-interface QoS statistics
VERSION = "1.1.0"


class LinkMetric:

    def __init__(self, hist_n=10):
        self.hist_n = hist_n
        self.success_hist = []

        self.avg_rtt_ms = None
        self.avg_rssi = None
        self.avg_snr = None
        self.avg_throughput_bps = None

        self.last_rtt_ms = None
        self.last_rssi = None
        self.last_snr = None
        self.last_throughput_bps = None

        self.consecutive_failures = 0
        self.total_tx = 0
        self.total_success = 0

    def _ewma(self, old, new, alpha=0.3):
        if new is None:
            return old
        if old is None:
            return new
        return ((1.0 - alpha) * old) + (alpha * new)

    def update(self, success, rtt_ms=None, rssi=None, snr=None, payload_len=0):
        self.total_tx += 1

        if success:
            self.total_success += 1
            self.consecutive_failures = 0
        else:
            self.consecutive_failures += 1

        self.success_hist.append(1 if success else 0)

        if len(self.success_hist) > self.hist_n:
            self.success_hist.pop(0)

        self.last_rtt_ms = rtt_ms
        self.last_rssi = rssi
        self.last_snr = snr

        if success and rtt_ms and rtt_ms > 0:
            throughput = (payload_len * 8 * 1000) / float(rtt_ms)
        else:
            throughput = None

        self.last_throughput_bps = throughput

        self.avg_rtt_ms = self._ewma(self.avg_rtt_ms, rtt_ms)
        self.avg_rssi = self._ewma(self.avg_rssi, rssi)
        self.avg_snr = self._ewma(self.avg_snr, snr)
        self.avg_throughput_bps = self._ewma(
            self.avg_throughput_bps,
            throughput
        )

    def success_ratio(self):
        if not self.success_hist:
            return 0.0
        return sum(self.success_hist) / float(len(self.success_hist))

    def packet_loss_rate(self):
        return 1.0 - self.success_ratio()

    def summary(self):
        return {
            "success_ratio": round(self.success_ratio(), 3),
            "packet_loss_rate": round(self.packet_loss_rate(), 3),
            "avg_rtt_ms": self.avg_rtt_ms,
            "avg_rssi": self.avg_rssi,
            "avg_snr": self.avg_snr,
            "avg_throughput_bps": self.avg_throughput_bps,
            "consecutive_failures": self.consecutive_failures,
            "total_tx": self.total_tx,
            "total_success": self.total_success
        }


class LinkMetrics:

    def __init__(self):
        self.lora = LinkMetric()
        self.wifi = LinkMetric()
        self.ble = LinkMetric()

    def dump(self):
        return {
            "lora": self.lora.summary(),
            "wifi": self.wifi.summary(),
            "ble": self.ble.summary()
        }