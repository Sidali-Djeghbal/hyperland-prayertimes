import argparse
import json
import sys

from .config import CONFIG_PATH, load_config, save_config
from .geo import resolve_location
from .methods import METHODS
from .render import render_waybar


def handle_cli(args):
    config = load_config(CONFIG_PATH)

    if args.list_methods:
        for key in METHODS:
            print(f"{key}: {METHODS[key]['name']}")
        return 0

    if args.list_locations:
        for name, loc in config.get("locations", {}).items():
            label = loc.get("label") or name
            lat = loc.get("lat")
            lng = loc.get("lng")
            tz = loc.get("tz", "local")
            if lat is not None and lng is not None:
                print(f"{name}: {label} ({lat}, {lng}) [{tz}]")
            else:
                print(f"{name}: {label} [unresolved] [{tz}]")
        return 0

    if args.use_location:
        location_key = args.use_location
        if location_key not in config.get("locations", {}):
            config.setdefault("locations", {})[location_key] = {
                "query": location_key,
                "tz": config.get("default_tz")
            }
        resolve_location(config, location_key, persist=True)
        config["location"] = location_key
        save_config(config, CONFIG_PATH)
        return 0

    if args.set_method:
        if args.set_method not in METHODS:
            raise ValueError(f"Unknown method: {args.set_method}")
        config["method"] = args.set_method
        save_config(config, CONFIG_PATH)
        return 0

    if args.set_offset:
        prayer, minutes = args.set_offset
        prayer_key = prayer.lower()
        if prayer_key not in config.get("adjustments", {}):
            raise ValueError(f"Unknown prayer for offset: {prayer}")
        config["adjustments"][prayer_key] = int(minutes)
        save_config(config, CONFIG_PATH)
        return 0

    if args.set_location:
        if args.lat and args.lng:
            config.setdefault("locations", {})[args.set_location] = {
                "lat": float(args.lat),
                "lng": float(args.lng),
                "tz": args.tz or config.get("default_tz"),
                "label": args.set_location
            }
            config["location"] = args.set_location
            save_config(config, CONFIG_PATH)
            return 0
        config.setdefault("locations", {})[args.set_location] = {
            "query": args.set_location,
            "tz": args.tz or config.get("default_tz")
        }
        resolve_location(config, args.set_location, persist=True)
        config["location"] = args.set_location
        save_config(config, CONFIG_PATH)
        return 0

    if args.waybar:
        payload = render_waybar(config)
        print(json.dumps(payload, ensure_ascii=True))
        return 0

    return 0


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Waybar prayer times module")
    parser.add_argument("--waybar", action="store_true", help="Output Waybar JSON payload")
    parser.add_argument("--list-methods", action="store_true", help="List calculation methods")
    parser.add_argument("--list-locations", action="store_true", help="List locations from config")
    parser.add_argument("--use-location", help="Switch current location (auto resolves if not saved)")
    parser.add_argument("--set-location", help="Add or update a location and set it active (coords optional)")
    parser.add_argument("--lat", help="Latitude for --set-location")
    parser.add_argument("--lng", help="Longitude for --set-location")
    parser.add_argument("--tz", help="IANA time zone for --set-location (optional)")
    parser.add_argument("--set-method", help="Set calculation method")
    parser.add_argument("--set-offset", nargs=2, metavar=("PRAYER", "MIN"), help="Set prayer offset in minutes")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        return handle_cli(args)
    except Exception as exc:
        if args.waybar:
            payload = {
                "text": "Prayer?",
                "tooltip": str(exc),
                "class": "prayertimes-error"
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0
        print(f"Error: {exc}", file=sys.stderr)
        return 1
