# flush_controller.py — simplified threshold-based version

class FlushController:

    def __init__(self):
        pass

    def scheduled_window_due(self):
        # No time-based flush anymore
        return True

    def maintenance_flag(self):
        return False

    def mark_flush(self):
        pass