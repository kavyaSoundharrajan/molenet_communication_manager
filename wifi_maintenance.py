# wifi_maintenance.py — periodic WiFi config/firmware-check maintenance
VERSION = "1.2.0"

import time
import network
import config
from runtime_config import apply_runtime_config_dict

try:
    import urequests as requests
except:
    requests = None

try:
    import ujson as json
except:
    import json


class WiFiMaintenance:

    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.last_result = {}

    # ------------------------------------------------------------
    # Basic WiFi helpers
    # ------------------------------------------------------------

    def _ensure_active(self):
        if not self.wlan.active():
            self.wlan.active(True)
            time.sleep_ms(1000)

    def _wifi_ssid(self):
        return config.WIFI_SSID

    def _wifi_password(self):
        if hasattr(config, "WIFI_PASS"):
            return config.WIFI_PASS
        if hasattr(config, "WIFI_PASSWORD"):
            return config.WIFI_PASSWORD
        return ""

    def _config_host(self):
        if hasattr(config, "CONFIG_UPDATE_HOST"):
            return config.CONFIG_UPDATE_HOST
        if hasattr(config, "WIFI_UDP_HOST"):
            return config.WIFI_UDP_HOST
        if hasattr(config, "WIFI_HOST"):
            return config.WIFI_HOST
        return "192.168.1.1"

    def _url(self, path):
        return "http://%s:%d%s" % (
            self._config_host(),
            config.CONFIG_UPDATE_PORT,
            path
        )

    # ------------------------------------------------------------
    # WiFi scan/connect/disconnect
    # ------------------------------------------------------------

    def scan_for_ssid(self, ssid, retries=3):
        self._ensure_active()

        for attempt in range(1, retries + 1):
            print("[WiFiMaint] scan attempt", attempt)

            try:
                time.sleep_ms(1000)
                nets = self.wlan.scan()
            except Exception as e:
                print("[WiFiMaint] scan failed:", e)
                continue

            for net in nets:
                try:
                    found_ssid = net[0].decode()
                except:
                    found_ssid = str(net[0])

                try:
                    channel = net[2]
                    rssi = net[3]
                except:
                    channel = 0
                    rssi = 0

                print(
                    "[WiFiMaint] seen:",
                    found_ssid,
                    "RSSI:",
                    rssi,
                    "CH:",
                    channel
                )

                if found_ssid == ssid:
                    print("[WiFiMaint] SSID found:", ssid)
                    return True

        print("[WiFiMaint] SSID not found:", ssid)
        return False

    def connect(self, timeout_ms=20000):
        self._ensure_active()

        ssid = self._wifi_ssid()
        password = self._wifi_password()

        if self.wlan.isconnected():
            print("[WiFiMaint] already connected:", self.wlan.ifconfig())
            return True

        print("[WiFiMaint] connecting to:", ssid)

        try:
            self.wlan.connect(ssid, password)
        except Exception as e:
            print("[WiFiMaint] connect call failed:", e)
            return False

        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.wlan.isconnected():
                print("[WiFiMaint] connected:", self.wlan.ifconfig())
                return True

            try:
                print(
                    "[WiFiMaint] status:",
                    self.wlan.status(),
                    "connected:",
                    self.wlan.isconnected()
                )
            except:
                pass

            time.sleep_ms(1000)

        print("[WiFiMaint] connection timeout")
        return False

    def disconnect(self):
        try:
            if self.wlan.isconnected():
                self.wlan.disconnect()
                time.sleep_ms(500)
        except:
            pass

        try:
            self.wlan.active(False)
        except:
            pass

        print("[WiFiMaint] WiFi powered down")

    # ------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------

    def _http_get_text(self, path):
        if requests is None:
            print("[WiFiMaint] urequests not available")
            return None

        url = self._url(path)
        print("[WiFiMaint] GET", url)

        try:
            try:
                r = requests.get(url, timeout=5)
            except TypeError:
                r = requests.get(url)

            text = r.text
            r.close()
            return text

        except Exception as e:
            print("[WiFiMaint] HTTP GET failed:", e)
            return None

    # ------------------------------------------------------------
    # Runtime config handling
    # ------------------------------------------------------------

    def _save_runtime_config(self, text):
        try:
            with open(config.RUNTIME_CONFIG_FILE, "w") as f:
                f.write(text)
            return True

        except Exception as e:
            print("[WiFiMaint] save runtime config failed:", e)
            return False

    def check_config_update(self):
        text = self._http_get_text(config.CONFIG_UPDATE_PATH)

        if text is None:
            return {
                "checked": 1,
                "updated": 0,
                "saved": 0,
                "reason": "download_failed",
                "applied": [],
                "rejected": []
            }

        try:
            cfg = json.loads(text)
        except Exception as e:
            print("[WiFiMaint] JSON parse failed:", e)
            return {
                "checked": 1,
                "updated": 0,
                "saved": 0,
                "reason": "json_parse_failed",
                "applied": [],
                "rejected": []
            }

        applied, rejected = apply_runtime_config_dict(cfg)
        saved = self._save_runtime_config(text)

        print("[WiFiMaint] config applied:", applied)
        print("[WiFiMaint] config rejected:", rejected)

        return {
            "checked": 1,
            "updated": 1 if applied else 0,
            "saved": 1 if saved else 0,
            "reason": "ok",
            "applied": applied,
            "rejected": rejected
        }

    # ------------------------------------------------------------
    # Firmware manifest check only
    # ------------------------------------------------------------

    def check_firmware_manifest(self):
        text = self._http_get_text(config.FIRMWARE_MANIFEST_PATH)

        if text is None:
            return {
                "checked": 1,
                "available": 0,
                "reason": "manifest_not_found_or_download_failed"
            }

        try:
            manifest = json.loads(text)
        except Exception:
            return {
                "checked": 1,
                "available": 0,
                "reason": "manifest_json_parse_failed"
            }

        remote_version = manifest.get("version", "")
        url = manifest.get("url", "")

        print("[WiFiMaint] firmware manifest version:", remote_version)

        return {
            "checked": 1,
            "available": 1 if remote_version else 0,
            "version": remote_version,
            "url": url,
            "reason": "manifest_checked"
        }

    # ------------------------------------------------------------
    # Public maintenance runner
    # ------------------------------------------------------------

    def run(self, check_firmware=False):
        result = {
            "wifi_scan_done": 0,
            "wifi_found": 0,
            "wifi_connected": 0,
            "config_update_checked": 0,
            "config_updated": 0,
            "firmware_checked": 0,
            "firmware_available": 0,
            "reason": ""
        }

        if not getattr(config, "WIFI_MAINTENANCE_ENABLED", False):
            result["reason"] = "disabled"
            self.last_result = result
            return result

        try:
            ssid = self._wifi_ssid()

            result["wifi_scan_done"] = 1

            if not self.scan_for_ssid(ssid):
                result["reason"] = "ssid_not_found"
                self.last_result = result
                return result

            result["wifi_found"] = 1

            if not self.connect():
                result["reason"] = "wifi_connect_failed"
                self.last_result = result
                return result

            result["wifi_connected"] = 1

            cfg_result = self.check_config_update()

            result["config_update_checked"] = cfg_result.get("checked", 0)
            result["config_updated"] = cfg_result.get("updated", 0)

            if check_firmware:
                fw_result = self.check_firmware_manifest()
                result["firmware_checked"] = fw_result.get("checked", 0)
                result["firmware_available"] = fw_result.get("available", 0)

            result["reason"] = "ok"
            self.last_result = result
            return result

        finally:
            self.disconnect()