# cm_manager.py — MoleNet Communication Manager
# Two-path architecture:
#   Path 1: NORMAL FUZZY PATH
#   Path 2: DETERMINISTIC EVENT PATH with sub-policies

VERSION = "5.1.1"

import time
import config

from runtime_config import load_runtime_config
from wifi_maintenance import WiFiMaintenance
from cm_eval_logger import CMEvalLogger
from packet import build_data_frame
from sx1276_raw import SX1276Raw
from lora_link import RawLoRaLink
from wifi_link import WiFiLink
from ble_if import BLEIF
from dtn_store import DTNStore
from energy_manager import EnergyManager
from flush_controller import FlushController
from ansa_lite import ANSALite
from fuzzy_layer import FuzzyLayer
from link_metrics import LinkMetrics


NODE_ID = config.NODE_ID


class CommunicationManager:

    def __init__(self):
        load_runtime_config()

        self.radio = SX1276Raw()
        self.lora_link = RawLoRaLink(self.radio)
        self.wifi_link = WiFiLink()
        self.ble = BLEIF()

        self.dtn = DTNStore()
        self.energy = EnergyManager()
        self.flush_ctrl = FlushController()

        self.fuzzy = FuzzyLayer()
        self.ansa = ANSALite()
        self.metrics = LinkMetrics()
        self.wifi_maint = WiFiMaintenance()

        from soil_moisture_sim import SoilMoistureSim
        self.soil = SoilMoistureSim()

        self.logger = CMEvalLogger()
        self.cycle_id = 0

    def _p(self, label, value):
        print("  %-30s : %s" % (label, value))

    def _section(self, title):
        print("\n" + "=" * 64)
        print(title)
        print("=" * 64)

    def _subsection(self, title):
        print("\n[%s]" % title)

    def classify_event(self, soil_m, energy_state):

        if energy_state == "CRITICAL":
            return {
                "priority": config.PRIORITY_CRITICAL,
                "event_type": config.EVENT_BATTERY_CRITICAL,
                "reason": "battery_critical_radio_shutdown",
                "main_path": config.PATH_DETERMINISTIC_EVENT,
                "sub_policy": config.SUBPOLICY_CRITICAL_BATTERY_SHUTDOWN,
                "alert_flag": 1
            }

        if soil_m <= config.MOISTURE_CRITICAL_DRY:
            sub = (
                config.SUBPOLICY_CRITICAL_ENVIRONMENTAL_LOW_ENERGY
                if energy_state == "LOW"
                else config.SUBPOLICY_CRITICAL_ENVIRONMENTAL
            )
            return {
                "priority": config.PRIORITY_CRITICAL,
                "event_type": config.EVENT_EXTREME_DRY,
                "reason": "soil_moisture_below_critical_dry_threshold",
                "main_path": config.PATH_DETERMINISTIC_EVENT,
                "sub_policy": sub,
                "alert_flag": 1
            }

        if soil_m >= config.MOISTURE_CRITICAL_HIGH:
            sub = (
                config.SUBPOLICY_CRITICAL_ENVIRONMENTAL_LOW_ENERGY
                if energy_state == "LOW"
                else config.SUBPOLICY_CRITICAL_ENVIRONMENTAL
            )
            return {
                "priority": config.PRIORITY_CRITICAL,
                "event_type": config.EVENT_EXTREME_WET,
                "reason": "soil_moisture_above_critical_wet_threshold",
                "main_path": config.PATH_DETERMINISTIC_EVENT,
                "sub_policy": sub,
                "alert_flag": 1
            }

        if energy_state == "LOW":
            return {
                "priority": config.PRIORITY_WARNING,
                "event_type": config.EVENT_LOW_BATTERY,
                "reason": "battery_low_warning_store_only",
                "main_path": config.PATH_DETERMINISTIC_EVENT,
                "sub_policy": config.SUBPOLICY_WARNING_LOW_BATTERY,
                "alert_flag": 1
            }

        return {
            "priority": config.PRIORITY_NORMAL,
            "event_type": config.EVENT_NONE,
            "reason": "normal_environment_and_energy",
            "main_path": config.PATH_NORMAL_FUZZY,
            "sub_policy": "",
            "alert_flag": 0
        }

    def _energy_policy(self, energy_state, priority):
        if energy_state == "CRITICAL":
            return config.ENERGY_POLICY_CRITICAL_STORE_ONLY
        if energy_state == "LOW" and priority == config.PRIORITY_CRITICAL:
            return config.ENERGY_POLICY_LOW_EMERGENCY_LORA_ONLY
        if energy_state == "LOW":
            return config.ENERGY_POLICY_LOW_WARNING_ONLY
        return config.ENERGY_POLICY_FULL_OPERATION

    def _lora_send(self, pkt, seq, retries):
        return self.lora_link.send_with_ack(
            pkt=pkt,
            node_id=NODE_ID,
            seq=seq,
            ack_wait_ms=config.ACK_WAIT_MS,
            retries=retries
        )

    def _wifi_send(self, pkt, seq):
        try:
            return self.wifi_link.send_with_ack(
                pkt=pkt,
                seq=seq,
                node_id=NODE_ID,
                timeout_ms=config.WIFI_ACK_WAIT_MS
            )
        except Exception as e:
            print("[WiFi] send_with_ack failed safely:", e)
            return {"status": config.OUTCOME_FAILED, "reason": str(e)}

    def _ble_send_reliable(self, pkt, seq):
        try:
            return self.ble.send_with_ack(
                pkt=pkt,
                seq=seq,
                timeout_ms=config.BLE_ACK_WAIT_MS
            )
        except Exception as e:
            print("[BLE] send_with_ack failed safely:", e)
            return {"status": config.OUTCOME_FAILED, "reason": str(e)}

    def _ble_advertise_only(self, pkt, seq):
        try:
            return self.ble.advertise(pkt, seq=seq)
        except Exception as e:
            print("[BLE ADV] failed safely:", e)
            return {"status": config.OUTCOME_FAILED, "reason": str(e)}

    def _is_success(self, result):
        return result is not None and result.get("status") == config.OUTCOME_SUCCESS

    def _update_lora_metrics(self, result, pkt):
        self.metrics.lora.update(
            success=self._is_success(result),
            rtt_ms=result.get("rtt_ms") if result else None,
            rssi=result.get("rssi") if result else None,
            snr=result.get("snr") if result else None,
            payload_len=len(pkt)
        )

    def _update_wifi_metrics(self, result, pkt):
        self.metrics.wifi.update(
            success=self._is_success(result),
            rtt_ms=result.get("rtt_ms") if result else None,
            payload_len=len(pkt)
        )

    def _update_ble_metrics(self, result, pkt):
        self.metrics.ble.update(
            success=self._is_success(result),
            rtt_ms=result.get("rtt_ms") if result else None,
            rssi=result.get("rssi") if result and "rssi" in result else None,
            payload_len=len(pkt)
        )

    def _current_lora_success_ratio(self):
        if self.metrics.lora.total_tx == 0:
            return config.LORA_SR_PRIOR
        return self.metrics.lora.success_ratio()

    def _battery_warning_already_sent(self):
        try:
            with open(config.LOW_BATTERY_WARNING_FILE, "r") as f:
                return f.read().strip() == "1"
        except Exception:
            return False

    def _mark_battery_warning_sent(self):
        try:
            with open(config.LOW_BATTERY_WARNING_FILE, "w") as f:
                f.write("1")
            return True
        except Exception:
            return False

    def _empty_maintenance_result(self):
        return {
            "wifi_scan_done": 0,
            "wifi_found": 0,
            "wifi_connected": 0,
            "config_update_checked": 0,
            "config_updated": 0,
            "firmware_checked": 0,
            "firmware_available": 0
        }

    def _maybe_wifi_maintenance(self, energy_state):
        if not getattr(config, "WIFI_MAINTENANCE_ENABLED", False):
            return self._empty_maintenance_result()

        if energy_state != "OK":
            print("\n[WIFI MAINTENANCE] skipped: energy is not OK")
            return self._empty_maintenance_result()

        interval = getattr(config, "WIFI_MAINTENANCE_INTERVAL_CYCLES", 0)

        if interval <= 0:
            return self._empty_maintenance_result()

        if self.cycle_id % interval != 0:
            return self._empty_maintenance_result()

        print("\n[WIFI MAINTENANCE] running scheduled scan/update check")
        return self.wifi_maint.run(check_firmware=True)

    def _opportunistic_flush(self, energy_state):
        backlog = self.dtn.count()
        usage = backlog / float(config.DTN_MAX_ITEMS)

        self._subsection("DTN / ANSA CHECK")
        self._p("Backlog", backlog)
        self._p("Usage", round(usage, 3))
        self._p("Flush threshold", config.DTN_FLUSH_THRESHOLD)

        if energy_state != "OK":
            print("  ANSA not executed: energy is not OK")
            return {"triggered": 0, "iface": "", "flushed": 0, "outcome": ""}

        if usage < config.DTN_FLUSH_THRESHOLD:
            print("  ANSA not executed: backlog below threshold")
            return {"triggered": 0, "iface": "", "flushed": 0, "outcome": ""}

        iface = self.ansa.choose_interface(
            energy_state=energy_state,
            backlog=backlog,
            lora_metrics=self.metrics.lora,
            wifi_metrics=self.metrics.wifi,
            ble_metrics=self.metrics.ble
        )

        print("  ANSA selected interface:", iface)

        flushed = 0
        attempted = 0
        final_outcome = config.OUTCOME_FLUSH_FAILED

        while flushed < config.FLUSH_MAX_BATCH:
            entry = self.dtn.peek_oldest()

            if entry is None:
                break

            pkt = entry["pkt"]
            seq = entry["seq"]
            attempted += 1

            print("[DTN FLUSH] iface=%s seq=%d" % (iface, seq))

            if iface == "lora":
                result = self._lora_send(pkt, seq, retries=1)
                self._update_lora_metrics(result, pkt)

            elif iface == "wifi":
                result = self._wifi_send(pkt, seq)
                self._update_wifi_metrics(result, pkt)

            elif iface == "ble":
                result = self._ble_send_reliable(pkt, seq)
                self._update_ble_metrics(result, pkt)

            else:
                print("[DTN KEEP] No valid interface selected")
                final_outcome = (
                    config.OUTCOME_FLUSH_PARTIAL
                    if flushed > 0
                    else config.OUTCOME_FLUSH_FAILED
                )
                break

            if self._is_success(result):
                self.dtn.dequeue_oldest()
                flushed += 1
                final_outcome = config.OUTCOME_FLUSH_SUCCESS
                print("[DTN DEQUEUE] %s ACK success seq=%d" % (iface, seq))
                continue

            print("[DTN KEEP] %s failed seq=%d" % (iface, seq))
            final_outcome = (
                config.OUTCOME_FLUSH_PARTIAL
                if flushed > 0
                else config.OUTCOME_FLUSH_FAILED
            )
            break

        return {
            "triggered": 1 if attempted > 0 else 0,
            "iface": iface,
            "flushed": flushed,
            "outcome": final_outcome
        }

    def _handle_warning_low_battery(self, pkt, seq, ts, soil_m_r, eval_data):
        self._subsection("DETERMINISTIC EVENT PATH")
        self._p("Sub-policy", "WARNING: LOW_BATTERY")
        print("  Rule: compact warning once if allowed, then store data in DTN")

        if getattr(config, "LOW_BATTERY_SEND_WARNING_ONCE", True):
            if self._battery_warning_already_sent():
                print("  Warning already attempted before -> not repeated")
            else:
                self._mark_battery_warning_sent()

                warn_seq = int(time.ticks_ms() % 65535)
                warn_payload = (
                    "TS=%d;SM=%.3f;EN=LOW;PR=WARNING;ALERT=1;EVT=%s"
                    % (ts, soil_m_r, config.EVENT_LOW_BATTERY)
                ).encode()

                warn_pkt = build_data_frame(
                    node_id=NODE_ID,
                    seq=warn_seq,
                    ts_s=ts,
                    payload=warn_payload,
                    priority=config.PRIORITY_WARNING
                )

                result = self._lora_send(
                    warn_pkt,
                    warn_seq,
                    getattr(config, "ACK_RETRIES_LOW_ENERGY_CRITICAL", 0)
                )

                self._update_lora_metrics(result, warn_pkt)
                eval_data["tx_attempts"] = getattr(self.lora_link, "last_attempts", 0)

                if self._is_success(result):
                    eval_data["battery_warning_sent"] = 1
                    eval_data["tx_success"] = 1
                    eval_data["ack_success"] = 1
                    eval_data["rtt_ms"] = result.get("rtt_ms") or 0
                    eval_data["rssi"] = result.get("rssi") or 0
                    eval_data["snr"] = result.get("snr") or 0
                else:
                    self.dtn.enqueue(
                        warn_pkt,
                        seq=warn_seq,
                        meta="low_battery_warning_not_confirmed"
                    )

        self.dtn.enqueue(pkt, seq=seq, meta="warning_low_battery_store")

        eval_data["decision"] = "warning_store_only"
        eval_data["selected_interface"] = "dtn"
        eval_data["outcome"] = config.OUTCOME_STORED

    def _handle_battery_critical_shutdown(self, pkt, seq, eval_data):
        self._subsection("DETERMINISTIC EVENT PATH")
        self._p("Sub-policy", "CRITICAL: BATTERY_CRITICAL")
        print("  Rule: battery critical -> all radios disabled -> store internally")

        self.dtn.enqueue(pkt, seq=seq, meta="battery_critical_store_only")

        eval_data["decision"] = "battery_critical_store_only"
        eval_data["selected_interface"] = "dtn"
        eval_data["outcome"] = config.OUTCOME_STORED

    def _handle_critical_environmental(self, pkt, seq, eval_data, energy_policy):
        self._subsection("DETERMINISTIC EVENT PATH")
        self._p("Sub-policy", "CRITICAL: ENVIRONMENTAL EVENT")
        print("  Rule: extreme dry/wet -> LoRa -> WiFi -> BLE -> DTN fallback")

        if energy_policy == config.ENERGY_POLICY_LOW_EMERGENCY_LORA_ONLY:
            result = self._lora_send(
                pkt,
                seq,
                getattr(config, "ACK_RETRIES_LOW_ENERGY_CRITICAL", 0)
            )

            self._update_lora_metrics(result, pkt)

            eval_data["decision"] = "low_energy_critical_lora_only"
            eval_data["selected_interface"] = "lora"
            eval_data["tx_attempts"] = getattr(self.lora_link, "last_attempts", 0)

            if self._is_success(result):
                eval_data["tx_success"] = 1
                eval_data["ack_success"] = 1
                eval_data["rtt_ms"] = result.get("rtt_ms") or 0
                eval_data["rssi"] = result.get("rssi") or 0
                eval_data["snr"] = result.get("snr") or 0
                eval_data["outcome"] = config.OUTCOME_SUCCESS
                return

            self.dtn.enqueue(pkt, seq=seq, meta="low_energy_critical_failed")
            eval_data["decision"] = "low_energy_critical_store"
            eval_data["selected_interface"] = "dtn"
            eval_data["outcome"] = config.OUTCOME_STORED
            return

        result = self._lora_send(pkt, seq, config.ACK_RETRIES_EMERG)
        self._update_lora_metrics(result, pkt)

        eval_data["decision"] = "critical_lora_tx"
        eval_data["selected_interface"] = "lora"
        eval_data["tx_attempts"] = getattr(self.lora_link, "last_attempts", 0)

        if self._is_success(result):
            eval_data["tx_success"] = 1
            eval_data["ack_success"] = 1
            eval_data["rtt_ms"] = result.get("rtt_ms") or 0
            eval_data["rssi"] = result.get("rssi") or 0
            eval_data["snr"] = result.get("snr") or 0
            eval_data["outcome"] = config.OUTCOME_SUCCESS
            return

        print("  LoRa failed -> trying WiFi")
        wifi_result = self._wifi_send(pkt, seq)
        self._update_wifi_metrics(wifi_result, pkt)

        if self._is_success(wifi_result):
            eval_data["decision"] = "critical_wifi_tx"
            eval_data["selected_interface"] = "wifi"
            eval_data["tx_success"] = 1
            eval_data["ack_success"] = 1
            eval_data["rtt_ms"] = wifi_result.get("rtt_ms") or 0
            eval_data["outcome"] = config.OUTCOME_SUCCESS
            return

        print("  WiFi failed -> trying BLE reliable mode")
        ble_result = self._ble_send_reliable(pkt, seq)
        self._update_ble_metrics(ble_result, pkt)

        if self._is_success(ble_result):
            eval_data["decision"] = "critical_ble_tx"
            eval_data["selected_interface"] = "ble"
            eval_data["tx_success"] = 1
            eval_data["ack_success"] = 1
            eval_data["rtt_ms"] = ble_result.get("rtt_ms") or 0
            eval_data["outcome"] = config.OUTCOME_SUCCESS
            return

        print("  All ACK-confirmed paths failed -> BLE advertise-only + DTN store")
        self._ble_advertise_only(pkt, seq)
        self.dtn.enqueue(pkt, seq=seq, meta="critical_environmental_not_confirmed")

        eval_data["decision"] = "critical_store_after_failed_paths"
        eval_data["selected_interface"] = "dtn"
        eval_data["outcome"] = config.OUTCOME_STORED

    def _handle_normal_fuzzy_path(
        self,
        pkt,
        seq,
        soil_m_r,
        energy_state,
        backlog_before,
        eval_data
    ):
        self._subsection("NORMAL FUZZY PATH")
        print("  Rule: NORMAL packet -> fuzzy decides SEND or STORE")

        fuzzy_result = self.fuzzy.evaluate(
            soil_moisture=soil_m_r,
            energy_state=energy_state,
            lora_success_ratio=self._current_lora_success_ratio(),
            backlog=backlog_before
        )

        eval_data["fuzzy_score"] = fuzzy_result["send_confidence"]
        eval_data["fuzzy_loss_prob"] = fuzzy_result["loss_probability"]
        eval_data["fuzzy_decision"] = fuzzy_result["decision"]
        eval_data["fuzzy_mst_percent"] = fuzzy_result["inputs"]["mst_percent"]
        eval_data["fuzzy_eng_state"] = fuzzy_result["inputs"]["energy_state"]
        eval_data["fuzzy_lora_ratio"] = fuzzy_result["inputs"]["lora_success_ratio"]

        if fuzzy_result["decision"] == "STORE":
            self.dtn.enqueue(pkt, seq=seq, meta="fuzzy_store")
            eval_data["sub_policy"] = config.SUBPOLICY_FUZZY_STORE
            eval_data["decision"] = "fuzzy_store"
            eval_data["selected_interface"] = "dtn"
            eval_data["outcome"] = config.OUTCOME_STORED
            return

        result = self._lora_send(pkt, seq, config.ACK_RETRIES_NORMAL)
        self._update_lora_metrics(result, pkt)

        eval_data["sub_policy"] = config.SUBPOLICY_FUZZY_SEND
        eval_data["decision"] = "fuzzy_lora_tx"
        eval_data["selected_interface"] = "lora"
        eval_data["tx_attempts"] = getattr(self.lora_link, "last_attempts", 0)

        if self._is_success(result):
            eval_data["tx_success"] = 1
            eval_data["ack_success"] = 1
            eval_data["rtt_ms"] = result.get("rtt_ms") or 0
            eval_data["rssi"] = result.get("rssi") or 0
            eval_data["snr"] = result.get("snr") or 0
            eval_data["outcome"] = config.OUTCOME_SUCCESS
            return

        self.dtn.enqueue(pkt, seq=seq, meta="normal_lora_failed")
        eval_data["sub_policy"] = config.SUBPOLICY_FUZZY_LORA_FAILED_STORE
        eval_data["decision"] = "fuzzy_lora_failed_store"
        eval_data["selected_interface"] = "dtn"
        eval_data["outcome"] = config.OUTCOME_STORED

    def _interpretation(self, eval_data):
        if eval_data["main_path"] == config.PATH_NORMAL_FUZZY:
            if eval_data["decision"] == "fuzzy_store":
                return "Normal packet used fuzzy path and was stored because send confidence was insufficient."
            if eval_data["decision"] == "fuzzy_lora_tx" and eval_data["ack_success"]:
                return "Normal packet used fuzzy path and was ACK-confirmed through LoRa."
            if eval_data["decision"] == "fuzzy_lora_failed_store":
                return "Normal packet attempted LoRa but was protected in DTN after missing ACK."

        if eval_data["sub_policy"] == config.SUBPOLICY_WARNING_LOW_BATTERY:
            return "Low-battery warning entered deterministic event path; packet was stored and warning policy was applied."

        if eval_data["sub_policy"] == config.SUBPOLICY_CRITICAL_BATTERY_SHUTDOWN:
            return "Battery-critical event entered deterministic event path; radios were stopped and packet was stored."

        if eval_data["sub_policy"] in [
            config.SUBPOLICY_CRITICAL_ENVIRONMENTAL,
            config.SUBPOLICY_CRITICAL_ENVIRONMENTAL_LOW_ENERGY
        ]:
            if eval_data["ack_success"]:
                return "Critical environmental event was ACK-confirmed through the deterministic event path."
            return "Critical environmental event was not ACK-confirmed; packet was preserved in DTN."

        return "CM wake cycle completed."

    def _print_final_report(self, eval_data):
        self._section("FINAL CM DECISION REPORT")
        self._p("Soil scenario", eval_data.get("soil_scenario", ""))
        self._p("Soil moisture", eval_data.get("soil_m", 0))
        self._p("Energy state", eval_data.get("energy_state", ""))
        self._p("Priority", eval_data.get("priority", ""))
        self._p("Event", eval_data.get("event_type", ""))
        self._p("Main path", eval_data.get("main_path", ""))
        self._p("Sub-policy", eval_data.get("sub_policy", ""))
        self._p("Decision", eval_data.get("decision", ""))
        self._p("Selected interface", eval_data.get("selected_interface", ""))
        self._p("ACK success", eval_data.get("ack_success", 0))
        self._p("DTN before", eval_data.get("dtn_before", 0))
        self._p("DTN after", eval_data.get("dtn_after", 0))
        self._p("Energy proxy", eval_data.get("energy_proxy", 0))
        print("\n[INTERPRETATION]")
        print("  " + self._interpretation(eval_data))
        print("=" * 64)

    def wake_cycle(self):
        self.cycle_id += 1
        ts = int(time.time())

        energy_state = self.energy.get_state()

        soil_m = float(self.soil.read_normalized())
        soil_m_r = round(soil_m, 3)

        try:
            soil_scenario = self.soil.status()
        except Exception:
            soil_scenario = ""

        humidity = 0

        backlog_before = self.dtn.count()

        classification = self.classify_event(soil_m_r, energy_state)

        priority = classification["priority"]
        event_type = classification["event_type"]
        priority_reason = classification["reason"]
        main_path = classification["main_path"]
        sub_policy = classification["sub_policy"]
        alert_flag = classification["alert_flag"]

        energy_policy = self._energy_policy(energy_state, priority)

        seq = int(time.ticks_ms() % 65535)

        payload = (
            "TS=%d;SM=%.3f;EN=%s;PR=%s;ALERT=%d;EVT=%s"
            % (ts, soil_m_r, energy_state, priority, alert_flag, event_type)
        ).encode()

        pkt = build_data_frame(
            node_id=NODE_ID,
            seq=seq,
            ts_s=ts,
            payload=payload,
            priority=priority
        )

        packet_size_bytes = len(pkt)

        eval_data = {
            "cycle_id": self.cycle_id,
            "timestamp": ts,
            "scenario": config.EVAL_SCENARIO,
            "run_id": getattr(config, "RUN_ID", 1),
            "node_id": NODE_ID,
            "firmware_version": VERSION,

            "soil_scenario": soil_scenario,
            "soil_m": soil_m_r,
            "humidity": humidity,
            "energy_state": energy_state,
            "energy_policy": energy_policy,

            "priority": priority,
            "event_type": event_type,
            "priority_reason": priority_reason,
            "main_path": main_path,
            "sub_policy": sub_policy,
            "alert_flag": alert_flag,

            "fuzzy_score": 0,
            "fuzzy_loss_prob": 0,
            "fuzzy_decision": "",
            "fuzzy_mst_percent": 0,
            "fuzzy_eng_state": "",
            "fuzzy_lora_ratio": 0,

            "decision": "",
            "selected_interface": "",
            "tx_attempts": 0,
            "tx_success": 0,
            "ack_success": 0,

            "rtt_ms": 0,
            "rssi": 0,
            "snr": 0,
            "packet_size_bytes": packet_size_bytes,

            "dtn_before": backlog_before,
            "dtn_after": 0,
            "dtn_usage": 0,

            "flush_triggered": 0,
            "flush_interface": "",
            "flush_sent": 0,

            "wifi_scan_done": 0,
            "wifi_found": 0,
            "wifi_connected": 0,
            "config_update_checked": 0,
            "config_updated": 0,
            "firmware_checked": 0,
            "firmware_available": 0,

            "battery_warning_sent": 0,

            "energy_cpu_wake": 0,
            "energy_lora_tx": 0,
            "energy_ack_wait": 0,
            "energy_sd_write": 0,
            "energy_wifi_tx": 0,
            "energy_ble": 0,
            "energy_wifi_maint": 0,
            "energy_proxy": 0,

            "outcome": ""
        }

        self._section("COMMUNICATION MANAGER WAKE CYCLE")

        self._subsection("1. INPUT STATE")
        self._p("Soil scenario", soil_scenario)
        self._p("Soil moisture", soil_m_r)
        self._p("Energy state", energy_state)
        self._p("DTN before", backlog_before)

        self._subsection("2. EVENT CLASSIFICATION")
        self._p("Priority", priority)
        self._p("Event", event_type)
        self._p("Reason", priority_reason)
        self._p("Main path", main_path)
        self._p("Sub-policy", sub_policy)
        self._p("Alert flag", alert_flag)

        if main_path == config.PATH_NORMAL_FUZZY:
            self._handle_normal_fuzzy_path(
                pkt=pkt,
                seq=seq,
                soil_m_r=soil_m_r,
                energy_state=energy_state,
                backlog_before=backlog_before,
                eval_data=eval_data
            )

        else:
            if sub_policy == config.SUBPOLICY_WARNING_LOW_BATTERY:
                self._handle_warning_low_battery(
                    pkt=pkt,
                    seq=seq,
                    ts=ts,
                    soil_m_r=soil_m_r,
                    eval_data=eval_data
                )

            elif sub_policy == config.SUBPOLICY_CRITICAL_BATTERY_SHUTDOWN:
                self._handle_battery_critical_shutdown(
                    pkt=pkt,
                    seq=seq,
                    eval_data=eval_data
                )

            elif sub_policy in [
                config.SUBPOLICY_CRITICAL_ENVIRONMENTAL,
                config.SUBPOLICY_CRITICAL_ENVIRONMENTAL_LOW_ENERGY
            ]:
                self._handle_critical_environmental(
                    pkt=pkt,
                    seq=seq,
                    eval_data=eval_data,
                    energy_policy=energy_policy
                )

            else:
                print("[CM] Unknown deterministic sub-policy -> store safely")
                self.dtn.enqueue(pkt, seq=seq, meta="unknown_subpolicy_store")
                eval_data["decision"] = "unknown_subpolicy_store"
                eval_data["selected_interface"] = "dtn"
                eval_data["outcome"] = config.OUTCOME_STORED

        flush_result = self._opportunistic_flush(energy_state)

        eval_data["flush_triggered"] = flush_result["triggered"]
        eval_data["flush_interface"] = flush_result["iface"]
        eval_data["flush_sent"] = flush_result["flushed"]

        maint_result = self._maybe_wifi_maintenance(energy_state)

        eval_data["wifi_scan_done"] = maint_result.get("wifi_scan_done", 0)
        eval_data["wifi_found"] = maint_result.get("wifi_found", 0)
        eval_data["wifi_connected"] = maint_result.get("wifi_connected", 0)
        eval_data["config_update_checked"] = maint_result.get("config_update_checked", 0)
        eval_data["config_updated"] = maint_result.get("config_updated", 0)
        eval_data["firmware_checked"] = maint_result.get("firmware_checked", 0)
        eval_data["firmware_available"] = maint_result.get("firmware_available", 0)

        dtn_after = self.dtn.count()

        eval_data["dtn_after"] = dtn_after
        eval_data["dtn_usage"] = round(dtn_after / float(config.DTN_MAX_ITEMS), 3)

        energy_cpu_wake = config.ENERGY_COST_CPU_WAKE
        energy_lora_tx = eval_data["tx_attempts"] * config.ENERGY_COST_LORA_TX
        energy_ack_wait = config.ENERGY_COST_LORA_ACK_WAIT if eval_data["ack_success"] else 0
        energy_sd_write = config.ENERGY_COST_SD_WRITE if eval_data["selected_interface"] == "dtn" else 0
        energy_wifi_tx = config.ENERGY_COST_WIFI_TX if eval_data["flush_interface"] == "wifi" else 0
        energy_ble = config.ENERGY_COST_BLE_GATT if eval_data["flush_interface"] == "ble" else 0
        energy_wifi_maint = getattr(config, "ENERGY_COST_WIFI_MAINT", 0.8) if eval_data["wifi_scan_done"] else 0

        eval_data["energy_cpu_wake"] = energy_cpu_wake
        eval_data["energy_lora_tx"] = energy_lora_tx
        eval_data["energy_ack_wait"] = energy_ack_wait
        eval_data["energy_sd_write"] = energy_sd_write
        eval_data["energy_wifi_tx"] = energy_wifi_tx
        eval_data["energy_ble"] = energy_ble
        eval_data["energy_wifi_maint"] = energy_wifi_maint

        eval_data["energy_proxy"] = round(
            energy_cpu_wake
            + energy_lora_tx
            + energy_ack_wait
            + energy_sd_write
            + energy_wifi_tx
            + energy_ble
            + energy_wifi_maint,
            3
        )

        self.logger.log(eval_data)
        self._print_final_report(eval_data)

        return eval_data


def main():
    cm = CommunicationManager()
    cm.wake_cycle()


if __name__ == "__main__":
    main()