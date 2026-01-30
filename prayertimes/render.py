from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

from .calc import Coordinates, PrayTimes
from .geo import auto_detect_location, resolve_location
from .methods import METHODS, PRAYER_ORDER
from .config import save_config, CONFIG_PATH


def get_timezone(tz_name):
    if tz_name and ZoneInfo:
        return ZoneInfo(tz_name)
    return datetime.now().astimezone().tzinfo


def tz_hours_for_day(day, tzinfo):
    dt = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=tzinfo)
    offset = dt.utcoffset()
    return offset.total_seconds() / 3600.0 if offset else 0.0


def float_to_time(value, tzinfo, day):
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


def format_time(dt, format_24h):
    if format_24h:
        return dt.strftime("%H:%M")
    return dt.strftime("%I:%M %p").lstrip("0")


def format_countdown(delta):
    total_minutes = int(delta.total_seconds() // 60)
    if total_minutes < 0:
        total_minutes = 0
    hours, minutes = divmod(total_minutes, 60)
    if hours > 0:
        return f"{hours}h{minutes:02d}"
    return f"{minutes}m"


def build_tooltip(times, tzinfo, day, method_name, asr_method, location_label, format_24h):
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
        dt = float_to_time(times[key], tzinfo, day)
        lines.append(f"{label} {format_time(dt, format_24h)}")
    return "\n".join(lines)


def next_prayer(now, tzinfo, today_times, tomorrow_times):
    today = now.date()
    prayer_map = {}
    for name, key in [
        ("Fajr", "fajr"),
        ("Dhuhr", "dhuhr"),
        ("Asr", "asr"),
        ("Maghrib", "maghrib"),
        ("Isha", "isha")
    ]:
        prayer_map[name] = float_to_time(today_times[key], tzinfo, today)
    for name in PRAYER_ORDER:
        dt = prayer_map[name]
        if now < dt:
            return name, dt
    tomorrow = today + timedelta(days=1)
    return "Fajr", float_to_time(tomorrow_times["fajr"], tzinfo, tomorrow)


def apply_adjustments(times, adjustments):
    adjusted = dict(times)
    for key, minutes in adjustments.items():
        if key in adjusted:
            adjusted[key] += minutes / 60.0
    return adjusted


def render_waybar(config):
    location_key = config.get("location")
    if not location_key or location_key == "Auto":
        location_key, loc = auto_detect_location(config)
        save_config(config, CONFIG_PATH)
    else:
        location_key, loc, _updated = resolve_location(config, location_key, persist=False)

    coords = Coordinates(lat=loc["lat"], lng=loc["lng"])
    tzinfo = get_timezone(loc.get("tz"))
    today = datetime.now(tzinfo).date()
    tz_hours_today = tz_hours_for_day(today, tzinfo)

    method_key = config.get("method", "Egyptian")
    asr_method = config.get("asr_method", "Standard")
    imsak = config.get("imsak_minutes", 10)
    dhuhr = config.get("dhuhr_minutes", 0)
    maghrib = config.get("maghrib_minutes", 0)
    isha = config.get("isha_minutes", 0)

    pray = PrayTimes(method_key, asr_method, imsak, dhuhr, maghrib, isha)
    times_today = pray.get_times(today, coords, tz_hours_today)
    times_today = apply_adjustments(times_today, config.get("adjustments", {}))

    tomorrow = today + timedelta(days=1)
    tz_hours_tomorrow = tz_hours_for_day(tomorrow, tzinfo)
    times_tomorrow = pray.get_times(tomorrow, coords, tz_hours_tomorrow)
    times_tomorrow = apply_adjustments(times_tomorrow, config.get("adjustments", {}))

    now = datetime.now(tzinfo)
    next_name, next_dt = next_prayer(now, tzinfo, times_today, times_tomorrow)
    countdown = format_countdown(next_dt - now)

    format_24h = config.get("time_format", "24h") == "24h"
    next_time = format_time(next_dt, format_24h)

    display_format = config.get("display", {}).get("format", "{next_name} {next_time} - {countdown}")
    text = display_format.format(next_name=next_name, next_time=next_time, countdown=countdown)

    location_label = loc.get("label") or location_key
    tooltip = build_tooltip(
        times_today,
        tzinfo,
        today,
        METHODS[method_key]["name"],
        asr_method,
        location_label,
        format_24h,
    )

    return {
        "text": text,
        "tooltip": tooltip,
        "class": "prayertimes"
    }
