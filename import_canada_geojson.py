#!/usr/bin/env python
"""Import Canadian census subdivisions GeoJSON into Community model."""
import json
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arc_backend.settings')
django.setup()

from django.db import transaction
from community.models import Community

GEOJSON_PATH = '/home/ubuntu/Desktop/New_____Folder/ArcGis/aqaq/arc_backend/georef-canada-census-subdivision (1).geojson'


def extract_name(prop_value):
    """Handle list-wrapped names like ['Pickering']"""
    if isinstance(prop_value, list):
        if prop_value:
            return str(prop_value[0]).strip()
        return None
    if prop_value:
        return str(prop_value).strip()
    return None


def run():
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    features = data.get('features', [])
    print(f"Total features in GeoJSON: {len(features)}")

    # Clear all existing communities and related data (cascades to census data, adjacencies, etc.)
    existing_count = Community.objects.count()
    print(f"Clearing {existing_count} existing communities...")
    Community.objects.all().delete()
    print("Existing communities cleared.")

    created = 0
    updated = 0
    skipped = 0
    errors = 0

    to_write = []
    for idx, feat in enumerate(features, start=1):
        props = feat.get('properties') or {}
        geom = feat.get('geometry')

        name = extract_name(props.get('csd_name_en'))
        csd_type = props.get('csd_type', '')
        prov = extract_name(props.get('prov_name_en'))
        cd_name = extract_name(props.get('cd_name_en'))

        if not name:
            print(f"[{idx}] Skipping feature without name")
            skipped += 1
            continue
        if not geom:
            print(f"[{idx}] Skipping '{name}' (no geometry)")
            skipped += 1
            continue

        # Build a display name with type prefix if available
        display_name = name
        if csd_type and str(csd_type).strip():
            type_clean = str(csd_type).strip().title()
            # Skip generic or non-municipal types for name prefixing
            if type_clean in ('City', 'Town', 'Village', 'Township', 'Municipality',
                              'Regional Municipality', 'County', 'District'):
                prefix = type_clean
                if prefix.endswith('y') and not prefix.endswith('ity'):
                    prefix += ' of '
                else:
                    prefix = prefix + ' of '
                display_name = prefix + name
            elif 'reserve' in type_clean.lower() or 'indian' in type_clean.lower():
                # Keep reserve names as-is or skip them
                pass

        to_write.append({
            'name': display_name,
            'raw_name': name,
            'geom': geom,
            'type': csd_type,
            'province': prov,
            'county': cd_name,
        })

    print(f"\nReady to import {len(to_write)} communities")

    with transaction.atomic():
        for item in to_write:
            try:
                obj, created_flag = Community.objects.update_or_create(
                    name=item['name'],
                    defaults={
                        'boundary': item['geom'],
                    }
                )
                if created_flag:
                    created += 1
                else:
                    updated += 1
            except Exception as e:
                print(f"ERROR importing '{item['name']}': {e}")
                errors += 1

    print(f"\nImport complete: created={created}, updated={updated}, skipped={skipped}, errors={errors}")


if __name__ == '__main__':
    run()
