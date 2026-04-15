from django.db import models
from django.db.models import Q
from django.utils import timezone
import uuid


class CensusYear(models.Model):
    """
    Census Year - represents a specific year for data collection.
    """
    year = models.PositiveIntegerField(unique=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return str(self.year)
    
    def save(self, *args, **kwargs):
        """
        Auto-create census data records for all active communities and sites
        when a new census year is created.
        Also sets the end_date of the previous census year.
        """
        is_new = self.pk is None
        if is_new:
            # Set end_date of previous census year to this census year's start_date
            previous_year = CensusYear.objects.filter(year__lt=self.year).order_by('-year').first()
            if previous_year and not previous_year.end_date:
                previous_year.end_date = self.start_date
                previous_year.save(update_fields=['end_date'])
        
        super().save(*args, **kwargs)
        
        if is_new:
            # Import here to avoid circular imports
            from sites.models import Site, SiteCensusData
            from regulatory_rules.models import RegulatoryRule, RegulatoryRuleCensusData
            
            # Get communities that have their latest census data as active
            active_communities = []
            for community in Community.objects.all():
                latest_census = community.census_data.order_by('-census_year__year').first()
                if latest_census and latest_census.is_active:
                    active_communities.append(community)
            
            # Create CommunityCensusData for each active community
            for community in active_communities:
                # Get the latest census data for this community to copy values
                latest_census = community.census_data.filter(
                    is_active=True
                ).order_by('-census_year__year').first()
                
                if latest_census:
                    CommunityCensusData.objects.create(
                        community=community,
                        census_year=self,
                        population=latest_census.population,
                        tier=latest_census.tier,
                        region=latest_census.region,
                        zone=latest_census.zone,
                        province=latest_census.province,
                        is_active=True,
                        start_date=latest_census.start_date,
                        end_date=latest_census.end_date,
                    )
            
            # Get sites that have their latest census data as active
            active_sites = []
            for site in Site.objects.all():
                latest_census = site.census_data.order_by('-census_year__year').first()
                if latest_census and latest_census.is_active:
                    active_sites.append(site)
            
            # Create SiteCensusData for each active site
            for site in active_sites:
                # Get the latest census data for this site to copy values
                latest_census = site.census_data.filter(
                    is_active=True
                ).order_by('-census_year__year').first()
                
                if latest_census:
                    SiteCensusData.objects.create(
                        site=site,
                        census_year=self,
                        community=latest_census.community,
                        site_type=latest_census.site_type,
                        operator_type=latest_census.operator_type,
                        service_partner=latest_census.service_partner,
                        address_line_1=latest_census.address_line_1,
                        address_line_2=latest_census.address_line_2,
                        address_city=latest_census.address_city,
                        address_postal_code=latest_census.address_postal_code,
                        region=latest_census.region,
                        service_area=latest_census.service_area,
                        address_latitude=latest_census.address_latitude,
                        address_longitude=latest_census.address_longitude,
                        latitude=latest_census.latitude,
                        longitude=latest_census.longitude,
                        is_active=True,
                        site_start_date=latest_census.site_start_date,
                        site_end_date=latest_census.site_end_date,
                        program_paint=latest_census.program_paint,
                        program_paint_start_date=latest_census.program_paint_start_date,
                        program_paint_end_date=latest_census.program_paint_end_date,
                        program_lights=latest_census.program_lights,
                        program_lights_start_date=latest_census.program_lights_start_date,
                        program_lights_end_date=latest_census.program_lights_end_date,
                        program_solvents=latest_census.program_solvents,
                        program_solvents_start_date=latest_census.program_solvents_start_date,
                        program_solvents_end_date=latest_census.program_solvents_end_date,
                        program_pesticides=latest_census.program_pesticides,
                        program_pesticides_start_date=latest_census.program_pesticides_start_date,
                        program_pesticides_end_date=latest_census.program_pesticides_end_date,
                        program_fertilizers=latest_census.program_fertilizers,
                        program_fertilizers_start_date=latest_census.program_fertilizers_start_date,
                        program_fertilizers_end_date=latest_census.program_fertilizers_end_date,
                    )
            
            # Get regulatory rules that have their latest census data as active
            active_rules = []
            for rule in RegulatoryRule.objects.all():
                latest_census = rule.census_data.order_by('-census_year__year').first()
                if latest_census and latest_census.is_active:
                    active_rules.append(rule)
            
            # Create RegulatoryRuleCensusData for each active rule
            for rule in active_rules:
                # Get the latest census data for this rule to copy values
                latest_census = rule.census_data.filter(
                    is_active=True
                ).order_by('-census_year__year').first()
                
                if latest_census:
                    RegulatoryRuleCensusData.objects.create(
                        regulatory_rule=rule,
                        census_year=self,
                        program=latest_census.program,
                        category=latest_census.category,
                        rule_type=latest_census.rule_type,
                        min_population=latest_census.min_population,
                        max_population=latest_census.max_population,
                        site_per_population=latest_census.site_per_population,
                        base_required_sites=latest_census.base_required_sites,
                        event_offset_percentage=latest_census.event_offset_percentage,
                        reallocation_percentage=latest_census.reallocation_percentage,
                        is_active=True,
                        start_date=latest_census.start_date,
                        end_date=latest_census.end_date,
                    )


class Community(models.Model):
    """
    Community - Static identity only.
    Stores only the community name and identity.
    All year-specific data is stored in CommunityCensusData.
    Optional boundary (PostGIS) powers map draw + spatial adjacency.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    boundary = models.JSONField(
        null=True,
        blank=True,
        help_text='GeoJSON geometry (Polygon, lon/lat). Used for map adjacency queries.',
    )
    adjacent = models.ManyToManyField(
        'self',
        symmetrical=True,
        blank=True,
        help_text=(
            'Bidirectional map neighbors: touch, overlap, boundary/geometry intersect, '
            'or within a small gap (see community.spatial_sql).'
        ),
    )
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


class AdjacentCommunity(models.Model):
    """
    AdjacentCommunity - Represents adjacency relationships between communities
    with site reallocation capabilities. Sites can be assigned from source to target.
    """
    from_community = models.ForeignKey(
        Community,
        related_name='adjacent_from',
        on_delete=models.CASCADE,
        help_text="Source community with excess sites"
    )
    to_communities = models.ManyToManyField(
        Community,
        related_name='adjacent_to',
        help_text="Target communities with shortfall"
    )

    # Census year
    census_year = models.ForeignKey(
        CensusYear,
        on_delete=models.CASCADE,
        related_name='adjacent_reallocations',
        help_text="Census year for this adjacency"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
