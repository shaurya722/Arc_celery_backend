from django.core.management.base import BaseCommand
from django.utils import timezone
from sites.models import Site
from faker import Faker
import random

class Command(BaseCommand):
    help = 'Populate the database with 10 dummy Site records'

    def handle(self, *args, **options):
        fake = Faker()
        # Choices from the model
        SITE_TYPE_CHOICES = [
            ('Collection Site', 'Collection Site'),
            ('Event', 'Event'),
            ('Municipal Depot', 'Municipal Depot'),
            ('Seasonal Depot', 'Seasonal Depot'),
            ('Return to Retail', 'Return to Retail'),
            ('Private Depot', 'Private Depot'),
        ]
        
        OPERATOR_TYPE_CHOICES = [
            ('Retailer', 'Retailer'),
            ('Distributor', 'Distributor'),
            ('Municipal', 'Municipal'),
            ('First Nation/Indigenous', 'First Nation/Indigenous'),
            ('Private Depot', 'Private Depot'),
            ('Product Care', 'Product Care'),
            ('Regional District', 'Regional District'),
            ('Regional Service Commission', 'Regional Service Commission'),
            ('Other', 'Other'),
        ]

        for i in range(10):
            start_date = fake.date_time_this_year()
            end_date = start_date.replace(year=start_date.year + 1)
            
            site = Site.objects.create(
                site_name=f"Sample Site {i+1}",
                site_type=random.choice(SITE_TYPE_CHOICES)[0],
                operator_type=random.choice(OPERATOR_TYPE_CHOICES)[0],
                service_partner=f"Partner {i+1}",
                address_line_1=f"{100 + i} Sample Street",
                address_line_2=f"Apt {i+1}" if i % 2 == 0 else "",
                address_city=f"City {i+1}",
                address_postal_code=f"V{i+1}A 1B{i}",
                is_active=random.choice([True, False]),
                site_start_date=start_date,
                site_end_date=end_date,
                region=f"Region {(i % 3) + 1}",
                service_area=f"Area {i+1}",
                address_latitude=49.0 + random.uniform(-0.5, 0.5),
                address_longitude=-123.0 + random.uniform(-0.5, 0.5),
                
                # Program fields
                program_paint=random.choice([True, False]),
                program_lights=random.choice([True, False]),
                program_solvents=random.choice([True, False]),
                program_pesticides=random.choice([True, False]),
                program_fertilizers=random.choice([True, False]),
                
                latitude=49.0 + random.uniform(-0.5, 0.5),
                longitude=-123.0 + random.uniform(-0.5, 0.5),
            )
            
            # Set dates if fields are true
            if site.program_paint:
                site.program_paint_start_date = start_date
                site.program_paint_end_date = end_date
            if site.program_lights:
                site.program_lights_start_date = start_date
                site.program_lights_end_date = end_date
            if site.program_solvents:
                site.program_solvents_start_date = start_date
                site.program_solvents_end_date = end_date
            if site.program_pesticides:
                site.program_pesticides_start_date = start_date
                site.program_pesticides_end_date = end_date
            if site.program_fertilizers:
                site.program_fertilizers_start_date = start_date
                site.program_fertilizers_end_date = end_date
                
            site.save()
        
        self.stdout.write(self.style.SUCCESS('Successfully created 10 dummy sites'))
