from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from community.models import CensusYear, Community, CommunityCensusData


class Command(BaseCommand):
    help = (
        "Create a CensusYear and ensure every Community has CommunityCensusData for that year.\n"
        "If a community already has data for the year, it is left unchanged.\n"
        "If not, a new CommunityCensusData row is created with provided defaults."
    )

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, default=2000, help="Census year to create/seed (default: 2000)")
        parser.add_argument("--population", type=int, default=0, help="Default population for new rows (default: 0)")
        parser.add_argument("--tier", type=str, default="", help="Default tier value for new rows")
        parser.add_argument("--region", type=str, default="", help="Default region value for new rows")
        parser.add_argument("--zone", type=str, default="", help="Default zone value for new rows")
        parser.add_argument("--province", type=str, default="", help="Default province value for new rows")
        parser.add_argument("--inactive", action="store_true", default=False, help="Create rows as inactive (default: active)")

    def handle(self, *args, **options):
        year: int = options["year"]
        default_population: int = options["population"]
        default_tier: str = options["tier"]
        default_region: str = options["region"]
        default_zone: str = options["zone"]
        default_province: str = options["province"]
        create_inactive: bool = options["inactive"]

        # Get or create the census year
        census_year, created = CensusYear.objects.get_or_create(year=year, defaults={
            "start_date": timezone.now(),
        })
        if created:
            self.stdout.write(self.style.SUCCESS(f"Created CensusYear {year}"))
        else:
            self.stdout.write(f"Using existing CensusYear {year}")

        created_count = 0
        skipped_count = 0

        communities = Community.objects.all().only("id", "name")
        now = timezone.now()

        with transaction.atomic():
            for community in communities.iterator():
                exists = CommunityCensusData.objects.filter(community=community, census_year=census_year).exists()
                if exists:
                    skipped_count += 1
                    continue
                CommunityCensusData.objects.create(
                    community=community,
                    census_year=census_year,
                    population=default_population,
                    tier=default_tier,
                    region=default_region,
                    zone=default_zone,
                    province=default_province,
                    is_active=not create_inactive,
                    start_date=now,
                    end_date=None,
                )
                created_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeding complete for {year}: created={created_count}, existing_skipped={skipped_count}"
        ))
