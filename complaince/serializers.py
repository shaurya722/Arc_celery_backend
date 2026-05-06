from rest_framework import serializers
from .models import ComplianceCalculation, DirectServiceOffset, CommunityOffset


class ComplianceCalculationSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source='community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()
    # Extra display fields for Tool A direct service offsets
    base_required_sites = serializers.IntegerField(read_only=True)
    direct_service_offset_percentage = serializers.IntegerField(read_only=True, allow_null=True)
    direct_service_offset_source = serializers.CharField(read_only=True)
    # New breakdown fields
    sites_from_requirements = serializers.IntegerField(read_only=True)
    sites_from_adjacent = serializers.IntegerField(read_only=True)
    sites_from_events = serializers.IntegerField(read_only=True)
    net_direct_service_offset = serializers.IntegerField(read_only=True)

    def get_status(self, obj):
        if obj.shortfall == 0 and obj.excess == 0:
            return 'compliant'
        elif obj.shortfall > 0:
            return 'shortfall'
        else:
            return 'excess'
    
    class Meta:
        model = ComplianceCalculation
        fields = [
            'id',
            'community',
            'community_name',
            'census_year',
            'census_year_value',
            'program',
            'base_required_sites',
            'sites_from_requirements',
            'sites_from_adjacent',
            'sites_from_events',
            'net_direct_service_offset',
            'direct_service_offset_percentage',
            'direct_service_offset_source',
            'required_sites',
            'actual_sites',
            'shortfall',
            'excess',
            'compliance_rate',
            'status',
            'calculation_date',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'calculation_date', 'created_at', 'updated_at']


class DirectServiceOffsetSerializer(serializers.ModelSerializer):
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)
    
    class Meta:
        model = DirectServiceOffset
        fields = [
            'id',
            'census_year',
            'census_year_value',
            'program',
            'percentage',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CommunityOffsetSerializer(serializers.ModelSerializer):
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)
    community_name = serializers.CharField(source='community.name', read_only=True)
    
    class Meta:
        model = CommunityOffset
        fields = [
            'id',
            'census_year',
            'census_year_value',
            'program',
            'community',
            'community_name',
            'percentage',
            'is_active',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
