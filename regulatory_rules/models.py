from django.db import models
from django.utils import timezone
import uuid


class RegulatoryRule(models.Model):
    """
    RegulatoryRule - Static identity only.
    Stores only the rule name and basic unchanging information.
    All year-specific data is stored in RegulatoryRuleCensusData.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class RegulatoryRuleCensusData(models.Model):
    """
    RegulatoryRuleCensusData - Year-wise versioned data for regulatory rules.
    Stores all time-varying attributes tied to a specific census year.
    """
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
    
    regulatory_rule = models.ForeignKey(
        RegulatoryRule,
        related_name='census_data',
        on_delete=models.CASCADE
    )
    census_year = models.ForeignKey(
        'community.CensusYear',
        related_name='regulatory_rule_data',
        on_delete=models.CASCADE
    )
    
    program = models.CharField(max_length=100, choices=PROGRAM_CHOICES)
    category = models.CharField(max_length=100, choices=CATEGORIES_CHOICES)
    rule_type = models.CharField(max_length=100, choices=RULE_CHOICES)

    # Site Calculation
    min_population = models.IntegerField(null=True, blank=True)
    max_population = models.IntegerField(null=True, blank=True)
    site_per_population = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    base_required_sites = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    
    # Events
    event_offset_percentage = models.IntegerField(null=True, blank=True)
    
    # Reallocation
    reallocation_percentage = models.IntegerField(null=True, blank=True)
    
    is_active = models.BooleanField(default=False, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('regulatory_rule', 'census_year')
        verbose_name = "Regulatory Rule Census Data"
        verbose_name_plural = "Regulatory Rule Census Data"
        ordering = ['-census_year__year', 'regulatory_rule__name']
        indexes = [
            models.Index(fields=['regulatory_rule', 'census_year']),
            models.Index(fields=['is_active']),
            models.Index(fields=['program', 'rule_type']),
        ]
    
    def __str__(self):
        return f"{self.regulatory_rule.name} - {self.census_year.year}"
    
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
        
        # Auto-deactivate if end date has passed
        if self.end_date and self.end_date < timezone.now():
            self.is_active = False
        
        super().save(*args, **kwargs)
