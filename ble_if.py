# ble_if.py — BLE transport with two modes:
# 1. advertise()      = opportunistic, no ACK, no DTN dequeue
# 2. send_with_ack()  = reliable BLE GATT delivery, ACK-confirmed

import time
import bluetooth
from micropython import const
import config


_IRQ_SCAN_RESULT = const(5)
_IRQ_SCAN_DONE = const(6)
_IRQ_PERIPHERAL_CONNECT = const(7)
_IRQ_PERIPHERAL_DISCONNECT = const(8)
_IRQ_GATTC_SERVICE_RESULT = const(9)
_IRQ_GATTC_SERVICE_DONE = const(10)
_IRQ_GATTC_CHARACTERISTIC_RESULT = const(11)
_IRQ_GATTC_CHARACTERISTIC_DONE = const(12)
_IRQ_GATTC_WRITE_DONE = const(17)
_IRQ_GATTC_NOTIFY = const(18)


UART_SERVICE_UUID = bluetooth.UUID("6E400001-B5A3-F393-E0A9-E50E24DCCA9E")
UART_RX_UUID = bluetooth.UUID("6E400002-B5A3-F393-E0A9-E50E24DCCA9E")
UART_TX_UUID = bluetooth.UUID("6E400003-B5A3-F393-E0A9-E50E24DCCA9E")


def decode_name(adv_data):
    i = 0
    while i + 1 < len(adv_data):
        length = adv_data[i]
        if length == 0:
            break

        ad_type = adv_data[i + 1]

        if ad_type == 0x09:
            return bytes(adv_data[i + 2:i + 1 + length]).decode()

        i += 1 + length

    return ""


class BLEIF:

    def __init__(self):
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.irq(self._irq)

        self.target_name = "MoleNet-BLE-RX"

        self._found = False

        self.addr_type = None
        self.addr = None
        self.conn_handle = None

        self.start_handle = None
        self.end_handle = None
        self.rx_handle = None
        self.tx_handle = None

        self.connected = False
        self.scan_done = False
        self.service_done = False
        self.char_done = False

        self.ack_msg = None
        self.write_done = False

    # ------------------------------------------------------------
    # BLE IRQ handler
    # ------------------------------------------------------------

    def _irq(self, event, data):

        if event == _IRQ_SCAN_RESULT:
            addr_type, addr, adv_type, rssi, adv_data = data

            self._found = True

            name = decode_name(adv_data)

            if name == self.target_name:
                print("[BLE] Found target:", name, "RSSI:", rssi)
                self.addr_type = addr_type
                self.addr = bytes(addr)

                try:
                    self.ble.gap_scan(None)
                except:
                    pass

        elif event == _IRQ_SCAN_DONE:
            self.scan_done = True
            print("[BLE] Scan done")

        elif event == _IRQ_PERIPHERAL_CONNECT:
            conn_handle, addr_type, addr = data
            self.conn_handle = conn_handle
            self.connected = True
            print("[BLE] Connected:", conn_handle)

            try:
                self.ble.gattc_discover_services(conn_handle)
            except Exception as e:
                print("[BLE] Service discovery start failed:", e)

        elif event == _IRQ_PERIPHERAL_DISCONNECT:
            conn_handle, addr_type, addr = data
            print("[BLE] Disconnected")
            self.connected = False
            self.conn_handle = None

        elif event == _IRQ_GATTC_SERVICE_RESULT:
            conn_handle, start_handle, end_handle, uuid = data

            if uuid == UART_SERVICE_UUID:
                self.start_handle = start_handle
                self.end_handle = end_handle
                print("[BLE] Service found")

        elif event == _IRQ_GATTC_SERVICE_DONE:
            self.service_done = True

            if self.start_handle is not None:
                try:
                    self.ble.gattc_discover_characteristics(
                        self.conn_handle,
                        self.start_handle,
                        self.end_handle
                    )
                except Exception as e:
                    print("[BLE] Characteristic discovery failed:", e)

        elif event == _IRQ_GATTC_CHARACTERISTIC_RESULT:
            conn_handle, def_handle, value_handle, properties, uuid = data

            if uuid == UART_RX_UUID:
                self.rx_handle = value_handle
                print("[BLE] RX write handle:", self.rx_handle)

            elif uuid == UART_TX_UUID:
                self.tx_handle = value_handle
                print("[BLE] TX notify handle:", self.tx_handle)

        elif event == _IRQ_GATTC_CHARACTERISTIC_DONE:
            self.char_done = True

        elif event == _IRQ_GATTC_WRITE_DONE:
            conn_handle, value_handle, status = data
            self.write_done = True
            print("[BLE] Write done, status:", status)

        elif event == _IRQ_GATTC_NOTIFY:
            conn_handle, value_handle, notify_data = data

            try:
                msg = bytes(notify_data).decode()
            except Exception:
                msg = str(bytes(notify_data))

            self.ack_msg = msg
            print("[BLE NOTIFY]", msg)

    # ------------------------------------------------------------
    # Opportunistic BLE scan
    # ------------------------------------------------------------

    def probe_scan(self, scan_ms):
        self._found = False

        try:
            self.ble.gap_scan(scan_ms, 30000, 30000)

            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < scan_ms:
                if self._found:
                    break
                time.sleep_ms(20)

        finally:
            try:
                self.ble.gap_scan(None)
            except:
                pass

        return self._found

    # ------------------------------------------------------------
    # Mode 1: BLE advertisement only
    # ------------------------------------------------------------

    def advertise(self, pkt, seq=None, adv_ms=None):

        if adv_ms is None:
            adv_ms = config.BLE_ADV_MS

        try:
            chunk = pkt[:config.BLE_ADV_MAX_PAYLOAD]
            payload = self._build_adv_payload(chunk)

            self.ble.gap_advertise(100000, adv_data=payload)
            time.sleep_ms(adv_ms)
            self.ble.gap_advertise(None)

            print("[BLE ADV ONLY] seq =", seq)

            return {
                "status": config.OUTCOME_BLE_ADVERTISED_ONLY,
                "confirmed": False,
                "seq": seq
            }

        except Exception as e:
            print("[BLE ADV ERROR]", e)

            try:
                self.ble.gap_advertise(None)
            except:
                pass

            return {
                "status": config.OUTCOME_FAILED,
                "reason": "ble_adv_failed",
                "confirmed": False,
                "seq": seq
            }

    def send_adv(self, pkt, adv_ms=800):
        result = self.advertise(pkt, seq=None, adv_ms=adv_ms)
        return result["status"] == config.OUTCOME_BLE_ADVERTISED_ONLY

    def _build_adv_payload(self, data):
        payload = bytearray()
        mfg = config.BLE_ADV_PREFIX + data
        payload += bytes((len(mfg) + 1, 0xFF)) + mfg
        return payload

    # ------------------------------------------------------------
    # Mode 2: Reliable BLE GATT delivery with ACK
    # ------------------------------------------------------------

    def _reset_connection_state(self):
        self.addr_type = None
        self.addr = None
        self.conn_handle = None

        self.start_handle = None
        self.end_handle = None
        self.rx_handle = None
        self.tx_handle = None

        self.connected = False
        self.scan_done = False
        self.service_done = False
        self.char_done = False

        self.ack_msg = None
        self.write_done = False

    def _connect_to_receiver(self, timeout_ms=8000):
        self._reset_connection_state()

        print("[BLE] Scanning for reliable receiver:", self.target_name)

        try:
            self.ble.gap_scan(timeout_ms, 30000, 30000)
        except Exception as e:
            print("[BLE] Scan start failed:", e)
            return False

        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.addr is not None:
                break
            time.sleep_ms(50)

        try:
            self.ble.gap_scan(None)
        except:
            pass

        if self.addr is None:
            print("[BLE] Target receiver not found")
            return False

        print("[BLE] Connecting...")

        try:
            self.ble.gap_connect(self.addr_type, self.addr)
        except Exception as e:
            print("[BLE] Connect failed:", e)
            return False

        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.connected:
                return True
            time.sleep_ms(50)

        print("[BLE] Connect timeout")
        return False

    def _discover_uart_service(self, timeout_ms=8000):
        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.rx_handle is not None and self.tx_handle is not None:
                return True
            time.sleep_ms(50)

        print("[BLE] Discovery timeout")
        return False

    def _disconnect(self):
        if self.conn_handle is not None:
            try:
                self.ble.gap_disconnect(self.conn_handle)
            except:
                pass

    def send_with_ack(self, pkt, seq, timeout_ms=5000):
        """
        Reliable BLE delivery:
        Node A connects to Node B.
        Node A writes DATA|seq|payload.
        Node B responds BLE_ACK:seq.
        Success only if matching ACK is received.
        """

        if not self._connect_to_receiver():
            return {
                "status": config.OUTCOME_FAILED,
                "reason": "ble_receiver_not_found_or_connect_failed",
                "seq": seq,
                "ack_success": 0
            }

        if not self._discover_uart_service():
            self._disconnect()
            return {
                "status": config.OUTCOME_FAILED,
                "reason": "ble_service_discovery_failed",
                "seq": seq,
                "ack_success": 0
            }

        self.ack_msg = None
        self.write_done = False

        # Keep payload short for BLE default MTU.
        # For CM packet, we transmit compact metadata plus first payload bytes.
        try:
            pkt_preview = pkt[:8]
            pkt_hex = "".join(["%02x" % b for b in pkt_preview])
        except:
            pkt_hex = "raw"

        msg = "DATA|%d|%s" % (int(seq), pkt_hex)
        expected = "BLE_ACK:%d" % int(seq)

        print("[BLE TX]", msg)
        print("[BLE expected ACK]", expected)

        try:
            self.ble.gattc_write(
                self.conn_handle,
                self.rx_handle,
                msg.encode(),
                1
            )
        except Exception as e:
            print("[BLE] Write failed:", e)
            self._disconnect()
            return {
                "status": config.OUTCOME_FAILED,
                "reason": "ble_write_failed",
                "seq": seq,
                "ack_success": 0
            }

        t0 = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
            if self.ack_msg == expected:
                rtt = time.ticks_diff(time.ticks_ms(), t0)
                print("[BLE ACK MATCHED]", self.ack_msg)

                self._disconnect()

                return {
                    "status": config.OUTCOME_SUCCESS,
                    "seq": seq,
                    "ack_success": 1,
                    "rtt_ms": rtt
                }

            time.sleep_ms(50)

        print("[BLE] ACK timeout")

        self._disconnect()

        return {
            "status": config.OUTCOME_FAILED,
            "reason": "ble_ack_timeout",
            "seq": seq,
            "ack_success": 0,
            "rtt_ms": None
        }