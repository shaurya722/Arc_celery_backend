import csv
import io
from datetime import datetime

from django.http import HttpResponse
from rest_framework.views import APIView
# APIView provides the base class for API views in Django REST Framework
from rest_framework.permissions import IsAuthenticated
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


def filter_regulatory_rule_census_queryset(queryset, query_params):
    """
    Same filters and ordering as ``RegulatoryRuleListCreate.get``.
    ``query_params`` may be ``request.query_params`` or any dict-like mapping.
    """
    qp = query_params

    search_query = qp.get('search', '') or qp.get('search_query', '')
    if search_query:
        queryset = queryset.filter(
            Q(regulatory_rule__name__icontains=search_query)
            | Q(description__icontains=search_query)
        )

    year = qp.get('year') or qp.get('census_year')
    if year:
        queryset = queryset.filter(census_year__year=year)

    census_year_id = qp.get('census_year_id')
    if census_year_id not in (None, ''):
        try:
            queryset = queryset.filter(census_year_id=int(census_year_id))
        except (TypeError, ValueError):
            pass

    program = qp.get('program')
    if program:
        queryset = queryset.filter(program=program)

    category = qp.get('category')
    if category:
        queryset = queryset.filter(category=category)

    rule_type = qp.get('rule_type')
    if rule_type:
        queryset = queryset.filter(rule_type=rule_type)

    is_active = qp.get('is_active')
    if is_active is not None and str(is_active).strip() != '':
        is_active_bool = str(is_active).lower() in ('true', '1', 'yes')
        queryset = queryset.filter(is_active=is_active_bool)

    sort_by = qp.get('sort', '-census_year__year')
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
        'name': 'regulatory_rule__name',
        '-name': '-regulatory_rule__name',
        'description': 'description',
        '-description': '-description',
    }
    sort_field = valid_sort_fields.get(sort_by, '-census_year__year')
    queryset = queryset.order_by(sort_field)
    return queryset


class AuthenticatedAPIView(APIView):
    permission_classes = [IsAuthenticated]


class RegulatoryRulePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100

class RegulatoryRuleListCreate(AuthenticatedAPIView):
    """
    APIView for listing all RegulatoryRuleCensusData and creating new ones.
    
    GET /rules/: Returns a list of all regulatory rule census data with optional search, filters, and sorting.
    POST /rules/: Creates a new regulatory rule census data.
    """
    pagination_class = RegulatoryRulePagination()
    def get(self, request):
        queryset = RegulatoryRuleCensusData.objects.select_related('regulatory_rule', 'census_year').all()
        queryset = filter_regulatory_rule_census_queryset(queryset, request.query_params)

        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = RegulatoryRuleCensusDataSerializer(paginated_queryset, many=True)

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


class RegulatoryRuleCensusDataExportView(AuthenticatedAPIView):
    """
    GET /rules/export/: CSV export of regulatory rule census rows using the same filters as list
    (search, year, census_year_id, program, category, rule_type, is_active, sort). No pagination.
    """

    CSV_HEADERS = [
        'id',
        'regulatory_rule_id',
        'regulatory_rule_name',
        'census_year_id',
        'census_year',
        'program',
        'category',
        'rule_type',
        'min_population',
        'max_population',
        'site_per_population',
        'base_required_sites',
        'event_offset_percentage',
        'reallocation_percentage',
        'description',
        'is_active',
        'start_date',
        'end_date',
        'created_at',
        'updated_at',
    ]

    def get(self, request):
        queryset = RegulatoryRuleCensusData.objects.select_related('regulatory_rule', 'census_year').all()
        queryset = filter_regulatory_rule_census_queryset(queryset, request.query_params)

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(self.CSV_HEADERS)
        for row in queryset.iterator(chunk_size=500):
            w.writerow(
                [
                    row.id,
                    str(row.regulatory_rule_id),
                    row.regulatory_rule.name if row.regulatory_rule_id else '',
                    row.census_year_id or '',
                    row.census_year.year if row.census_year_id else '',
                    row.program,
                    row.category,
                    row.rule_type,
                    row.min_population if row.min_population is not None else '',
                    row.max_population if row.max_population is not None else '',
                    str(row.site_per_population) if row.site_per_population is not None else '',
                    row.base_required_sites if row.base_required_sites is not None else '',
                    row.event_offset_percentage if row.event_offset_percentage is not None else '',
                    row.reallocation_percentage if row.reallocation_percentage is not None else '',
                    (row.description or '').replace('\n', ' ').replace('\r', ''),
                    'true' if row.is_active else 'false',
                    row.start_date.isoformat() if row.start_date else '',
                    row.end_date.isoformat() if row.end_date else '',
                    row.created_at.isoformat() if row.created_at else '',
                    row.updated_at.isoformat() if row.updated_at else '',
                ]
            )
        buf.seek(0)
        fn = f'regulatory_rules_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        resp = HttpResponse(buf.getvalue(), content_type='text/csv; charset=utf-8')
        resp['Content-Disposition'] = f'attachment; filename="{fn}"'
        return resp

    def post(self, request):
        """Allow POST as an alias for GET (some frontends default to POST for exports)."""
        return self.get(request)


class RegulatoryRuleDetail(AuthenticatedAPIView):
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
