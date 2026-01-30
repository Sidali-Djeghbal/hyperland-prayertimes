import json
import re

_LATIN_RE = re.compile(r"[A-Za-z]")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
_TIFINAGH_RE = re.compile(r"[\u2D30-\u2D7F]")
_DIGIT_RE = re.compile(r"[0-9]")


def clean_label(label):
    parts = [p.strip() for p in label.split(",") if p.strip()]
    kept = []
    for part in parts:
        if _TIFINAGH_RE.search(part):
            continue
        has_latin = _LATIN_RE.search(part) is not None
        has_arabic = _ARABIC_RE.search(part) is not None
        has_digit = _DIGIT_RE.search(part) is not None
        if not (has_latin or has_arabic):
            continue
        if has_digit and not (has_latin or has_arabic):
            continue
        kept.append(part)
    return ", ".join(kept) if kept else label

import urllib.parse
import urllib.request


def fetch_json(url, timeout=6):
    req = urllib.request.Request(url, headers={"User-Agent": "hyperland-prayertimes/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def auto_detect_location(config):
    providers = [
        "https://ipapi.co/json/",
        "https://ipinfo.io/json"
    ]
    data = None
    for url in providers:
        try:
            data = fetch_json(url)
            if data:
                break
        except Exception:
            continue
    if not data:
        raise ValueError("Unable to auto-detect location (network or provider error)")

    city = data.get("city") or "Auto"
    region = data.get("region") or data.get("regionName")
    country = data.get("country_name") or data.get("country")
    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is None or lon is None:
        loc = data.get("loc")
        if loc and "," in loc:
            lat_str, lon_str = loc.split(",", 1)
            lat, lon = float(lat_str), float(lon_str)

    if lat is None or lon is None:
        raise ValueError("Auto-detect failed to resolve coordinates")

    label_parts = [p for p in [city, region, country] if p]
    label = ", ".join(label_parts) if label_parts else city
    label = clean_label(label)

    location_key = city or "Auto"
    config.setdefault("locations", {})[location_key] = {
        "lat": float(lat),
        "lng": float(lon),
        "tz": data.get("timezone") or config.get("default_tz"),
        "label": label
    }
    config["location"] = location_key
    return location_key, config["locations"][location_key]


def normalize_location_query(name, default_country):
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


def geocode_location(query):
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
        "label": clean_label(item.get("display_name", query))
    }


def resolve_location(config, location_key, persist):
    locations = config.get("locations", {})
    loc = locations.get(location_key, {})

    if "lat" in loc and "lng" in loc:
        return location_key, loc, False

    query = loc.get("query") or location_key
    default_country = config.get("default_country")
    query = normalize_location_query(query, default_country)
    if "," not in query and default_country:
        query_default = f"{query}, {default_country}"
    else:
        query_default = query

    result = geocode_location(query_default)
    if not result and query_default != query:
        result = geocode_location(query)
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
