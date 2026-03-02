from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
from django.db.models import F, Exists, OuterRef, Q
from .models import ComplianceCalculation
from .serializers import ComplianceCalculationSerializer
from .tasks import calculate_community_compliance


class ComplianceCalculationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ComplianceCalculationListCreate(APIView):
    """
    List all compliance calculations or trigger a new calculation.
    """
    pagination_class = ComplianceCalculationPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['community', 'program', 'created_at']
    search_fields = ['community__name', 'program']
    ordering_fields = ['created_at', 'compliance_rate', 'shortfall']
    
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
        
        if program:
            calculations = calculations.filter(program=program)
        if community:
            calculations = calculations.filter(community__id=community)
        if census_year:
            calculations = calculations.filter(census_year__id=census_year)
        
        # Apply ordering
        ordering = request.query_params.get('ordering', '-created_at')
        calculations = calculations.order_by(ordering)
        
        # Pagination
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(calculations, request)
        
        if page is not None:
            serializer = ComplianceCalculationSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        
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

