from rest_framework.views import APIView
# APIView provides the base class for API views in Django REST Framework
from rest_framework.response import Response
# Response is used to return HTTP responses with data
from rest_framework import status
# status contains HTTP status codes
from django.shortcuts import get_object_or_404
# get_object_or_404 raises 404 if object not found
from django.db.models import Q
# Q is used for complex database queries
from rest_framework.pagination import PageNumberPagination
# Importing PageNumberPagination for pagination support
from .models import RegulatoryRuleCensusData
# Importing the models for database operations
from .serializers import RegulatoryRuleCensusDataSerializer
# Importing serializers for data validation and conversion

class RegulatoryRulePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100

class RegulatoryRuleListCreate(APIView):
    """
    APIView for listing all RegulatoryRuleCensusData and creating new ones.
    
    GET /rules/: Returns a list of all regulatory rule census data with optional search, filters, and sorting.
    POST /rules/: Creates a new regulatory rule census data.
    """
    pagination_class = RegulatoryRulePagination()
    def get(self, request):
        # Retrieve all RegulatoryRuleCensusData instances initially
        queryset = RegulatoryRuleCensusData.objects.select_related('regulatory_rule', 'census_year').all()

        # Search functionality
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(regulatory_rule__name__icontains=search_query) |
                Q(regulatory_rule__description__icontains=search_query)
            )

        # Filters
        year = request.GET.get('year')
        if year:
            queryset = queryset.filter(census_year__year=year)

        program = request.GET.get('program')
        if program:
            queryset = queryset.filter(program=program)

        category = request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)

        rule_type = request.GET.get('rule_type')
        if rule_type:
            queryset = queryset.filter(rule_type=rule_type)

        is_active = request.GET.get('is_active')
        if is_active is not None:
            is_active_bool = is_active.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_active=is_active_bool)

        # Sorting - handle valid field names
        sort_by = request.GET.get('sort', '-census_year__year')  # Default sort by census year descending
        
        # Map of allowed sort fields to prevent FieldError
        valid_sort_fields = {
            'census_year__year': 'census_year__year',
            '-census_year__year': '-census_year__year',
            'program': 'program',
            '-program': '-program',
            'category': 'category', 
            '-category': '-category',
            'rule_type': 'rule_type',
            '-rule_type': '-rule_type',
            'is_active': 'is_active',
            '-is_active': '-is_active',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'updated_at': 'updated_at',
            '-updated_at': '-updated_at',
            'min_population': 'min_population',
            '-min_population': '-min_population',
            'max_population': 'max_population',
            '-max_population': '-max_population',
            'site_per_population': 'site_per_population',
            '-site_per_population': '-site_per_population',
            'base_required_sites': 'base_required_sites',
            '-base_required_sites': '-base_required_sites',
            # Related field sorting
            'name': 'regulatory_rule__name',
            '-name': '-regulatory_rule__name',
            'description': 'regulatory_rule__description',
            '-description': '-regulatory_rule__description',
        }
        
        # Use valid sort field or default
        sort_field = valid_sort_fields.get(sort_by, '-census_year__year')
        queryset = queryset.order_by(sort_field)

        # Serialize the filtered and sorted queryset
        serializer = RegulatoryRuleCensusDataSerializer(queryset, many=True)
        
        # Apply pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = RegulatoryRuleCensusDataSerializer(paginated_queryset, many=True)
        
        # Return the serialized data in the response with pagination metadata
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Deserialize the incoming JSON data
        serializer = RegulatoryRuleCensusDataSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            # Save the new rule census data to the database
            serializer.save()
            # Return the created data with 201 status
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Return validation errors with 400 status
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegulatoryRuleDetail(APIView):
    """
    APIView for retrieving, updating, and deleting a specific RegulatoryRuleCensusData.
    
    GET /rules/<pk>/: Returns details of a specific rule census data (pk is integer ID).
    PUT /rules/<pk>/: Updates a specific rule census data.
    DELETE /rules/<pk>/: Deletes a specific rule census data.
    """
    def get(self, request, pk):
        # Retrieve the rule census data by primary key (integer), raise 404 if not found
        rule = get_object_or_404(RegulatoryRuleCensusData, pk=pk)
        # Serialize the rule instance
        serializer = RegulatoryRuleCensusDataSerializer(rule)
        # Return the serialized data
        return Response(serializer.data)

    def put(self, request, pk):
        # Retrieve the rule census data by primary key
        rule = get_object_or_404(RegulatoryRuleCensusData, pk=pk)
        # Deserialize and validate the update data
        serializer = RegulatoryRuleCensusDataSerializer(rule, data=request.data, context={'request': request})
        if serializer.is_valid():
            # Save the updated rule census data
            serializer.save()
            # Return the updated data
            return Response(serializer.data)
        # Return validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # Retrieve the rule census data by primary key
        rule = get_object_or_404(RegulatoryRuleCensusData, pk=pk)
        # Delete the rule census data from the database
        rule.delete()
        # Return 204 No Content status
        return Response(status=status.HTTP_204_NO_CONTENT)
