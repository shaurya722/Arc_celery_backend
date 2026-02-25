from rest_framework import serializers
from .models import Community


class CommunitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ['id', 'name', 'population', 'tier', 'region', 'zone', 'province', 'year', 'is_active', 'start_date', 'end_date', 'created_at', 'updated_at']
