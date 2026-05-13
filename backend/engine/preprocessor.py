from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform


def convert_to_meters(geojson_polygon):
    coords     = geojson_polygon["coordinates"][0]
    avg_lat    = sum(c[1] for c in coords) / len(coords)
    avg_lng    = sum(c[0] for c in coords) / len(coords)
    utm_zone   = int((avg_lng + 180) / 6) + 1
    hemisphere = "north" if avg_lat >= 0 else "south"
    utm_crs    = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84"

    fwd = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)

    shapely_polygon = shape(geojson_polygon)
    metric_polygon  = transform(fwd.transform, shapely_polygon)
    setback_polygon = metric_polygon.buffer(-3)

    return {
        "original_polygon": shapely_polygon,
        "metric_polygon":   metric_polygon,
        "setback_polygon":  setback_polygon,
        "area_m2":          round(metric_polygon.area, 2),
        "setback_area_m2":  round(setback_polygon.area, 2),
        "centroid_lat":     avg_lat,
        "centroid_lng":     avg_lng,
        "utm_zone":         utm_zone,
        "hemisphere":       hemisphere,
        "perimeter_m":      round(metric_polygon.length, 2),
    }


def calculate_slope_risk(elevation_data):
    if not elevation_data:
        return {"max_slope_degrees": 0, "slope_risk": "low"}
    elev_range = max(elevation_data) - min(elevation_data)
    if elev_range < 5:
        return {"max_slope_degrees": 2,  "slope_risk": "low"}
    elif elev_range < 15:
        return {"max_slope_degrees": 8,  "slope_risk": "medium"}
    else:
        return {"max_slope_degrees": 20, "slope_risk": "high"}


def get_inverse_transformer(centroid_lat, centroid_lng):
    utm_zone   = int((centroid_lng + 180) / 6) + 1
    hemisphere = "north" if centroid_lat >= 0 else "south"
    utm_crs    = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84"
    return Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)


def utm_to_lnglat(x, y, transformer):
    """Convert single UTM point to [lng, lat]"""
    lng, lat = transformer.transform(float(x), float(y))
    return [round(lng, 8), round(lat, 8)]


def convert_coord_ring(ring, transformer):
    """Convert a list of (x,y) UTM coords to [[lng,lat], ...]"""
    result = []
    for c in ring:
        if isinstance(c, (list, tuple)) and len(c) >= 2:
            lng, lat = transformer.transform(float(c[0]), float(c[1]))
            result.append([round(lng, 8), round(lat, 8)])
    return result


def convert_layout_to_latlng(layout_data: dict, centroid_lat: float, centroid_lng: float) -> dict:
    transformer = get_inverse_transformer(centroid_lat, centroid_lng)

    def convert_features(features):
        out = []
        for feat in features:
            try:
                raw_ring  = feat["coordinates"][0]
                converted = convert_coord_ring(raw_ring, transformer)
                if len(converted) < 3:
                    continue
                # Ensure ring is closed
                if converted[0] != converted[-1]:
                    converted.append(converted[0])
                out.append({**feat, "coordinates": [converted]})
            except Exception as e:
                print(f"  ⚠️  Feature conversion error: {e}")
        return out

    # Convert entrance
    entrance_lnglat = [centroid_lng, centroid_lat]
    if layout_data.get("entrance"):
        try:
            ex, ey = float(layout_data["entrance"][0]), float(layout_data["entrance"][1])
            elng, elat = transformer.transform(ex, ey)
            entrance_lnglat = [round(elng, 8), round(elat, 8)]
        except Exception as e:
            print(f"  ⚠️  Entrance conversion error: {e}")

    converted_plots = convert_features(layout_data.get("plots", []))
    converted_parks = convert_features(layout_data.get("parks", []))
    converted_roads = convert_features(layout_data.get("roads", []))

    print(f"  ✅ Converted: {len(converted_plots)} plots, "
          f"{len(converted_parks)} parks, {len(converted_roads)} roads")

    # Validate first plot coordinate is near centroid
    if converted_plots:
        fp = converted_plots[0]["coordinates"][0][0]
        dlng = abs(fp[0] - centroid_lng)
        dlat = abs(fp[1] - centroid_lat)
        print(f"  📍 First plot coord: [{fp[0]:.6f}, {fp[1]:.6f}]")
        print(f"  📍 Centroid:         [{centroid_lng:.6f}, {centroid_lat:.6f}]")
        print(f"  📍 Delta:            lng={dlng:.6f}, lat={dlat:.6f}")
        if dlng > 1.0 or dlat > 1.0:
            print("  ❌ WARNING: Coordinates are far from centroid!")
        else:
            print("  ✅ Coordinates look valid")

    return {
        **layout_data,
        "plots":    converted_plots,
        "parks":    converted_parks,
        "roads":    converted_roads,
        "entrance": entrance_lnglat,
    }