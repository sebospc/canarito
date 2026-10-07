"""Quake catalogs and the missed-quake check.

Every catalog turns its feed into the same event: {"id", "source", "time" (epoch s), "lat",
"lon", "mag"}. To add a national catalog, write one fetch function and add it to CATALOGS
with the area it covers; receptors inside that area use it on their own.
"""
import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# Google's alert radius by its own magnitude estimate, measured on 1,279 real alerts
# (Allen et al. 2025). Below M4.5 Google does not alert.
RADIUS_KM = {
    4.5: 31, 4.6: 37, 4.7: 45, 4.8: 53, 4.9: 64, 5.0: 78, 5.1: 94, 5.2: 113,
    5.3: 136, 5.4: 164, 5.5: 197, 5.6: 236, 5.7: 279, 5.8: 310, 5.9: 328,
    6.0: 346, 6.1: 367, 6.2: 385, 6.3: 405, 6.4: 424, 6.5: 443, 6.6: 462,
    6.7: 472, 6.8: 499, 7.7: 645, 7.8: 669,
}
# Google's magnitude differs from the catalogs' by tenths (an SGC M3.6 came as M4.46), so a
# quake that only reaches the receptor with this much more magnitude is "possibly missed".
MAGNITUDE_SLACK = 0.5
QUERY_RADIUS_KM = 700
QUERY_MIN_MAG = 3.5
# Catalogs publish minutes after a quake; the alert itself comes within a minute.
SETTLE_S = 10 * 60
LOOK_BACK_S = 24 * 3600
# Two catalogs reporting one quake.
SAME_QUAKE_S = 60
SAME_QUAKE_KM = 100
# An alert belongs to a quake when it was captured this soon after it.
ALERT_WINDOW_S = (-60, 10 * 60)


def radius_km(mag):
    if mag is None or mag < 4.5:
        return 0.0
    keys = sorted(RADIUS_KM)
    if mag >= keys[-1]:
        return float(RADIUS_KM[keys[-1]])
    low = max(k for k in keys if k <= mag)
    high = min(k for k in keys if k >= mag)
    if low == high:
        return float(RADIUS_KM[low])
    return RADIUS_KM[low] + (mag - low) / (high - low) * (RADIUS_KM[high] - RADIUS_KM[low])


def km_between(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def fetch_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "canarito"}),
                                timeout=20) as response:
        return json.load(response)


def usgs(lat, lon, since):
    feed = fetch_json("https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode({
        "format": "geojson", "starttime": since.strftime("%Y-%m-%dT%H:%M:%S"), "minmagnitude": QUERY_MIN_MAG,
        "latitude": lat, "longitude": lon, "maxradiuskm": QUERY_RADIUS_KM}))
    return [{"id": f["id"], "source": "USGS", "time": f["properties"]["time"] / 1000,
             "lat": f["geometry"]["coordinates"][1], "lon": f["geometry"]["coordinates"][0],
             "mag": f["properties"].get("mag")} for f in feed.get("features", [])]


def emsc(lat, lon, since):
    feed = fetch_json("https://www.seismicportal.eu/fdsnws/event/1/query?" + urllib.parse.urlencode({
        "format": "json", "starttime": since.strftime("%Y-%m-%dT%H:%M:%S"), "minmag": QUERY_MIN_MAG,
        "lat": lat, "lon": lon, "maxradius": round(QUERY_RADIUS_KM / 111.2, 2)}))
    return [{"id": f["id"], "source": "EMSC",
             "time": datetime.fromisoformat(f["properties"]["time"].replace("Z", "+00:00")).timestamp(),
             "lat": f["properties"]["lat"], "lon": f["properties"]["lon"], "mag": f["properties"].get("mag")}
            for f in feed.get("features", [])]


def sgc(lat, lon, since):
    """Servicio Geológico Colombiano. USGS misses many small Colombian quakes (it never listed
    the M4.5 of 23-Sep-2026 that reached our emulator). Dates are Bogotá time, 14 days at most."""
    bogota = timezone(timedelta(hours=-5))
    feed = fetch_json("https://api.sgc.gov.co/biweekly/biweekly_earthquakes?" + urllib.parse.urlencode({
        "startdate": since.astimezone(bogota).strftime("%Y-%m-%dT00:00:00"),
        "enddate": datetime.now(bogota).strftime("%Y-%m-%dT23:59:59")}))
    # Failures come back as HTTP 200 with an "error" object; an empty list would read as "no quakes".
    if "error" in feed:
        raise ValueError(f"SGC error: {feed['error']}")
    events = []
    for f in feed.get("features", []):
        props = f["properties"]
        if props.get("agency") != "SGC" or props.get("type", "earthquake") != "earthquake":
            continue
        when = datetime.strptime(props["utcTime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        event_lon, event_lat = f["geometry"]["coordinates"][:2]
        events.append({"id": f["id"], "source": "SGC", "time": when.timestamp(),
                       "lat": event_lat, "lon": event_lon, "mag": props.get("mag")})
    return events


# name: (fetch, area as (min lat, max lat, min lon, max lon), or None for the whole world)
CATALOGS = {
    "usgs": (usgs, None),
    "emsc": (emsc, None),
    "sgc": (sgc, (-4.3, 13.6, -82.0, -66.8)),
}


def catalogs_for(lat, lon):
    return [name for name, (_, area) in CATALOGS.items()
            if area is None or (area[0] <= lat <= area[1] and area[2] <= lon <= area[3])]


def fetch_events(lat, lon, names, now_s):
    """Events from every catalog that answered, and the names of those that did not."""
    since = datetime.fromtimestamp(now_s - LOOK_BACK_S, timezone.utc)
    events, failed = [], []
    for name in names:
        try:
            events.extend(CATALOGS[name][0](lat, lon, since))
        except (OSError, ValueError, KeyError) as error:
            failed.append(f"{name}: {error}")
    return events, failed


def merge(events):
    """One entry per quake. The larger magnitude wins, which expects more of the receptor."""
    merged = []
    for event in sorted(events, key=lambda e: e["time"]):
        twin = next((m for m in merged if abs(m["time"] - event["time"]) <= SAME_QUAKE_S
                     and km_between(m["lat"], m["lon"], event["lat"], event["lon"]) <= SAME_QUAKE_KM), None)
        if twin is None:
            merged.append({**event, "sources": [event["source"]], "key": f"{event['source']}:{event['id']}"})
        else:
            twin["sources"].append(event["source"])
            twin["mag"] = max(twin["mag"] or 0, event["mag"] or 0)
    return merged


def missed(events, lat, lon, alert_times, late_times, now_s, reported):
    """Quakes this receptor should have alerted on and did not: (event, km, verdict) with verdict
    "missed" inside the radius of the catalog magnitude, "possibly" only inside the radius of
    magnitude + MAGNITUDE_SLACK, "late" when only Google's later notice arrived. Every quake judged,
    alerted or not, goes into `reported` (key -> quake time) so it is judged once."""
    findings = []
    for event in merge(events):
        if event["key"] in reported or not SETTLE_S <= now_s - event["time"] <= LOOK_BACK_S:
            continue
        km = km_between(lat, lon, event["lat"], event["lon"])
        if km > radius_km((event["mag"] or 0) + MAGNITUDE_SLACK):
            continue
        reported[event["key"]] = event["time"]
        def near(times):
            return any(ALERT_WINDOW_S[0] <= t - event["time"] <= ALERT_WINDOW_S[1] for t in times)
        if near(alert_times):
            continue
        if near(late_times):
            findings.append((event, km, "late"))
        else:
            findings.append((event, km, "missed" if km <= radius_km(event["mag"]) else "possibly"))
    return findings
