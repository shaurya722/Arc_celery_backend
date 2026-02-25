from rest_framework import serializers
from .models import ComplianceCalculation


class ComplianceCalculationSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source='community.name', read_only=True)
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = ComplianceCalculation
        fields = [
            'id',
            'community',
            'community_name',
            'program',
            'required_sites',
            'actual_sites',
            'shortfall',
            'excess',
            'compliance_rate',
            'created_by',
            'created_by_username',
            'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
