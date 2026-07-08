# cm_metrics.py — lightweight CSV logger for CM evaluation (MicroPython)

import time

METRICS_FILE = "cm_metrics.csv"

class CMMetrics:
    def __init__(self):
        # Create file with header if not present
        try:
            with open(METRICS_FILE, "r") as f:
                _ = f.readline()
        except:
            with open(METRICS_FILE, "w") as f:
                f.write("ts,energy,priority,soil_m,fuzzy_u,action,iface,success,lat_ms,dtn_before,dtn_after\n")

    def log(self, *,
            ts: int,
            energy: str,
            priority: str,
            soil_m,
            fuzzy_u,
            action: str,
            iface: str,
            success: int,
            lat_ms: int,
            dtn_before: int,
            dtn_after: int):

        def _fmt(x):
            if x is None:
                return ""
            if isinstance(x, float):
                return "{:.4f}".format(x)
            return str(x)

        line = ",".join([
            str(ts),
            energy,
            priority,
            _fmt(soil_m),
            _fmt(fuzzy_u),
            action,
            iface,
            str(int(success)),
            str(int(lat_ms)),
            str(int(dtn_before)),
            str(int(dtn_after)),
        ]) + "\n"

        with open(METRICS_FILE, "a") as f:
            f.write(line)