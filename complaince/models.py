from django.db import models


class ComplianceCalculation(models.Model):
    """
    Stores compliance calculation results for a specific census year.
    """
    community = models.ForeignKey(
        'community.Community',
        on_delete=models.CASCADE,
        related_name='compliance_calculations'
    )
    census_year = models.ForeignKey(
        'community.CensusYear',
        on_delete=models.CASCADE,
        related_name='compliance_calculations',
        null=True,
        blank=True
    )
    program = models.CharField(max_length=100)
    # Base required before any Tool A Direct Service Offset is applied.
    base_required_sites = models.IntegerField(default=0)
    # Applied Tool A offset percentage (global or per-community override).
    direct_service_offset_percentage = models.IntegerField(null=True, blank=True)
    # 'global', 'community', or '' when no offset applied.
    direct_service_offset_source = models.CharField(max_length=20, blank=True, default='')
    # Breakdown of site requirements
    sites_from_requirements = models.IntegerField(default=0, help_text="Sites required based on population and regulations")
    sites_from_adjacent = models.IntegerField(default=0, help_text="Sites from adjacent community reallocations")
    sites_from_events = models.IntegerField(default=0, help_text="Sites from approved events")
    net_direct_service_offset = models.IntegerField(default=0, help_text="Net direct service offset applied")
    required_sites = models.IntegerField()
    actual_sites = models.IntegerField()
    shortfall = models.IntegerField(default=0)
    excess = models.IntegerField(default=0)
    compliance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    calculation_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compliance_calculations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compliance_calculations'
        ordering = ['-calculation_date']
        unique_together = [['community', 'program', 'census_year']]
        indexes = [
            models.Index(fields=['community', 'program', 'census_year']),
            models.Index(fields=['calculation_date']),
            models.Index(fields=['census_year']),
        ]
    
    def __str__(self):
        year_str = f" ({self.census_year.year})" if self.census_year else ""
        return f"{self.community.name} - {self.program}{year_str}: {self.compliance_rate}%"


class DirectServiceOffset(models.Model):
    """
    Tool A: per-program, per-census-year global percentage reduction applied to required sites.
    """

    PROGRAM_CHOICES = [
        ('Paint', 'Paint'),
        ('Lighting', 'Lighting'),
        ('Solvents', 'Solvents'),
        ('Pesticides', 'Pesticides'),
        ('Fertilizers', 'Fertilizers'),
    ]

    census_year = models.ForeignKey(
        'community.CensusYear',
        on_delete=models.CASCADE,
        related_name='direct_service_offsets',
    )
    program = models.CharField(max_length=100, choices=PROGRAM_CHOICES, db_index=True)
    percentage = models.IntegerField(default=0)  # 0-100
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('census_year', 'program')]
        indexes = [
            models.Index(fields=['census_year', 'program', 'is_active']),
        ]

    def __str__(self):
        return f"{self.program} {self.census_year.year}: {self.percentage}%"


class CommunityOffset(models.Model):
    """
    Tool A: per-community override percentage (wins over DirectServiceOffset if active).
    """

    PROGRAM_CHOICES = DirectServiceOffset.PROGRAM_CHOICES

    census_year = models.ForeignKey(
        'community.CensusYear',
        on_delete=models.CASCADE,
        related_name='community_offsets',
    )
    program = models.CharField(max_length=100, choices=PROGRAM_CHOICES, db_index=True)
    community = models.ForeignKey(
        'community.Community',
        on_delete=models.CASCADE,
        related_name='community_offsets',
    )
    percentage = models.IntegerField(default=0)  # 0-100
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('census_year', 'program', 'community')]
        indexes = [
            models.Index(fields=['census_year', 'program', 'community', 'is_active']),
        ]

    def __str__(self):
        return f"{self.community.name} {self.program} {self.census_year.year}: {self.percentage}%"
