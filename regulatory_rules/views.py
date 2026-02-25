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
from .models import RegulatoryRule
# Importing the models for database operations
from .serializers import RegulatoryRuleSerializer
# Importing serializers for data validation and conversion

class RegulatoryRuleListCreate(APIView):
    """
    APIView for listing all RegulatoryRules and creating new ones.
    
    GET /rules/: Returns a list of all regulatory rules with optional search, filters, and sorting.
    POST /rules/: Creates a new regulatory rule.
    """
    def get(self, request):
        # Retrieve all RegulatoryRule instances initially
        queryset = RegulatoryRule.objects.all()

        # Search functionality
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(name__icontains=search_query) |
                Q(description__icontains=search_query)
            )

        # Filters
        year = request.GET.get('year')
        if year:
            queryset = queryset.filter(year=year)

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

        # Sorting
        sort_by = request.GET.get('sort', 'created_at')  # Default sort by created_at
        if sort_by.startswith('-'):
            # Descending
            queryset = queryset.order_by(sort_by)
        else:
            # Ascending, but allow descending with - prefix
            queryset = queryset.order_by(sort_by)

        # Serialize the filtered and sorted queryset
        serializer = RegulatoryRuleSerializer(queryset, many=True)
        # Return the serialized data in the response
        return Response(serializer.data)

    def post(self, request):
        # Deserialize the incoming JSON data
        serializer = RegulatoryRuleSerializer(data=request.data)
        if serializer.is_valid():
            # Save the new rule to the database
            serializer.save()
            # Return the created data with 201 status
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Return validation errors with 400 status
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegulatoryRuleDetail(APIView):
    """
    APIView for retrieving, updating, and deleting a specific RegulatoryRule.
    
    GET /rules/<pk>/: Returns details of a specific rule (pk is UUID).
    PUT /rules/<pk>/: Updates a specific rule.
    DELETE /rules/<pk>/: Deletes a specific rule.
    """
    def get(self, request, pk):
        # Retrieve the rule by primary key (UUID), raise 404 if not found
        rule = get_object_or_404(RegulatoryRule, pk=pk)
        # Serialize the rule instance
        serializer = RegulatoryRuleSerializer(rule)
        # Return the serialized data
        return Response(serializer.data)

    def put(self, request, pk):
        # Retrieve the rule by primary key
        rule = get_object_or_404(RegulatoryRule, pk=pk)
        # Deserialize and validate the update data
        serializer = RegulatoryRuleSerializer(rule, data=request.data)
        if serializer.is_valid():
            # Save the updated rule
            serializer.save()
            # Return the updated data
            return Response(serializer.data)
        # Return validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # Retrieve the rule by primary key
        rule = get_object_or_404(RegulatoryRule, pk=pk)
        # Delete the rule from the database
        rule.delete()
        # Return 204 No Content status
        return Response(status=status.HTTP_204_NO_CONTENT)
