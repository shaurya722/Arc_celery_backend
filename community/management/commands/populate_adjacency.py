from typing import Dict, List, Tuple, Optional, Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from community.models import Community


class Command(BaseCommand):
    help = (
        "Compute and populate Community.adjacent using stored GeoJSON boundaries.\n"
        "Requires shapely. Adjacency is created when geometries touch or intersect;\n"
        "optionally, neighbors within a small gap (distance <= --min-gap) are also linked."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--min-gap",
            type=float,
            default=0.0,
            help="Include communities whose boundaries are within this gap distance (in coordinate units, degrees). Default 0.",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="Clear existing adjacency relationships before recomputing.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Only process first N communities (for testing).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Compute and report counts but do not write to the database.",
        )

    def handle(self, *args, **options):
        try:
            from shapely.geometry import shape
            try:
                # Shapely 2.x
                from shapely.strtree import STRtree  # type: ignore
            except Exception:  # pragma: no cover
                STRtree = None  # shapely <2 fallback handled below
        except Exception as e:  # pragma: no cover
            raise CommandError(
                "This command requires the 'shapely' package. Install with: pip install shapely"
            )

        min_gap: float = options["min_gap"]
        reset: bool = options["reset"]
        limit: Optional[int] = options["limit"]
        dry_run: bool = options["dry_run"]

        qs = Community.objects.exclude(boundary__isnull=True).order_by("name")
        if limit:
            qs = qs[:limit]

        items: List[Tuple[str, str, object]] = []  # (id, name, shapely_geom)
        id_to_index: Dict[str, int] = {}

        self.stdout.write(f"Loading boundaries for {qs.count()} communities...")
        for i, c in enumerate(qs.iterator(), start=0):
            try:
                geom = shape(c.boundary)
            except Exception:
                # Skip invalid geometry
                continue
            items.append((str(c.id), c.name, geom))
            id_to_index[str(c.id)] = i

        if not items:
            self.stdout.write(self.style.WARNING("No communities with valid boundaries found."))
            return

        geoms = [g for (_id, _name, g) in items]

        # Build spatial index if available
        index = None
        self.stdout.write(f"STRtree available: {STRtree is not None}")
        if STRtree is not None:
            try:
                index = STRtree(geoms)
                self.stdout.write(f"STRtree index built with {len(geoms)} geometries")
            except Exception as e:
                self.stdout.write(f"STRtree build failed: {e}")
                index = None

        def candidate_indices(i: int) -> Iterable[int]:
            if index is not None:
                try:
                    hits = index.query(geoms[i])  # returns array of indices (numpy.int64)
                    for j in hits:
                        j = int(j)  # Convert numpy.int64 to Python int
                        if j != i:
                            yield j
                    return
                except Exception as e:
                    # STRtree query failed, fall through to brute force
                    pass
            # Fallback: brute force
            for j in range(len(geoms)):
                if j != i:
                    yield j

        self.stdout.write("Computing adjacency...")
        neighbors: Dict[str, set] = {cid: set() for cid, _n, _g in items}
        added_pairs = 0
        
        total_comparisons = 0
        for i, (cid, name, g1) in enumerate(items):
            # Get candidates via bbox overlap (from STRtree) or all
            candidates_checked = 0
            for j in candidate_indices(i):
                candidates_checked += 1
                total_comparisons += 1
                cid2, name2, g2 = items[j]
                try:
                    # Fast pre-check: bbox overlap
                    if not g1.bounds or not g2.bounds:
                        continue
                    b1 = g1.bounds  # (minx, miny, maxx, maxy)
                    b2 = g2.bounds
                    # Check if bboxes are completely separate (no overlap)
                    no_bbox_overlap = (b1[2] < b2[0]) or (b2[2] < b1[0]) or (b1[3] < b2[1]) or (b2[3] < b1[1])
                    if no_bbox_overlap and min_gap <= 0:
                        # No bbox overlap and no gap tolerance; skip expensive checks
                        continue
                    # Exact relation checks
                    touches_or_intersects = g1.touches(g2) or g1.intersects(g2)
                    close_enough = False
                    if not touches_or_intersects and min_gap > 0:
                        try:
                            # Distance computation may be expensive; only if requested
                            close_enough = g1.distance(g2) <= min_gap
                        except Exception:
                            close_enough = False
                    if touches_or_intersects or close_enough:
                        if cid2 not in neighbors[cid]:
                            neighbors[cid].add(cid2)
                            neighbors[cid2].add(cid)
                            added_pairs += 1
                except Exception:
                    # Skip problematic geometry pair
                    continue

        self.stdout.write(f"Total comparisons: {total_comparisons}")
        self.stdout.write(f"Computed adjacency links: {added_pairs} pairs across {len(items)} communities.")

        if dry_run:
            # Show a small sample
            sample = list(neighbors.items())[:10]
            for cid, nbrs in sample:
                self.stdout.write(f" - {cid}: {len(nbrs)} neighbors")
            self.stdout.write(self.style.NOTICE("Dry run: no database writes performed."))
            return

        with transaction.atomic():
            if reset:
                self.stdout.write("Clearing existing adjacency relations (reset)...")
                # Clear M2M for all
                for c in Community.objects.all().only("id"):
                    c.adjacent.clear()

            # Apply new adjacency links
            id_to_obj = {str(c.id): c for c in Community.objects.filter(id__in=neighbors.keys())}
            total_links = 0
            for cid, nbrs in neighbors.items():
                c = id_to_obj.get(cid)
                if not c or not nbrs:
                    continue
                # Add in batches
                objs = [id_to_obj[nid] for nid in nbrs if nid in id_to_obj and nid != cid]
                if objs:
                    c.adjacent.add(*objs)
                    total_links += len(objs)

        self.stdout.write(self.style.SUCCESS(
            f"Adjacency populated successfully. Communities updated: {len(neighbors)}; links set: {total_links}."
        ))
