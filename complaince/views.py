from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.db.models import F, Exists, OuterRef, Q, Sum, Avg
from .models import ComplianceCalculation
from .serializers import ComplianceCalculationSerializer
from .tasks import calculate_community_compliance


class ComplianceCalculationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'limit'
    max_page_size = 100


class ComplianceCalculationListCreate(APIView):
    """
    List all compliance calculations or trigger a new calculation.
    """
    pagination_class = ComplianceCalculationPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['community', 'program', 'created_at', 'census_year', 'shortfall', 'excess', 'compliance_rate']
    search_fields = ['community__name', 'program', 'census_year__year']
    ordering_fields = ['created_at', 'compliance_rate', 'shortfall', 'excess', 'required_sites', 'actual_sites', 'community__name', 'census_year__year', 'program']
    
    def get(self, request):
        from community.models import CommunityCensusData
        
        # Start with all compliance records
        calculations = ComplianceCalculation.objects.all().select_related('community', 'census_year', 'created_by')
        
        # Exclude compliance records for communities that are inactive in their census year
        inactive_community_census = CommunityCensusData.objects.filter(is_active=False)
        
        # Create exclude filter for inactive combinations
        exclude_filters = Q()
        for census_data in inactive_community_census:
            exclude_filters |= Q(
                community_id=census_data.community_id,
                census_year_id=census_data.census_year_id
            )
        
        if exclude_filters:
            calculations = calculations.exclude(exclude_filters)
        
        # Apply user filters
        program = request.query_params.get('program')
        community = request.query_params.get('community')
        census_year = request.query_params.get('census_year')
        year = request.query_params.get('year')
        status_filter = request.query_params.get('status')
        search = request.query_params.get('search')
        
        if search:
            calculations = calculations.filter(
                Q(community__name__icontains=search) |
                Q(program__icontains=search) |
                Q(census_year__year__icontains=search)
            )
        if program:
            calculations = calculations.filter(program=program)
        if community:
            calculations = calculations.filter(community__id=community)
        if census_year:
            calculations = calculations.filter(census_year__id=census_year)
        if year:
            calculations = calculations.filter(census_year__year=year)
        if status_filter:
            if status_filter == 'compliant':
                calculations = calculations.filter(shortfall=0, excess=0)
            elif status_filter == 'shortfall':
                calculations = calculations.filter(shortfall__gt=0)
            elif status_filter == 'excess':
                calculations = calculations.filter(excess__gt=0)
        
        # Compute summary aggregates
        compliant_communities = calculations.filter(shortfall=0, excess=0).count()
        total_shortfall = calculations.aggregate(total=Sum('shortfall'))['total'] or 0
        total_excess = calculations.aggregate(total=Sum('excess'))['total'] or 0
        overall_rate = calculations.aggregate(avg=Avg('compliance_rate'))['avg'] or 0
        total_sites = calculations.aggregate(total=Sum('actual_sites'))['total'] or 0
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        calculations = calculations.order_by(ordering)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(calculations, request)
        
        if page is not None:
            serializer = ComplianceCalculationSerializer(page, many=True)
            response_data = paginator.get_paginated_response(serializer.data).data
            response_data['summary'] = {
                'compliant_communities': compliant_communities,
                'shortfalls': total_shortfall,
                'excesses': total_excess,
                'overall_rate': round(overall_rate, 2) if overall_rate else 0,
                'total_sites': total_sites
            }
            return Response(response_data)
        
        serializer = ComplianceCalculationSerializer(calculations, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """
        Trigger compliance calculation for a specific community and census year.
        """
        community_id = request.data.get('community')
        program = request.data.get('program')
        census_year_id = request.data.get('census_year')
        
        if not community_id:
            return Response(
                {'error': 'community field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate that the community exists
        try:
            from community.models import Community, CensusYear
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {'error': 'Community not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get census year
        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=census_year_id)
            except CensusYear.DoesNotExist:
                return Response(
                    {'error': 'Census year not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Get the latest census year for this community
            latest_census_data = community.census_data.order_by('-census_year__year').first()
            if latest_census_data:
                census_year = latest_census_data.census_year
            else:
                return Response(
                    {'error': 'No census data found for this community'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Trigger async calculation (will create zero values if community is inactive)
        task = calculate_community_compliance.delay(
            str(community_id), 
            program, 
            census_year_id
        )
        
        return Response({
            'message': 'Compliance calculation triggered',
            'task_id': task.id,
            'community': community_id,
            'program': program or 'all',
            'census_year': census_year_id or 'latest'
        }, status=status.HTTP_202_ACCEPTED)


class ComplianceCalculationDetail(APIView):
    """
    Retrieve or delete a compliance calculation.
    """
    def get_object(self, pk):
        try:
            return ComplianceCalculation.objects.select_related('community', 'census_year', 'created_by').get(pk=pk)
        except ComplianceCalculation.DoesNotExist:
            return None
    
    def get(self, request, pk):
        calculation = self.get_object(pk)
        if calculation is None:
            return Response(
                {'error': 'Compliance calculation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = ComplianceCalculationSerializer(calculation)
        return Response(serializer.data)
    
    def delete(self, request, pk):
        calculation = self.get_object(pk)
        if calculation is None:
            return Response(
                {'error': 'Compliance calculation not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        calculation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManualComplianceRecalculation(APIView):
    """
    API endpoint to manually trigger full compliance recalculation for all communities.
    Recalculates compliance for all active communities, checking all regulatory rules and sites.
    """
    
    def post(self, request):
        """
        Trigger manual compliance recalculation for all communities or a specific census year.
        
        Query Parameters:
        - census_year (optional): Census year ID to recalculate. If not provided, uses latest census year.
        """
        from .tasks import calculate_all_compliance
        from community.models import CensusYear
        
        census_year_id = request.data.get('census_year') or request.query_params.get('census_year')
        
        # Validate census year if provided
        if census_year_id:
            try:
                census_year = CensusYear.objects.get(id=census_year_id)
                census_year_value = census_year.year
            except CensusYear.DoesNotExist:
                return Response(
                    {'error': f'Census year with ID {census_year_id} not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Use latest census year
            census_year = CensusYear.objects.order_by('-year').first()
            if not census_year:
                return Response(
                    {'error': 'No census year found in the system'},
                    status=status.HTTP_404_NOT_FOUND
                )
            census_year_id = census_year.id
            census_year_value = census_year.year
        
        # Trigger async calculation for all communities
        task = calculate_all_compliance.delay(census_year_id)
        
        return Response({
            'message': 'Full compliance recalculation triggered successfully',
            'task_id': task.id,
            'census_year': census_year_value,
            'census_year_id': census_year_id,
            'description': 'Recalculating compliance for all active communities with all regulatory rules and site data',
            'status': 'processing'
        }, status=status.HTTP_202_ACCEPTED)
