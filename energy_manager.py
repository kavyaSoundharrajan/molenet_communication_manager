# energy_manager.py — MoleNet energy-state manager

import config

try:
    import urandom as random
except ImportError:
    import random


class EnergyManager:

    def __init__(self):
        pass

    def get_state(self):
        mode = getattr(config, "ENERGY_MODE", "SIM_FIXED")

        if mode == "SIM_FIXED":
            return getattr(config, "SIM_ENERGY_STATE", "OK")

        if mode == "SIM_RANDOM":
            ok_p = getattr(config, "ENERGY_RANDOM_OK_PROB", 0.60)
            low_p = getattr(config, "ENERGY_RANDOM_LOW_PROB", 0.25)

            try:
                x = random.getrandbits(16) / 65535
            except Exception:
                x = random.random()

            if x < ok_p:
                return "OK"

            if x < ok_p + low_p:
                return "LOW"

            return "CRITICAL"

        if mode == "ADC":
            # Future real ADC battery sensing
            return "OK"

        return getattr(config, "SIM_ENERGY_STATE", "OK")