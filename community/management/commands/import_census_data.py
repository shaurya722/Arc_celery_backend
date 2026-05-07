import csv
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from community.models import CensusYear, Community, CommunityCensusData


class Command(BaseCommand):
    help = (
        "Import CommunityCensusData from a CSV file.\n"
        "CSV columns: community_name,year,population,tier,region,zone,province,is_active\n"
        "Creates CensusYear if missing. Matches communities by name (case-insensitive)."
    )

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str, help="Path to CSV file with census data")
        parser.add_argument(
            "--update",
            action="store_true",
            default=False,
            help="Update existing CommunityCensusData if community+year already exists",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Parse CSV and report what would be imported without writing to DB",
        )

    def handle(self, *args, **options):
        csv_path = Path(options["csv_path"]).expanduser().resolve()
        do_update: bool = options["update"]
        dry_run: bool = options["dry_run"]

        if not csv_path.exists():
            raise CommandError(f"CSV file not found: {csv_path}")

        # Read CSV
        rows = []
        with csv_path.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required_cols = {"community_name", "year", "population", "tier", "region", "zone", "province"}
            if not required_cols.issubset(set(reader.fieldnames or [])):
                raise CommandError(
                    f"CSV must have columns: {', '.join(sorted(required_cols))}. "
                    f"Found: {', '.join(reader.fieldnames or [])}"
                )
            for row in reader:
                rows.append(row)

        if not rows:
            self.stdout.write(self.style.WARNING("No rows found in CSV"))
            return

        # Build community name lookup (case-insensitive)
        community_map = {c.name.upper(): c for c in Community.objects.all().only("id", "name")}

        # Group by year to create CensusYear objects
        years_needed = {int(row["year"]) for row in rows}
        census_years = {}
        for year in years_needed:
            cy, created = CensusYear.objects.get_or_create(year=year, defaults={"start_date": timezone.now()})
            census_years[year] = cy
            if created:
                self.stdout.write(f"Created CensusYear {year}")

        created = 0
        updated = 0
        skipped = 0
        errors = []

        if dry_run:
            self.stdout.write(self.style.NOTICE("Dry run: no changes will be made"))

        with transaction.atomic():
            for i, row in enumerate(rows, start=1):
                name = row["community_name"].strip()
                year = int(row["year"])
                population = int(row["population"])
                tier = row["tier"].strip()
                region = row["region"].strip()
                zone = row["zone"].strip()
                province = row["province"].strip()
                is_active_str = row.get("is_active", "true").strip().lower()
                is_active = is_active_str in {"true", "1", "yes", "active"}

                # Match community
                community = community_map.get(name.upper())
                if not community:
                    errors.append(f"Row {i}: Community '{name}' not found")
                    skipped += 1
                    continue

                census_year = census_years[year]

                if dry_run:
                    self.stdout.write(
                        f"Would import: {community.name} ({year}): pop={population}, tier={tier}, "
                        f"region={region}, zone={zone}, province={province}, active={is_active}"
                    )
                    created += 1
                    continue

                # Check if exists
                existing = CommunityCensusData.objects.filter(
                    community=community, census_year=census_year
                ).first()

                if existing:
                    if do_update:
                        existing.population = population
                        existing.tier = tier
                        existing.region = region
                        existing.zone = zone
                        existing.province = province
                        existing.is_active = is_active
                        existing.save()
                        updated += 1
                    else:
                        skipped += 1
                else:
                    CommunityCensusData.objects.create(
                        community=community,
                        census_year=census_year,
                        population=population,
                        tier=tier,
                        region=region,
                        zone=zone,
                        province=province,
                        is_active=is_active,
                        start_date=timezone.now(),
                    )
                    created += 1

        if errors:
            self.stdout.write(self.style.WARNING(f"\nErrors encountered ({len(errors)}):"))
            for err in errors[:10]:
                self.stdout.write(f"  {err}")
            if len(errors) > 10:
                self.stdout.write(f"  ... and {len(errors) - 10} more")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport complete: created={created}, updated={updated}, skipped={skipped}, errors={len(errors)}"
            )
        )
