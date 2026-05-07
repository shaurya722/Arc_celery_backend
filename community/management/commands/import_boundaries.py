"""
Management command to import community boundaries from TopoJSON file
and calculate adjacent communities based on spatial relationships.
"""
import json
from django.core.management.base import BaseCommand
from community.models import Community
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union


class Command(BaseCommand):
    help = 'Import community boundaries from TopoJSON and calculate adjacencies'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='Municipal_Boundary_-_Upper_Tier_and_District.json',
            help='Path to TopoJSON file'
        )
        parser.add_argument(
            '--buffer',
            type=float,
            default=0.001,
            help='Buffer distance for adjacency detection (degrees)'
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
            '--touch-only',
            action='store_true',
            help='Adjacency only when polygons share a boundary (no overlaps/intersections, no buffer)'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        buffer_distance = options['buffer']
        limit = options.get('limit')
        skip_adjacency = options.get('no_adjacency', False)
        touch_only = options.get('touch_only', False)

        self.stdout.write(f'Loading TopoJSON from {file_path}...')

        with open(file_path, 'r') as f:
            topo_data = json.load(f)

        # Manually decode TopoJSON arcs
        self.stdout.write('Decoding TopoJSON arcs...')
        
        arcs = topo_data['arcs']
        transform = topo_data.get('transform')
        
        # Decode arcs to absolute coordinates
        def decode_arc(arc_indices):
            """Decode arc indices to coordinates"""
            coords = []
            for arc_idx in arc_indices:
                if arc_idx < 0:
                    # Reversed arc
                    arc = list(reversed(arcs[~arc_idx]))
                else:
                    arc = arcs[arc_idx]
                
                # Decode delta-encoded coordinates
                x, y = 0, 0
                for dx, dy in arc:
                    x += dx
                    y += dy
                    
                    # Apply transform if present
                    if transform:
                        lon = x * transform['scale'][0] + transform['translate'][0]
                        lat = y * transform['scale'][1] + transform['translate'][1]
                        coords.append([lon, lat])
                    else:
                        coords.append([x, y])
            
            return coords
        
        # Get the object name (first key in objects)
        object_name = list(topo_data['objects'].keys())[0]
        geometries = topo_data['objects'][object_name]['geometries']

        self.stdout.write(f'Found {len(geometries)} geometries')

        features = []
        for idx, geom_data in enumerate(geometries):
            if limit is not None and idx >= limit:
                break
            props = geom_data.get('properties', {})
            geom_type = geom_data.get('type')
            
            # Skip if no arcs
            if 'arcs' not in geom_data:
                continue
            
            try:
                if geom_type == 'Polygon':
                    # Decode polygon rings
                    rings = []
                    for ring_arcs in geom_data['arcs']:
                        coords = decode_arc(ring_arcs)
                        if len(coords) >= 4:  # Valid polygon ring
                            rings.append(coords)
                    
                    if rings:
                        geometry = {
                            'type': 'Polygon',
                            'coordinates': rings
                        }
                        features.append({
                            'type': 'Feature',
                            'properties': props,
                            'geometry': geometry
                        })
                        
                elif geom_type == 'MultiPolygon':
                    # Decode multipolygon
                    polygons = []
                    for polygon_arcs in geom_data['arcs']:
                        rings = []
                        for ring_arcs in polygon_arcs:
                            coords = decode_arc(ring_arcs)
                            if len(coords) >= 4:
                                rings.append(coords)
                        if rings:
                            polygons.append(rings)
                    
                    if polygons:
                        geometry = {
                            'type': 'MultiPolygon',
                            'coordinates': polygons
                        }
                        features.append({
                            'type': 'Feature',
                            'properties': props,
                            'geometry': geometry
                        })
            except Exception as e:
                name = props.get('OFFICIAL_M', 'Unknown')
                self.stdout.write(self.style.WARNING(f'Error decoding geometry for {name}: {e}'))

        self.stdout.write(f'Processing {len(features)} features...')

        community_data = {}
        
        for feature in features:
            props = feature.get('properties', {})
            
            # Extract community name from properties
            name = props.get('OFFICIAL_M') or props.get('MUNICIPA_2') or props.get('MUNICIPAL_')
            
            if not name or name == 'Water':
                continue
            
            # Clean up name
            name = name.strip().title()
            
            # Get or create community
            community, created = Community.objects.get_or_create(
                name=name,
                defaults={'boundary': feature['geometry']}
            )
            
            if not created and feature['geometry']:
                # Update boundary if community already exists
                community.boundary = feature['geometry']
                community.save()
            
            # Store geometry for adjacency calculation
            try:
                geom = shape(feature['geometry'])
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
        
        for i, id1 in enumerate(community_ids):
            data1 = community_data[id1]
            comm1 = data1['community']
            geom1 = data1['geometry']
            
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
