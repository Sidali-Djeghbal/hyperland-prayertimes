#!/usr/bin/env python3
import argparse
import json
import math
import os
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, date, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".config", "hyperland-prayertimes")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "location": "Guelma",
    "locations": {
        "Guelma": {"lat": 36.4629, "lng": 7.4339, "tz": "Africa/Algiers", "label": "Guelma, Algeria"},
        "Biskra": {"lat": 34.8504, "lng": 5.7280, "tz": "Africa/Algiers", "label": "Biskra, Algeria"}
    },
    "default_tz": "Africa/Algiers",
    "default_country": "Algeria",
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

METHODS = {
    "MWL": {"name": "Muslim World League", "params": {"fajr": 18, "isha": 17}},
    "Egyptian": {"name": "Egyptian General Authority", "params": {"fajr": 19.5, "isha": 17.5}},
    "Makkah": {"name": "Umm al-Qura", "params": {"fajr": 18.5, "isha": "90 min"}}
}

PRAYER_ORDER = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]


@dataclass
class Coordinates:
    lat: float
    lng: float


def _dtr(d):
    return (d * math.pi) / 180.0


def _rtd(r):
    return (r * 180.0) / math.pi


def _fix_angle(a):
    return a - 360.0 * math.floor(a / 360.0)


def _fix_hour(h):
    return h - 24.0 * math.floor(h / 24.0)


def _clamp(x, min_val, max_val):
    return max(min_val, min(max_val, x))


def _julian_date(y, m, d):
    if m <= 2:
        y -= 1
        m += 12
    a = math.floor(y / 100)
    b = 2 - a + math.floor(a / 4)
    return math.floor(365.25 * (y + 4716)) + math.floor(30.6001 * (m + 1)) + d + b - 1524.5


def _sun_position(jd):
    d = jd - 2451545.0
    g = _fix_angle(357.529 + 0.98560028 * d)
    q = _fix_angle(280.459 + 0.98564736 * d)
    L = _fix_angle(q + 1.915 * math.sin(_dtr(g)) + 0.020 * math.sin(_dtr(2 * g)))
    e = 23.439 - 0.00000036 * d
    ra = _rtd(math.atan2(math.cos(_dtr(e)) * math.sin(_dtr(L)), math.cos(_dtr(L)))) / 15.0
    ra = _fix_hour(ra)
    eqt = q / 15.0 - ra
    decl = _rtd(math.asin(math.sin(_dtr(e)) * math.sin(_dtr(L))))
    return decl, eqt
5

class PrayTimes:
    def __init__(self, method_key, asr_method, imsak_minutes, dhuhr_minutes, maghrib_minutes, isha_minutes):
        method = METHODS.get(method_key)
        if not method:
            raise ValueError(f"Unknown method: {method_key}")
        self.method = method
        self.params = dict(method["params"])
        self.params.setdefault("imsak", f"{imsak_minutes} min")
        self.params.setdefault("dhuhr", dhuhr_minutes)
        if maghrib_minutes:
            self.params["maghrib"] = f"{maghrib_minutes} min"
        if isha_minutes:
            self.params["isha"] = f"{isha_minutes} min"
        self.asr_factor = 1 if asr_method.lower() in {"standard", "shafi", "maliki", "hanbali"} else 2
        self.lat = 0.0
        self.lng = 0.0
        self.jdate = 0.0

    def get_times(self, day, coords, tz_hours):
        self.lat = coords.lat
        self.lng = coords.lng
        self.jdate = _julian_date(day.year, day.month, day.day) - self.lng / (15 * 24)
        times = {
            "imsak": 5,
            "fajr": 5,
            "sunrise": 6,
            "dhuhr": 12,
            "asr": 13,
            "sunset": 18,
            "maghrib": 18,
            "isha": 18,
            "midnight": 0
        }
        times = self._compute_times(times)
        times = self._adjust_times(times, tz_hours)
        return times

    def _mid_day(self, time):
        _, eqt = _sun_position(self.jdate + time)
        return _fix_hour(12 - eqt)

    def _sun_angle_time(self, angle, time, direction):
        decl, _ = _sun_position(self.jdate + time)
        noon = self._mid_day(time)
        numerator = -math.sin(_dtr(angle)) - math.sin(_dtr(decl)) * math.sin(_dtr(self.lat))
        denominator = math.cos(_dtr(decl)) * math.cos(_dtr(self.lat))
        x = _clamp(numerator / denominator, -1, 1)
        t = _rtd(math.acos(x)) / 15.0
        return noon - t if direction == "ccw" else noon + t

    def _asr_time(self, factor, time):
        decl, _ = _sun_position(self.jdate + time)
        angle = -_rtd(math.atan(1.0 / (factor + math.tan(abs(_dtr(self.lat - decl))))))
        return self._sun_angle_time(angle, time, "cw")

    def _rise_set_angle(self):
        return 0.833

    def _compute_times(self, times):
        times = {k: v / 24 for k, v in times.items()}
        imsak = self._sun_angle_time(self._get_param_angle("imsak"), times["imsak"], "ccw")
        fajr = self._sun_angle_time(self._get_param_angle("fajr"), times["fajr"], "ccw")
        sunrise = self._sun_angle_time(self._rise_set_angle(), times["sunrise"], "ccw")
        dhuhr = self._mid_day(times["dhuhr"])
        asr = self._asr_time(self.asr_factor, times["asr"])
        sunset = self._sun_angle_time(self._rise_set_angle(), times["sunset"], "cw")
        maghrib = self._sun_angle_time(self._get_param_angle("maghrib"), times["maghrib"], "cw")
        isha = self._sun_angle_time(self._get_param_angle("isha"), times["isha"], "cw")
        return {
            "imsak": imsak,
            "fajr": fajr,
            "sunrise": sunrise,
            "dhuhr": dhuhr,
            "asr": asr,
            "sunset": sunset,
            "maghrib": maghrib,
            "isha": isha,
            "midnight": 0
        }

    def _get_param_angle(self, key):
        val = self.params.get(key, 0)
        if isinstance(val, str) and "min" in val:
            return 0.0
        return float(val)

    def _get_param_minutes(self, key):
        val = self.params.get(key, 0)
        if isinstance(val, str) and "min" in val:
            return float(val.split()[0])
        return 0.0

    def _adjust_times(self, times, tz_hours):
        for key in list(times.keys()):
            times[key] = times[key] + tz_hours - self.lng / 15.0
        times["dhuhr"] += self.params.get("dhuhr", 0) / 60.0

        imsak_minutes = self._get_param_minutes("imsak")
        if imsak_minutes:
            times["imsak"] = times["fajr"] - imsak_minutes / 60.0

        maghrib_minutes = self._get_param_minutes("maghrib")
        if maghrib_minutes:
            times["maghrib"] = times["sunset"] + maghrib_minutes / 60.0

        isha_minutes = self._get_param_minutes("isha")
        if isha_minutes:
            times["isha"] = times["sunset"] + isha_minutes / 60.0

        times["midnight"] = self._compute_midnight(times)

        return {k: _fix_hour(v) for k, v in times.items()}

    def _compute_midnight(self, times):
        midnight_mode = self.params.get("midnight", "Standard")
        if midnight_mode == "Jafari":
            return times["sunset"] + self._time_diff(times["sunset"], times["fajr"]) / 2.0
        return times["sunset"] + self._time_diff(times["sunset"], times["sunrise"]) / 2.0

    def _time_diff(self, time1, time2):
        return _fix_hour(time2 - time1)


def _load_config(path):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_config(path, config):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def _get_timezone(tz_name):
    if tz_name and ZoneInfo:
        return ZoneInfo(tz_name)
    return datetime.now().astimezone().tzinfo


def _normalize_location_query(name, default_country):
    query = name.strip()
    if "-" in query and "," not in query:
        parts = [p.strip() for p in query.split("-") if p.strip()]
        if len(parts) >= 2:
            town = " ".join(parts[:-1])
            city = parts[-1]
            query = f"{town}, {city}"
            if default_country and default_country.lower() not in query.lower():
                query = f"{query}, {default_country}"
    return query


def _geocode_location(query):
    base = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
        "q": query
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "hyperland-prayertimes/1.0"}
    )
    with urllib.request.urlopen(req, timeout=6) as resp:
        data = json.load(resp)
    if not data:
        return None
    item = data[0]
    return {
        "lat": float(item["lat"]),
        "lng": float(item["lon"]),
        "label": item.get("display_name", query)
    }


def _tz_hours_for_day(day, tzinfo):
    dt = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tzinfo)
    offset = dt.utcoffset()
    return offset.total_seconds() / 3600.0 if offset else 0.0


def _float_to_time(value, tzinfo, day):
    hours = int(value)
    minutes = int((value - hours) * 60)
    seconds = int(round((value - hours - minutes / 60) * 3600))
    if seconds == 60:
        seconds = 0
        minutes += 1
    if minutes == 60:
        minutes = 0
        hours = (hours + 1) % 24
    return datetime(day.year, day.month, day.day, hours, minutes, seconds, tzinfo=tzinfo)


def _format_time(dt, format_24h):
    if format_24h:
        return dt.strftime("%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0")


def _format_countdown(delta):
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 0:
        total_minutes = 0
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}"
    return f"{minutes}m"


def _build_tooltip(times, tzinfo, day, method_name, asr_method, location_label, format_24h):
    lines = [f"{location_label} ({method_name}, Asr: {asr_method})"]
    order = [
        ("Fajr", "fajr"),
        ("Sunrise", "sunrise"),
        ("Dhuhr", "dhuhr"),
        ("Asr", "asr"),
        ("Maghrib", "maghrib"),
        ("Isha", "isha")
    ]
    for label, key in order:
        dt = _float_to_time(times[key], tzinfo, day)
        lines.append(f"{label} { _format_time(dt, format_24h)}")
    return "\n".join(lines)


def _next_prayer(now, tzinfo, today_times, tomorrow_times):
    today = now.date()
    prayer_map = {}
    for name, key in [("Fajr", "fajr"), ("Dhuhr", "dhuhr"), ("Asr", "asr"), ("Maghrib", "maghrib"), ("Isha", "isha")]:
        prayer_map[name] = _float_to_time(today_times[key], tzinfo, today)
    for name in PRAYER_ORDER:
        dt = prayer_map[name]
        if now < dt:
            return name, dt
    tomorrow = today + timedelta(days=1)
    return "Fajr", _float_to_time(tomorrow_times["fajr"], tzinfo, tomorrow)


def _apply_adjustments(times, adjustments):
    adjusted = dict(times)
    for key, minutes in adjustments.items():
        if key in adjusted:
            adjusted[key] += minutes / 60.0
    return adjusted


def _resolve_location(config, location_key, persist):
    locations = config.get("locations", {})
    loc = locations.get(location_key, {})

    if "lat" in loc and "lng" in loc:
        return location_key, loc, False

    query = loc.get("query") or location_key
    default_country = config.get("default_country")
    query = _normalize_location_query(query, default_country)
    if "," not in query and default_country:
        query_algeria = f"{query}, {default_country}"
    else:
        query_algeria = query

    result = _geocode_location(query_algeria)
    if not result and query_algeria != query:
        result = _geocode_location(query)
    if not result:
        raise ValueError(f"Location not found: {location_key}")

    loc = {
        "lat": result["lat"],
        "lng": result["lng"],
        "tz": loc.get("tz") or config.get("default_tz"),
        "label": result["label"],
        "query": query
    }
    if persist:
        locations[location_key] = loc
        config["locations"] = locations
    return location_key, loc, True


def _render_waybar(config):
    location_key = config.get("location")
    location_key, loc, updated = _resolve_location(config, location_key, persist=False)
    coords = Coordinates(lat=loc["lat"], lng=loc["lng"])
    tzinfo = _get_timezone(loc.get("tz"))
    today = datetime.now(tzinfo).date()
    tz_hours_today = _tz_hours_for_day(today, tzinfo)

    method_key = config.get("method", "Egyptian")
    asr_method = config.get("asr_method", "Standard")
    imsak = config.get("imsak_minutes", 10)
    dhuhr = config.get("dhuhr_minutes", 0)
    maghrib = config.get("maghrib_minutes", 0)
    isha = config.get("isha_minutes", 0)

    pray = PrayTimes(method_key, asr_method, imsak, dhuhr, maghrib, isha)
    times_today = pray.get_times(today, coords, tz_hours_today)
    times_today = _apply_adjustments(times_today, config.get("adjustments", {}))

    tomorrow = today + timedelta(days=1)
    tz_hours_tomorrow = _tz_hours_for_day(tomorrow, tzinfo)
    times_tomorrow = pray.get_times(tomorrow, coords, tz_hours_tomorrow)
    times_tomorrow = _apply_adjustments(times_tomorrow, config.get("adjustments", {}))

    now = datetime.now(tzinfo)
    next_name, next_dt = _next_prayer(now, tzinfo, times_today, times_tomorrow)
    countdown = _format_countdown(next_dt - now)

    format_24h = config.get("time_format", "24h") == "24h"
    next_time = _format_time(next_dt, format_24h)

    display_format = config.get("display", {}).get("format", "{next_name} {next_time} - {countdown}")
    text = display_format.format(next_name=next_name, next_time=next_time, countdown=countdown)

    location_label = loc.get("label") or location_key
    tooltip = _build_tooltip(
        times_today,
        tzinfo,
        today,
        METHODS[method_key]["name"],
        asr_method,
        location_label,
        format_24h,
    )

    payload = {
        "text": text,
        "tooltip": tooltip,
        "class": "prayertimes"
    }
    print(json.dumps(payload, ensure_ascii=True))


def _handle_cli(args):
    config = _load_config(CONFIG_PATH)

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
        _resolve_location(config, location_key, persist=True)
        config["location"] = location_key
        _save_config(CONFIG_PATH, config)
        return 0

    if args.set_method:
        if args.set_method not in METHODS:
            raise ValueError(f"Unknown method: {args.set_method}")
        config["method"] = args.set_method
        _save_config(CONFIG_PATH, config)
        return 0

    if args.set_offset:
        prayer, minutes = args.set_offset
        prayer_key = prayer.lower()
        if prayer_key not in config.get("adjustments", {}):
            raise ValueError(f"Unknown prayer for offset: {prayer}")
        config["adjustments"][prayer_key] = int(minutes)
        _save_config(CONFIG_PATH, config)
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
            _save_config(CONFIG_PATH, config)
            return 0
        config.setdefault("locations", {})[args.set_location] = {
            "query": args.set_location,
            "tz": args.tz or config.get("default_tz")
        }
        _resolve_location(config, args.set_location, persist=True)
        config["location"] = args.set_location
        _save_config(CONFIG_PATH, config)
        return 0

    if args.waybar:
        _render_waybar(config)
        return 0

    return 0


def main():
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

    args = parser.parse_args()

    try:
        return _handle_cli(args)
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


if __name__ == "__main__":
    raise SystemExit(main())
