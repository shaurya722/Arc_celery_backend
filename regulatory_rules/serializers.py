from rest_framework import serializers
from .models import RegulatoryRuleCensusData, RegulatoryRule
from community.models import CensusYear

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
            'base_required_sites', 'is_active', 'start_date', 'end_date', 
            'created_at', 'updated_at'
        ]
        read_only_fields = ['name', 'description', 'year']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For POST/PUT requests, make regulatory_rule and census_year accept names/values instead of IDs
        if self.context.get('request') and self.context['request'].method in ['POST', 'PUT', 'PATCH']:
            # Change field types for input
            self.fields['regulatory_rule'] = serializers.CharField()
            # Make name writable for updates
            self.fields['name'] = serializers.CharField(required=False)
            self.fields['census_year'] = serializers.IntegerField()

    def validate_name(self, value):
        """Validate and update regulatory rule name for updates"""
        if self.instance and isinstance(value, str):
            # For updates, update the regulatory rule name
            regulatory_rule = self.instance.regulatory_rule
            regulatory_rule.name = value
            regulatory_rule.save()
            return value
        return value

    def validate_regulatory_rule(self, value):
        """Validate and lookup regulatory rule by ID or name"""
        if isinstance(value, str):
            # Try to parse as UUID first (for existing rule IDs)
            try:
                from uuid import UUID
                rule_id = UUID(value)
                try:
                    regulatory_rule = RegulatoryRule.objects.get(id=rule_id)
                    return regulatory_rule
                except RegulatoryRule.DoesNotExist:
                    raise serializers.ValidationError(f"Regulatory rule with ID {value} not found.")
            except ValueError:
                # Not a UUID, treat as name
                if self.instance:
                    # For updates, find the existing rule linked to this census data and update its name
                    regulatory_rule = self.instance.regulatory_rule
                    regulatory_rule.name = value
                    regulatory_rule.save()
                    return regulatory_rule
                else:
                    # For creates, get or create the rule
                    regulatory_rule, created = RegulatoryRule.objects.get_or_create(name=value)
                    return regulatory_rule
        elif isinstance(value, int):
            # Handle integer IDs (though unlikely for UUID)
            try:
                regulatory_rule = RegulatoryRule.objects.get(id=value)
                return regulatory_rule
            except RegulatoryRule.DoesNotExist:
                raise serializers.ValidationError(f"Regulatory rule with ID {value} not found.")
        return value

    def validate_census_year(self, value):
        """Validate and lookup census year by ID or year value"""
        if isinstance(value, int):
            # First try to get by ID (for cases where census_year ID is passed)
            try:
                census_year = CensusYear.objects.get(id=value)
                return census_year
            except CensusYear.DoesNotExist:
                pass
            
            # If not found by ID, try by year value
            try:
                census_year = CensusYear.objects.get(year=value)
                return census_year
            except CensusYear.DoesNotExist:
                raise serializers.ValidationError(f"Census year {value} not found.")
        return value

    def to_representation(self, instance):
        """Override to ensure proper serialization of foreign keys and handle decimal fields manually"""
        # Temporarily restore original field types for serialization
        self.fields['regulatory_rule'] = serializers.PrimaryKeyRelatedField(queryset=RegulatoryRule.objects.all())
        self.fields['census_year'] = serializers.PrimaryKeyRelatedField(queryset=CensusYear.objects.all())
        
        # Manually build the representation to avoid DRF decimal field issues
        data = {
            'id': instance.id,
            'regulatory_rule': instance.regulatory_rule.id,
            'census_year': instance.census_year.id,
            'name': instance.regulatory_rule.name,
            'description': instance.description,
            'year': instance.census_year.year,
            'program': instance.program,
            'category': instance.category,
            'rule_type': instance.rule_type,
            'min_population': instance.min_population,
            'max_population': instance.max_population,
            'base_required_sites': instance.base_required_sites,
            'is_active': instance.is_active,
            'start_date': instance.start_date,
            'end_date': instance.end_date,
            'created_at': instance.created_at,
            'updated_at': instance.updated_at,
        }
        
        # Manually handle decimal fields to avoid InvalidOperation
        data['site_per_population'] = float(instance.site_per_population) if instance.site_per_population is not None else None
        data['event_offset_percentage'] = int(instance.event_offset_percentage) if instance.event_offset_percentage is not None else None
        data['reallocation_percentage'] = int(instance.reallocation_percentage) if instance.reallocation_percentage is not None else None
        
        return data
