# dtn_store.py — ACK-safe DTN storage
# Stores seq + packet hex + meta.
# Packet is never removed by peek_oldest().
# Packet is removed only by dequeue_oldest() after ACK-confirmed delivery.

import ubinascii
import config
from sd_mount import mount_sd

QUEUE_FILE = config.DTN_QUEUE_FILE
MAX_ITEMS = config.DTN_MAX_ITEMS


class DTNStore:

    def __init__(self):
        mount_sd()
        self._init_file()

    # ------------------------------------------------------------
    # File helpers
    # ------------------------------------------------------------

    def _init_file(self):
        try:
            open(QUEUE_FILE, "r").close()
        except:
            open(QUEUE_FILE, "w").close()

    def _read_lines(self):
        try:
            with open(QUEUE_FILE, "r") as f:
                return [line.strip() for line in f if line.strip()]
        except Exception as e:
            print("[DTN READ ERROR]", e)
            return []

    def _write_lines(self, lines):
        try:
            with open(QUEUE_FILE, "w") as f:
                for line in lines:
                    f.write(line + "\n")
            return True
        except Exception as e:
            print("[DTN WRITE ERROR]", e)
            return False

    # ------------------------------------------------------------
    # Basic queue state
    # ------------------------------------------------------------

    def count(self):
        return len(self._read_lines())

    def is_empty(self):
        return self.count() == 0

    def usage_ratio(self):
        if MAX_ITEMS <= 0:
            return 0.0
        return self.count() / float(MAX_ITEMS)

    # ------------------------------------------------------------
    # Encoding / decoding
    # ------------------------------------------------------------

    def _encode_entry(self, pkt, seq, meta):
        """
        Format:
            seq|hex_payload|meta
        """
        if seq is None:
            seq = 0

        if meta is None:
            meta = ""

        pkt_hex = ubinascii.hexlify(pkt).decode()

        # Avoid breaking line format if meta accidentally contains "|"
        meta = str(meta).replace("|", "_")

        return "%d|%s|%s" % (int(seq), pkt_hex, meta)

    def _parse_line(self, line):
        """
        Returns:
            {
                "seq": int,
                "pkt": bytes,
                "meta": str
            }

        Supports:
            new format: seq|hex_payload|meta
            legacy format: hex_payload
        """

        if not line:
            return None

        parts = line.split("|")

        # New format
        if len(parts) >= 2:
            try:
                seq = int(parts[0])
                pkt = ubinascii.unhexlify(parts[1])
                meta = parts[2] if len(parts) >= 3 else ""

                return {
                    "seq": seq,
                    "pkt": pkt,
                    "meta": meta
                }
            except Exception:
                pass

        # Legacy fallback: old queue contained only hex payload
        try:
            pkt = ubinascii.unhexlify(line)
            return {
                "seq": 0,
                "pkt": pkt,
                "meta": "legacy"
            }
        except Exception as e:
            print("[DTN PARSE ERROR]", e)
            return None

    # ------------------------------------------------------------
    # Queue operations
    # ------------------------------------------------------------

    def enqueue(self, pkt, seq=None, meta=""):
        """
        Store packet persistently.

        Important:
            enqueue() stores the packet.
            It does NOT imply delivery.
        """

        lines = self._read_lines()

        if len(lines) >= MAX_ITEMS:
            if config.DTN_DROP_POLICY == "DROP_OLDEST":
                dropped = lines.pop(0)
                print("[DTN DROP OLDEST]", dropped)
            else:
                print("[DTN FULL] enqueue rejected")
                return False

        line = self._encode_entry(pkt, seq, meta)
        lines.append(line)

        ok = self._write_lines(lines)

        if ok:
            print("[DTN ENQUEUE] seq =", seq, "count =", len(lines))

        return ok

    def peek_oldest(self):
        """
        Read oldest packet WITHOUT deleting it.

        This is the correct function before transmission.
        """

        lines = self._read_lines()

        if not lines:
            return None

        entry = self._parse_line(lines[0])

        if entry is None:
            print("[DTN PEEK ERROR] Could not parse oldest entry")

        return entry

    def dequeue_oldest(self):
        """
        Remove oldest packet.

        Critical rule:
            Call this ONLY after ACK-confirmed delivery.
        """

        lines = self._read_lines()

        if not lines:
            return None

        first = lines.pop(0)

        ok = self._write_lines(lines)

        if not ok:
            print("[DTN DEQUEUE ERROR] Write-back failed")
            return None

        entry = self._parse_line(first)

        if entry is not None:
            print("[DTN DEQUEUE] seq =", entry["seq"], "count =", len(lines))

        return entry

    # ------------------------------------------------------------
    # Backward-compatible aliases
    # ------------------------------------------------------------

    def peek(self):
        """
        Legacy helper.
        Returns only packet bytes.
        Prefer peek_oldest() for ACK-safe logic.
        """
        entry = self.peek_oldest()
        if entry is None:
            return None
        return entry["pkt"]

    def dequeue(self):
        """
        Legacy helper.
        Returns only packet bytes.
        Prefer dequeue_oldest() after ACK success.
        """
        entry = self.dequeue_oldest()
        if entry is None:
            return None
        return entry["pkt"]

    def clear(self):
        ok = self._write_lines([])
        if ok:
            print("[DTN CLEAR]")
        return ok