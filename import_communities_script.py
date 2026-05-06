#!/usr/bin/env python
"""
Import script for community census data from CSV.
Updates population and other demographic fields for existing communities.
"""
import os
import sys
import django
import csv
import re
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arc_backend.settings')
django.setup()

from django.utils import timezone
from community.models import Community, CensusYear, CommunityCensusData


def parse_bool(value):
    """Parse boolean values from CSV"""
    if not value:
        return False
    return str(value).strip().lower() in ['true', '1', 'yes', 't']


def parse_int(value):
    """Parse integer values from CSV"""
    if not value or str(value).strip() == '':
        return None
    try:
        return int(str(value).strip().replace(',', ''))
    except ValueError:
        return None


def parse_datetime(value):
    """Parse datetime values from CSV and make timezone-aware"""
    if not value or str(value).strip() == '':
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt
    except ValueError:
        return None


def import_communities_from_csv(csv_path, default_census_year=2000):
    """Import community census data from CSV file"""

    # Get or create default census year
    census_year_obj, created = CensusYear.objects.get_or_create(
        year=default_census_year,
        defaults={'start_date': timezone.now()}
    )
    if created:
        print(f"Created census year: {default_census_year}")
    else:
        print(f"Using existing census year: {default_census_year}")

    imported_count = 0
    updated_count = 0
    error_count = 0
    skipped_no_community = 0
    errors = []

    # Build normalized community name map to match 'CITY OF X' vs 'X', etc.
    def _normalize(name: str) -> str:
        s = (name or '').upper().strip()
        # Remove common government prefixes
        prefixes = [
            'CITY OF ', 'TOWN OF ', 'TOWNSHIP OF ', 'MUNICIPALITY OF ', 'VILLAGE OF ',
            'COUNTY OF ', 'REGIONAL MUNICIPALITY OF ', 'THE ', 'TOWNSHIP ', 'TOWN ', 'CITY ',
        ]
        for p in prefixes:
            if s.startswith(p):
                s = s[len(p):]
                break
        # Remove known trailing qualifiers (suffixes)
        suffixes = [
            ' TERRITORIAL DISTRICT', ' REGIONAL MUNICIPALITY', ' COUNTY', ' DISTRICT',
            ' MUNICIPALITY', ' TOWNSHIP', ' CITY', ' TOWN', ' VILLAGE'
        ]
        for suf in suffixes:
            if s.endswith(suf):
                s = s[: -len(suf)]
                break
        # Remove specific phrases
        s = s.replace(' - TERRITORIAL DISTRICT', '')
        # Remove slashes and words after slash variants like 'GORDON / BARRIE ISLAND'
        s = s.replace('/', ' ')
        # Remove punctuation and spaces
        s = re.sub(r"[^A-Z0-9]", "", s)
        return s

    all_communities = list(Community.objects.all().only('id', 'name'))
    norm_map = {}
    for c in all_communities:
        key = _normalize(c.name)
        # Keep first unique; if collision, store as list to mark ambiguity
        if key in norm_map:
            prev = norm_map[key]
            if isinstance(prev, list):
                prev.append(c)
            else:
                norm_map[key] = [prev, c]
        else:
            norm_map[key] = c

    # Alias map for tricky names -> exact Community.name
    alias_map = {
        'HALDIMAND': 'HALDIMAND COUNTY',
        'ST CLAIR': 'TOWNSHIP OF ST. CLAIR',
        'PARRY SOUND': 'TOWN OF PARRY SOUND',
        'KAWARTHA LAKES': 'CITY OF KAWARTHA LAKES',
    }

    def _resolve_community(community_name, row_num):
        """Resolve community name to existing Community instance"""
        if not community_name:
            return None

        # First try case-insensitive exact
        try:
            return Community.objects.get(name__iexact=community_name)
        except Community.DoesNotExist:
            pass

        # Try alias map
        alias_target = alias_map.get(community_name.upper())
        if alias_target:
            try:
                return Community.objects.get(name__iexact=alias_target)
            except Community.DoesNotExist:
                pass

        # Try normalized match
        nkey = _normalize(community_name)
        match = norm_map.get(nkey)
        if match is None:
            errors.append(f"Row {row_num}: Community '{community_name}' not found - skipped")
            return None
        if isinstance(match, list):
            names = ", ".join([m.name for m in match[:3]])
            errors.append(f"Row {row_num}: Ambiguous community '{community_name}' matches [{names}...] - skipped")
            return None
        return match

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row_num, row in enumerate(reader, start=2):
            try:
                community_name = row.get('community_name', '').strip()
                if not community_name:
                    errors.append(f"Row {row_num}: Missing community_name")
                    error_count += 1
                    continue

                # Resolve community
                community = _resolve_community(community_name, row_num)
                if not community:
                    skipped_no_community += 1
                    continue

                # Use census year from CSV if provided, otherwise use default
                census_year_str = row.get('census_year', '').strip()
                if census_year_str:
                    try:
                        year_val = int(census_year_str)
                        census_year_obj, _ = CensusYear.objects.get_or_create(
                            year=year_val,
                            defaults={'start_date': timezone.now()}
                        )
                    except ValueError:
                        pass  # Use default census year

                # Parse demographic fields
                population = parse_int(row.get('population', ''))
                tier = row.get('tier', '').strip()
                region = row.get('region', '').strip()
                zone = row.get('zone', '').strip()
                province = row.get('province', '').strip()
                is_active = parse_bool(row.get('is_active', 'true'))
                start_date = parse_datetime(row.get('start_date', ''))
                end_date = parse_datetime(row.get('end_date', ''))

                # Prepare data
                data = {
                    'community': community,
                    'census_year': census_year_obj,
                    'population': population if population is not None else 0,
                    'tier': tier[:50] if tier else '',
                    'region': region[:50] if region else '',
                    'zone': zone[:50] if zone else '',
                    'province': province[:50] if province else '',
                    'is_active': is_active,
                    'start_date': start_date,
                    'end_date': end_date,
                }

                # Check if record exists
                existing = CommunityCensusData.objects.filter(
                    community=community,
                    census_year=census_year_obj
                ).first()

                if existing:
                    # Update existing record
                    for key, value in data.items():
                        setattr(existing, key, value)
                    existing.save()
                    updated_count += 1
                else:
                    # Create new record
                    CommunityCensusData.objects.create(**data)
                    imported_count += 1

                if (imported_count + updated_count) % 100 == 0:
                    print(f"Processed {imported_count + updated_count} records...")

            except Exception as e:
                error_msg = f"Row {row_num} ({community_name}): {str(e)}"
                errors.append(error_msg)
                error_count += 1
                print(f"ERROR: {error_msg}")

    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)
    print(f"Total records imported: {imported_count}")
    print(f"Total records updated: {updated_count}")
    print(f"Total errors: {error_count}")
    print(f"Total skipped (unknown community): {skipped_no_community}")

    if errors:
        print("\nERRORS:")
        for error in errors[:10]:  # Show first 10 errors
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more errors")

    return imported_count, updated_count, error_count


if __name__ == '__main__':
    csv_file = 'Updated_Communities_Import_111.csv'

    if not os.path.exists(csv_file):
        print(f"ERROR: CSV file not found: {csv_file}")
        sys.exit(1)

    print(f"Starting import from {csv_file}...")
    print(f"Using default census year: 2000")
    print("-" * 60)

    import_communities_from_csv(csv_file, default_census_year=2000)
