from django.core.management.base import BaseCommand
from django.utils import timezone
from sites.models import Site
from faker import Faker
import random
from django.db.models.signals import post_save
from sites.signals import trigger_compliance_on_save

class Command(BaseCommand):
    help = 'Populate the database with 10 dummy Site records'

    def handle(self, *args, **options):
        fake = Faker()

        # Disconnect signal to avoid errors
        post_save.disconnect(trigger_compliance_on_save, sender=Site)

        for i in range(10):
            site = Site.objects.create(
                site_name=f"Sample Site {i+1}",
            )
        
        # Reconnect signal
        post_save.connect(trigger_compliance_on_save, sender=Site)
        
        self.stdout.write(self.style.SUCCESS('Successfully created  10 dummy sites'))
