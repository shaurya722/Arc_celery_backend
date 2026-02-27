from django.db import models
from django.utils import timezone
import uuid


class CensusYear(models.Model):
    """
    Census Year - represents a specific year for data collection.
    """
    year = models.PositiveIntegerField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return str(self.year)


class Community(models.Model):
    """
    Community - Static identity only.
    Stores only the community name and identity.
    All year-specific data is stored in CommunityCensusData.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Communities"
        ordering = ['name']

    def __str__(self):
        return self.name


class CommunityCensusData(models.Model):
    """
    CommunityCensusData - Year-wise versioned data for communities.
    Stores all time-varying attributes tied to a specific census year.
    """
    community = models.ForeignKey(
        Community,
        related_name='census_data',
        on_delete=models.CASCADE
    )
    census_year = models.ForeignKey(
        CensusYear,
        related_name='community_data',
        on_delete=models.CASCADE
    )
    
    # Year-specific demographic data
    population = models.PositiveIntegerField()
    tier = models.CharField(max_length=50)
    region = models.CharField(max_length=50)
    zone = models.CharField(max_length=50)
    province = models.CharField(max_length=50)
    
    # Year-specific status
    is_active = models.BooleanField(default=True, db_index=True)
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True, db_index=True)
    
    # Sites associated with this community in this census year
    sites = models.ManyToManyField('sites.Site', related_name='community_census_data', blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('community', 'census_year')
        verbose_name = "Community Census Data"
        verbose_name_plural = "Community Census Data"
        ordering = ['-census_year__year', 'community__name']
        indexes = [
            models.Index(fields=['community', 'census_year']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.community.name} - {self.census_year.year}"
    
    def save(self, *args, **kwargs):
        # Auto-deactivate if end date has passed
        if self.end_date and self.end_date < timezone.now():
            self.is_active = False
        super().save(*args, **kwargs)
