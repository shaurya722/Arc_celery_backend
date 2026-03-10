from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from uuid import UUID
from .models import Community, CommunityCensusData, CensusYear, AdjacentCommunity
from .serializers import CommunitySerializer, CommunityCensusDataSerializer, CensusYearSerializer, CensusYearWithDataSerializer, AdjacentCommunitySerializer, AdjacentCommunityReallocationSerializer, MapDataSerializer
from complaince.tasks import calculate_community_compliance


class CommunityPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100


class CommunityListCreate(APIView):
    """
    API for Community static identity with nested census data.
    Returns communities with their census_years as nested arrays.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        # Query Community objects with prefetch_related for census data
        queryset = Community.objects.prefetch_related('census_data__census_year').all()

        # Search by name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))

        # Filters for census data (will filter communities that have matching census data)
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_data__census_year__year=year)

        tier = request.query_params.get('tier', None)
        if tier:
            queryset = queryset.filter(census_data__tier=tier)

        region = request.query_params.get('region', None)
        if region:
            queryset = queryset.filter(census_data__region=region)

        is_active = request.query_params.get('is_active', None)
        if is_active:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(census_data__is_active=is_active_bool)

        # Sort
        sort = request.query_params.get('sort', 'name')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunitySerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Create new census data record
        serializer = CommunityCensusDataSerializer(data=request.data)
        if serializer.is_valid():
            census_data = serializer.save()
            calculate_community_compliance.delay(str(census_data.community.id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityCensusDataListCreate(APIView):
    """
    API for year-specific community data.
    Use this for filtering by population, tier, region, is_active, etc.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        queryset = CommunityCensusData.objects.select_related('community', 'census_year').all()

        # Search by community name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(community__name__icontains=search))

        # Filters for year-specific data
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_year__year=year)

        tier = request.query_params.get('tier', None)
        if tier:
            queryset = queryset.filter(tier=tier)

        region = request.query_params.get('region', None)
        if region:
            queryset = queryset.filter(region=region)

        zone = request.query_params.get('zone', None)
        if zone:
            queryset = queryset.filter(zone=zone)

        province = request.query_params.get('province', None)
        if province:
            queryset = queryset.filter(province=province)

        is_active = request.query_params.get('is_active', None)
        if is_active:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)

        min_population = request.query_params.get('min_population', None)
        if min_population:
            queryset = queryset.filter(population__gte=min_population)

        max_population = request.query_params.get('max_population', None)
        if max_population:
            queryset = queryset.filter(population__lte=max_population)

        # Sort - handle valid field names
        sort_by = request.query_params.get('sort', 'community__name')  # Default sort by community name
        
        # Map of allowed sort fields to prevent FieldError
        valid_sort_fields = {
            # Direct model fields
            'id': 'id',
            '-id': '-id',
            'population': 'population',
            '-population': '-population',
            'tier': 'tier',
            '-tier': '-tier',
            'region': 'region',
            '-region': '-region',
            'zone': 'zone',
            '-zone': '-zone',
            'province': 'province',
            '-province': '-province',
            'is_active': 'is_active',
            '-is_active': '-is_active',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'updated_at': 'updated_at',
            '-updated_at': '-updated_at',
            'start_date': 'start_date',
            '-start_date': '-start_date',
            'end_date': 'end_date',
            '-end_date': '-end_date',
            
            # Related field sorting
            'name': 'community__name',
            '-name': '-community__name',
            'year': 'census_year__year',
            '-year': '-census_year__year',
        }
        
        # Use valid sort field or default to 'community__name'
        sort_field = valid_sort_fields.get(sort_by, 'community__name')
        queryset = queryset.order_by(sort_field)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunityCensusDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CommunityCensusDataSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            # Trigger compliance calculation for the community
            calculate_community_compliance.delay(str(census_data.community.id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityDetail(APIView):
    """CRUD operations for single census data record"""
    
    def get_object(self, pk):
        try:
            return CommunityCensusData.objects.select_related('community', 'census_year').get(pk=pk)
        except CommunityCensusData.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            calculate_community_compliance.delay(str(census_data.community.id))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        census_data.delete()
        return Response({"message": "Census data deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class CommunityCensusDataDetail(APIView):
    """CRUD operations for year-specific community data"""
    
    def get_object(self, pk):
        try:
            return CommunityCensusData.objects.select_related('community', 'census_year').get(pk=pk)
        except CommunityCensusData.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single community census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update community census data for a specific year"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            # Trigger compliance calculation
            calculate_community_compliance.delay(str(census_data.community.id))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete community census data for a specific year"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        census_data.delete()
        return Response({"message": "Community census data deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class YearDropdown(APIView):
    """
    API for Year dropdown with CRUD operations.
    Returns simple year list for dropdowns and supports full CRUD.
    """

    def get(self, request):
        """Get all years for dropdown"""
        years = CensusYear.objects.values('id', 'year').order_by('-year')
        return Response({
            'years': list(years),
            'total': len(years)
        })

    def post(self, request):
        """Create a new year"""
        serializer = CensusYearSerializer(data=request.data)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response({
                'id': census_year.id,
                'year': census_year.year,
                'message': f'Year {census_year.year} created successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        """Update a year"""
        try:
            census_year = CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return Response({"error": "Year not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CensusYearSerializer(census_year, data=request.data, partial=True)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response({
                'id': census_year.id,
                'year': census_year.year,
                'message': f'Year {census_year.year} updated successfully'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Delete a year"""
        try:
            census_year = CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return Response({"error": "Year not found"}, status=status.HTTP_404_NOT_FOUND)

        year_value = census_year.year
        census_year.delete()
        return Response({
            'message': f'Year {year_value} deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)


class CensusYearListCreate(APIView):
    pagination_class = CommunityPagination()

    def get(self, request):
        # Query CensusYear with prefetch_related for efficiency
        queryset = CensusYear.objects.prefetch_related(
            'community_data__community',
            'site_data__site',
            'site_data__community',
            'regulatory_rule_data__regulatory_rule'
        ).all()

        # Sort
        sort = request.query_params.get('sort', '-year')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CensusYearWithDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Create a new census year"""
        serializer = CensusYearSerializer(data=request.data)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CensusYearDetail(APIView):
    """CRUD operations for individual census year"""
    
    def get_object(self, pk):
        try:
            return CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single census year"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CensusYearSerializer(census_year)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update a census year"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CensusYearSerializer(census_year, data=request.data, partial=True)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a census year and all associated data"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        census_year.delete()
        return Response({"message": "Census year deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class AdjacentCommunityReallocationListCreate(APIView):
    """List all adjacent communities with reallocation data or create new ones"""

    def get(self, request):
        """List all adjacent communities with detailed reallocation information"""
        adjacencies = AdjacentCommunity.objects.select_related(
            'from_community', 'census_year'
        ).prefetch_related('to_communities').all()

        # Filters
        from_community = request.query_params.get('from_community')
        if from_community:
            # Check if it's a UUID or name
            try:
                # Try to parse as UUID
                UUID(from_community)
                # If successful, filter by ID
                adjacencies = adjacencies.filter(from_community__id=from_community)
            except ValueError:
                # Not a UUID, filter by name
                adjacencies = adjacencies.filter(from_community__name__icontains=from_community)

        census_year = request.query_params.get('census_year')
        if census_year:
            adjacencies = adjacencies.filter(census_year__year=census_year)

        serializer = AdjacentCommunityReallocationSerializer(adjacencies, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create new adjacent community with basic adjacency info"""
        serializer = AdjacentCommunitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdjacentCommunityReallocationDetail(APIView):
    """Get detailed reallocation information for a specific adjacency"""

    def get_object(self, pk):
        try:
            return AdjacentCommunity.objects.select_related(
                'from_community', 'census_year'
            ).prefetch_related('to_communities').get(pk=pk)
        except AdjacentCommunity.DoesNotExist:
            return None

    def get(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunityReallocationSerializer(adjacency)
        return Response(serializer.data)

    def put(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunitySerializer(adjacency, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunitySerializer(adjacency, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        adjacency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MapDataView(APIView):
    """API view for map data providing sites and municipalities for the React component"""

    def get(self, request):
        """Get map data (sites and municipalities) for the React component"""
        serializer = MapDataSerializer({}, context={'request': request})
        return Response(serializer.data)
