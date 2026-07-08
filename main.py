# main.py — autonomous MoleNet Communication Manager wake-to-sleep runner
VERSION = "1.1.0"

import time
import config
from cm_manager import CommunicationManager


def _cfg(name, default):
    return getattr(config, name, default)


def _print_summary(result):
    print("\n================================")
    print(" CM WAKE CYCLE SUMMARY")
    print("================================")
    print("Priority          :", result.get("priority"))
    print("Event             :", result.get("event_type"))
    print("Path              :", result.get("path_name"))
    print("Energy state      :", result.get("energy_state"))
    print("Decision          :", result.get("decision"))
    print("Selected interface:", result.get("selected_interface"))
    print("ACK success       :", result.get("ack_success"))
    print("TX attempts       :", result.get("tx_attempts"))
    print("DTN before/after  :", result.get("dtn_before"), "→", result.get("dtn_after"))
    print("Energy proxy      :", result.get("energy_proxy"))
    print("================================")


def main():
    print("\n================================")
    print(" AUTONOMOUS MOLE-NET CM CYCLE")
    print("================================")

    print("[BOOT]")
    print("  ENABLE_DEEPSLEEP:", _cfg("ENABLE_DEEPSLEEP", False))
    print("  SENSOR_INTERVAL_SECONDS:", _cfg("SENSOR_INTERVAL_SECONDS", 60))

    cm = CommunicationManager()

    print("\n[CM START]")
    result = cm.wake_cycle()

    _print_summary(result)

    if _cfg("ENABLE_DEEPSLEEP", False):
        try:
            import machine

            sleep_s = max(1, int(_cfg("SENSOR_INTERVAL_SECONDS", 60)))
            sleep_ms = sleep_s * 1000

            print("\n[SLEEP]")
            print("  Entering deep sleep for", sleep_s, "seconds")
            time.sleep(1)
            machine.deepsleep(sleep_ms)

        except Exception as e:
            print("[SLEEP ERROR]", e)
            print("  Deep sleep skipped.")
    else:
        print("\n[SLEEP]")
        print("  Deep sleep disabled. Wake cycle complete.")


main()