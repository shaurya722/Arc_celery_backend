from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.pagination import PageNumberPagination
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
        calculations = ComplianceCalculation.objects.all().select_related('community', 'created_by')
        
        # Apply filters
        program = request.query_params.get('program')
        community = request.query_params.get('community')
        
        if program:
            calculations = calculations.filter(program=program)
        if community:
            calculations = calculations.filter(community__id=community)
        
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
        Trigger compliance calculation for a specific community.
        """
        community_id = request.data.get('community')
        program = request.data.get('program')
        
        if not community_id:
            return Response(
                {'error': 'community field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Trigger async calculation
        task = calculate_community_compliance.delay(str(community_id), program)
        
        return Response({
            'message': 'Compliance calculation triggered',
            'task_id': task.id,
            'community': community_id,
            'program': program or 'all'
        }, status=status.HTTP_202_ACCEPTED)


class ComplianceCalculationDetail(APIView):
    """
    Retrieve or delete a compliance calculation.
    """
    def get_object(self, pk):
        try:
            return ComplianceCalculation.objects.select_related('community', 'created_by').get(pk=pk)
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

