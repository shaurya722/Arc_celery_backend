from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Community
from .serializers import CommunitySerializer
from complaince.tasks import calculate_community_compliance


class CommunityPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100


class CommunityListCreate(APIView):
    pagination_class = CommunityPagination()

    def get(self, request):
        queryset = Community.objects.all()

        # Search
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))

        # Filters
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(year=year)

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
        sort = request.query_params.get('sort', 'created_at')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunitySerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CommunitySerializer(data=request.data)
        if serializer.is_valid():
            community = serializer.save()
            calculate_community_compliance.delay(str(community.id))
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityDetail(APIView):
    def get_object(self, pk):
        try:
            return Community.objects.get(pk=pk)
        except Community.DoesNotExist:
            return None

    def get(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response({"error": "Community not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunitySerializer(community)
        return Response(serializer.data)

    def put(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response({"error": "Community not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunitySerializer(community, data=request.data)
        if serializer.is_valid():
            community = serializer.save()
            calculate_community_compliance.delay(str(community.id))
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response({"error": "Community not found"}, status=status.HTTP_404_NOT_FOUND)
        community.delete()
        return Response({"message": "Community deleted"}, status=status.HTTP_204_NO_CONTENT)
