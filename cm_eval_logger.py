# cm_eval_logger.py — structured CSV logger for thesis evaluation

import os
import config


CSV_FIELDS = [
    # Metadata
    "cycle_id",
    "timestamp",
    "scenario",
    "run_id",
    "node_id",
    "firmware_version",

    # Environment
    "soil_scenario",
    "soil_m",
    "humidity",
    "energy_state",
    "energy_policy",

    # Classification
    "priority",
    "event_type",
    "priority_reason",
    "main_path",
    "sub_policy",
    "alert_flag",

    # Fuzzy
    "fuzzy_score",
    "fuzzy_loss_prob",
    "fuzzy_decision",
    "fuzzy_mst_percent",
    "fuzzy_eng_state",
    "fuzzy_lora_ratio",

    # Decision
    "decision",
    "selected_interface",
    "tx_attempts",
    "tx_success",
    "ack_success",

    # Link metrics
    "rtt_ms",
    "rssi",
    "snr",
    "packet_size_bytes",

    # DTN
    "dtn_before",
    "dtn_after",
    "dtn_usage",

    # ANSA
    "flush_triggered",
    "flush_interface",
    "flush_sent",

    # WiFi maintenance
    "wifi_scan_done",
    "wifi_found",
    "wifi_connected",
    "config_update_checked",
    "config_updated",
    "firmware_checked",
    "firmware_available",

    # Energy proxy breakdown
    "energy_cpu_wake",
    "energy_lora_tx",
    "energy_ack_wait",
    "energy_sd_write",
    "energy_wifi_tx",
    "energy_ble",
    "energy_wifi_maint",
    "energy_proxy",

    # Final result
    "outcome"
]


class CMEvalLogger:

    def __init__(self):
        # Allows each scenario to write to its own CSV file.
        # Example:
        # config.EVAL_LOG_DIR = "/sd"
        # config.EVAL_OUTPUT_FILE = "F1_normal_send.csv"
        output_file = getattr(config, "EVAL_OUTPUT_FILE", "cm_functionality.csv")
        log_dir = getattr(config, "EVAL_LOG_DIR", "/sd")

        self.path = log_dir + "/" + output_file

        try:
            os.mkdir(log_dir)
        except Exception:
            pass

        self._ensure_header()

    def _ensure_header(self):
        try:
            with open(self.path, "r") as f:
                first = f.readline()
                if first:
                    return
        except Exception:
            pass

        with open(self.path, "w") as f:
            f.write(",".join(CSV_FIELDS) + "\n")

    def _clean(self, value):
        if value is None:
            return ""

        text = str(value)

        # Protect CSV structure
        text = text.replace(",", ";")
        text = text.replace("\n", " ")
        text = text.replace("\r", " ")

        return text

    def log(self, row_dict):
        row = []

        for field in CSV_FIELDS:
            row.append(self._clean(row_dict.get(field, "")))

        with open(self.path, "a") as f:
            f.write(",".join(row) + "\n")