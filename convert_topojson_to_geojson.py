#!/usr/bin/env python3
"""
Convert TopoJSON to GeoJSON format
"""
import json
import sys


def decode_arc(arcs, arc_indices, transform=None):
    """Decode TopoJSON arc indices to coordinates"""
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


def topojson_to_geojson(input_file, output_file):
    """Convert TopoJSON file to GeoJSON"""
    print(f'Loading TopoJSON from {input_file}...')
    
    with open(input_file, 'r') as f:
        topo_data = json.load(f)
    
    arcs = topo_data['arcs']
    transform = topo_data.get('transform')
    
    # Get the object name (first key in objects)
    object_name = list(topo_data['objects'].keys())[0]
    geometries = topo_data['objects'][object_name]['geometries']
    
    print(f'Found {len(geometries)} geometries')
    
    features = []
    for geom_data in geometries:
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
                    coords = decode_arc(arcs, ring_arcs, transform)
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
                        coords = decode_arc(arcs, ring_arcs, transform)
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
            print(f'Warning: Error decoding geometry for {name}: {e}')
    
    # Create GeoJSON FeatureCollection
    geojson = {
        'type': 'FeatureCollection',
        'features': features
    }
    
    print(f'Writing GeoJSON to {output_file}...')
    with open(output_file, 'w') as f:
        json.dump(geojson, f, indent=2)
    
    print(f'Successfully converted {len(features)} features to GeoJSON')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        input_file = 'Municipal_Boundary_-_Upper_Tier_and_District.json'
        output_file = 'Municipal_Boundary_-_Upper_Tier_and_District.geojson'
    elif len(sys.argv) < 3:
        input_file = sys.argv[1]
        output_file = input_file.replace('.json', '.geojson')
    else:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    
    topojson_to_geojson(input_file, output_file)
