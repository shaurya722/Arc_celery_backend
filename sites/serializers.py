from rest_framework import serializers
from .models import Site, SiteCensusData, SiteReallocation
from community.models import CensusYear, AdjacentCommunity, Community


class SiteSerializer(serializers.ModelSerializer):
    """Serializer for Site static identity with detailed census data"""
    census_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Site
        fields = ['id', 'site_name', 'census_data', 'created_at', 'updated_at']
    
    def get_census_data(self, obj):
        """Return all census data for this site across all years with complete details"""
        census_data_list = []
        for census_data in obj.census_data.all().select_related('census_year', 'community'):
            census_data_list.append({
                'id': census_data.id,
                'site': str(census_data.site.id),
                'site_name': census_data.site.site_name,
                'census_year': census_data.census_year.id,
                'census_year_value': census_data.census_year.year,
                'community': str(census_data.community.id) if census_data.community else None,
                'community_name': census_data.community.name if census_data.community else None,
                'site_type': census_data.site_type,
                'operator_type': census_data.operator_type,
                'service_partner': census_data.service_partner,
                'address_line_1': census_data.address_line_1,
                'address_line_2': census_data.address_line_2,
                'address_city': census_data.address_city,
                'address_postal_code': census_data.address_postal_code,
                'region': census_data.region,
                'service_area': census_data.service_area,
                'is_active': census_data.is_active,
                'site_start_date': census_data.site_start_date,
                'site_end_date': census_data.site_end_date,
                'program_paint': census_data.program_paint,
                'program_lights': census_data.program_lights,
                'program_solvents': census_data.program_solvents,
                'program_pesticides': census_data.program_pesticides,
                'program_fertilizers': census_data.program_fertilizers,
                'created_at': census_data.created_at,
                'updated_at': census_data.updated_at,
            })
        return census_data_list


class SiteCensusDataSerializer(serializers.ModelSerializer):
    """Serializer for year-specific site data with auto-site creation"""
    site_name = serializers.CharField(required=False, allow_blank=False)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True, allow_null=True)
    
    class Meta:
        model = SiteCensusData
        fields = [
            'id', 'site_name', 'census_year', 'census_year_value',
            'community', 'community_name', 'site_type', 'operator_type', 'service_partner',
            'address_line_1', 'address_line_2', 'address_city', 'address_postal_code',
            'region', 'service_area', 'address_latitude', 'address_longitude',
            'latitude', 'longitude', 'is_active', 'site_start_date', 'site_end_date',
            'program_paint', 'program_paint_start_date', 'program_paint_end_date',
            'program_lights', 'program_lights_start_date', 'program_lights_end_date',
            'program_solvents', 'program_solvents_start_date', 'program_solvents_end_date',
            'program_pesticides', 'program_pesticides_start_date', 'program_pesticides_end_date',
            'program_fertilizers', 'program_fertilizers_start_date', 'program_fertilizers_end_date',
            'material_paint', 'material_light_bulbs', 'material_batteries', 'material_oil_filters',
            'material_tires', 'material_electronics', 'material_household_hazardous_waste',
            'sector_residential', 'sector_commercial', 'sector_industrial', 'sector_institutional',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'site': {'required': False}
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For POST/PUT requests, make site accept name/values instead of IDs
        if self.context.get('request') and self.context['request'].method in ['POST', 'PUT', 'PATCH']:
            # Change field types for input
            self.fields['site'] = serializers.CharField(required=False, allow_blank=True)
            self.fields['census_year'] = serializers.IntegerField()

    def validate_site(self, value):
        """Validate and lookup site by name, create if it doesn't exist (for create operations only)"""
        if isinstance(value, str):
            if self.instance:
                # For updates, find the existing site linked to this census data and update its name
                site = self.instance.site
                site.site_name = value
                site.save()
                return site
            else:
                # For creates, get or create the site
                site, created = Site.objects.get_or_create(
                    site_name=value,
                    defaults={'site_name': value}
                )
                return site
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
    
    def create(self, validated_data):
        """Override create to handle site_name field which is not part of the model"""
        # Remove site_name from validated_data as it's not a model field
        validated_data.pop('site_name', None)
        return super().create(validated_data)
    
    def validate(self, data):
        """
        Resolve ``site`` from ``site_name`` when needed.
        Multiple ``SiteCensusData`` rows may share the same ``site`` and ``census_year``; rows are distinct by ``id``.
        """
        instance = self.instance

        site_name = data.pop('site_name', None)
        if site_name and not data.get('site'):
            if instance:
                site = instance.site
                site.site_name = site_name
                site.save()
                data['site'] = site
            else:
                site, created = Site.objects.get_or_create(
                    site_name=site_name,
                    defaults={'site_name': site_name}
                )
                data['site'] = site

        return data
    
    def to_representation(self, instance):
        """Override to include site_name in response"""
        representation = super().to_representation(instance)
        representation['site_name'] = instance.site.site_name
        return representation


class SiteReallocationSerializer(serializers.ModelSerializer):
    """Serializer for site reallocation records (per-program move)."""
    site_name = serializers.CharField(source='site_census_data.site.site_name', read_only=True)
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    to_community_name = serializers.CharField(source='to_community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = SiteReallocation
        fields = [
            'id', 'site_census_data', 'site_name',
            'from_community', 'from_community_name',
            'to_community', 'to_community_name',
            'census_year', 'census_year_value',
            'program',
            'reallocated_at', 'created_by', 'created_by_username', 'reason'
        ]
        read_only_fields = ['id', 'reallocated_at', 'from_community', 'census_year', 'program']


class ReallocateSiteSerializer(serializers.Serializer):
    """Serializer for site reallocation API request"""
    site_census_id = serializers.PrimaryKeyRelatedField(
        queryset=SiteCensusData.objects.select_related('site', 'community', 'census_year'),
        source='site_census_data'
    )
    to_community_id = serializers.PrimaryKeyRelatedField(
        queryset=Community.objects.all(),
        source='to_community'
    )
    program = serializers.ChoiceField(
        choices=['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers'],
        required=False,
        allow_null=True,
        help_text=(
            'Program being reallocated (required when the site has more than one program flag). '
            'Otherwise inferred from the single enabled program.'
        ),
    )
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AdjacentCommunitySerializer(serializers.ModelSerializer):
    """Serializer for adjacent community relationships"""
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    to_communities_data = serializers.SerializerMethodField()
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)
    
    class Meta:
        model = AdjacentCommunity
        fields = [
            'id', 'from_community', 'from_community_name',
            'to_communities', 'to_communities_data',
            'census_year', 'census_year_value',
            'created_at', 'updated_at'
        ]
    
    def get_to_communities_data(self, obj):
        """Return list of adjacent communities with their details"""
        return [
            {'id': str(comm.id), 'name': comm.name}
            for comm in obj.to_communities.all()
        ]