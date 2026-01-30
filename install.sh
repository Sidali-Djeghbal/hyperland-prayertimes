#!/usr/bin/env bash
set -euo pipefail

CONFIG_DIR="$HOME/.config/hyperland-prayertimes"
WAYBAR_SCRIPTS="$HOME/.config/waybar/scripts"

mkdir -p "$CONFIG_DIR" "$WAYBAR_SCRIPTS"

cp -f "$(dirname "$0")/scripts/prayertimes.py" "$WAYBAR_SCRIPTS/prayertimes.py"
chmod +x "$WAYBAR_SCRIPTS/prayertimes.py"

if [ ! -f "$CONFIG_DIR/config.json" ]; then
  cp "$(dirname "$0")/config/config.json" "$CONFIG_DIR/config.json"
fi

echo "Installed prayertimes script and config."
