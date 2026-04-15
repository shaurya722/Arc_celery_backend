"""
Spatial adjacency for map-drawn community polygons.

Adjacent (bidirectional via Community.adjacent symmetrical M2M) when ANY of:
  • geometries **touch** (meet at boundary, interiors disjoint)
  • interiors **overlap** (partial area in common)
  • **boundaries intersect** (e.g. shared edge/vertex; also covers many touch cases)
  • geometries **intersect** in general (includes overlap, touch, containment)
  • boundaries within **MAP_BOUNDARY_GAP_DEGREES** (near-miss from drawing / float noise)
"""

import json
import logging

from django.db import DatabaseError, connection
from shapely.geometry import shape

logger = logging.getLogger(__name__)

# Degrees ≈ tens of metres at mid-latitudes; boundary–boundary gap still counts as adjacent
MAP_BOUNDARY_GAP_DEGREES = 0.00025


def _geoms_map_adjacent(a, b):
    """
    True if a and b should be map-neighbors: touch, overlap, boundary intersect,
    or general intersection, plus small boundary gap tolerance.
    """
    if a.equals(b) or a.is_empty or b.is_empty:
        return False

    touch = a.touches(b)
    overlap = a.overlaps(b)
    boundary_meets = a.boundary.intersects(b.boundary)
    geom_meets = a.intersects(b)
    try:
        near = a.boundary.distance(b.boundary) < MAP_BOUNDARY_GAP_DEGREES
    except Exception:
        near = False

    return touch or overlap or boundary_meets or geom_meets or near


def _community_ids_adjacent_polygon_postgis(geojson_polygon: dict, exclude_id=None):
    payload = json.dumps(geojson_polygon)
    # q.g = new polygon; ex.e = existing row polygon (parsed once per row)
    sql = """
        SELECT c.id::text
        FROM community_community c
        CROSS JOIN LATERAL (
            SELECT public.ST_SetSRID(public.ST_GeomFromGeoJSON(%s::text), 4326) AS g
        ) AS q
        CROSS JOIN LATERAL (
            SELECT public.ST_SetSRID(public.ST_GeomFromGeoJSON(c.boundary::text), 4326) AS e
        ) AS ex
        WHERE c.boundary IS NOT NULL
          AND (
            public.ST_Intersects(q.g, ex.e)
            OR public.ST_Touches(q.g, ex.e)
            OR public.ST_Overlaps(q.g, ex.e)
            OR public.ST_Intersects(public.ST_Boundary(q.g), public.ST_Boundary(ex.e))
            OR public.ST_DWithin(
                public.ST_Boundary(q.g),
                public.ST_Boundary(ex.e),
                %s
            )
          )
    """
    params = [payload, MAP_BOUNDARY_GAP_DEGREES]
    if exclude_id is not None:
        sql += " AND c.id <> %s"
        params.append(str(exclude_id))

    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return [row[0] for row in cursor.fetchall()]


def _community_ids_adjacent_polygon_python(geojson_polygon: dict, exclude_id=None):
    from .models import Community

    new_geom = shape(geojson_polygon)
    ids = []
    qs = Community.objects.filter(boundary__isnull=False).only('id', 'boundary')
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)

    for c in qs.iterator():
        try:
            other = shape(c.boundary)
            if _geoms_map_adjacent(new_geom, other):
                ids.append(str(c.id))
        except (TypeError, ValueError, KeyError):
            continue

    return ids


def community_ids_touching_polygon(geojson_polygon: dict, exclude_id=None):
    """
    UUIDs of communities adjacent to this polygon (touch / overlap / boundary or
    geometry intersect / near boundary). Symmetrical M2M makes links bidirectional.
    """
    try:
        return _community_ids_adjacent_polygon_postgis(geojson_polygon, exclude_id)
    except DatabaseError as e:
        logger.warning(
            'PostGIS spatial query failed; using Shapely fallback. '
            'Enable PostGIS for better performance: CREATE EXTENSION postgis; — %s',
            e,
        )
        return _community_ids_adjacent_polygon_python(geojson_polygon, exclude_id)


def rebuild_adjacent_for_all_communities_with_boundaries():
    """
    Refresh symmetrical adjacent M2M for every community that has a boundary.
    """
    from .models import Community

    with_boundary = list(
        Community.objects.filter(boundary__isnull=False).prefetch_related('adjacent')
    )
    for c in with_boundary:
        ids = community_ids_touching_polygon(c.boundary, exclude_id=c.pk)
        c.adjacent.set(Community.objects.filter(pk__in=ids))
