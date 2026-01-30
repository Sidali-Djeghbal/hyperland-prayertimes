#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.config/hyperland-prayertimes"
WAYBAR_SCRIPTS="$HOME/.config/waybar/scripts"
WAYBAR_LIB="$HOME/.config/waybar/prayertimes"

mkdir -p "$CONFIG_DIR" "$WAYBAR_SCRIPTS" "$WAYBAR_LIB"

cp -f "$(dirname "$0")/scripts/prayertimes.py" "$WAYBAR_SCRIPTS/prayertimes.py"
chmod +x "$WAYBAR_SCRIPTS/prayertimes.py"
cp -a "$(dirname "$0")/prayertimes/." "$WAYBAR_LIB/"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
  cp "$(dirname "$0")/config/config.json" "$CONFIG_DIR/config.json"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 - <<'PY'
import json
import os
import sys

repo_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, repo_root)

from prayertimes.config import DEFAULT_CONFIG, CONFIG_PATH, save_config
from prayertimes.geo import auto_detect_location, resolve_location


def safe_input(prompt):
    try:
        return input(prompt)
    except EOFError:
        return ""


config = DEFAULT_CONFIG.copy()
try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config.update(json.load(f))
except FileNotFoundError:
    pass

config["location"] = "Auto"
config.setdefault("locations", {})

try:
    location_key, loc = auto_detect_location(config)
    label = loc.get("label") or location_key
    answer = safe_input(f"Is your place '{label}'? [y/n] ").strip().lower()
    if answer in {"", "y", "yes"}:
        config["location"] = location_key
    else:
        manual = safe_input("Enter your location: ").strip()
        if manual:
            config.setdefault("locations", {})[manual] = {
                "query": manual,
                "tz": config.get("default_tz")
            }
            resolve_location(config, manual, persist=True)
            config["location"] = manual
        else:
            config["location"] = location_key
except Exception as exc:
    print(f"Auto-detect failed: {exc}")
    manual = safe_input("Enter your location: ").strip()
    if manual:
        config.setdefault("locations", {})[manual] = {
            "query": manual,
            "tz": config.get("default_tz")
        }
        try:
            resolve_location(config, manual, persist=True)
            config["location"] = manual
        except Exception as exc2:
            print(f"Manual resolve failed: {exc2}")

save_config(config, CONFIG_PATH)
PY
  "$WAYBAR_SCRIPTS/prayertimes.py" --waybar >/dev/null 2>&1 || true
fi

echo "Installed prayertimes script and config."
