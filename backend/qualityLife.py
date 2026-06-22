import time
import requests

# ============================================================
# CONFIGURATION
# ============================================================

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OPEN_METEO_AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
SEARCH_RADIUS_M = 3000

CRITERIA_WEIGHTS = {
    "schools": 20,
    "hospitals": 20,
    "commerce": 15,
    "parks": 15,
    "air": 20,
    "transport": 10,
}

# One tag per query — split into individual requests to avoid 406 errors
OVERPASS_TAGS = {
    "schools": [
        '["amenity"="school"]',
        '["amenity"="university"]',
        '["amenity"="college"]',
        '["amenity"="kindergarten"]',
    ],
    "hospitals": [
        '["amenity"="hospital"]',
        '["amenity"="clinic"]',
        '["amenity"="pharmacy"]',
        '["amenity"="doctors"]',
    ],
    "commerce": [
        '["shop"="supermarket"]',
        '["shop"="bakery"]',
        '["shop"="mall"]',
        '["shop"="convenience"]',
        '["amenity"="marketplace"]',
        '["amenity"="bank"]',
        '["amenity"="restaurant"]',
        '["amenity"="cafe"]',
    ],
    "parks": [
        '["leisure"="park"]',
        '["leisure"="garden"]',
        '["leisure"="playground"]',
        '["natural"="wood"]',
    ],
    "transport": [
        '["highway"="bus_stop"]',
        '["railway"="station"]',
        '["railway"="tram_stop"]',
        '["amenity"="ferry_terminal"]',
        '["amenity"="bus_station"]',
    ],
}

AQI_THRESHOLDS = [
    (5, 100),
    (15, 85),
    (25, 65),
    (35, 40),
    (50, 20),
    (999, 5),
]

POI_SCORING = {
    "schools": [(0, 0), (1, 40), (2, 65), (3, 85), (5, 100)],
    "hospitals": [(0, 0), (1, 50), (2, 75), (3, 90), (5, 100)],
    "commerce": [(0, 0), (1, 35), (3, 60), (5, 85), (8, 100)],
    "parks": [(0, 0), (1, 40), (2, 65), (3, 85), (4, 100)],
    "transport": [(0, 0), (1, 40), (2, 65), (4, 85), (6, 100)],
}

# ============================================================
# NOMINATIM GEOCODING
# ============================================================


def geocode_address(address: str):
    try:
        headers = {"User-Agent": "PropIQ-QualityOfLife/1.1"}
        params = {"q": address, "format": "json", "limit": 1, "addressdetails": 1}
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        return {
            "lat": float(data[0]["lat"]),
            "lon": float(data[0]["lon"]),
            "display_name": data[0].get("display_name", address),
        }
    except Exception as e:
        print(f"Geocoding error: {e}")
        return None


# ============================================================
# OVERPASS — ONE TAG PER REQUEST (fixes 406)
# ============================================================

def _overpass_single_tag(lat: float, lon: float, tag: str, radius: int, server: str) -> list:
    """
    Send ONE tag per request as raw POST body (not JSON), which all Overpass
    servers accept.  Using data= with a dict triggers multipart/form-data on
    some servers → 406.  Sending data= as a plain string forces
    application/x-www-form-urlencoded which is universally supported.
    """
    query = (
        f"[out:json][timeout:30];"
        f"("
        f"  node{tag}(around:{radius},{lat},{lon});"
        f"  way{tag}(around:{radius},{lat},{lon});"
        f"  relation{tag}(around:{radius},{lat},{lon});"
        f");out center;"
    )
    # IMPORTANT: send as raw string, not dict — avoids multipart/form-data → 406
    payload = "data=" + requests.utils.quote(query)
    resp = requests.post(
        server,
        data=payload,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": "PropIQ-QualityOfLife/1.1",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("elements", [])


def _overpass_query(lat: float, lon: float, tags: list, radius: int = SEARCH_RADIUS_M) -> list:
    """
    Fire one request per tag, cycling through servers on failure.
    Deduplicates by element ID.
    """
    all_elements: list = []
    seen_ids: set = set()

    for tag in tags:
        fetched = False
        for server in OVERPASS_SERVERS:
            try:
                elements = _overpass_single_tag(lat, lon, tag, radius, server)
                for el in elements:
                    eid = el.get("id")
                    if eid not in seen_ids:
                        seen_ids.add(eid)
                        all_elements.append(el)
                fetched = True
                break                          # success — move to next tag
            except Exception:
                # Silent — no noise in production logs
                pass

        if not fetched:
            pass  # all servers failed for this tag — skip silently

        time.sleep(0.25)   # polite rate limit

    return all_elements


# ============================================================
# POI FETCHING
# ============================================================

def fetch_pois(lat: float, lon: float):
    results = {}
    for criterion, tags in OVERPASS_TAGS.items():
        elements = _overpass_query(lat, lon, tags)
        seen, items = set(), []
        for el in elements:
            eid = el.get("id")
            if eid in seen:
                continue
            seen.add(eid)
            center = el.get("center", {})
            el_lat = el.get("lat") or center.get("lat")
            el_lon = el.get("lon") or center.get("lon")
            if el_lat is None or el_lon is None:
                continue
            items.append({
                "id": eid,
                "name": el.get("tags", {}).get("name", "Unknown"),
                "lat": el_lat,
                "lon": el_lon,
            })
        results[criterion] = items
        print(f"[QoL] {criterion}: {len(items)} POIs found")
        time.sleep(0.25)
    return results


# ============================================================
# AIR QUALITY
# ============================================================

def fetch_air_quality(lat: float, lon: float):
    try:
        params = {
            "latitude": lat,
            "longitude": lon,
            "current": "pm2_5,pm10,us_aqi",
            "timezone": "auto",
        }
        resp = requests.get(OPEN_METEO_AIR_URL, params=params, timeout=10)
        resp.raise_for_status()
        current = resp.json().get("current", {})

        pm25 = current.get("pm2_5")
        pm10 = current.get("pm10")
        us_aqi = current.get("us_aqi")

        value = pm25 if pm25 is not None else pm10
        parameter = "pm2.5" if pm25 is not None else "pm10"

        if value is None:
            return None

        print(f"[QoL] Air quality: {parameter.upper()} = {value} µg/m³ | US AQI = {us_aqi}")
        return {
            "aqi_value": float(value),
            "parameter": parameter,
            "unit": "µg/m³",
            "us_aqi": us_aqi,
            "station": "Open-Meteo (CAMS European forecast)",
            "distance": 0,
        }
    except Exception as e:
        print(f"Air quality error: {e}")
        return None


# ============================================================
# SCORING
# ============================================================

def _score_from_count(criterion: str, count: int) -> int:
    thresholds = POI_SCORING.get(criterion, [(0, 0), (1, 50), (3, 100)])
    score = 0
    for min_count, s in thresholds:
        if count >= min_count:
            score = s
    return score


def _score_air(aqi_value: float) -> int:
    for threshold, score in AQI_THRESHOLDS:
        if aqi_value <= threshold:
            return score
    return 5


def calculate_quality_score(pois: dict, air_data) -> dict:
    breakdown = {}

    for criterion in ["schools", "hospitals", "commerce", "parks", "transport"]:
        count = len(pois.get(criterion, []))
        breakdown[criterion] = {
            "count": count,
            "score": _score_from_count(criterion, count),
            "weight": CRITERIA_WEIGHTS[criterion],
            "items": pois.get(criterion, [])[:5],
        }

    if air_data and air_data.get("aqi_value") is not None:
        breakdown["air"] = {
            "score": _score_air(air_data["aqi_value"]),
            "weight": CRITERIA_WEIGHTS["air"],
            "aqi_value": air_data["aqi_value"],
            "parameter": air_data.get("parameter", "PM2.5"),
            "unit": air_data.get("unit", "µg/m³"),
            "us_aqi": air_data.get("us_aqi"),
            "station": air_data.get("station", "Open-Meteo"),
            "distance": air_data.get("distance", 0),
        }
    else:
        breakdown["air"] = {
            "score": 50,
            "weight": CRITERIA_WEIGHTS["air"],
            "aqi_value": None,
            "note": "Air quality data unavailable — neutral score applied.",
        }

    total = round(sum(v["score"] * v["weight"] / 100 for v in breakdown.values()))

    if total >= 75:
        recommendation = "buy"
        verdict_text = "Excellent quality of life. Highly recommended for purchase."
        verdict_color = "#2dce89"
    elif total >= 55:
        recommendation = "neutral"
        verdict_text = "Good quality of life with minor considerations."
        verdict_color = "#c9a84c"
    elif total >= 35:
        recommendation = "caution"
        verdict_text = "Moderate quality of life. Investigate further before buying."
        verdict_color = "#fb6340"
    else:
        recommendation = "avoid"
        verdict_text = "Low quality of life score. Purchase not recommended."
        verdict_color = "#f5365c"

    return {
        "total": total,
        "breakdown": breakdown,
        "recommendation": recommendation,
        "verdict_text": verdict_text,
        "verdict_color": verdict_color,
    }


# ============================================================
# MAIN
# ============================================================

def analyze_address(address: str):
    print(f"Analyzing address: {address}")
    location = geocode_address(address)
    if not location:
        print("Failed to geocode address.")
        return None

    pois = fetch_pois(location["lat"], location["lon"])
    air = fetch_air_quality(location["lat"], location["lon"])
    score = calculate_quality_score(pois, air)

    score["address"] = location["display_name"]
    score["lat"] = location["lat"]
    score["lon"] = location["lon"]
    return score


if __name__ == "__main__":
    address = "Rua José Adelino dos Santos 2B, Setúbal, Portugal"
    result = analyze_address(address)
    import pprint
    pprint.pprint(result)
