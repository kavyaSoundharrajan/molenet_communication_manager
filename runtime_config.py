# runtime_config.py — load and apply downloaded runtime config
VERSION = "1.0.0"

try:
    import ujson as json
except:
    import json

import config
from sd_mount import mount_sd


def _allowed_keys():
    return getattr(config, "CONFIG_UPDATE_ALLOWED_KEYS", [])


def apply_runtime_config_dict(cfg):
    applied = []
    rejected = []

    allowed = _allowed_keys()

    for key in cfg:
        if key in allowed:
            try:
                setattr(config, key, cfg[key])
                applied.append(key)
            except Exception:
                rejected.append(key)
        else:
            rejected.append(key)

    return applied, rejected


def load_runtime_config():
    mount_sd()

    path = getattr(config, "RUNTIME_CONFIG_FILE", "/sd/runtime_config.json")

    try:
        with open(path, "r") as f:
            text = f.read()
    except Exception:
        print("[RuntimeConfig] no runtime config found")
        return {
            "loaded": 0,
            "applied": [],
            "rejected": [],
            "reason": "file_not_found"
        }

    try:
        cfg = json.loads(text)
    except Exception as e:
        print("[RuntimeConfig] JSON parse failed:", e)
        return {
            "loaded": 0,
            "applied": [],
            "rejected": [],
            "reason": "json_parse_failed"
        }

    applied, rejected = apply_runtime_config_dict(cfg)

    print("[RuntimeConfig] applied:", applied)
    print("[RuntimeConfig] rejected:", rejected)

    return {
        "loaded": 1,
        "applied": applied,
        "rejected": rejected,
        "reason": "ok"
    }