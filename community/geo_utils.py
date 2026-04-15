import json

from shapely.geometry import shape, mapping


def extract_geojson_geometry(boundary):
    """Return a GeoJSON geometry dict from Feature, FeatureCollection, or Geometry."""
    if boundary is None:
        raise ValueError('boundary is required')

    if isinstance(boundary, str):
        data = json.loads(boundary)
    else:
        data = boundary

    t = data.get('type')
    if t == 'Feature':
        data = data.get('geometry')
        if not data:
            raise ValueError('Feature has no geometry')
    elif t == 'FeatureCollection':
        features = data.get('features') or []
        if not features:
            raise ValueError('FeatureCollection has no features')
        data = features[0].get('geometry')
        if not data:
            raise ValueError('Feature has no geometry')

    if not data or 'type' not in data:
        raise ValueError('Invalid GeoJSON geometry')

    return data


def normalize_polygon_geojson(geometry_dict):
    """
    Repair with buffer(0), keep the largest polygon if MultiPolygon/collection.
    Returns a GeoJSON geometry dict (Polygon).
    """
    geom = shape(geometry_dict)
    geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError('Empty geometry after repair')

    if geom.geom_type == 'Polygon':
        return mapping(geom)
    if geom.geom_type == 'MultiPolygon':
        largest = max(geom.geoms, key=lambda g: g.area)
        return mapping(largest)
    if geom.geom_type == 'GeometryCollection':
        polys = [g for g in geom.geoms if g.geom_type == 'Polygon']
        if not polys:
            raise ValueError('No polygon found in geometry collection')
        largest = max(polys, key=lambda g: g.area)
        return mapping(largest)

    raise ValueError(f'Expected polygon geometry, got {geom.geom_type}')


def geometry_to_geojson_dict(stored):
    """JSONField already stores a dict; pass through for API responses."""
    return stored
