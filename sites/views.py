from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Site, SiteCensusData
from .serializers import SiteSerializer, SiteCensusDataSerializer


class SitePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100


class SiteListCreate(APIView):
    """
    API for Site census data in flat format.
    Returns all site census data records with site and community information.
    """
    pagination_class = SitePagination()

    def get(self, request):
        # Query SiteCensusData instead of Site for flat format
        queryset = SiteCensusData.objects.select_related('site', 'census_year', 'community').all()

        # Search by site name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(site__site_name__icontains=search) |
                Q(address_city__icontains=search)
            )

        # Filters
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_year__year=year)

        site_type = request.query_params.get('site_type', None)
        if site_type:
            queryset = queryset.filter(site_type=site_type)

        operator_type = request.query_params.get('operator_type', None)
        if operator_type:
            queryset = queryset.filter(operator_type=operator_type)

        community = request.query_params.get('community', None)
        if community:
            queryset = queryset.filter(community__id=community)

        region = request.query_params.get('region', None)
        if region:
            queryset = queryset.filter(region=region)

        is_active = request.query_params.get('is_active', None)
        if is_active:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(is_active=is_active_bool)

        # Sort
        sort = request.query_params.get('sort', 'site__site_name')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = SiteCensusDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Create new site census data record
        serializer = SiteCensusDataSerializer(data=request.data)
        if serializer.is_valid():
            site_census_data = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SiteDetail(APIView):
    """CRUD operations for single site census data record"""
    
    def get_object(self, pk):
        try:
            return SiteCensusData.objects.select_related('site', 'census_year', 'community').get(pk=pk)
        except SiteCensusData.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single site census data record"""
        site_census_data = self.get_object(pk)
        if not site_census_data:
            return Response({"error": "Site census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SiteCensusDataSerializer(site_census_data)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update site census data record"""
        site_census_data = self.get_object(pk)
        if not site_census_data:
            return Response({"error": "Site census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SiteCensusDataSerializer(site_census_data, data=request.data, partial=True)
        if serializer.is_valid():
            site_census_data = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a site census data record"""
        site_census_data = self.get_object(pk)
        if not site_census_data:
            return Response({"error": "Site census data not found"}, status=status.HTTP_404_NOT_FOUND)
        site_census_data.delete()
        return Response({"message": "Site census data deleted successfully"}, status=status.HTTP_204_NO_CONTENT)