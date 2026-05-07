#!/usr/bin/env python
"""
Import script for site census data from CSV.
Handles empty census_year by using year 2000 as default.
"""
import os
import sys
import django
import csv
from datetime import datetime

# Setup Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'arc_backend.settings')
django.setup()

from django.utils import timezone
from sites.models import Site, SiteCensusData
from community.models import Community, CensusYear
import re

def parse_bool(value):
    """Parse boolean values from CSV"""
    if not value:
        return False
    return str(value).strip().lower() in ['true', '1', 'yes']

def parse_decimal(value):
    """Parse decimal values from CSV"""
    if not value or str(value).strip() == '':
        return None
    try:
        return float(str(value).strip())
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

def import_sites_from_csv(csv_path, default_census_year=2000):
    """Import site census data from CSV file"""
    
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
        'DYSART, DUDLEY, HARCOURT, GUILFORD, HARBURN, BRUTON, HAVELOCK, EYRE AND CLYDE': 'MUNICIPALITY OF DYSART ET AL',
        'FRENCH RIVER': 'FRENCH RIVER / RIVIÈRE DES FRANÇAIS',
        'GREATER SUDBURY': 'GREATER SUDBURY / GRAND SUDBURY',
        'THE BLUE MOUNTAINS': 'TOWN OF THE BLUE MOUNTAINS',
        'WHITEWATER': 'TOWNSHIP OF WHITEWATER REGION',
        'THE NATION': 'THE NATION / LA NATION',
        'NIPISSING - TERRITORIAL DISTRICT': 'NIPISSING',
        'PARRY SOUND - TERRITORIAL DISTRICT': 'PARRY SOUND',
        'HEAD, CLARA AND MARIA': 'TOWNSHIP OF HEAD',
        'MACDONALD, MEREDITH AND ABERDEEN ADDITIONAL': 'TOWNSHIP OF MACDONALD',
        'HAMILTON/NORTHUMBERLAND': 'HAMILTON',
        'PARIS': 'TOWN OF PARIS',
    }

    def _clip(s: str, max_len: int) -> str:
        s = (s or '').strip()
        return s[:max_len]

    def _clean_region(region: str) -> str:
        if not region:
            return ''
        r = region.strip()
        # Normalize common long forms to fit max_length=20
        r = r.replace(' - Territorial District', '')
        for suf in [' County', ' county', ' District', ' district', ' Territorial District']:
            if r.endswith(suf):
                r = r[: -len(suf)]
                break
        return _clip(r, 20)

    def _normalize_site_type(raw: str) -> str:
        """
        Normalize CSV site_type into model choices:
        - 'Event' or anything containing 'event' -> 'Event'
        - otherwise -> 'Collection Site'
        """
        s = (raw or '').strip()
        if not s:
            return 'Collection Site'
        if 'event' in s.lower():
            return 'Event'
        return 'Collection Site'

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row_num, row in enumerate(reader, start=2):
            try:
                site_name = row.get('site_name', '').strip()
                if not site_name:
                    errors.append(f"Row {row_num}: Missing site_name")
                    error_count += 1
                    continue
                
                # Get or create site
                site, _ = Site.objects.get_or_create(site_name=site_name)
                
                # Match to existing community only (case-insensitive). Skip if not found.
                community = None
                community_name = row.get('community_name', '').strip()
                if community_name:
                    # First try case-insensitive exact
                    try:
                        community = Community.objects.get(name__iexact=community_name)
                    except Community.DoesNotExist:
                        # Try alias map
                        alias_target = alias_map.get(community_name.upper())
                        if alias_target:
                            try:
                                community = Community.objects.get(name__iexact=alias_target)
                            except Community.DoesNotExist:
                                community = None
                        if community is None:
                            # Try normalized match
                            nkey = _normalize(community_name)
                            match = norm_map.get(nkey)
                            if match is None:
                                errors.append(f"Row {row_num} ({site_name}): Community '{community_name}' not found - skipped")
                                skipped_no_community += 1
                                continue
                            if isinstance(match, list):
                                names = ", ".join([m.name for m in match[:3]])
                                errors.append(f"Row {row_num} ({site_name}): Ambiguous community '{community_name}' matches [{names}...] - skipped")
                                skipped_no_community += 1
                                continue
                            community = match
                
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
                
                row_id = (row.get('id') or row.get('site_census_data_id') or '').strip()
                existing = None
                if row_id:
                    try:
                        existing = SiteCensusData.objects.filter(pk=int(row_id)).first()
                    except ValueError:
                        existing = None
                
                # Prepare data
                site_type_norm = _normalize_site_type(row.get('site_type', ''))
                # For events, default event_approved to true unless explicitly provided.
                raw_event_approved = row.get('event_approved', '')
                event_approved_val = (
                    parse_bool(raw_event_approved) if str(raw_event_approved).strip() != '' else (site_type_norm == 'Event')
                )
                data = {
                    'site': site,
                    'census_year': census_year_obj,
                    'community': community,
                    'site_type': site_type_norm,
                    'operator_type': (_clip(row.get('operator_type', ''), 50) or None),
                    'service_partner': (_clip(row.get('service_partner', ''), 255) or None),
                    'address_line_1': _clip(row.get('address_line_1', ''), 255),
                    'address_line_2': (_clip(row.get('address_line_2', ''), 255) or None),
                    'address_city': _clip(row.get('address_city', ''), 100),
                    'address_postal_code': (_clip(row.get('address_postal_code', ''), 20) or None),
                    'region': _clean_region(row.get('region', '')),
                    'service_area': (_clip(row.get('service_area', ''), 100) or None),
                    'address_latitude': parse_decimal(row.get('address_latitude', '')),
                    'address_longitude': parse_decimal(row.get('address_longitude', '')),
                    'latitude': parse_decimal(row.get('latitude', '')),
                    'longitude': parse_decimal(row.get('longitude', '')),
                    'is_active': parse_bool(row.get('is_active', 'true')),
                    'event_approved': event_approved_val,
                    'site_start_date': parse_datetime(row.get('site_start_date', '')),
                    'site_end_date': parse_datetime(row.get('site_end_date', '')),
                    'program_paint': parse_bool(row.get('program_paint', '')),
                    'program_paint_start_date': parse_datetime(row.get('program_paint_start_date', '')),
                    'program_paint_end_date': parse_datetime(row.get('program_paint_end_date', '')),
                    'program_lights': parse_bool(row.get('program_lights', '')),
                    'program_lights_start_date': parse_datetime(row.get('program_lights_start_date', '')),
                    'program_lights_end_date': parse_datetime(row.get('program_lights_end_date', '')),
                    'program_solvents': parse_bool(row.get('program_solvents', '')),
                    'program_solvents_start_date': parse_datetime(row.get('program_solvents_start_date', '')),
                    'program_solvents_end_date': parse_datetime(row.get('program_solvents_end_date', '')),
                    'program_pesticides': parse_bool(row.get('program_pesticides', '')),
                    'program_pesticides_start_date': parse_datetime(row.get('program_pesticides_start_date', '')),
                    'program_pesticides_end_date': parse_datetime(row.get('program_pesticides_end_date', '')),
                    'program_fertilizers': parse_bool(row.get('program_fertilizers', '')),
                    'program_fertilizers_start_date': parse_datetime(row.get('program_fertilizers_start_date', '')),
                    'program_fertilizers_end_date': parse_datetime(row.get('program_fertilizers_end_date', ''))
                }
                
                if existing:
                    # Update existing record
                    for key, value in data.items():
                        setattr(existing, key, value)
                    existing.save()
                    updated_count += 1
                else:
                    # Create new record
                    SiteCensusData.objects.create(**data)
                    imported_count += 1
                
                if (imported_count + updated_count) % 100 == 0:
                    print(f"Processed {imported_count + updated_count} records...")
                    
            except Exception as e:
                error_msg = f"Row {row_num} ({site_name}): {str(e)}"
                errors.append(error_msg)
                error_count += 1
                print(f"ERROR: {error_msg}")
    
    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
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
    csv_file = 'Updated_Sites_Import__111.csv'
    
    if not os.path.exists(csv_file):
        print(f"ERROR: CSV file not found: {csv_file}")
        sys.exit(1)
    
    print(f"Starting import from {csv_file}...")
    print(f"Using default census year: 2000")
    print("-" * 60)
    
    import_sites_from_csv(csv_file, default_census_year=2000)
