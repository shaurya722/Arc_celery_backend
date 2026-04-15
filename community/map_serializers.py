from rest_framework import serializers

from .models import Community


class CommunityMapListSerializer(serializers.ModelSerializer):
    """Communities with GeoJSON boundary + adjacent IDs for map clients."""

    boundary = serializers.SerializerMethodField()
    adjacent_ids = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = ['id', 'name', 'boundary', 'adjacent_ids', 'created_at', 'updated_at']

    def get_boundary(self, obj):
        from .geo_utils import geometry_to_geojson_dict

        return geometry_to_geojson_dict(obj.boundary)

    def get_adjacent_ids(self, obj):
        return [str(x.id) for x in obj.adjacent.all()]
