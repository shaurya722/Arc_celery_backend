from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models.signals import post_save
from sites.models import Site, SiteCensusData
from community.models import Community, CommunityCensusData, CensusYear
from sites.signals import recalculate_compliance_on_site_census_change
from faker import Faker
import random

class Command(BaseCommand):
    help = 'Populate the database with comprehensive dummy data for testing'

    def handle(self, *args, **options):
        # Disconnect signal to avoid any issues
        post_save.disconnect(recalculate_compliance_on_site_census_change, sender=SiteCensusData)

        # Create Census Years
        self.stdout.write('Creating 5 dummy Census Years...')
        for i in range(5):
            CensusYear.objects.get_or_create(
                year=2020 + i,
                defaults={'description': f'Census Year {2020 + i}'}
            )

        # Create Communities
        self.stdout.write('Creating 5 dummy Communities...')
        for i in range(5):
            Community.objects.get_or_create(
                name=f'Community {i+1}',
                defaults={
                    'region': 'Test Region',
                    'tier': 'Tier 1'
                }
            )

        # Reconnect signal
        post_save.connect(recalculate_compliance_on_site_census_change, sender=SiteCensusData)

        self.stdout.write(
            self.style.SUCCESS(
                'Successfully created 5 dummy records for CensusYear and Community'
            )
        )
