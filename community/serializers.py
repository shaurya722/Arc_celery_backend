from rest_framework import serializers
from .models import Community, CensusYear, CommunityCensusData


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
    
    def validate(self, data):
        """
        Custom validation to handle unique_together constraint when updating.
        Allows changing community and census_year if the combination doesn't already exist.
        """
        # Get the instance being updated (if this is an update operation)
        instance = self.instance
        
        # Get community and census_year from data (use existing values if not provided)
        community = data.get('community', instance.community if instance else None)
        census_year = data.get('census_year', instance.census_year if instance else None)
        
        # Check if this combination already exists (excluding the current instance)
        if community and census_year:
            existing = CommunityCensusData.objects.filter(
                community=community,
                census_year=census_year
            )
            
            # If updating, exclude the current instance from the check
            if instance:
                existing = existing.exclude(pk=instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f'Community census data for {community.name} and year {census_year.year} already exists.'
                    ]
                })
        
        return data


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
                'community': str(census_data.community.id) if census_data.community else None,
                'community_name': census_data.community.name if census_data.community else None,
                'site_type': census_data.site_type,
                'operator_type': census_data.operator_type,
                'region': census_data.region,
                'address_city': census_data.address_city,
                'is_active': census_data.is_active,
                'program_paint': census_data.program_paint,
                'program_lights': census_data.program_lights,
                'program_solvents': census_data.program_solvents,
                'program_pesticides': census_data.program_pesticides,
                'program_fertilizers': census_data.program_fertilizers
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
