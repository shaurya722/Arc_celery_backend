from rest_framework.views import APIView
# APIView provides the base class for API views in Django REST Framework
from rest_framework.response import Response
# Response is used to return HTTP responses with data
from rest_framework import status
# status contains HTTP status codes
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
# get_object_or_404 raises 404 if object not found
from django.db.models import Q
# Q is used for complex database queries
from .models import Site
# Importing the models for database operations
from .serializers import SiteSerializer
# Importing serializers for data validation and conversion

class SiteListCreate(APIView):
    """
    APIView for listing all Sites and creating new ones.
    
    GET /sites/: Returns a list of all sites with optional search, filters, sorting, and pagination.
    POST /sites/: Creates a new site.
    """
    def get(self, request):
        # Retrieve all Site instances initially
        queryset = Site.objects.all()

        # Search functionality
        search_query = request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(site_name__icontains=search_query) |
                Q(site_type__icontains=search_query) |
                Q(address_city__icontains=search_query) |
                Q(address_postal_code__icontains=search_query)
            )

        # Filters
        is_active_filter = request.GET.get('is_active')
        if is_active_filter is not None:
            is_active_bool = is_active_filter.lower() in ('true', '1', 'yes')
            queryset = queryset.filter(is_active=is_active_bool)

        site_type = request.GET.get('site_type')
        if site_type:
            queryset = queryset.filter(site_type=site_type)

        operator_type = request.GET.get('operator_type')
        if operator_type:
            queryset = queryset.filter(operator_type=operator_type)

        community = request.GET.get('community')
        if community:
            queryset = queryset.filter(community=community)

        region = request.GET.get('region')
        if region:
            queryset = queryset.filter(region=region)

        # Sorting
        sort_by = request.GET.get('sort', 'created_at')  # Default sort by created_at
        queryset = queryset.order_by(sort_by)

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 10
        paginator.page_size_query_param = 'page_size'
        paginator.max_page_size = 100
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = SiteSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)
        else:
            serializer = SiteSerializer(queryset, many=True)
            return Response(serializer.data)

    def post(self, request):
        # Deserialize the incoming JSON data
        serializer = SiteSerializer(data=request.data)
        if serializer.is_valid():
            # Save the new site to the database
            serializer.save()
            # Return the created data with 201 status
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Return validation errors with 400 status
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SiteDetail(APIView):
    """
    APIView for retrieving, updating, and deleting a specific Site.
    
    GET /sites/<pk>/: Returns details of a specific site (pk is UUID).
    PUT /sites/<pk>/: Updates a specific site.
    DELETE /sites/<pk>/: Deletes a specific site.
    """
    def get(self, request, pk):
        # Retrieve the site by primary key (UUID), raise 404 if not found
        site = get_object_or_404(Site, pk=pk)
        # Serialize the site instance
        serializer = SiteSerializer(site)
        # Return the serialized data
        return Response(serializer.data)

    def put(self, request, pk):
        # Retrieve the site by primary key
        site = get_object_or_404(Site, pk=pk)
        # Deserialize and validate the update data
        serializer = SiteSerializer(site, data=request.data)
        if serializer.is_valid():
            # Save the updated site
            serializer.save()
            # Return the updated data
            return Response(serializer.data)
        # Return validation errors
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        # Retrieve the site by primary key
        site = get_object_or_404(Site, pk=pk)
        # Delete the site from the database
        site.delete()
        # Return 204 No Content status
        return Response(status=status.HTTP_204_NO_CONTENT)