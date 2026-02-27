from django.db import models
import uuid
from django.utils import timezone


class Site(models.Model):
    """
    Site - Static identity only.
    Stores only the site name and basic unchanging information.
    All year-specific data is stored in SiteCensusData.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site_name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.site_name


class SiteCensusData(models.Model):
    """
    SiteCensusData - Year-wise versioned data for sites.
    Stores all time-varying attributes tied to a specific census year.
    """
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
    
    site = models.ForeignKey(
        Site,
        related_name='census_data',
        on_delete=models.CASCADE
    )
    census_year = models.ForeignKey(
        'community.CensusYear',
        related_name='site_data',
        on_delete=models.CASCADE
    )
    community = models.ForeignKey(
        'community.Community',
        related_name='site_census_data',
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    
    site_type = models.CharField(max_length=50, choices=SITE_TYPE_CHOICES)
    operator_type = models.CharField(max_length=50, choices=OPERATOR_TYPE_CHOICES, blank=True, null=True)
    service_partner = models.CharField(max_length=255, blank=True, null=True)
    
    
    # Location and address information
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    address_city = models.CharField(max_length=100)
    address_postal_code = models.CharField(max_length=20)
    region = models.CharField(max_length=20)
    service_area = models.CharField(max_length=100, blank=True, null=True)
    
    address_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    address_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    longitude = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    
    # Year-specific status
    is_active = models.BooleanField(default=True, db_index=True)
    site_start_date = models.DateTimeField(null=True, blank=True)
    site_end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Program participation (year-specific)
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
    
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('site', 'census_year')
        verbose_name = "Site Census Data"
        verbose_name_plural = "Site Census Data"
        ordering = ['-census_year__year', 'site__site_name']
        indexes = [
            models.Index(fields=['site', 'census_year']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.site.site_name} - {self.census_year.year}"
    
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
        
        # Auto-deactivate if end date has passed
        if self.site_end_date and self.site_end_date < timezone.now():
            self.is_active = False
        
        super().save(*args, **kwargs)
