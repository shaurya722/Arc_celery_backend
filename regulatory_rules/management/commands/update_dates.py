from django.core.management.base import BaseCommand
from regulatory_rules.models import RegulatoryRule
from community.models import Community
from django.utils import timezone


class Command(BaseCommand):
    help = 'Update existing records with null start_date and end_date'

    def handle(self, *args, **options):
        # Update RegulatoryRule
        regulatory_rules = RegulatoryRule.objects.filter(start_date__isnull=True)
        for rule in regulatory_rules:
            rule.start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            rule.end_date = rule.start_date.replace(year=rule.start_date.year + 1) - timezone.timedelta(seconds=1)
            rule.save()

        # Update Community
        communities = Community.objects.filter(start_date__isnull=True)
        for community in communities:
            community.start_date = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
            community.end_date = community.start_date.replace(year=community.start_date.year + 1) - timezone.timedelta(seconds=1)
            community.save()

        self.stdout.write(self.style.SUCCESS(f'Updated {regulatory_rules.count()} RegulatoryRules and {communities.count()} Communities with dates.'))
