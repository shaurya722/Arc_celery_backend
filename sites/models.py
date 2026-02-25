from django.db import models
import uuid
from community.models import Community


class Site(models.Model):
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
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_name = models.CharField(max_length=255)
    site_type = models.CharField(max_length=50, choices=SITE_TYPE_CHOICES)
    operator_type = models.CharField(max_length=50, choices=OPERATOR_TYPE_CHOICES, blank=True, null=True)
    service_partner = models.CharField(max_length=255, blank=True, null=True)
    
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=100)
    address_postal_code = models.CharField(max_length=20)
    
    # status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    is_active = models.BooleanField(default=True, db_index=True)
    site_start_date = models.DateTimeField(null=True, blank=True)
    site_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    community = models.ForeignKey(
        Community,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='collection_sites'
    )
    region = models.CharField(max_length=20)

    service_area = models.CharField(max_length=100, blank=True, null=True)
    
    address_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    address_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # program 
    program_paint = models.BooleanField(default=False)
    program_paint_start_date = models.DateTimeField(null=True, blank=True)
    program_paint_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
        
    program_lights = models.BooleanField(default=False)
    program_lights_start_date = models.DateTimeField(null=True, blank=True)
    program_lights_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    program_solvents = models.BooleanField(default=False)
    program_solvents_start_date = models.DateTimeField(null=True, blank=True)
    program_solvents_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    program_pesticides = models.BooleanField(default=False)
    program_pesticides_start_date = models.DateTimeField(null=True, blank=True)
    program_pesticides_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    program_fertilizers = models.BooleanField(default=False)
    program_fertilizers_start_date = models.DateTimeField(null=True, blank=True)
    program_fertilizers_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # # Materials
    # material_paint_and_pesticides = models.BooleanField(default=False)
    # material_paint_and_pesticides_start_date = models.DateTimeField(null=True, blank=True)
    # material_paint_and_pesticides_end_date = models.DateTimeField(null=True, blank=True)
    
    # material_solvents = models.BooleanField(default=False)
    # material_solvents_start_date = models.DateTimeField(null=True, blank=True)
    # material_solvents_end_date = models.DateTimeField(null=True, blank=True)
    
    # material_fertilizers = models.BooleanField(default=False)
    # material_fertilizers_start_date = models.DateTimeField(null=True, blank=True)
    # material_fertilizers_end_date = models.DateTimeField(null=True, blank=True)
    
    # material_pesticides = models.BooleanField(default=False)
    # material_pesticides_start_date = models.DateTimeField(null=True, blank=True)
    # material_pesticides_end_date = models.DateTimeField(null=True, blank=True)
    
    # material_lights = models.BooleanField(default=False)
    # material_lights_start_date = models.DateTimeField(null=True, blank=True)
    # material_lights_end_date = models.DateTimeField(null=True, blank=True)

    # material_paintShare = models.BooleanField(default=False)
    # material_paintShare_start_date = models.DateTimeField(null=True, blank=True)
    # material_paintShare_end_date = models.DateTimeField(null=True, blank=True)

    # # Collection Sector
    # residential = models.BooleanField(default=False)
    # residential_start_date = models.DateTimeField(null=True, blank=True)
    # residential_end_date = models.DateTimeField(null=True, blank=True)

    # commercial = models.BooleanField(default=False)
    # commercial_start_date = models.DateTimeField(null=True, blank=True)
    # commercial_end_date = models.DateTimeField(null=True, blank=True)

    # industrial = models.BooleanField(default=False)
    # industrial_start_date = models.DateTimeField(null=True, blank=True)
    # industrial_end_date = models.DateTimeField(null=True, blank=True)

    # institutional = models.BooleanField(default=False)
    # institutional_start_date = models.DateTimeField(null=True, blank=True)
    # institutional_end_date = models.DateTimeField(null=True, blank=True)

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=8,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=11,
        decimal_places=8,
        null=True,
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.site_name
    
    @property
    def is_event(self):
        return self.site_type == 'Event'
    
    @property
    def is_reallocatable(self):
        """Check if site can be reallocated."""
        non_reallocatable = ['Municipal', 'First Nation/Indigenous', 'Regional District']
        return (
            self.site_type != 'Event' and
            self.operator_type not in non_reallocatable
        )
    
    def save(self, *args, **kwargs):
        # Nullify dates if program is disabled
        if not self.program_paint:
            self.program_paint_start_date = None
            self.program_paint_end_date = None
        if not self.program_lights:
            self.program_lights_start_date = None
            self.program_lights_end_date = None
        if not self.program_solvents:
            self.program_solvents_start_date = None
            self.program_solvents_end_date = None
        if not self.program_pesticides:
            self.program_pesticides_start_date = None
            self.program_pesticides_end_date = None
        if not self.program_fertilizers:
            self.program_fertilizers_start_date = None
            self.program_fertilizers_end_date = None
        super().save(*args, **kwargs)
