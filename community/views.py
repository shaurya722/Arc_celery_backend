from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Community, CommunityCensusData, CensusYear
from .serializers import CommunitySerializer, CommunityCensusDataSerializer, CensusYearSerializer
from complaince.tasks import calculate_community_compliance


class CommunityPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100


class CommunityListCreate(APIView):
    """
    API for Community census data in flat format.
    Returns all census data records with community information.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        # Query CommunityCensusData instead of Community for flat format
        queryset = CommunityCensusData.objects.select_related('community', 'census_year').all()

        # Search by community name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(community__name__icontains=search))

        # Filters
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_year__year=year)

        tier = request.query_params.get('tier', None)
        if tier:
            queryset = queryset.filter(tier=tier)

        region = request.query_params.get('region', None)
        if region:
            queryset = queryset.filter(region=region)

        is_active = request.query_params.get('is_active', None)
        if is_active:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)

        # Sort
        sort = request.query_params.get('sort', 'community__name')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunityCensusDataSerializer(paginated_queryset, many=True)
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

        # Sort
        sort = request.query_params.get('sort', 'community__name')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunityCensusDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CommunityCensusDataSerializer(data=request.data)
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
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True)
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
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True)
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


class CensusYearListCreate(APIView):
    """List and Create census years"""
    pagination_class = CommunityPagination()

    def get(self, request):
        """List all census years"""
        queryset = CensusYear.objects.all().order_by('-year')
        
        # Search by year
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(year=year)
        
        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CensusYearSerializer(paginated_queryset, many=True)
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
