import json
import os

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "hyperland-prayertimes")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "location": "Auto",
    "locations": {},
    "default_tz": None,
    "default_country": None,
    "method": "Egyptian",
    "asr_method": "Standard",
    "imsak_minutes": 10,
    "dhuhr_minutes": 0,
    "maghrib_minutes": 0,
    "isha_minutes": 0,
    "adjustments": {
        "fajr": 0,
        "sunrise": 0,
        "dhuhr": 0,
        "asr": 0,
        "maghrib": 0,
        "isha": 0
    },
    "time_format": "24h",
    "display": {
        "format": "{next_name} {next_time} - {countdown}"
    }
}


def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(config, path=CONFIG_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
