from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform


def convert_to_meters(geojson_polygon):
    coords   = geojson_polygon["coordinates"][0]
    avg_lat  = sum(c[1] for c in coords) / len(coords)
    avg_lng  = sum(c[0] for c in coords) / len(coords)

    utm_zone  = int((avg_lng + 180) / 6) + 1
    hemisphere = "north" if avg_lat >= 0 else "south"
    utm_crs   = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84"

    transformer     = Transformer.from_crs("EPSG:4326", utm_crs, always_xy=True)
    shapely_polygon = shape(geojson_polygon)
    metric_polygon  = transform(transformer.transform, shapely_polygon)
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


def get_utm_transformer_inverse(centroid_lat, centroid_lng):
    utm_zone   = int((centroid_lng + 180) / 6) + 1
    hemisphere = "north" if centroid_lat >= 0 else "south"
    utm_crs    = f"+proj=utm +zone={utm_zone} +{hemisphere} +ellps=WGS84"
    return Transformer.from_crs(utm_crs, "EPSG:4326", always_xy=True)


def utm_coords_to_lnglat(coords_list, transformer):
    """Convert list of [x, y] UTM coords → [lng, lat]"""
    result = []
    for c in coords_list:
        lng, lat = transformer.transform(c[0], c[1])
        result.append([lng, lat])
    return result


def convert_layout_to_latlng(layout_data: dict, centroid_lat: float, centroid_lng: float) -> dict:
    transformer = get_utm_transformer_inverse(centroid_lat, centroid_lng)

    def convert_feature_list(features):
        out = []
        for feat in features:
            try:
                raw = feat["coordinates"][0]
                converted = utm_coords_to_lnglat(raw, transformer)
                if len(converted) < 3:
                    continue
                out.append({**feat, "coordinates": [converted]})
            except Exception as e:
                print(f"Coord conversion error: {e}")
        return out

    # Convert entrance
    entrance_lnglat = [centroid_lng, centroid_lat]
    if layout_data.get("entrance"):
        try:
            ex, ey = layout_data["entrance"]
            elng, elat = transformer.transform(ex, ey)
            entrance_lnglat = [elng, elat]
        except Exception as e:
            print(f"Entrance conversion error: {e}")

    return {
        **layout_data,
        "plots":    convert_feature_list(layout_data.get("plots", [])),
        "parks":    convert_feature_list(layout_data.get("parks", [])),
        "roads":    convert_feature_list(layout_data.get("roads", [])),
        "entrance": entrance_lnglat,
    }