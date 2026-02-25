from django.db import models
import uuid

class RegulatoryRule(models.Model):
    PROGRAM_CHOICES = [
        ('Paint', 'Paint (HSP)'),
        ('Lighting', 'Lighting (EEE)'),
        ('Solvents', 'Solvents (HSP)'),
        ('Pesticides', 'Pesticides (HSP)'),
    ]

    CATEGORIES_CHOICES = [
        ('HSP', 'HSP'),
        ('EEE', 'EEE'),
        ('Other', 'Other'),
    ]

    RULE_CHOICES = [
        ('Site Requirements', 'Site Requirements'),
        ('Reallocation', 'Reallocation'),
        ('Events', 'Events'),
        ('Offsets', 'Offsets'),
    ]

    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    year = models.IntegerField()
    program = models.CharField(max_length=100, choices=PROGRAM_CHOICES)
    category = models.CharField(max_length=100, choices=CATEGORIES_CHOICES)
    rule_type = models.CharField(max_length=100, choices=RULE_CHOICES)

    # Site Calculation
    min_population = models.IntegerField(null=True, blank=True)
    max_population = models.IntegerField(null=True, blank=True)
    site_per_population = models.IntegerField(null=True, blank=True)
    base_required_sites = models.IntegerField(null=True, blank=True)
    
    # Events
    event_offset_percentage = models.IntegerField(null=True, blank=True)
    
    # Reallocation
    reallocation_percentage = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=False, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        # Set percentage fields based on rule_type
        if self.rule_type == 'Reallocation':
            self.event_offset_percentage = None
        elif self.rule_type == 'Events':
            self.reallocation_percentage = None
        else:
            # For other rule_types, ensure both are None
            self.event_offset_percentage = None
            self.reallocation_percentage = None
        
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
