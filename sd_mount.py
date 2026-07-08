import os
import config

def ensure_dir(path):
    parts = path.split("/")
    cur = ""
    for p in parts:
        if not p:
            continue
        cur += "/" + p
        try:
            os.mkdir(cur)
        except OSError:
            pass

def mount_sd():
    mount_point = config.SD_MOUNT_POINT

    try:
        os.listdir(mount_point)
    except:
        raise OSError("SD NOT MOUNTED")

    ensure_dir(config.DTN_DIR)