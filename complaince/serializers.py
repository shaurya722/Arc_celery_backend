from rest_framework import serializers
from .models import ComplianceCalculation


class ComplianceCalculationSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source='community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True, allow_null=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    status = serializers.SerializerMethodField()
    
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
