# packet.py — compact CM frame for raw LoRa + ACK matching

# Frame layout:
# [node_id:1][seq:2][timestamp:4][priority_flag:1][payload:n]
#
# priority_flag:
#   0 = NORMAL
#   1 = CRITICAL

PRIORITY_NORMAL = 0
PRIORITY_CRITICAL = 1


def build_data_frame(node_id, seq, ts_s, payload, priority):
    if payload is None:
        payload = b""

    if isinstance(payload, str):
        payload = payload.encode()

    prio = PRIORITY_CRITICAL if priority == "CRITICAL" else PRIORITY_NORMAL

    frame = (
        int(node_id & 0xFF).to_bytes(1, "big") +
        int(seq & 0xFFFF).to_bytes(2, "big") +
        int(ts_s & 0xFFFFFFFF).to_bytes(4, "big") +
        int(prio & 0xFF).to_bytes(1, "big") +
        payload
    )

    return frame


def parse_data_frame(raw):
    if raw is None or len(raw) < 8:
        return None

    try:
        node_id = raw[0]
        seq = int.from_bytes(raw[1:3], "big")
        ts_s = int.from_bytes(raw[3:7], "big")
        priority_flag = raw[7]
        payload = raw[8:]

        priority = "CRITICAL" if priority_flag == PRIORITY_CRITICAL else "NORMAL"

        return {
            "node_id": node_id,
            "seq": seq,
            "ts_s": ts_s,
            "priority_flag": priority_flag,
            "priority": priority,
            "payload": payload
        }

    except Exception:
        return None


def build_ack(seq):
    return ("ACK:%d" % int(seq)).encode()


def is_ack_for(raw_ack, seq):
    if raw_ack is None:
        return False

    expected = "ACK:%d" % int(seq)

    try:
        msg = raw_ack.decode()
    except Exception:
        msg = str(raw_ack)

    return msg == expected