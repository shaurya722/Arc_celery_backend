"""
Management command to import community boundaries from GeoJSON file
and optionally calculate adjacent communities based on spatial relationships.
"""
import json
from django.core.management.base import BaseCommand
from community.models import Community
from shapely.geometry import shape, mapping
from shapely.ops import transform as shp_transform


class Command(BaseCommand):
    help = 'Import community boundaries from GeoJSON'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            required=True,
            help='Path to GeoJSON file'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Import only the first N features from the file'
        )
        parser.add_argument(
            '--no-adjacency',
            action='store_true',
            help='Skip adjacency calculation after importing boundaries'
        )
        parser.add_argument(
            '--buffer',
            type=float,
            default=0.001,
            help='Buffer distance for adjacency detection (degrees)'
        )
        parser.add_argument(
            '--touch-only',
            action='store_true',
            help='Adjacency only when polygons share a boundary (no overlaps/intersections, no buffer)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        limit = options.get('limit')
        skip_adjacency = options.get('no_adjacency', False)
        buffer_distance = options['buffer']
        touch_only = options.get('touch_only', False)

        self.stdout.write(f'Loading GeoJSON from {file_path}...')

        with open(file_path, 'r') as f:
            geojson_data = json.load(f)

        if geojson_data.get('type') != 'FeatureCollection':
            self.stdout.write(self.style.ERROR('Invalid GeoJSON: expected FeatureCollection'))
            return

        # Detect CRS; many Canadian datasets ship in EPSG:3347 (projected meters)
        crs_info = geojson_data.get('crs') or {}
        crs_name = None
        if isinstance(crs_info, dict):
            props = crs_info.get('properties') or {}
            crs_name = props.get('name')
        
        # Prepare transformer if a known projected CRS is detected
        transformer = None
        if crs_name and ('EPSG::3347' in crs_name or 'EPSG:3347' in crs_name or '3347' in crs_name):
            try:
                from pyproj import Transformer
                transformer = Transformer.from_crs('EPSG:3347', 'EPSG:4326', always_xy=True)
                self.stdout.write('Detected EPSG:3347; will reproject to EPSG:4326 (lon/lat)')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'CRS transform unavailable ({e}); storing coordinates as-is'))

        features = geojson_data.get('features', [])
        self.stdout.write(f'Found {len(features)} features')

        if limit:
            features = features[:limit]
            self.stdout.write(f'Processing first {len(features)} features (--limit {limit})')

        community_data = {}
        
        for idx, feature in enumerate(features):
            props = feature.get('properties', {})
            geometry = feature.get('geometry')
            
            if not geometry:
                continue
            
            # Extract community name from properties
            name = (
                props.get('MUNICIPAL_NAME') or 
                props.get('OFFICIAL_M') or 
                props.get('OFFICIAL_NAME') or 
                props.get('NAME') or 
                props.get('name')
            )
            
            if not name:
                self.stdout.write(self.style.WARNING(f'  Skipping feature {idx}: no name found'))
                continue
            
            # Clean up name
            name = name.strip().title()
            
            # Skip water features
            if 'water' in name.lower():
                continue
            
            # Reproject if needed
            store_geometry = geometry
            try:
                if transformer is not None:
                    geom_src = shape(geometry)
                    geom_wgs = shp_transform(transformer.transform, geom_src)
                    store_geometry = mapping(geom_wgs)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Reprojection failed for {name}: {e}; storing as-is'))

            # Get or create community
            community, created = Community.objects.get_or_create(
                name=name,
                defaults={'boundary': store_geometry}
            )
            
            if not created:
                # Update boundary if community already exists
                community.boundary = store_geometry
                community.save()
            
            # Store geometry for adjacency calculation
            try:
                geom = shape(store_geometry)
                community_data[community.id] = {
                    'community': community,
                    'geometry': geom,
                    'name': name
                }
                
                action = 'Created' if created else 'Updated'
                self.stdout.write(f'  {action}: {name}')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  Error processing geometry for {name}: {e}'))

        # Calculate adjacencies (unless skipped)
        if skip_adjacency:
            self.stdout.write(self.style.SUCCESS(f'\nSuccessfully imported {len(community_data)} communities'))
            self.stdout.write(self.style.WARNING('Adjacency calculation skipped (--no-adjacency)'))
            return

        self.stdout.write('\nCalculating adjacencies...')
        
        adjacency_count = 0
        community_ids = list(community_data.keys())
        total_pairs = len(community_ids) * (len(community_ids) - 1) // 2
        
        self.stdout.write(f'Checking {total_pairs} community pairs...')
        
        for i, id1 in enumerate(community_ids):
            data1 = community_data[id1]
            comm1 = data1['community']
            geom1 = data1['geometry']
            
            # Progress indicator
            if i % 10 == 0:
                self.stdout.write(f'  Progress: {i}/{len(community_ids)} communities processed...')
            
            for id2 in community_ids[i+1:]:
                data2 = community_data[id2]
                comm2 = data2['community']
                geom2 = data2['geometry']
                
                # Check adjacency according to selected strategy
                try:
                    if touch_only:
                        cond = geom1.touches(geom2)
                    else:
                        cond = geom1.touches(geom2) or geom1.intersects(geom2)

                    if cond:
                        comm1.adjacent.add(comm2)
                        adjacency_count += 1
                        self.stdout.write(f'  Adjacent: {data1["name"]} <-> {data2["name"]}')
                    elif (not touch_only) and buffer_distance > 0:
                        # Check if within buffer distance
                        if geom1.distance(geom2) <= buffer_distance:
                            comm1.adjacent.add(comm2)
                            adjacency_count += 1
                            self.stdout.write(f'  Adjacent (buffered): {data1["name"]} <-> {data2["name"]}')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  Error checking adjacency: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully imported {len(community_data)} communities'))
        self.stdout.write(self.style.SUCCESS(f'Created {adjacency_count} adjacency relationships'))
