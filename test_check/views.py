from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Community, CensusYear, Site
from .serializers import CommunitySerializer, CensusYearSerializer, SiteSerializer


class CommunityListCreateAPIView(APIView):
    def get(self, request):
        # Get query parameters
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        search = request.query_params.get('search', '')
        tier = request.query_params.get('tier')
        province = request.query_params.get('province')
        region = request.query_params.get('region')
        census_year = request.query_params.get('census_year')
        sort_order = int(request.query_params.get('sort', -1))
        sort_by = request.query_params.get('sortBy', 'created_at')

        # Start with base queryset with prefetch
        queryset = Community.objects.prefetch_related('census_years', 'sites').all()

        # Apply search across multiple fields
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(province__icontains=search) |
                Q(region__icontains=search) |
                Q(zone__icontains=search)
            )

        # Apply filters
        if tier and tier != 'all':
            queryset = queryset.filter(tier=tier)
        if province and province != 'all':
            queryset = queryset.filter(province=province)
        if region and region != 'all':
            queryset = queryset.filter(region=region)
        if census_year and census_year != 'all':
            queryset = queryset.filter(census_years__year=int(census_year))

        # Apply ordering
        order_prefix = '-' if sort_order == -1 else ''
        queryset = queryset.order_by(f'{order_prefix}{sort_by}')

        # Paginate
        paginator = Paginator(queryset, limit)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        # Serialize data
        serializer = CommunitySerializer(page_obj.object_list, many=True)

        # Custom response matching UI format
        return Response({
            'docs': serializer.data,
            'totalDocs': paginator.count,
            'limit': limit,
            'page': page_obj.number,
            'totalPages': paginator.num_pages,
            'hasNextPage': page_obj.has_next(),
            'hasPrevPage': page_obj.has_previous(),
            'nextPage': page_obj.next_page_number() if page_obj.has_next() else None,
            'prevPage': page_obj.previous_page_number() if page_obj.has_previous() else None,
        })
    
    def post(self, request):
        """Create a new community"""
        serializer = CommunitySerializer(data=request.data)
        if serializer.is_valid():
            community = serializer.save()
            
            # Handle many-to-many relationships
            if 'census_years' in request.data:
                community.census_years.set(request.data['census_years'])
            if 'sites' in request.data:
                community.sites.set(request.data['sites'])
            
            return Response(
                CommunitySerializer(community).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityDetailAPIView(APIView):
    """Retrieve, update, or delete a community instance"""
    
    def get(self, request, pk):
        """Get a single community by ID"""
        community = get_object_or_404(Community, pk=pk)
        serializer = CommunitySerializer(community)
        return Response(serializer.data)
    
    def put(self, request, pk):
        """Update a community"""
        community = get_object_or_404(Community, pk=pk)
        serializer = CommunitySerializer(community, data=request.data, partial=True)
        
        if serializer.is_valid():
            community = serializer.save()
            
            # Handle many-to-many relationships
            if 'census_years' in request.data:
                community.census_years.set(request.data['census_years'])
            if 'sites' in request.data:
                community.sites.set(request.data['sites'])
            
            return Response(CommunitySerializer(community).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        """Delete a community"""
        community = get_object_or_404(Community, pk=pk)
        community_name = community.name
        community.delete()
        return Response(
            {'message': f'Community "{community_name}" deleted successfully'},
            status=status.HTTP_204_NO_CONTENT
        )


class CensusYearListCreateAPIView(APIView):
    def get(self, request):
        # Get all census years without filtering, search, or pagination
        queryset = CensusYear.objects.prefetch_related('communities', 'sites').all().order_by('-year')

        # Serialize data
        serializer = CensusYearSerializer(queryset, many=True)

        # Return all data without pagination
        return Response(serializer.data)
    
    def post(self, request):
        """Create a new census year - automatically assigns all active sites"""
        serializer = CensusYearSerializer(data=request.data)
        if serializer.is_valid():
            census_year = serializer.save()
            # The save method in the model will automatically assign active sites
            
            return Response(
                CensusYearSerializer(census_year).data,
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SiteListAPIView(APIView):
    def get(self, request):
        # Get query parameters
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        search = request.query_params.get('search', '')
        site_type = request.query_params.get('site_type')
        operator_type = request.query_params.get('operator_type')
        region = request.query_params.get('region')
        sort_order = int(request.query_params.get('sort', -1))
        sort_by = request.query_params.get('sortBy', 'created_at')

        # Start with base queryset with prefetch
        queryset = Site.objects.prefetch_related('communities', 'census_years').all()

        # Apply search
        if search:
            queryset = queryset.filter(
                Q(site_name__icontains=search) |
                Q(address_city__icontains=search) |
                Q(region__icontains=search) |
                Q(service_area__icontains=search)
            )

        # Apply filters
        if site_type and site_type != 'all':
            queryset = queryset.filter(site_type=site_type)
        if operator_type and operator_type != 'all':
            queryset = queryset.filter(operator_type=operator_type)
        if region and region != 'all':
            queryset = queryset.filter(region=region)

        # Apply ordering
        order_prefix = '-' if sort_order == -1 else ''
        queryset = queryset.order_by(f'{order_prefix}{sort_by}')

        # Paginate
        paginator = Paginator(queryset, limit)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages if paginator.num_pages > 0 else 1)

        # Serialize data
        serializer = SiteSerializer(page_obj.object_list, many=True)

        # Custom response
        return Response({
            'docs': serializer.data,
            'totalDocs': paginator.count,
            'limit': limit,
            'page': page_obj.number,
            'totalPages': paginator.num_pages,
            'hasNextPage': page_obj.has_next(),
            'hasPrevPage': page_obj.has_previous(),
            'nextPage': page_obj.next_page_number() if page_obj.has_next() else None,
            'prevPage': page_obj.previous_page_number() if page_obj.has_previous() else None,
        })
