from rest_framework import serializers
from .models import RegulatoryRuleCensusData

class RegulatoryRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryRuleCensusData
        fields = ['id', 'name', 'description', 'year', 'program', 'category', 'rule_type', 'min_population', 'max_population', 'site_per_population', 'base_required_sites', 'event_offset_percentage', 'reallocation_percentage', 'is_active', 'start_date', 'end_date', 'created_at', 'updated_at']


class RegulatoryRuleCensusDataSerializer(serializers.ModelSerializer):
    # Include related fields for display
    name = serializers.CharField(source='regulatory_rule.name', read_only=True)
    description = serializers.CharField(source='regulatory_rule.description', read_only=True)
    year = serializers.IntegerField(source='census_year.year', read_only=True)
    
    class Meta:
        model = RegulatoryRuleCensusData
        fields = [
            'id', 'regulatory_rule', 'census_year', 'name', 'description', 'year',
            'program', 'category', 'rule_type', 'min_population', 'max_population', 
            'site_per_population', 'base_required_sites', 'event_offset_percentage', 
            'reallocation_percentage', 'is_active', 'start_date', 'end_date', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['name', 'description', 'year']
