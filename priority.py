# priority.py — classify packet priority

NORMAL = 0
CRITICAL = 1


def classify(payload):
    """
    Payload-level fallback classifier.

    CRITICAL is only for explicit alert packets.
    Normal rainfall/storage packets are not critical.
    """

    if not payload:
        return NORMAL

    if b"ALERT=1" in payload:
        return CRITICAL

    if b"PR=CRITICAL" in payload:
        return CRITICAL

    return NORMAL