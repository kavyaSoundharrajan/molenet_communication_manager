# soil_moisture_sim.py — scenario-based soil moisture simulator
VERSION = "2.0.0"

import random
import config


class SoilMoistureSim:

    def __init__(self, start=None):
        self.value = (
            float(start)
            if start is not None
            else getattr(config, "SIM_SOIL_FIXED_VALUE", 0.45)
        )
        self.last_scenario = "init"

    def _rand_range(self, lo, hi):
        return random.uniform(float(lo), float(hi))

    def _choose_scenario(self):
        r = random.random()

        p_normal = getattr(config, "SOIL_SCENARIO_NORMAL_PROB", 0.40)
        p_rain = getattr(config, "SOIL_SCENARIO_RAINFALL_PROB", 0.35)
        p_dry = getattr(config, "SOIL_SCENARIO_EXTREME_DRY_PROB", 0.10)

        if r < p_normal:
            return "normal"

        if r < p_normal + p_rain:
            return "rainfall"

        if r < p_normal + p_rain + p_dry:
            return "extreme_dry"

        return "extreme_wet"

    def read_normalized(self):
        mode = getattr(config, "SOIL_MODE", "SIM_RANDOM_SCENARIO")

        if mode == "SIM_FIXED":
            self.value = getattr(config, "SIM_SOIL_FIXED_VALUE", 0.45)
            self.last_scenario = "fixed"

        elif mode == "SIM_RANDOM":
            self.value = self._rand_range(
                getattr(config, "SOIL_RANDOM_MIN", 0.05),
                getattr(config, "SOIL_RANDOM_MAX", 0.95)
            )
            self.last_scenario = "random"

        elif mode == "SIM_RANDOM_SCENARIO":
            scenario = self._choose_scenario()
            self.last_scenario = scenario

            if scenario == "normal":
                self.value = self._rand_range(
                    config.SOIL_NORMAL_MIN,
                    config.SOIL_NORMAL_MAX
                )

            elif scenario == "rainfall":
                self.value = self._rand_range(
                    config.SOIL_RAINFALL_MIN,
                    config.SOIL_RAINFALL_MAX
                )

            elif scenario == "extreme_dry":
                self.value = self._rand_range(
                    config.SOIL_EXTREME_DRY_MIN,
                    config.SOIL_EXTREME_DRY_MAX
                )

            elif scenario == "extreme_wet":
                self.value = self._rand_range(
                    config.SOIL_EXTREME_WET_MIN,
                    config.SOIL_EXTREME_WET_MAX
                )

        else:
            self.value = getattr(config, "SIM_SOIL_FIXED_VALUE", 0.45)
            self.last_scenario = "fallback_fixed"

        return round(float(self.value), 3)

    def read_raw(self):
        return self.read_normalized()

    def read_temperature(self):
        return None

    def status(self):
        return self.last_scenario