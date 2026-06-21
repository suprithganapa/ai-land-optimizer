"""
amenity_scorer.py
Query OSM Overpass API for nearby schools, hospitals, bus stops, metro, markets.
Returns a walkability / connectivity score and distances.
"""
import math
import requests

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

AMENITY_TYPES = {
    "school":    {"query_key": "amenity", "value": "school",       "label": "School",       "icon": "🏫", "weight": 20},
    "hospital":  {"query_key": "amenity", "value": "hospital",     "label": "Hospital",     "icon": "🏥", "weight": 20},
    "bus_stop":  {"query_key": "highway", "value": "bus_stop",     "label": "Bus Stop",     "icon": "🚌", "weight": 15},
    "metro":     {"query_key": "station", "value": "subway",       "label": "Metro Station","icon": "🚇", "weight": 25},
    "market":    {"query_key": "amenity", "value": "marketplace",  "label": "Market",       "icon": "🛒", "weight": 10},
    "park":      {"query_key": "leisure", "value": "park",         "label": "Public Park",  "icon": "🌳", "weight": 10},
}

DISTANCE_SCORES = {
    "excellent": (0,    500,  100),
    "good":      (500,  1000, 80),
    "average":   (1000, 2000, 60),
    "far":       (2000, 4000, 35),
    "very_far":  (4000, 9999, 10),
}


def _haversine_m(lat1, lng1, lat2, lng2) -> float:
    R    = 6371000
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a    = (math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _dist_score(dist_m: float) -> int:
    for label, (lo, hi, score) in DISTANCE_SCORES.items():
        if lo <= dist_m < hi:
            return score
    return 5


def query_amenities(lat: float, lng: float, radius_m: int = 2000) -> dict:
    """Query OSM for social amenities near (lat, lng). Returns structured results."""
    results   = {}
    weighted  = 0
    max_score = 0

    for key, cfg in AMENITY_TYPES.items():
        qk  = cfg["query_key"]
        val = cfg["value"]
        query = f"""
        [out:json][timeout:8];
        (
          node["{qk}"="{val}"](around:{radius_m},{lat},{lng});
          way["{qk}"="{val}"](around:{radius_m},{lat},{lng});
        );
        out center 5;
        """
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=8)
            if r.status_code != 200:
                continue
            elements = r.json().get("elements", [])
            found = []
            for el in elements[:5]:
                el_lat = el.get("lat") or el.get("center", {}).get("lat")
                el_lng = el.get("lon") or el.get("center", {}).get("lon")
                name   = el.get("tags", {}).get("name", cfg["label"])
                if el_lat and el_lng:
                    dist = _haversine_m(lat, lng, el_lat, el_lng)
                    found.append({
                        "name":     name,
                        "dist_m":   round(dist),
                        "dist_km":  round(dist / 1000, 2),
                        "lat":      el_lat,
                        "lng":      el_lng,
                    })
            found.sort(key=lambda x: x["dist_m"])
            nearest_dist = found[0]["dist_m"] if found else radius_m + 1
            score        = _dist_score(nearest_dist) if found else 0
            weighted     += score * cfg["weight"]
            max_score    += 100  * cfg["weight"]
            results[key]  = {
                "label":       cfg["label"],
                "icon":        cfg["icon"],
                "count":       len(found),
                "nearest_m":   found[0]["dist_m"] if found else None,
                "nearest_km":  found[0]["dist_km"] if found else None,
                "nearest_name": found[0]["name"] if found else None,
                "items":       found[:3],
                "score":       score,
            }
        except Exception as e:
            print(f"  Amenity query ({key}) failed: {e}")
            results[key] = {
                "label": cfg["label"], "icon": cfg["icon"],
                "count": 0, "nearest_m": None, "nearest_km": None,
                "nearest_name": None, "items": [], "score": 0,
            }

    overall = round(weighted / max_score * 100) if max_score > 0 else 50

    # Grade
    if   overall >= 80: grade, color = "Excellent",    "#3ecf8e"
    elif overall >= 60: grade, color = "Good",         "#4f9cf9"
    elif overall >= 40: grade, color = "Average",      "#f59e0b"
    else:               grade, color = "Poor",         "#f87171"

    print(f"  🏙️  Amenity score: {overall}/100 ({grade})")

    return {
        "amenities":     results,
        "overall_score": overall,
        "grade":         grade,
        "grade_color":   color,
        "radius_m":      radius_m,
    }
