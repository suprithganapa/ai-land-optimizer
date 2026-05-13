import requests

OVERPASS_URL = "http://overpass-api.de/api/interpreter"

ZONE_RULES = {
    "residential":       {"buildable": True,  "label": "Residential Zone",   "color": "#3ecf8e"},
    "commercial":        {"buildable": True,  "label": "Commercial Zone",     "color": "#4f9cf9"},
    "industrial":        {"buildable": True,  "label": "Industrial Zone",     "color": "#f59e0b"},
    "retail":            {"buildable": True,  "label": "Retail Zone",         "color": "#4f9cf9"},
    "construction":      {"buildable": True,  "label": "Under Construction",  "color": "#f59e0b"},
    "meadow":            {"buildable": True,  "label": "Open Meadow",         "color": "#3ecf8e"},
    "grass":             {"buildable": True,  "label": "Grassland",           "color": "#3ecf8e"},
    "recreation_ground": {"buildable": True,  "label": "Recreation Ground",   "color": "#f59e0b"},
    "farmland":          {"buildable": False, "label": "Agricultural Land",   "color": "#f87171"},
    "farm":              {"buildable": False, "label": "Agricultural Land",   "color": "#f87171"},
    "forest":            {"buildable": False, "label": "Protected Forest",    "color": "#f87171"},
    "wood":              {"buildable": False, "label": "Forest / Wood Area",  "color": "#f87171"},
    "nature_reserve":    {"buildable": False, "label": "Nature Reserve",      "color": "#f87171"},
    "water":             {"buildable": False, "label": "Water Body",          "color": "#f87171"},
    "wetland":           {"buildable": False, "label": "Protected Wetland",   "color": "#f87171"},
    "park":              {"buildable": False, "label": "Public Park",         "color": "#f87171"},
    "village_green":     {"buildable": False, "label": "Village Green",       "color": "#f87171"},
    "military":          {"buildable": False, "label": "Military Zone",       "color": "#f87171"},
    "cemetery":          {"buildable": False, "label": "Cemetery",            "color": "#f87171"},
    "allotments":        {"buildable": False, "label": "Allotment Gardens",   "color": "#f87171"},
    "orchard":           {"buildable": False, "label": "Orchard / Farmland",  "color": "#f87171"},
}

BUILDING_LABELS = {
    "yes":         "Building",
    "residential": "Residential Building",
    "commercial":  "Commercial Building",
    "industrial":  "Industrial Structure",
    "office":      "Office Building",
    "retail":      "Retail Store",
    "school":      "School",
    "hospital":    "Hospital",
    "stadium":     "Stadium",
    "warehouse":   "Warehouse",
    "apartments":  "Apartment Block",
    "hotel":       "Hotel",
    "college":     "College / University",
    "church":      "Place of Worship",
    "mosque":      "Mosque",
    "temple":      "Temple",
}


def check_zoning(lat: float, lng: float, radius_m: float = 200) -> dict:
    query = f"""
    [out:json][timeout:10];
    (
      way["landuse"](around:{radius_m},{lat},{lng});
      relation["landuse"](around:{radius_m},{lat},{lng});
      way["natural"](around:{radius_m},{lat},{lng});
      way["leisure"](around:{radius_m},{lat},{lng});
    );
    out body;
    """
    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, timeout=10)
        if r.status_code == 200:
            for el in r.json().get("elements", []):
                tags = el.get("tags", {})
                key  = tags.get("landuse") or tags.get("natural") or tags.get("leisure")
                if key and key in ZONE_RULES:
                    rule = ZONE_RULES[key]
                    return {
                        "zone_type":    key,
                        "zone_label":   rule["label"],
                        "is_buildable": rule["buildable"],
                        "zone_color":   rule["color"],
                        "source":       "OpenStreetMap",
                    }
    except Exception as e:
        print(f"Zoning error: {e}")
    return _default_zone()


def _default_zone():
    return {
        "zone_type":    "residential",
        "zone_label":   "Residential Zone",
        "is_buildable": True,
        "zone_color":   "#3ecf8e",
        "source":       "Default",
    }


def get_elevation(lat: float, lng: float) -> dict:
    try:
        r = requests.get(
            f"https://api.open-elevation.com/api/v1/lookup?locations={lat},{lng}",
            timeout=8,
        )
        if r.status_code == 200:
            elev = r.json()["results"][0]["elevation"]
            return {"elevation_m": elev, "source": "Open-Elevation"}
    except Exception as e:
        print(f"Elevation error: {e}")
    return {"elevation_m": 800, "source": "Default (Bengaluru avg)"}


def check_buildings_on_land(lat: float, lng: float, radius_m: float = 100) -> dict:
    query = f"""
    [out:json][timeout:10];
    (
      way["building"](around:{radius_m},{lat},{lng});
      relation["building"](around:{radius_m},{lat},{lng});
      way["amenity"](around:{radius_m},{lat},{lng});
      way["man_made"](around:{radius_m},{lat},{lng});
      way["leisure"="stadium"](around:{radius_m},{lat},{lng});
    );
    out body;
    """
    try:
        r = requests.post(OVERPASS_URL, data={"data": query}, timeout=10)
        if r.status_code != 200:
            return {"has_buildings": False, "buildings": [], "count": 0}

        buildings = []
        for el in r.json().get("elements", []):
            tags     = el.get("tags", {})
            raw_type = (
                tags.get("building") or tags.get("amenity") or
                tags.get("man_made") or tags.get("leisure") or "structure"
            )
            label = BUILDING_LABELS.get(raw_type, raw_type.replace("_", " ").title())
            buildings.append({"type": raw_type, "label": label, "name": tags.get("name", "")})

        return {
            "has_buildings": len(buildings) > 0,
            "buildings":     buildings[:6],
            "count":         len(buildings),
        }
    except Exception as e:
        print(f"Building check error: {e}")
    return {"has_buildings": False, "buildings": [], "count": 0}