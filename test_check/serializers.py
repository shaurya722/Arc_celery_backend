from rest_framework import serializers
from .models import Community, CensusYear, Site


class CensusYearSerializer(serializers.ModelSerializer):
    communities = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    sites = serializers.SerializerMethodField()

    def get_sites(self, obj):
        sites = obj.sites.all()
        return [{
            "id": site.id,
            "name": site.site_name
        } for site in sites]

    class Meta:
        model = CensusYear
        fields = '__all__'


class CommunitySerializer(serializers.ModelSerializer):
    census_years = serializers.SerializerMethodField()
    sites = serializers.SerializerMethodField()

    class Meta:
        model = Community
        fields = '__all__'

    def get_census_years(self, obj):
        return obj.census_years.values_list('year')

    def get_sites(self, obj):
        return obj.sites.values_list('site_name')


class SiteSerializer(serializers.ModelSerializer):
    communities = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    census_years = CensusYearSerializer(many=True, read_only=True)

    class Meta:
        model = Site
        fields = '__all__'
