# run_controlled_dataset.py
# Controlled scenario-dataset runner for MoleNet Communication Manager.
#
# How to use on MoleNet hardware with Thonny:
#   1. Copy this file, cm_manager.py, config.py, and all CM modules to the board.
#   2. Copy controlled_scenario_dataset.csv to the board root OR to /sd/.
#   3. In Thonny, run this file.
#   4. The board writes:
#        /sd/cm_controlled_eval.csv       (native CM logger output)
#        /sd/cm_controlled_runner.csv     (dataset + CM output + comparison fields)
#
# Important honesty note:
#   In the default mode, this is a CONTROLLED HARDWARE-EXECUTED evaluation:
#   the Communication Manager logic runs on the MoleNet MCU, but sensor values,
#   ACK results, Wi-Fi/BLE availability, and backlog states are injected from
#   the dataset. It is not an uncontrolled field/RF measurement.

try:
    import uos as os
except ImportError:
    import os

try:
    import utime as time
except ImportError:
    import time

try:
    import ubinascii
except ImportError:
    import binascii as ubinascii

import config
from cm_manager import CommunicationManager


# -------------------------------------------------------------------
# User settings
# -------------------------------------------------------------------

# The runner will try these paths in order.
DATASET_PATHS = [
    "controlled_scenario_dataset.csv",
    "/sd/controlled_scenario_dataset.csv",
    "fansa_cm_controlled_dataset_100_cycles.csv",
    "/sd/fansa_cm_controlled_dataset_100_cycles.csv",
]

# Native cm_manager logger output.
CM_EVAL_OUTPUT_FILE = "cm_controlled_eval.csv"

# Extra runner output with dataset columns + CM result + simple comparisons.
RUNNER_OUTPUT_FILE = "/sd/cm_controlled_runner.csv"

# If True, each dataset row forces DTN queue length to row['dtn_backlog_before'].
# This makes the dataset the controlled input source for backlog pressure.
FORCE_DTN_BACKLOG_FROM_DATASET = True

# If True, S9-style DTN flush interface can be controlled by row['flush_interface'].
# This is useful for validating ACK-safe flush/dequeue behaviour with controlled inputs.
# Set False if you want ANSA-Lite to choose the flush interface from its live scores.
USE_DATASET_FLUSH_INTERFACE = True

# Default = False. This prevents real radio transmissions during dataset execution.
# The CM still runs on MoleNet hardware, but link outcomes are injected from the dataset.
# Set True only if you have real LoRa/Wi-Fi/BLE receivers and want real ACK behaviour.
USE_REAL_RADIOS = False

# Keep the controlled run short and predictable.
QUIET_BULK_OUTPUT = False



# Small CSV support for MicroPython


def _strip_bom(s):
    if s and len(s) >= 1 and ord(s[0]) == 0xFEFF:
        return s[1:]
    return s


def parse_csv_line(line):
    """Minimal CSV parser with quote support. Handles comma inside quoted fields."""
    out = []
    cur = []
    in_quotes = False
    i = 0
    line = line.rstrip("\n").rstrip("\r")

    while i < len(line):
        ch = line[i]
        if ch == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                cur.append('"')
                i += 1
            else:
                in_quotes = not in_quotes
        elif ch == "," and not in_quotes:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1

    out.append("".join(cur))
    return out


def find_dataset_path():
    for path in DATASET_PATHS:
        try:
            with open(path, "r") as f:
                f.readline()
            return path
        except Exception:
            pass
    raise Exception("Dataset CSV not found. Copy controlled_scenario_dataset.csv to board root or /sd/.")


def read_dataset_rows(path):
    with open(path, "r") as f:
        header = None
        for line in f:
            if not line.strip():
                continue
            if header is None:
                header = parse_csv_line(_strip_bom(line))
                continue
            vals = parse_csv_line(line)
            row = {}
            for i, h in enumerate(header):
                row[h] = vals[i] if i < len(vals) else ""
            yield row


# Basic conversion helpers

def clean(v):
    if v is None:
        return ""
    s = str(v)
    s = s.replace("\n", " ").replace("\r", " ").replace(",", ";")
    return s


def is_yes(v):
    s = str(v).strip().lower()
    return s in ("yes", "y", "true", "1", "available", "success")


def is_no(v):
    s = str(v).strip().lower()
    return s in ("no", "n", "false", "0", "none", "na", "nan", "")


def to_int(v, default=0):
    try:
        if v is None or v == "":
            return default
        return int(float(str(v)))
    except Exception:
        return default


def to_float(v, default=0.0):
    try:
        if v is None or v == "":
            return default
        return float(str(v))
    except Exception:
        return default


def norm_iface(v):
    s = str(v).strip().upper()
    if s in ("LORA", "RAW_LORA"):
        return "lora"
    if s in ("WIFI", "WI-FI"):
        return "wifi"
    if s in ("BLE", "BLE_RELIABLE", "BLUETOOTH"):
        return "ble"
    if s in ("DTN", "STORE", "STORAGE"):
        return "dtn"
    return ""


def norm_outcome(v):
    s = str(v).strip().lower()
    if s in ("delivered", "success", "sent"):
        return "success"
    if s in ("stored", "store", "retained"):
        return "stored"
    if s in ("failed", "fail"):
        return "failed"
    return s


def ensure_dir(path):
    parts = path.split("/")
    cur = ""
    for p in parts[:-1]:
        if p == "":
            continue
        cur += "/" + p
        try:
            os.stat(cur)
        except Exception:
            try:
                os.mkdir(cur)
            except Exception:
                pass


def remove_if_exists(path):
    try:
        os.remove(path)
    except Exception:
        pass


# Controlled dataset providers / stubs


class DatasetSoil:
    def __init__(self):
        self.row = None

    def set_row(self, row):
        self.row = row

    def read_normalized(self):
        return round(to_float(self.row.get("soil_moisture_pct", 0), 0.0) / 100.0, 3)

    def read_raw(self):
        return self.read_normalized()

    def read_temperature(self):
        return None

    def status(self):
        return self.row.get("soil_state", "dataset")


class DatasetEnergy:
    def __init__(self):
        self.row = None

    def set_row(self, row):
        self.row = row

    def get_state(self):
        return self.row.get("energy_state", "OK")


class RadioCounters:
    def __init__(self):
        self.reset()

    def reset(self):
        self.lora = 0
        self.wifi = 0
        self.ble_reliable = 0
        self.ble_adv = 0
        self.wifi_maint = 0

    def total(self):
        return self.lora + self.wifi + self.ble_reliable + self.ble_adv + self.wifi_maint


class ControlledHarness:
    def __init__(self, cm):
        self.cm = cm
        self.row = None
        self.soil = DatasetSoil()
        self.energy = DatasetEnergy()
        self.counters = RadioCounters()

        cm.soil = self.soil
        cm.energy = self.energy

        if not USE_REAL_RADIOS:
            self._install_radio_stubs()

        self._install_controlled_maintenance()

        if USE_DATASET_FLUSH_INTERFACE:
            self._install_controlled_ansa_choice()

    def set_row(self, row):
        self.row = row
        self.soil.set_row(row)
        self.energy.set_row(row)
        self.counters.reset()

        # Dataset-driven scenario metadata.
        config.EVAL_SCENARIO = row.get("scenario_id", "DATASET")
        config.MIX_LABEL = row.get("scenario_name", "")
        config.GLOBAL_CYCLE = to_int(row.get("cycle_id"), 0)

        # Feed fuzzy layer with dataset's recent LoRa reliability.
        def forced_lora_ratio():
            return to_float(row.get("lora_success_ratio"), getattr(config, "LORA_SR_PRIOR", 0.6))

        self.cm._current_lora_success_ratio = forced_lora_ratio

    def _ok_result(self, iface, seq, rtt_ms):
        if iface == "lora":
            return {
                "status": config.OUTCOME_SUCCESS,
                "seq": int(seq),
                "attempts": 1,
                "ack_success": 1,
                "rtt_ms": rtt_ms,
                "rssi": None,
                "snr": None,
            }
        return {
            "status": config.OUTCOME_SUCCESS,
            "seq": int(seq),
            "ack_success": 1,
            "rtt_ms": rtt_ms,
        }

    def _fail_result(self, iface, seq, reason):
        if iface == "lora":
            return {
                "status": config.OUTCOME_FAILED,
                "reason": reason,
                "seq": int(seq),
                "attempts": 1,
                "ack_success": 0,
                "rtt_ms": None,
                "rssi": None,
                "snr": None,
            }
        return {
            "status": config.OUTCOME_FAILED,
            "reason": reason,
            "seq": int(seq),
            "ack_success": 0,
            "rtt_ms": None,
        }

    def _install_radio_stubs(self):
        harness = self

        def controlled_lora_send(pkt, seq, retries):
            harness.counters.lora += 1
            harness.cm.lora_link.last_attempts = 1
            if is_yes(harness.row.get("lora_ack_condition", "No")):
                return harness._ok_result("lora", seq, 90 + (to_int(harness.row.get("cycle_id"), 0) % 30))
            return harness._fail_result("lora", seq, "controlled_lora_no_ack")

        def controlled_wifi_send(pkt, seq):
            harness.counters.wifi += 1
            if not is_yes(harness.row.get("wifi_available", "No")):
                return harness._fail_result("wifi", seq, "controlled_wifi_unavailable")
            if is_yes(harness.row.get("wifi_ack_condition", "No")):
                return harness._ok_result("wifi", seq, 45 + (to_int(harness.row.get("cycle_id"), 0) % 20))
            return harness._fail_result("wifi", seq, "controlled_wifi_no_ack")

        def controlled_ble_send_reliable(pkt, seq):
            harness.counters.ble_reliable += 1
            if not is_yes(harness.row.get("ble_available", "No")):
                return harness._fail_result("ble", seq, "controlled_ble_unavailable")
            if is_yes(harness.row.get("ble_reliable_ack_condition", "No")):
                return harness._ok_result("ble", seq, 60 + (to_int(harness.row.get("cycle_id"), 0) % 25))
            return harness._fail_result("ble", seq, "controlled_ble_no_ack")

        def controlled_ble_advertise(pkt, seq):
            harness.counters.ble_adv += 1
            return {
                "status": config.OUTCOME_BLE_ADVERTISED_ONLY,
                "confirmed": False,
                "seq": seq,
            }

        self.cm._lora_send = controlled_lora_send
        self.cm._wifi_send = controlled_wifi_send
        self.cm._ble_send_reliable = controlled_ble_send_reliable
        self.cm._ble_advertise_only = controlled_ble_advertise

    def _install_controlled_maintenance(self):
        harness = self

        def controlled_wifi_maintenance(energy_state):
            result = {
                "wifi_scan_done": 0,
                "wifi_found": 0,
                "wifi_connected": 0,
                "config_update_checked": 0,
                "config_updated": 0,
                "firmware_checked": 0,
                "firmware_available": 0,
            }

            if energy_state != "OK":
                return result

            if not is_yes(harness.row.get("maintenance_due", "No")):
                return result

            result["wifi_scan_done"] = 1
            harness.counters.wifi_maint += 1

            if is_yes(harness.row.get("wifi_available", "No")):
                result["wifi_found"] = 1
                result["wifi_connected"] = 1
                result["config_update_checked"] = 1
                result["firmware_checked"] = 1

            return result

        self.cm._maybe_wifi_maintenance = controlled_wifi_maintenance

    def _install_controlled_ansa_choice(self):
        harness = self
        original_choose = self.cm.ansa.choose_interface

        def controlled_choose_interface(energy_state, backlog, lora_metrics, wifi_metrics, ble_metrics):
            row_iface = norm_iface(harness.row.get("flush_interface", ""))
            if row_iface and row_iface != "dtn":
                return row_iface
            return original_choose(
                energy_state=energy_state,
                backlog=backlog,
                lora_metrics=lora_metrics,
                wifi_metrics=wifi_metrics,
                ble_metrics=ble_metrics,
            )

        self.cm.ansa.choose_interface = controlled_choose_interface



# DTN forcing: create dataset-controlled backlog before each cycle


def packet_to_hex(pkt):
    hx = ubinascii.hexlify(pkt)
    try:
        return hx.decode()
    except Exception:
        return str(hx, "utf-8")


def force_dtn_backlog(n):
    # Writes directly to the same queue file format used by dtn_store.py:
    # seq|hex_payload|meta
    try:
        ensure_dir(config.DTN_QUEUE_FILE)
    except Exception:
        pass

    lines = []
    for i in range(int(n)):
        seq = 50000 + i
        payload = ("DUMMY_DTN_%03d" % i).encode()
        lines.append("%d|%s|dataset_seed" % (seq, packet_to_hex(payload)))

    with open(config.DTN_QUEUE_FILE, "w") as f:
        for line in lines:
            f.write(line + "\n")


# Runner CSV output


RUNNER_FIELDS = [
    "cycle_id", "scenario_id", "scenario_cycle", "scenario_name",
    "soil_moisture_pct", "soil_state", "energy_state", "lora_success_ratio",
    "lora_ack_condition", "wifi_available", "wifi_ack_condition", "ble_available", "ble_reliable_ack_condition",
    "dtn_backlog_before_dataset", "packet_size", "event_type_dataset", "priority_dataset",

    "cm_priority", "cm_event_type", "cm_main_path", "cm_sub_policy", "cm_decision",
    "cm_selected_interface", "cm_outcome", "cm_ack_success", "cm_dtn_before", "cm_dtn_after",
    "cm_flush_triggered", "cm_flush_interface", "cm_flush_sent", "cm_wifi_scan_done", "cm_energy_proxy",

    "runner_lora_ops", "runner_wifi_ops", "runner_ble_reliable_ops", "runner_ble_adv_ops", "runner_wifi_maint_ops", "runner_total_radio_ops",

    "expected_policy", "expected_selected_interface", "expected_decision", "expected_outcome", "expected_dtn_action", "expected_dtn_backlog_after",
    "match_interface", "match_outcome", "match_dtn_after",
]


def init_runner_output():
    ensure_dir(RUNNER_OUTPUT_FILE)
    with open(RUNNER_OUTPUT_FILE, "w") as f:
        f.write(",".join(RUNNER_FIELDS) + "\n")


def append_runner_output(row, cm_row, counters):
    expected_iface = norm_iface(row.get("expected_selected_interface", ""))
    cm_iface = norm_iface(cm_row.get("selected_interface", ""))

    expected_out = norm_outcome(row.get("expected_outcome", ""))
    cm_out = norm_outcome(cm_row.get("outcome", ""))

    expected_after = to_int(row.get("expected_dtn_backlog_after", -999), -999)
    cm_after = to_int(cm_row.get("dtn_after", -1), -1)

    out = {
        "cycle_id": row.get("cycle_id", ""),
        "scenario_id": row.get("scenario_id", ""),
        "scenario_cycle": row.get("scenario_cycle", ""),
        "scenario_name": row.get("scenario_name", ""),
        "soil_moisture_pct": row.get("soil_moisture_pct", ""),
        "soil_state": row.get("soil_state", ""),
        "energy_state": row.get("energy_state", ""),
        "lora_success_ratio": row.get("lora_success_ratio", ""),
        "lora_ack_condition": row.get("lora_ack_condition", ""),
        "wifi_available": row.get("wifi_available", ""),
        "wifi_ack_condition": row.get("wifi_ack_condition", ""),
        "ble_available": row.get("ble_available", ""),
        "ble_reliable_ack_condition": row.get("ble_reliable_ack_condition", ""),
        "dtn_backlog_before_dataset": row.get("dtn_backlog_before", ""),
        "packet_size": row.get("packet_size", ""),
        "event_type_dataset": row.get("event_type", ""),
        "priority_dataset": row.get("priority", ""),

        "cm_priority": cm_row.get("priority", ""),
        "cm_event_type": cm_row.get("event_type", ""),
        "cm_main_path": cm_row.get("main_path", ""),
        "cm_sub_policy": cm_row.get("sub_policy", ""),
        "cm_decision": cm_row.get("decision", ""),
        "cm_selected_interface": cm_row.get("selected_interface", ""),
        "cm_outcome": cm_row.get("outcome", ""),
        "cm_ack_success": cm_row.get("ack_success", ""),
        "cm_dtn_before": cm_row.get("dtn_before", ""),
        "cm_dtn_after": cm_row.get("dtn_after", ""),
        "cm_flush_triggered": cm_row.get("flush_triggered", ""),
        "cm_flush_interface": cm_row.get("flush_interface", ""),
        "cm_flush_sent": cm_row.get("flush_sent", ""),
        "cm_wifi_scan_done": cm_row.get("wifi_scan_done", ""),
        "cm_energy_proxy": cm_row.get("energy_proxy", ""),

        "runner_lora_ops": counters.lora,
        "runner_wifi_ops": counters.wifi,
        "runner_ble_reliable_ops": counters.ble_reliable,
        "runner_ble_adv_ops": counters.ble_adv,
        "runner_wifi_maint_ops": counters.wifi_maint,
        "runner_total_radio_ops": counters.total(),

        "expected_policy": row.get("expected_policy", ""),
        "expected_selected_interface": row.get("expected_selected_interface", ""),
        "expected_decision": row.get("expected_decision", ""),
        "expected_outcome": row.get("expected_outcome", ""),
        "expected_dtn_action": row.get("expected_dtn_action", ""),
        "expected_dtn_backlog_after": row.get("expected_dtn_backlog_after", ""),
        "match_interface": 1 if expected_iface == cm_iface else 0,
        "match_outcome": 1 if expected_out == cm_out else 0,
        "match_dtn_after": 1 if expected_after == cm_after else 0,
    }

    with open(RUNNER_OUTPUT_FILE, "a") as f:
        f.write(",".join([clean(out.get(k, "")) for k in RUNNER_FIELDS]) + "\n")


# Main controlled run


def configure_for_controlled_run():
    # Keep file names deterministic.
    config.EVAL_LOG_DIR = "/sd"
    config.EVAL_OUTPUT_FILE = CM_EVAL_OUTPUT_FILE

    # Dataset supplies values; do not use random/ADC modes here.
    config.SOIL_MODE = "SIM_FIXED"
    config.ENERGY_MODE = "SIM_FIXED"

    # Make the run quick and one-attempt-per-interface.
    config.ACK_RETRIES_NORMAL = 0
    config.ACK_RETRIES_EMERG = 0
    config.ACK_RETRIES_LOW_ENERGY_CRITICAL = 0

    # Avoid extra low-battery warning TX in controlled S7-type scenarios.
    config.LOW_BATTERY_SEND_WARNING_ONCE = False

    # Dataset S9 backlog is around 30..39 with DTN_MAX_ITEMS=200.
    # Threshold 0.15 allows S9 flush while keeping smaller-backlog OK-energy scenarios mostly below threshold.
    config.DTN_FLUSH_THRESHOLD = 0.15
    config.ANSA_WIFI_BACKLOG_THRESHOLD = 0.15
    config.FLUSH_MAX_BATCH = 3

    # Maintenance is controlled by the dataset row, not by cycle modulo.
    config.WIFI_MAINTENANCE_ENABLED = True
    config.WIFI_MAINTENANCE_INTERVAL_CYCLES = 999999



def main():
    configure_for_controlled_run()

    dataset_path = find_dataset_path()
    print("[RUNNER] Dataset:", dataset_path)
    print("[RUNNER] CM eval output:", "/sd/" + CM_EVAL_OUTPUT_FILE)
    print("[RUNNER] Runner output:", RUNNER_OUTPUT_FILE)

    # Remove old output files before CM/logger is created.
    remove_if_exists("/sd/" + CM_EVAL_OUTPUT_FILE)
    remove_if_exists(RUNNER_OUTPUT_FILE)
    init_runner_output()

    cm = CommunicationManager()
    harness = ControlledHarness(cm)

    count = 0

    for row in read_dataset_rows(dataset_path):
        count += 1
        cycle_id = to_int(row.get("cycle_id", count), count)

        if not QUIET_BULK_OUTPUT:
            print("\n\n############################")
            print("[RUNNER] Cycle", cycle_id, row.get("scenario_id", ""), row.get("scenario_name", ""))
            print("############################")

        harness.set_row(row)

        # Make cm_manager.py report the dataset cycle_id.
        cm.cycle_id = cycle_id - 1

        if FORCE_DTN_BACKLOG_FROM_DATASET:
            force_dtn_backlog(to_int(row.get("dtn_backlog_before"), 0))

        try:
            eval_row = cm.wake_cycle()
        except Exception as e:
            print("[RUNNER ERROR] cycle", cycle_id, "failed:", e)
            eval_row = {
                "cycle_id": cycle_id,
                "priority": "",
                "event_type": "RUNNER_ERROR",
                "main_path": "",
                "sub_policy": "",
                "decision": "runner_error",
                "selected_interface": "",
                "outcome": "failed",
                "ack_success": 0,
                "dtn_before": "",
                "dtn_after": "",
                "flush_triggered": 0,
                "flush_interface": "",
                "flush_sent": 0,
                "wifi_scan_done": 0,
                "energy_proxy": 0,
            }

        append_runner_output(row, eval_row, harness.counters)

    print("\n[RUNNER] Completed cycles:", count)
    print("[RUNNER] Native CM log:", "/sd/" + CM_EVAL_OUTPUT_FILE)
    print("[RUNNER] Runner comparison log:", RUNNER_OUTPUT_FILE)
    print("[RUNNER] Use these logs as controlled hardware-executed outputs, not field-measured RF outputs.")


if __name__ == "__main__":
    main()
