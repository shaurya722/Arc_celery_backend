import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.conf import settings

from community.models import Community

try:
    # Optional reprojection support
    from pyproj import Transformer, CRS
except Exception:  # pragma: no cover
    Transformer = None
    CRS = None

try:
    from community.geo_utils import normalize_polygon_geojson
except Exception:  # pragma: no cover
    normalize_polygon_geojson = None


class Command(BaseCommand):
    help = "Import communities from a GeoJSON FeatureCollection into the Community model.\n\n"

    def add_arguments(self, parser):
        parser.add_argument(
            "geojson_path",
            type=str,
            help="Path to the GeoJSON file containing FeatureCollection with features having properties.CSDNAME and geometry",
        )
        parser.add_argument(
            "--name-field",
            default="CSDNAME",
            help="Property key to use for the community name (default: CSDNAME)",
        )
        parser.add_argument(
            "--update-only",
            action="store_true",
            help="If set, will only update existing communities and skip creation",
        )
        parser.add_argument(
            "--source-crs",
            default="auto",
            help=(
                "Source CRS for input coordinates. Use 'auto' to detect projected meters "
                "and assume EPSG:3347 (StatCan Lambert). Or specify an EPSG code like 'EPSG:3347'."
            ),
        )

    def handle(self, *args, **options):
        path = options["geojson_path"]
        name_field = options["name_field"]
        update_only = options["update_only"]
        source_crs_opt = options.get("source_crs", "auto")

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"GeoJSON file not found: {path}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
            raise CommandError("Input must be a GeoJSON FeatureCollection")

        features = data.get("features") or []
        if not isinstance(features, list):
            raise CommandError("FeatureCollection.features must be a list")

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Build a transformer if needed (projected -> WGS84 lon/lat)
        transformer = None
        assumed = None
        if source_crs_opt and source_crs_opt != "none" and Transformer is not None and CRS is not None:
            if source_crs_opt == "auto":
                # Peek at the first feature's first coordinate to detect projected meters
                for feat in features:
                    geom0 = feat.get("geometry") or {}
                    coords = None
                    try:
                        # Handle Polygon or MultiPolygon
                        t = geom0.get("type")
                        if t == "Polygon":
                            coords = geom0.get("coordinates", [])[0][0]
                        elif t == "MultiPolygon":
                            coords = geom0.get("coordinates", [])[0][0][0]
                    except Exception:
                        coords = None
                    if coords and isinstance(coords, (list, tuple)) and len(coords) >= 2:
                        x, y = coords[0], coords[1]
                        # If values are far outside lon/lat degrees, assume projected meters
                        if abs(x) > 180 or abs(y) > 90:
                            assumed = "EPSG:3347"  # StatCan Lambert (common for Canadian boundaries)
                        break
                if assumed and assumed.upper().startswith("EPSG:"):
                    transformer = Transformer.from_crs(CRS.from_string(assumed), CRS.from_epsg(4326), always_xy=True)
            else:
                try:
                    transformer = Transformer.from_crs(CRS.from_string(source_crs_opt), CRS.from_epsg(4326), always_xy=True)
                except Exception:
                    transformer = None

        # Temporarily disable adjacency recomputation for speed during bulk import
        prev_skip_adj = getattr(settings, "COMMUNITY_SKIP_ADJACENCY", False)
        setattr(settings, "COMMUNITY_SKIP_ADJACENCY", True)

        try:
            # Use a transaction so partial failures can be retried safely
            with transaction.atomic():
                for idx, feature in enumerate(features, start=1):
                    try:
                        props = feature.get("properties") or {}
                        geom = feature.get("geometry")

                        name = (props.get(name_field) or "").strip()
                        if not name:
                            skipped += 1
                            continue

                        if not isinstance(geom, dict) or not geom.get("type"):
                            skipped += 1
                            continue

                        # Optional reprojection to WGS84 lon/lat for map compatibility
                        if transformer is not None:
                            try:
                                def _reproj_ring(ring):
                                    return [
                                        list(transformer.transform(x, y)) for x, y in ring
                                    ]

                                t = geom.get("type")
                                if t == "Polygon":
                                    geom["coordinates"] = [
                                        _reproj_ring(r) for r in geom.get("coordinates", [])
                                    ]
                                elif t == "MultiPolygon":
                                    new_coords = []
                                    for poly in geom.get("coordinates", []):
                                        new_coords.append([_reproj_ring(r) for r in poly])
                                    geom["coordinates"] = new_coords
                                # else: leave as-is
                            except Exception:
                                # If reprojection fails, proceed with original
                                pass

                        # Optional topology repair / normalization to Polygon
                        if normalize_polygon_geojson is not None and geom.get("type") in {"Polygon", "MultiPolygon", "GeometryCollection"}:
                            try:
                                geom = normalize_polygon_geojson(geom)
                            except Exception:
                                # If normalization fails, keep original geometry
                                pass

                        if update_only:
                            # Only update if exists; otherwise skip
                            obj = Community.objects.filter(name=name).only("id", "boundary").first()
                            if not obj:
                                skipped += 1
                                continue
                            if obj.boundary != geom:
                                obj.boundary = geom
                                obj.save(update_fields=["boundary", "updated_at"])
                                updated += 1
                            else:
                                skipped += 1
                        else:
                            # Upsert by unique name
                            obj, was_created = Community.objects.get_or_create(
                                name=name,
                                defaults={"boundary": geom},
                            )
                            if was_created:
                                created += 1
                            else:
                                # Update boundary if changed
                                if obj.boundary != geom:
                                    obj.boundary = geom
                                    obj.save(update_fields=["boundary", "updated_at"])
                                    updated += 1
                                else:
                                    skipped += 1
                    except Exception:
                        # Count and continue without aborting the entire import
                        errors += 1
        finally:
            # Restore previous setting
            setattr(settings, "COMMUNITY_SKIP_ADJACENCY", prev_skip_adj)

        self.stdout.write(self.style.SUCCESS(
            f"Import completed: created={created}, updated={updated}, skipped={skipped}, errors={errors}"
        ))
