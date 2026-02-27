from rest_framework import serializers
from .models import Site, SiteCensusData


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
            'id', 'site', 'site_name', 'census_year', 'census_year_value',
            'community', 'community_name', 'site_type', 'operator_type', 'service_partner',
            'address_line_1', 'address_line_2', 'address_city', 'address_postal_code',
            'region', 'service_area', 'address_latitude', 'address_longitude',
            'latitude', 'longitude', 'is_active', 'site_start_date', 'site_end_date',
            'program_paint', 'program_paint_start_date', 'program_paint_end_date',
            'program_lights', 'program_lights_start_date', 'program_lights_end_date',
            'program_solvents', 'program_solvents_start_date', 'program_solvents_end_date',
            'program_pesticides', 'program_pesticides_start_date', 'program_pesticides_end_date',
            'program_fertilizers', 'program_fertilizers_start_date', 'program_fertilizers_end_date',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'site': {'required': False}
        }
    
    def validate(self, data):
        """
        Custom validation to handle unique_together constraint when updating.
        Allows changing site and census_year if the combination doesn't already exist.
        """
        instance = self.instance
        
        # Handle site_name - create or get site
        site_name = data.pop('site_name', None)
        if site_name and not data.get('site'):
            # Create new site or get existing one by name
            site, created = Site.objects.get_or_create(
                site_name=site_name,
                defaults={'site_name': site_name}
            )
            data['site'] = site
        
        # Get site and census_year from data (use existing values if not provided)
        site = data.get('site', instance.site if instance else None)
        census_year = data.get('census_year', instance.census_year if instance else None)
        
        # Check if this combination already exists (excluding the current instance)
        if site and census_year:
            existing = SiteCensusData.objects.filter(
                site=site,
                census_year=census_year
            )
            
            # If updating, exclude the current instance from the check
            if instance:
                existing = existing.exclude(pk=instance.pk)
            
            if existing.exists():
                raise serializers.ValidationError({
                    'non_field_errors': [
                        f'Site census data for {site.site_name} and year {census_year.year} already exists.'
                    ]
                })
        
        return data
    
    def to_representation(self, instance):
        """Override to include site_name in response"""
        representation = super().to_representation(instance)
        representation['site_name'] = instance.site.site_name
        return representation