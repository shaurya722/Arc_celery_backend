from rest_framework import serializers
from .models import RegulatoryRule

class RegulatoryRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegulatoryRule
        fields = ['id', 'name', 'description', 'year', 'program', 'category', 'rule_type', 'min_population', 'max_population', 'site_per_population', 'base_required_sites', 'event_offset_percentage', 'reallocation_percentage', 'is_active', 'start_date', 'end_date', 'created_at', 'updated_at']

