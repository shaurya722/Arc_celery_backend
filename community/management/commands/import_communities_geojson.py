import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from community.models import Community


class Command(BaseCommand):
    help = "Import communities from a GeoJSON file. Stores geometry into Community.boundary and uses a property as the name."

    def add_arguments(self, parser):
        parser.add_argument("geojson_path", type=str, help="Path to the GeoJSON file (FeatureCollection)")
        parser.add_argument(
            "--name-field",
            dest="name_field",
            default="name",
            help="Property key to use for the community name (default: 'name'). If missing, first string field will be used.",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            default=False,
            help="Update existing communities with the same name (boundary only).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Import only the first N features (useful for testing).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Parse and report what would be imported without writing to DB.",
        )

    def handle(self, *args, **options):
        path = Path(options["geojson_path"]).expanduser().resolve()
        name_field: str = options["name_field"]
        do_update: bool = options["update"]
        limit: Optional[int] = options["limit"]
        dry_run: bool = options["dry_run"]

        if not path.exists():
            raise CommandError(f"GeoJSON file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise CommandError(f"Invalid JSON in {path}: {e}")

        if data.get("type") != "FeatureCollection":
            raise CommandError("GeoJSON must be a FeatureCollection")

        features: Iterable[Dict[str, Any]] = data.get("features") or []
        if not isinstance(features, list) or not features:
            self.stdout.write(self.style.WARNING("No features found to import."))
            return

        if limit is not None:
            features = features[:limit]

        created = 0
        updated = 0
        skipped = 0

        def pick_name(props: Dict[str, Any]) -> Optional[str]:
            if not isinstance(props, dict):
                return None
            # Preferred key
            if name_field in props and props[name_field]:
                return str(props[name_field]).strip()
            # Common alternates
            for key in [
                "NAME",
                "Name",
                "Municipality",
                "MUNICNAME",
                "MUNICIPALITY",
                "COMMUNITY",
                "TOWN",
                "CITY",
            ]:
                if key in props and props[key]:
                    return str(props[key]).strip()
            # Fallback: first string-like property
            for k, v in props.items():
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None

        to_write = []
        for idx, feat in enumerate(features, start=1):
            geom = feat.get("geometry")
            props = feat.get("properties") or {}
            name = pick_name(props)

            if not name:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"[{idx}] Skipping feature without resolvable name"))
                continue
            if geom is None:
                skipped += 1
                self.stdout.write(self.style.WARNING(f"[{idx}] Skipping '{name}' (no geometry)"))
                continue
            if geom.get("type") not in {"Polygon", "MultiPolygon"}:
                # Store as-is (model accepts any GeoJSON geometry), but warn
                self.stdout.write(self.style.WARNING(f"[{idx}] '{name}' geometry type is {geom.get('type')} (storing anyway)"))

            to_write.append((name, geom))

        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run: no changes will be made."))
            self.stdout.write(f"Would import {len(to_write)} communities; skipped {skipped} features")
            sample = to_write[:5]
            for name, geom in sample:
                self.stdout.write(f" - {name}: {geom.get('type')}")
            return

        with transaction.atomic():
            for name, geom in to_write:
                if do_update:
                    obj, created_flag = Community.objects.update_or_create(
                        name=name,
                        defaults={"boundary": geom},
                    )
                    if created_flag:
                        created += 1
                    else:
                        updated += 1
                else:
                    obj, created_flag = Community.objects.get_or_create(name=name, defaults={"boundary": geom})
                    if created_flag:
                        created += 1
                    else:
                        skipped += 1  # already existed

        self.stdout.write(self.style.SUCCESS(
            f"Import complete: created={created}, updated={updated}, skipped={skipped}"
        ))
