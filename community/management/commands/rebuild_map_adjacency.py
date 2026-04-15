from django.core.management.base import BaseCommand

from community.spatial_sql import rebuild_adjacent_for_all_communities_with_boundaries


class Command(BaseCommand):
    help = 'Recompute Community.adjacent for all rows with a boundary (after rule changes or bad data).'

    def handle(self, *args, **options):
        rebuild_adjacent_for_all_communities_with_boundaries()
        self.stdout.write(self.style.SUCCESS('Map adjacency rebuilt for all communities with boundaries.'))
