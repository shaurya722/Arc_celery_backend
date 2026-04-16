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
    event_approved = models.BooleanField(default=False, help_text="Whether this Event site has been approved by the user")
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
    
    # Materials services (year-specific)
    material_paint = models.BooleanField(default=False)
    material_light_bulbs = models.BooleanField(default=False)
    material_batteries = models.BooleanField(default=False)
    material_oil_filters = models.BooleanField(default=False)
    material_tires = models.BooleanField(default=False)
    material_electronics = models.BooleanField(default=False)
    material_household_hazardous_waste = models.BooleanField(default=False)
    
    # Collection sectors (year-specific)
    sector_residential = models.BooleanField(default=False)
    sector_commercial = models.BooleanField(default=False)
    sector_industrial = models.BooleanField(default=False)
    sector_institutional = models.BooleanField(default=False)
    
    
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
        # For Event sites: sync is_active and event_approved bidirectionally
        if self.site_type == 'Event':
            # If this is a new Event site being created, set it as active by default
            if not self.pk:  # New instance
                self.is_active = True
                self.event_approved = True
            else:
                # For existing Event sites, ensure both properties are always in sync
                # If event_approved is set to false, is_active should also be false
                # If event_approved is set to true, is_active should also be true
                # Both properties should change together in either direction
                self.is_active = self.event_approved
        
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
    
    @property
    def effective_community(self):
        """
        Returns the effective community after considering reallocations.
        If site has been reallocated, returns the latest destination community.
        Otherwise, returns the original community.
        """
        latest_reallocation = self.reallocations.order_by('-reallocated_at').first()
        return latest_reallocation.to_community if latest_reallocation else self.community


class SiteReallocation(models.Model):
    """
    Tracks adjacent reallocation history from one community to another.
    SiteReallocationService creates these records and keeps SiteCensusData.community
    in sync with the latest allocation for compliance and listings.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    site_census_data = models.ForeignKey(
        SiteCensusData,
        on_delete=models.CASCADE,
        related_name='reallocations'
    )
    
    from_community = models.ForeignKey(
        'community.Community',
        on_delete=models.CASCADE,
        related_name='reallocations_from'
    )
    
    to_community = models.ForeignKey(
        'community.Community',
        on_delete=models.CASCADE,
        related_name='reallocations_to'
    )
    
    census_year = models.ForeignKey(
        'community.CensusYear',
        on_delete=models.CASCADE,
        related_name='site_reallocations'
    )
    
    reallocated_at = models.DateTimeField(auto_now_add=True)
    
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    reason = models.TextField(blank=True, null=True, help_text="Reason for reallocation")
    
    class Meta:
        verbose_name = 'Adjacent site allocation'
        verbose_name_plural = 'Adjacent site allocations'
        ordering = ['-reallocated_at']
        indexes = [
            models.Index(fields=['site_census_data', '-reallocated_at']),
            models.Index(fields=['from_community', 'census_year']),
            models.Index(fields=['to_community', 'census_year']),
        ]
    
    def __str__(self):
        return f"{self.site_census_data.site.site_name}: {self.from_community.name} → {self.to_community.name}"