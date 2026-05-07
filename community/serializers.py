from rest_framework import serializers
from django.db.models import Q
from functools import reduce
import operator
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from .models import Community, CensusYear, CommunityCensusData, AdjacentCommunity


class AdjacentCommunityReallocationSerializer(serializers.ModelSerializer):
    """
    Serializer for AdjacentCommunity showing detailed reallocation information
    including source community sites, compliance, excess, and target communities with shortfall
    """
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    census_year_value = serializers.IntegerField(source='census_year.year', read_only=True)

    # Source community details
    from_community_details = serializers.SerializerMethodField()
    # compliance_info = serializers.SerializerMethodField()
    excess_info = serializers.SerializerMethodField()

    # Target communities with shortfall
    target_communities = serializers.SerializerMethodField()

    class Meta:
        model = AdjacentCommunity
        fields = [
            'id', 'from_community', 'from_community_name', 'to_communities',
            'census_year', 'census_year_value', 'from_community_details',
            'excess_info', 'target_communities',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_from_community_details(self, obj):
        """Get detailed information about the source community including its sites"""
        from sites.models import SiteCensusData

        community = obj.from_community
        census_year = obj.census_year

        # Get community census data
        census_data = CommunityCensusData.objects.filter(
            community=community,
            census_year=census_year
        ).first()

        # Get sites for this community and census year
        sites = SiteCensusData.objects.filter(
            community=community,
            census_year=census_year
        ).select_related('site')

        site_details = []
        for site_data in sites:
            site_details.append({
                'id': str(site_data.site.id),
                'site_name': site_data.site.site_name,
            })

        return {
            'id': str(community.id),
            'name': community.name,
            'population': census_data.population if census_data else 0,
            'region': census_data.region if census_data else '',
            'tier': census_data.tier if census_data else '',
            'sites': site_details,
            'total_sites': len(site_details)
        }

    def get_compliance_info(self, obj):
        """Get compliance calculation for the source community"""
        from complaince.models import ComplianceCalculation

        compliance = ComplianceCalculation.objects.filter(
            community=obj.from_community,
            census_year=obj.census_year,
            program__in=['Paint', 'Lighting']  # Check for relevant programs
        ).first()

        if compliance:
            from complaince.utils import compliance_rate_percentage

            return {
                'program': compliance.program,
                'required_sites': compliance.required_sites,
                'actual_sites': compliance.actual_sites,
                'shortfall': compliance.shortfall,
                'excess': compliance.excess,
                'compliance_rate': compliance_rate_percentage(
                    compliance.actual_sites, compliance.required_sites
                ),
                'calculation_date': compliance.calculation_date
            }
        return None

    def get_excess_info(self, obj):
        """Calculate and return excess information for the source community from stored compliance data"""
        from complaince.models import ComplianceCalculation

        # Get all compliance calculations for this community and census year
        compliance_records = ComplianceCalculation.objects.filter(
            community=obj.from_community,
            census_year=obj.census_year,
            program__in=['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']
        )

        total_required = 0
        total_actual = 0
        total_excess = 0

        for compliance in compliance_records:
            total_required += compliance.required_sites or 0
            total_actual += compliance.actual_sites or 0
            total_excess += compliance.excess or 0

        return {
            'required_sites': total_required,
            'actual_sites': total_actual,
            'excess_sites': total_excess,
            'has_excess': total_excess > 0,
            'can_reallocate': total_excess > 0
        }

    def get_target_communities(self, obj):
        """Get target communities with shortfall information from stored compliance data"""
        from complaince.models import ComplianceCalculation

        target_data = []
        for target_community in obj.to_communities.all():
            # Get all compliance calculations for this community and census year
            compliance_records = ComplianceCalculation.objects.filter(
                community=target_community,
                census_year=obj.census_year,
                program__in=['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']
            )

            total_required = 0
            total_actual = 0
            total_shortfall = 0

            for compliance in compliance_records:
                total_required += compliance.required_sites or 0
                total_actual += compliance.actual_sites or 0
                total_shortfall += compliance.shortfall or 0

            # Get census data for additional info
            census_data = CommunityCensusData.objects.filter(
                community=target_community,
                census_year=obj.census_year
            ).first()

            target_data.append({
                'id': str(target_community.id),
                'name': target_community.name,
                'population': census_data.population if census_data else 0,
                'region': census_data.region if census_data else '',
                'tier': census_data.tier if census_data else '',
                'required_sites': total_required,
                'actual_sites': total_actual,
                'shortfall': total_shortfall,
                'needs_sites': total_shortfall > 0
            })

        return target_data


class AdjacentCommunitySerializer(serializers.ModelSerializer):
    """Basic serializer for AdjacentCommunity CRUD operations"""
    from_community_name = serializers.CharField(source='from_community.name', read_only=True)
    to_communities_names = serializers.SerializerMethodField()

    class Meta:
        model = AdjacentCommunity
        fields = [
            'id', 'from_community', 'from_community_name', 'to_communities',
            'to_communities_names', 'census_year', 'created_at', 'updated_at'
        ]

    def get_to_communities_names(self, obj):
        return [comm.name for comm in obj.to_communities.all()]


class CommunitySerializer(serializers.ModelSerializer):
    """Serializer for Community static identity with nested census data"""
    census_years = serializers.SerializerMethodField()
    
    class Meta:
        model = Community
        fields = ['id', 'name', 'census_years', 'created_at', 'updated_at']
    
    def get_census_years(self, obj):
        """Return all census data for this community as nested census_years array"""
        census_years_list = []
        for census_data in obj.census_data.all().select_related('census_year'):
            census_years_list.append({
                'id': census_data.id,
                'year': census_data.census_year.year,
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
        return census_years_list


class CommunityBaseSerializer(serializers.ModelSerializer):
    """Basic serializer for CRUD on Community model (static identity only)."""
    adjacent = serializers.SerializerMethodField()
    adjacent_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text='List of adjacent community UUIDs to set on create/update.'
    )

    class Meta:
        model = Community
        fields = ['id', 'name', 'boundary', 'adjacent', 'adjacent_ids', 'created_at', 'updated_at']

    def get_adjacent(self, obj):
        return [
            {
                'id': str(comm.id),
                'name': comm.name,
            }
            for comm in obj.adjacent.all()
        ]

    def create(self, validated_data):
        adjacent_ids = validated_data.pop('adjacent_ids', [])
        instance = super().create(validated_data)
        if adjacent_ids:
            instance.adjacent.set(adjacent_ids)
        return instance

    def update(self, instance, validated_data):
        adjacent_ids = validated_data.pop('adjacent_ids', None)
        instance = super().update(instance, validated_data)
        if adjacent_ids is not None:
            instance.adjacent.set(adjacent_ids)
        return instance


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For POST/PUT requests, make community and census_year accept names/values instead of IDs
        if self.context.get('request') and self.context['request'].method in ['POST', 'PUT', 'PATCH']:
            # Change field types for input
            self.fields['community'] = serializers.CharField()
            self.fields['census_year'] = serializers.IntegerField()

    def validate_community(self, value):
        """Validate and lookup community by name, create if it doesn't exist (for create operations only)"""
        if isinstance(value, str):
            if self.instance:
                # For updates, find the existing community linked to this census data and update its name
                community = self.instance.community
                community.name = value
                community.save()
                return community
            else:
                # For creates, get or create the community
                community, created = Community.objects.get_or_create(name=value)
                return community
        return value

    def validate_census_year(self, value):
        """Validate and lookup census year by year value"""
        if isinstance(value, int):
            try:
                census_year = CensusYear.objects.get(year=value)
                return census_year
            except CensusYear.DoesNotExist:
                raise serializers.ValidationError(f"Census year {value} not found.")
        return value

    def to_representation(self, instance):
        """Override to ensure proper serialization of foreign keys in response"""
        # Temporarily restore original field types for serialization
        self.fields['community'] = serializers.PrimaryKeyRelatedField(queryset=Community.objects.all())
        self.fields['census_year'] = serializers.PrimaryKeyRelatedField(queryset=CensusYear.objects.all())
        return super().to_representation(instance)


class CensusYearSerializer(serializers.ModelSerializer):
    """Serializer for CensusYear"""
    class Meta:
        model = CensusYear
        fields = ['id', 'year', 'start_date', 'end_date', 'created_at', 'updated_at']


class CensusYearWithDataSerializer(serializers.ModelSerializer):
    """Serializer for CensusYear with associated communities, sites, and regulatory rules"""
    communities = serializers.SerializerMethodField()
    sites = serializers.SerializerMethodField()
    regulatory_rules = serializers.SerializerMethodField()
    
    class Meta:
        model = CensusYear
        fields = ['id', 'year', 'start_date', 'end_date', 'communities', 'sites', 'regulatory_rules', 'created_at', 'updated_at']
    
    def get_communities(self, obj):
        """Return communities that have census data for this year"""
        communities_data = []
        for census_data in obj.community_data.filter(is_active=True).select_related('community'):
            community = census_data.community
            communities_data.append({
                'id': str(community.id),
                'name': community.name,
                'population': census_data.population,
                'tier': census_data.tier,
                'region': census_data.region,
                'zone': census_data.zone,
                'province': census_data.province,
                'is_active': census_data.is_active,
                'census_data_id': census_data.id
            })
        return communities_data
    
    def get_sites(self, obj):
        """Return sites that have census data for this year"""
        sites_data = []
        for census_data in obj.site_data.filter(is_active=True).select_related('site', 'community'):
            site = census_data.site
            sites_data.append({
                'id': census_data.id,
                'site_name': site.site_name,
                'site_id': str(site.id),
            })
        return sites_data
    
    def get_regulatory_rules(self, obj):
        """Return regulatory rules that have census data for this year"""
        rules_data = []
        for census_data in obj.regulatory_rule_data.filter(is_active=True).select_related('regulatory_rule'):
            rule = census_data.regulatory_rule
            rules_data.append({
                'id': census_data.id,
                'rule_id': str(rule.id),
                'rule_name': rule.name,
                'description': census_data.description,
                'program': census_data.program,
                'category': census_data.category,
                'rule_type': census_data.rule_type,
                'min_population': census_data.min_population,
                'max_population': census_data.max_population,
                'site_per_population': census_data.site_per_population,
                'base_required_sites': census_data.base_required_sites,
                'event_offset_percentage': census_data.event_offset_percentage,
                'reallocation_percentage': census_data.reallocation_percentage,
                'is_active': census_data.is_active,
                'start_date': census_data.start_date,
                'end_date': census_data.end_date
            })
        return rules_data


class MapDataSerializer(serializers.Serializer):
    """Serializer for map data providing sites and municipalities in React component format"""

    def to_representation(self, instance):
        """Transform Django data into React component expected format"""
        request = self.context.get('request')
        filters = request.query_params if request else {}

        # Parse filters that should be lists
        def parse_list_filter(value):
            """Parse comma-separated string or list into list"""
            if isinstance(value, str):
                return [item.strip() for item in value.split(',') if item.strip()]
            elif isinstance(value, list):
                return value
            return []

        parsed_filters = {}
        for key, value in filters.items():
            if key in ['operator_types', 'site_types', 'municipalities', 'communities', 'status', 'programs']:
                parsed_filters[key] = parse_list_filter(value)
            else:
                parsed_filters[key] = value

        census_year_param = parsed_filters.get('census_year')

        # Get census year or use latest
        census_year = None
        if census_year_param:
            try:
                census_year = CensusYear.objects.get(year=int(census_year_param))
            except (CensusYear.DoesNotExist, ValueError):
                census_year = CensusYear.objects.order_by('-year').first()
        else:
            census_year = CensusYear.objects.order_by('-year').first()

        if not census_year:
            return {'sites': [], 'municipalities': []}

        # Filter sites and communities by census year
        # Get municipalities (communities) for this census year
        municipalities_queryset = CommunityCensusData.objects.filter(
            census_year=census_year,
            is_active=True
        ).select_related('community')

        # Apply search filter to municipalities if provided (legacy text search)
        if parsed_filters.get('search'):
            municipalities_queryset = municipalities_queryset.filter(
                community__name__icontains=parsed_filters['search']
            )
        # Apply dropdown-style community filter (by community UUID)
        communities_filter = parsed_filters.get('communities') or parsed_filters.get('municipalities')
        if communities_filter:
            municipalities_queryset = municipalities_queryset.filter(
                community__id__in=communities_filter
            )

        municipalities_data = []
        municipalities_pagination_info = None

        # Handle municipalities pagination
        if parsed_filters.get('municipalities_page') and parsed_filters.get('municipalities_limit'):
            try:
                municipalities_page = int(parsed_filters['municipalities_page'])
                municipalities_limit = int(parsed_filters['municipalities_limit'])
                if municipalities_limit > 2000:  # Max limit
                    municipalities_limit = 2000
                if municipalities_limit < 1:
                    municipalities_limit = 1
                if municipalities_page < 1:
                    municipalities_page = 1

                municipalities_paginator = Paginator(municipalities_queryset, municipalities_limit)
                paginated_municipalities = municipalities_paginator.page(municipalities_page)
                municipalities_pagination_info = {
                    'page': paginated_municipalities.number,
                    'limit': municipalities_limit,
                    'total': municipalities_paginator.count,
                    'total_pages': municipalities_paginator.num_pages
                }
            except (PageNotAnInteger, EmptyPage, ValueError):
                paginated_municipalities = municipalities_queryset
        else:
            paginated_municipalities = municipalities_queryset

        for community_data in paginated_municipalities:
            municipalities_data.append({
                'id': str(community_data.community.id),
                'name': community_data.community.name,
                'tier': community_data.tier or 'Unknown',
                'population': community_data.population or 0,
                'boundary': community_data.community.boundary,
            })

        # Get sites for this census year
        from sites.models import SiteCensusData
        sites_queryset = SiteCensusData.objects.filter(
            census_year=census_year,
        )

        # Apply filters
        # Dropdown-style community filter (accepts both 'communities' and legacy 'municipalities')
        communities_filter = parsed_filters.get('communities') or parsed_filters.get('municipalities')
        if communities_filter:
            sites_queryset = sites_queryset.filter(community__id__in=communities_filter)
        if parsed_filters.get('search'):
            search_query = parsed_filters['search']
            sites_queryset = sites_queryset.filter(
                Q(site__site_name__icontains=search_query) | Q(community__name__icontains=search_query)
            )

        if parsed_filters.get('site_types'):
            sites_queryset = sites_queryset.filter(site_type__in=parsed_filters['site_types'])

        if parsed_filters.get('operator_types'):
            sites_queryset = sites_queryset.filter(operator_type__in=parsed_filters['operator_types'])

        # Backward compatibility: explicit municipalities filter
        if parsed_filters.get('municipalities') and not communities_filter:
            sites_queryset = sites_queryset.filter(community__id__in=parsed_filters['municipalities'])

        # Compute overall counts BEFORE applying status filter so the response
        # always shows active / inactive / total regardless of the status param.
        sites_count_active = sites_queryset.filter(is_active=True).count()
        sites_count_inactive = sites_queryset.filter(is_active=False).count()
        sites_count_total = sites_count_active + sites_count_inactive

        if parsed_filters.get('status'):
            status_filters = []
            if 'Active' in parsed_filters['status']:
                status_filters.append(Q(is_active=True))
            if 'Inactive' in parsed_filters['status']:
                status_filters.append(Q(is_active=False))
            if status_filters:
                sites_queryset = sites_queryset.filter(reduce(operator.or_, status_filters))

        if parsed_filters.get('programs'):
            program_filters = []
            program_fields = {
                'Paint': 'program_paint',
                'Lighting': 'program_lights',
                'Solvents': 'program_solvents',
                'Pesticides': 'program_pesticides',
                'Fertilizers': 'program_fertilizers',
            }
            for program in parsed_filters['programs']:
                field = program_fields.get(program)
                if field:
                    program_filters.append(Q(**{field: True}))
            if program_filters:
                sites_queryset = sites_queryset.filter(reduce(operator.or_, program_filters))

        sites_data = []
        paginated_sites = None
        sites_pagination_info = None

        # Handle sites pagination
        if parsed_filters.get('page') and parsed_filters.get('limit'):
            try:
                page = int(parsed_filters['page'])
                limit = int(parsed_filters['limit'])
                if limit > 1000:  # Max limit
                    limit = 1000
                if limit < 1:
                    limit = 1
                if page < 1:
                    page = 1

                paginator = Paginator(sites_queryset, limit)
                paginated_sites = paginator.page(page)
                sites_pagination_info = {
                    'page': paginated_sites.number,
                    'limit': limit,
                    'total': paginator.count,
                    'total_pages': paginator.num_pages,
                    'total_active': sites_count_active,
                    'total_inactive': sites_count_inactive,
                    'total_overall': sites_count_total,
                }
            except (PageNotAnInteger, EmptyPage, ValueError):
                paginated_sites = sites_queryset
                sites_pagination_info = None
        else:
            paginated_sites = sites_queryset
            sites_pagination_info = None

        for site_census in paginated_sites:
            site = site_census.site
            community = site_census.community

            # Get municipality info
            municipality_info = None
            if community:
                # Get population from community census data
                community_census = CommunityCensusData.objects.filter(
                    community=community,
                    census_year=census_year
                ).first()
                population = community_census.population if community_census else 0
                
                municipality_info = {
                    'name': community.name,
                    'population': population
                }

            # Parse programs from the site census data
            programs = []
            if hasattr(site_census, 'program_paint') and site_census.program_paint:
                programs.append('Paint')
            if hasattr(site_census, 'program_lights') and site_census.program_lights:
                programs.append('Lighting')
            if hasattr(site_census, 'program_solvents') and site_census.program_solvents:
                programs.append('Solvents')
            if hasattr(site_census, 'program_pesticides') and site_census.program_pesticides:
                programs.append('Pesticides')
            if hasattr(site_census, 'program_fertilizers') and site_census.program_fertilizers:
                programs.append('Fertilizers')

            # Calculate population served (this might need adjustment based on your business logic)
            population_served = 0
            if community:
                community_census = CommunityCensusData.objects.filter(
                    community=community,
                    census_year=census_year
                ).first()
                if community_census:
                    population_served = community_census.population or 0

            sites_data.append({
                'id': str(site.id),
                'name': site.site_name or 'Unknown Site',
                'address': getattr(site_census, 'address_city', '') or getattr(site, 'location', ''),
                'status': 'Active' if site_census.is_active else 'Inactive',
                'operator_type': getattr(site_census, 'operator_type', 'Unknown'),
                'site_type': getattr(site_census, 'site_type', 'Collection site'),
                'latitude': getattr(site_census, 'latitude', None) or getattr(site_census, 'address_latitude', None) or getattr(site, 'latitude', None),
                'longitude': getattr(site_census, 'longitude', None) or getattr(site_census, 'address_longitude', None) or getattr(site, 'longitude', None),
                'programs': programs,
                'municipality': municipality_info,
                'population_served': population_served,
                'created_at': site_census.created_at.isoformat() if site_census.created_at else None,
                'active_dates': str(site_census.site_start_date) if site_census.site_start_date else None,
            })

        return {
            'sites': sites_data,
            'municipalities': municipalities_data,
            'census_year': {
                'id': census_year.id,
                'year': census_year.year,
            },
            'pagination': {
                'sites': sites_pagination_info,
                'municipalities': municipalities_pagination_info,
            } if sites_pagination_info or municipalities_pagination_info else None
        }
