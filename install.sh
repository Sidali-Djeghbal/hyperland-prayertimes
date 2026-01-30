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
  "$WAYBAR_SCRIPTS/prayertimes.py" --waybar >/dev/null 2>&1 || true
fi

echo "Installed prayertimes script and config."
