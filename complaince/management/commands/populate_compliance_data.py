from django.core.management.base import BaseCommand
from faker import Faker
from complaince.models import ComplianceCalculation
from complaince.utils import calculate_compliance
from community.models import Community
import random


class Command(BaseCommand):
    help = 'Populate dummy compliance calculation data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=50,
            help='Number of compliance records to create'
        )

    def handle(self, *args, **options):
        fake = Faker()
        count = options['count']
        
        # Get all communities
        communities = list(Community.objects.all())
        if not communities:
            self.stdout.write(
                self.style.WARNING('No communities found. Please populate communities first.')
            )
            return
        
        programs = ['Paint', 'Lighting', 'Solvents', 'Pesticides']
        
        created_count = 0
        for i in range(count):
            community = random.choice(communities)
            program = random.choice(programs)
            
            # Use actual calculation logic instead of random
            metrics = calculate_compliance(community, program)
            
            # Create the record with calculated metrics
            ComplianceCalculation.objects.create(
                community=community,
                program=program,
                required_sites=metrics['required_sites'],
                actual_sites=metrics['actual_sites'],
                shortfall=metrics['shortfall'],
                excess=metrics['excess'],
                compliance_rate=metrics['compliance_rate'],
                created_by=None  # System generated
            )
            
            created_count += 1
            
            if created_count % 10 == 0:
                self.stdout.write(f'Created {created_count} compliance records...')
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully created {created_count} dummy compliance records with calculated data')
        )
