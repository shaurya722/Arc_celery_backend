from rest_framework import serializers
from .models import Community, CensusYear, CommunityCensusData


class CommunitySerializer(serializers.ModelSerializer):
    """Serializer for Community static identity with detailed census data"""
    census_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = ['id', 'name', 'census_data', 'created_at', 'updated_at']
    
    def get_census_data(self, obj):
        """Return all census data for this community across all years with complete details"""
        census_data_list = []
        for census_data in obj.census_data.all().select_related('census_year'):
            census_data_list.append({
                'id': census_data.id,
                'community': str(census_data.community.id),
                'community_name': census_data.community.name,
                'census_year': census_data.census_year.id,
                'census_year_value': census_data.census_year.year,
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
        return census_data_list


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
