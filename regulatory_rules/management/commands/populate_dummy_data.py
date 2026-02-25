from django.core.management.base import BaseCommand
from regulatory_rules.models import RegulatoryRule

class Command(BaseCommand):
    help = 'Populate dummy data for regulatory_rules app'

    def handle(self, *args, **options):
        self.stdout.write('Creating dummy data...')

        # Create 10 dummy rules with string choices
        rules_data = [
            {
                'name': 'Rule 1',
                'description': 'Description 1',
                'year': 2023,
                'program': 'Paint',
                'category': 'HSP',
                'rule_type': 'Site Requirements',
                'min_population': 1000,
                'max_population': 5000,
                'site_per_population': 10,
                'base_required_sites': 5,
                'is_active': True,
                'start_date': '2023-01-01T00:00:00Z',
                'end_date': '2024-12-31T23:59:59Z',
            },
            {
                'name': 'Rule 2',
                'description': 'Description 2',
                'year': 2022,
                'program': 'Paint',
                'category': 'HSP',
                'rule_type': 'Site Requirements',
                'min_population': 500,
                'max_population': 3000,
                'site_per_population': 8,
                'base_required_sites': 3,
                'is_active': True,
                'start_date': '2022-01-01T00:00:00Z',
                'end_date': '2023-12-31T23:59:59Z',
            },
            {
                'name': 'Rule 3',
                'description': 'Description 3',
                'year': 2023,
                'program': 'Paint',
                'category': 'HSP',
                'rule_type': 'Site Requirements',
                'min_population': 2000,
                'max_population': 10000,
                'site_per_population': 15,
                'base_required_sites': 10,
                'is_active': True,
                'start_date': '2023-06-01T00:00:00Z',
                'end_date': '2025-05-31T23:59:59Z',
            },
            {
                'name': 'Expired Rule',
                'description': 'This rule is expired',
                'year': 2021,
                'program': 'Paint',
                'category': 'HSP',
                'rule_type': 'Site Requirements',
                'min_population': 100,
                'max_population': 1000,
                'site_per_population': 5,
                'base_required_sites': 2,
                'is_active': True,
                'start_date': '2021-01-01T00:00:00Z',
                'end_date': '2022-12-31T23:59:59Z',  # Past date
            },
            {'name': 'Rule 5', 'description': 'Description 5', 'year': 2024, 'program': 'Lighting', 'category': 'EEE', 'rule_type': 'Reallocation', 'reallocation_percentage': 15, 'is_active': False, 'start_date': '2024-01-01T00:00:00Z', 'end_date': '2025-12-31T23:59:59Z'},
            {'name': 'Rule 6', 'description': 'Description 6', 'year': 2024, 'program': 'Solvents', 'category': 'HSP', 'rule_type': 'Events', 'event_offset_percentage': 40, 'is_active': True, 'start_date': '2024-01-01T00:00:00Z', 'end_date': '2025-12-31T23:59:59Z'},
            {'name': 'Rule 7', 'description': 'Description 7', 'year': 2023, 'program': 'Paint', 'category': 'EEE', 'rule_type': 'Site Requirements', 'min_population': 500, 'max_population': 3000, 'site_per_population': 8, 'base_required_sites': 3, 'is_active': True, 'start_date': '2023-01-01T00:00:00Z', 'end_date': '2024-12-31T23:59:59Z'},
            {'name': 'Rule 8', 'description': 'Description 8', 'year': 2023, 'program': 'Lighting', 'category': 'HSP', 'rule_type': 'Reallocation', 'reallocation_percentage': 12, 'is_active': True, 'start_date': '2023-01-01T00:00:00Z', 'end_date': '2024-12-31T23:59:59Z'},
            {'name': 'Rule 9', 'description': 'Description 9', 'year': 2024, 'program': 'Solvents', 'category': 'EEE', 'rule_type': 'Events', 'event_offset_percentage': 30, 'is_active': False, 'start_date': '2024-01-01T00:00:00Z', 'end_date': '2025-12-31T23:59:59Z'},
            {'name': 'Rule 10', 'description': 'Description 10', 'year': 2024, 'program': 'Paint', 'category': 'Other', 'rule_type': 'Site Requirements', 'min_population': 1500, 'max_population': 7000, 'site_per_population': 12, 'base_required_sites': 7, 'is_active': True, 'start_date': '2024-01-01T00:00:00Z', 'end_date': '2025-12-31T23:59:59Z'},
        ]

        for rule_data in rules_data:
            RegulatoryRule.objects.get_or_create(**rule_data)

        self.stdout.write(self.style.SUCCESS('Successfully populated dummy data!'))
