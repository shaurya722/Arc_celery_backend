from rest_framework import serializers
from django.db.models import Q
from .models import Community, CensusYear, CommunityCensusData, AdjacentCommunity


class AdjacentCommunityReallocationSerializer(serializers.ModelSerializer):
    """
    Serializer for AdjacentCommunity showing detailed reallocation information
    including source community sites, compliance, excess, and target communities with shortfall
    """
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)

    # Source community details
    from_community_details = serializers.SerializerMethodField()
    # compliance_info = serializers.SerializerMethodField()
    excess_info = serializers.SerializerMethodField()

    # Target communities with shortfall
    target_communities = serializers.SerializerMethodField()

    class Meta:
        model = AdjacentCommunity
        fields = [
            'id', 'from_community', 'from_community_name', 'to_communities',
            'census_year', 'census_year_value', 'from_community_details',
            'excess_info', 'target_communities',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_from_community_details(self, obj):
        """Get detailed information about the source community including its sites"""
        from sites.models import SiteCensusData

        community = obj.from_community
        census_year = obj.census_year

        # Get community census data
        census_data = CommunityCensusData.objects.filter(
            community=community,
            census_year=census_year
        ).first()

        # Get sites for this community and census year
        sites = SiteCensusData.objects.filter(
            community=community,
            census_year=census_year
        ).select_related('site')

        site_details = []
        for site_data in sites:
            site_details.append({
                'id': str(site_data.site.id),
                'site_name': site_data.site.site_name,
            })

        return {
            'id': str(community.id),
            'name': community.name,
            'population': census_data.population if census_data else 0,
            'region': census_data.region if census_data else '',
            'tier': census_data.tier if census_data else '',
            'sites': site_details,
            'total_sites': len(site_details)
        }

    def get_compliance_info(self, obj):
        """Get compliance calculation for the source community"""
        from complaince.models import ComplianceCalculation

        compliance = ComplianceCalculation.objects.filter(
            community=obj.from_community,
            census_year=obj.census_year,
            program__in=['Paint', 'Lighting']  # Check for relevant programs
        ).first()

        if compliance:
            return {
                'program': compliance.program,
                'required_sites': compliance.required_sites,
                'actual_sites': compliance.actual_sites,
                'shortfall': compliance.shortfall,
                'excess': compliance.excess,
                'compliance_rate': str(compliance.compliance_rate),
                'calculation_date': compliance.calculation_date
            }
        return None

    def get_excess_info(self, obj):
        """Calculate and return excess information for the source community from stored compliance data"""
        from complaince.models import ComplianceCalculation

        # Get all compliance calculations for this community and census year
        compliance_records = ComplianceCalculation.objects.filter(
            community=obj.from_community,
            census_year=obj.census_year,
            program__in=['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']
        )

        total_required = 0
        total_actual = 0
        total_excess = 0

        for compliance in compliance_records:
            total_required += compliance.required_sites or 0
            total_actual += compliance.actual_sites or 0
            total_excess += compliance.excess or 0

        return {
            'required_sites': total_required,
            'actual_sites': total_actual,
            'excess_sites': total_excess,
            'has_excess': total_excess > 0,
            'can_reallocate': total_excess > 0
        }

    def get_target_communities(self, obj):
        """Get target communities with shortfall information from stored compliance data"""
        from complaince.models import ComplianceCalculation

        target_data = []
        for target_community in obj.to_communities.all():
            # Get all compliance calculations for this community and census year
            compliance_records = ComplianceCalculation.objects.filter(
                community=target_community,
                census_year=obj.census_year,
                program__in=['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']
            )

            total_required = 0
            total_actual = 0
            total_shortfall = 0

            for compliance in compliance_records:
                total_required += compliance.required_sites or 0
                total_actual += compliance.actual_sites or 0
                total_shortfall += compliance.shortfall or 0

            # Get census data for additional info
            census_data = CommunityCensusData.objects.filter(
                community=target_community,
                census_year=obj.census_year
            ).first()

            target_data.append({
                'id': str(target_community.id),
                'name': target_community.name,
                'population': census_data.population if census_data else 0,
                'region': census_data.region if census_data else '',
                'tier': census_data.tier if census_data else '',
                'required_sites': total_required,
                'actual_sites': total_actual,
                'shortfall': total_shortfall,
                'needs_sites': total_shortfall > 0
            })

        return target_data


class AdjacentCommunitySerializer(serializers.ModelSerializer):
    """Basic serializer for AdjacentCommunity CRUD operations"""
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    to_communities_names = serializers.SerializerMethodField()

    class Meta:
        model = AdjacentCommunity
        fields = [
            'id', 'from_community', 'from_community_name', 'to_communities',
            'to_communities_names', 'census_year', 'created_at', 'updated_at'
        ]

    def get_to_communities_names(self, obj):
        return [comm.name for comm in obj.to_communities.all()]


class CommunitySerializer(serializers.ModelSerializer):
    """Serializer for Community static identity with nested census data"""
    census_years = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = ['id', 'name', 'census_years', 'created_at', 'updated_at']
    
    def get_census_years(self, obj):
        """Return all census data for this community as nested census_years array"""
        census_years_list = []
        for census_data in obj.census_data.all().select_related('census_year'):
            census_years_list.append({
                'id': census_data.id,
                'year': census_data.census_year.year,
                'population': census_data.population,
                'tier': census_data.tier,
                'region': census_data.region,
                'zone': census_data.zone,
                'province': census_data.province,
                'is_active': census_data.is_active,
                'start_date': census_data.start_date,
                'end_date': census_data.end_date,
                'created_at': census_data.created_at,
                'updated_at': census_data.updated_at,
            })
        return census_years_list


class CommunityCensusDataSerializer(serializers.ModelSerializer):
    """Serializer for year-specific community data"""
    community_name = serializers.CharField(source='community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)

    class Meta:
        model = CommunityCensusData
        fields = [
            'id', 'community', 'community_name', 'census_year', 'census_year_value',
            'population', 'tier', 'region', 'zone', 'province',
            'is_active', 'start_date', 'end_date', 'created_at', 'updated_at'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For POST/PUT requests, make community and census_year accept names/values instead of IDs
        if self.context.get('request') and self.context['request'].method in ['POST', 'PUT', 'PATCH']:
            # Change field types for input
            self.fields['community'] = serializers.CharField()
            self.fields['census_year'] = serializers.IntegerField()

    def validate_community(self, value):
        """Validate and lookup community by name, create if it doesn't exist"""
        if isinstance(value, str):
            community, created = Community.objects.get_or_create(name=value)
            return community
        return value

    def validate_census_year(self, value):
        """Validate and lookup census year by year value"""
        if isinstance(value, int):
            try:
                census_year = CensusYear.objects.get(year=value)
                return census_year
            except CensusYear.DoesNotExist:
                raise serializers.ValidationError(f"Census year {value} not found.")
        return value

    def to_representation(self, instance):
        """Override to ensure proper serialization of foreign keys in response"""
        # Temporarily restore original field types for serialization
        self.fields['community'] = serializers.PrimaryKeyRelatedField(queryset=Community.objects.all())
        self.fields['census_year'] = serializers.PrimaryKeyRelatedField(queryset=CensusYear.objects.all())
        return super().to_representation(instance)


class CensusYearSerializer(serializers.ModelSerializer):
    """Serializer for CensusYear"""
    class Meta:
        model = CensusYear
        fields = ['id', 'year', 'created_at', 'updated_at']


class CensusYearWithDataSerializer(serializers.ModelSerializer):
    """Serializer for CensusYear with associated communities, sites, and regulatory rules"""
    communities = serializers.SerializerMethodField()
    sites = serializers.SerializerMethodField()
    regulatory_rules = serializers.SerializerMethodField()
    
    class Meta:
        model = CensusYear
        fields = ['id', 'year', 'communities', 'sites', 'regulatory_rules', 'created_at', 'updated_at']
    
    def get_communities(self, obj):
        """Return communities that have census data for this year"""
        communities_data = []
        for census_data in obj.community_data.filter(is_active=True).select_related('community'):
            community = census_data.community
            communities_data.append({
                'id': str(community.id),
                'name': community.name,
                'population': census_data.population,
                'tier': census_data.tier,
                'region': census_data.region,
                'zone': census_data.zone,
                'province': census_data.province,
                'is_active': census_data.is_active,
                'census_data_id': census_data.id
            })
        return communities_data
    
    def get_sites(self, obj):
        """Return sites that have census data for this year"""
        sites_data = []
        for census_data in obj.site_data.filter(is_active=True).select_related('site', 'community'):
            site = census_data.site
            sites_data.append({
                'id': census_data.id,
                'site_name': site.site_name,
                'site_id': str(site.id),
            })
        return sites_data
    
    def get_regulatory_rules(self, obj):
        """Return regulatory rules that have census data for this year"""
        rules_data = []
        for census_data in obj.regulatory_rule_data.filter(is_active=True).select_related('regulatory_rule'):
            rule = census_data.regulatory_rule
            rules_data.append({
                'id': census_data.id,
                'rule_id': str(rule.id),
                'rule_name': rule.name,
                'description': rule.description,
                'program': census_data.program,
                'category': census_data.category,
                'rule_type': census_data.rule_type,
                'min_population': census_data.min_population,
                'max_population': census_data.max_population,
                'site_per_population': census_data.site_per_population,
                'base_required_sites': census_data.base_required_sites,
                'event_offset_percentage': census_data.event_offset_percentage,
                'reallocation_percentage': census_data.reallocation_percentage,
                'is_active': census_data.is_active,
                'start_date': census_data.start_date,
                'end_date': census_data.end_date
            })
        return rules_data


class MapDataSerializer(serializers.Serializer):
    """Serializer for map data providing sites and municipalities in React component format"""

    def to_representation(self, instance):
        """Transform Django data into React component expected format"""
        request = self.context.get('request')
        census_year_param = request.query_params.get('census_year') if request else None

        # Get census year or use latest
        census_year = None
        if census_year_param:
            try:
                census_year = CensusYear.objects.get(year=int(census_year_param))
            except (CensusYear.DoesNotExist, ValueError):
                census_year = CensusYear.objects.order_by('-year').first()
        else:
            census_year = CensusYear.objects.order_by('-year').first()

        if not census_year:
            return {'sites': [], 'municipalities': []}

        # Filter sites and communities by census year
        # Get municipalities (communities) for this census year
        municipalities_data = []
        for community_data in CommunityCensusData.objects.filter(
            census_year=census_year,
            is_active=True
        ).select_related('community'):
            municipalities_data.append({
                'id': str(community_data.community.id),
                'name': community_data.community.name,
                'tier': community_data.tier or 'Unknown',
                'population': community_data.population or 0,
            })

        # Get sites for this census year
        from sites.models import SiteCensusData
        sites_data = []

        for site_census in SiteCensusData.objects.filter(
            census_year=census_year,
            is_active=True
        ).filter(
            ~Q(site_type='Event') | Q(event_approved=True)
        ).select_related('site', 'community'):
            site = site_census.site
            community = site_census.community

            # Get municipality info
            municipality_info = None
            if community:
                municipality_info = {'name': community.name}

            # Parse programs from the site census data
            programs = []
            if hasattr(site_census, 'program_paint') and site_census.program_paint:
                programs.append('Paint')
            if hasattr(site_census, 'program_lights') and site_census.program_lights:
                programs.append('Lighting')
            if hasattr(site_census, 'program_solvents') and site_census.program_solvents:
                programs.append('Solvents')
            if hasattr(site_census, 'program_pesticides') and site_census.program_pesticides:
                programs.append('Pesticides')
            if hasattr(site_census, 'program_fertilizers') and site_census.program_fertilizers:
                programs.append('Fertilizers')

            # Calculate population served (this might need adjustment based on your business logic)
            population_served = 0
            if community:
                community_census = CommunityCensusData.objects.filter(
                    community=community,
                    census_year=census_year
                ).first()
                if community_census:
                    population_served = community_census.population or 0

            sites_data.append({
                'id': str(site.id),
                'name': site.site_name or 'Unknown Site',
                'address': getattr(site_census, 'address_city', '') or getattr(site, 'location', ''),
                'status': 'Active' if site_census.is_active else 'Inactive',
                'operator_type': getattr(site_census, 'operator_type', 'Unknown'),
                'site_type': getattr(site_census, 'site_type', 'Collection site'),
                'latitude': getattr(site_census, 'latitude', None) or getattr(site_census, 'address_latitude', None) or getattr(site, 'latitude', None),
                'longitude': getattr(site_census, 'longitude', None) or getattr(site_census, 'address_longitude', None) or getattr(site, 'longitude', None),
                'programs': programs,
                'municipality': municipality_info,
                'population_served': population_served,
                'created_at': site_census.created_at.isoformat() if site_census.created_at else None,
                'active_dates': str(site_census.site_start_date) if site_census.site_start_date else None,
            })

        return {
            'sites': sites_data,
            'municipalities': municipalities_data,
            'census_year': {
                'id': census_year.id,
                'year': census_year.year,
            }
        }
