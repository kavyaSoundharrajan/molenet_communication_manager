# payload_builder.py — MicroPython-safe binary payload packing

import ustruct as struct

VER = 2

ENERGY_MAP = {
    "CRITICAL": 0,
    "LOW": 1,
    "OK": 2
}

EVENT_MAP = {
    "NONE": 0,
    "EXTREME_DRY": 1,
    "EXTREME_WET": 2,
    "LOW_BATTERY": 3,
    "BATTERY_CRITICAL": 4
}

VALID_SOIL = 0x01
VALID_BME = 0x02


def clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def build_payload(ts_s,
                  soil_m,
                  temp_c,
                  hum_pct,
                  press_hpa,
                  energy_state,
                  priority="NORMAL",
                  alert_flag=0,
                  event_type="NONE"):

    valid = 0

    if soil_m is None:
        soil_u16 = 0
    else:
        soil_m = clamp(float(soil_m), 0.0, 1.0)
        soil_u16 = int(soil_m * 65535) & 0xFFFF
        valid |= VALID_SOIL

    if temp_c is None or hum_pct is None or press_hpa is None:
        temp_i16 = 0
        hum_u16 = 0
        press_u16 = 0
    else:
        temp_i16 = int(clamp(float(temp_c), -40.0, 85.0) * 100)
        if temp_i16 < -32768:
            temp_i16 = -32768
        if temp_i16 > 32767:
            temp_i16 = 32767

        hum_u16 = int(clamp(float(hum_pct), 0.0, 100.0) * 100) & 0xFFFF
        press_u16 = int(clamp(float(press_hpa), 300.0, 1100.0) * 10) & 0xFFFF
        valid |= VALID_BME

    energy = ENERGY_MAP.get(energy_state, 2) & 0xFF
    prio = 1 if priority == "CRITICAL" else 0
    alert = 1 if alert_flag else 0
    event = EVENT_MAP.get(event_type, 0) & 0xFF

    # v2 layout:
    # [ver:1][ts:4][soil:2][temp:2][hum:2][press:2]
    # [energy:1][priority:1][alert:1][event:1][valid:1]
    return struct.pack(
        "<B L H h H H B B B B B",
        VER,
        int(ts_s) & 0xFFFFFFFF,
        soil_u16,
        temp_i16,
        hum_u16,
        press_u16,
        energy,
        prio,
        alert,
        event,
        valid
    )