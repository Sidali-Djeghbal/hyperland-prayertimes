import math
from dataclasses import dataclass

from .methods import METHODS


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


@dataclass
class Coordinates:
    lat: float
    lng: float


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
