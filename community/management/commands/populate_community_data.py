from django.core.management.base import BaseCommand
from community.models import Community


class Command(BaseCommand):
    help = 'Populate dummy data for Community'

    def handle(self, *args, **options):
        Community.objects.all().delete()

        communities = [
            {
                'name': 'Springfield',
                'population': 50000,
                'tier': 'Urban',
                'region': 'Central',
                'zone': 'North',
                'province': 'Ontario',
                'year': 2023,
                'is_active': True,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Riverside',
                'population': 30000,
                'tier': 'Suburban',
                'region': 'East',
                'zone': 'South',
                'province': 'Quebec',
                'year': 2023,
                'is_active': False,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Mountainview',
                'population': 15000,
                'tier': 'Rural',
                'region': 'West',
                'zone': 'Central',
                'province': 'British Columbia',
                'year': 2022,
                'is_active': True,
                'start_date': '2022-01-01T00:00:00Z',
                'end_date': '2023-12-31T23:59:59Z',
            },
            {
                'name': 'Lakeside',
                'population': 8000,
                'tier': 'Small Town',
                'region': 'North',
                'zone': 'East',
                'province': 'Alberta',
                'year': 2023,
                'is_active': False,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Hilltop',
                'population': 25000,
                'tier': 'Urban',
                'region': 'South',
                'zone': 'West',
                'province': 'Manitoba',
                'year': 2022,
                'is_active': True,
                'start_date': '2022-01-01T00:00:00Z',
                'end_date': '2023-12-31T23:59:59Z',
            },
            {
                'name': 'Valley',
                'population': 12000,
                'tier': 'Suburban',
                'region': 'Central',
                'zone': 'North',
                'province': 'Saskatchewan',
                'year': 2023,
                'is_active': False,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Forest',
                'population': 6000,
                'tier': 'Rural',
                'region': 'East',
                'zone': 'South',
                'province': 'Nova Scotia',
                'year': 2022,
                'is_active': True,
                'start_date': '2022-01-01T00:00:00Z',
                'end_date': '2023-12-31T23:59:59Z',
            },
            {
                'name': 'Bayview',
                'population': 18000,
                'tier': 'Small Town',
                'region': 'West',
                'zone': 'Central',
                'province': 'New Brunswick',
                'year': 2023,
                'is_active': False,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Sunset',
                'population': 40000,
                'tier': 'Urban',
                'region': 'North',
                'zone': 'East',
                'province': 'Ontario',
                'year': 2022,
                'is_active': True,
                'start_date': '2022-01-01T00:00:00Z',
                'end_date': '2023-12-31T23:59:59Z',
            },
            {
                'name': 'Prairie',
                'population': 9000,
                'tier': 'Suburban',
                'region': 'South',
                'zone': 'West',
                'province': 'Alberta',
                'year': 2023,
                'is_active': False,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
        ]

        for community_data in communities:
            Community.objects.create(**community_data)

        self.stdout.write('Successfully populated dummy data!')
