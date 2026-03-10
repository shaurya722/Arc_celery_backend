from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from .models import Site, SiteCensusData
from .serializers import SiteSerializer, SiteCensusDataSerializer
from complaince.utils import calculate_required_events
from community.models import Community, CensusYear
import uuid


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


class SiteApproveEvents(APIView):
    """
    API for approving multiple Event sites.
    Accepts a list of site census data IDs and sets event_approved=True and is_active=True for Event sites.
    """

    def put(self, request):
        """Approve or unapprove multiple Event sites based on is_event flag"""
        site_ids = request.data.get('site_ids', [])
        is_event = request.data.get('is_event', True)  # Default to approve if not specified

        if not site_ids:
            return Response(
                {"error": "site_ids list is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not isinstance(site_ids, list):
            return Response(
                {"error": "site_ids must be a list of integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            site_ids = [int(site_id) for site_id in site_ids]
        except (ValueError, TypeError):
            return Response(
                {"error": "All site_ids must be valid integers"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get the sites to update
        sites_to_update = SiteCensusData.objects.filter(
            id__in=site_ids,
            site_type='Event'
        )

        if not sites_to_update.exists():
            return Response(
                {"message": "No Event sites found with the provided IDs"},
                status=status.HTTP_200_OK
            )

        # Count before update
        sites_found = sites_to_update.count()

        # Update based on is_event
        updated_count = 0
        for site in sites_to_update:
            site.event_approved = is_event
            site.save()  # This will sync is_active based on site_type and event_approved
            updated_count += 1

        action = "approved" if is_event else "unapproved"

        return Response({
            "message": f"Successfully {action} {updated_count} Event sites",
            "updated_sites": updated_count,
            "total_requested": len(site_ids),
            "sites": [
                {
                    "id": site.id,
                    "site_name": site.site.site_name,
                    "community": site.community.name if site.community else None,
                    "census_year": site.census_year.year,
                    "is_active": site.is_active,
                    "event_approved": site.event_approved
                }
                for site in sites_to_update
            ]
        }, status=status.HTTP_200_OK)


class EventListing(APIView):
    """
    API for Event Listing - shows communities with event shortfall, their associated events,
    and compliance data (shortfall, applied_event, available_event) for a specific census year.
    Only returns communities with shortfall > 0.
    """
    pagination_class = SitePagination()

    def get(self, request, pk=None):
        # Get census year from query params
        year = request.query_params.get('year', None)
        if year:
            try:
                from community.models import CensusYear
                census_year = CensusYear.objects.get(year=year)
            except CensusYear.DoesNotExist:
                return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Use latest census year
            from community.models import CensusYear
            census_year = CensusYear.objects.order_by('-year').first()
            if not census_year:
                return Response({"error": "No census year found"}, status=status.HTTP_404_NOT_FOUND)

        if pk:
            # Get single community
            from django.shortcuts import get_object_or_404
            community = get_object_or_404(Community, id=pk)

            # Get all event sites in this census year (active and inactive)
            event_sites = SiteCensusData.objects.filter(
                site_type='Event',
                census_year=census_year
            ).select_related('site', 'community')

            # Calculate required events
            required = calculate_required_events(community, census_year)

            # Count applied events (active events assigned to this community)
            applied_event = event_sites.filter(
                community=community,
                is_active=True
            ).count()

            # Count available events (inactive events assigned to this community)
            available_event = event_sites.filter(
                community=community,
                is_active=False
            ).count()

            # Calculate shortfall
            shortfall = max(0, required - applied_event)

            # Get associated events (all assigned events)
            associated_events = event_sites.filter(
                community=community
            ).values('id', 'site__id', 'site__site_name', 'is_active')

            events_list = [
                {"id": event['id'], "site_id": event['site__id'], "site_name": event['site__site_name'], "is_active": event['is_active']}
                for event in associated_events
            ]

            data = {
                "id": str(uuid.uuid4()),
                "community": {"id": community.id, "name": community.name},
                "Events": events_list,
                "shortfall": shortfall,
                "applied_event": applied_event,
                "availabel_event": available_event
            }

            return Response(data, status=status.HTTP_200_OK)

        # List all communities
        # Get all event sites in this census year (active and inactive)
        event_sites = SiteCensusData.objects.filter(
            site_type='Event',
            census_year=census_year
        ).select_related('site', 'community')

        # Get available events (not assigned to any community or inactive)
        available_event_count = event_sites.filter(
            Q(community__isnull=True) | Q(is_active=False)
        ).count()

        # Group by community (unique IDs)
        communities_with_events = set(
            event_sites.filter(community__isnull=False).values_list('community', flat=True)
        )

        result = []

        for community_id in communities_with_events:
            from community.models import Community
            try:
                community = Community.objects.get(id=community_id)
            except Community.DoesNotExist:
                continue

            # Calculate required events
            required = calculate_required_events(community, census_year)

            # Count applied events (active events assigned to this community)
            applied_event = event_sites.filter(
                community=community,
                is_active=True
            ).count()

            # Count available events (inactive events assigned to this community)
            available_event = event_sites.filter(
                community=community,
                is_active=False
            ).count()

            # Calculate shortfall
            shortfall = max(0, required - applied_event)

            # Include if there are any assigned events (active or inactive)
            if applied_event > 0 or available_event > 0:
                # Get associated events (all assigned events)
                associated_events = event_sites.filter(
                    community=community
                ).values('id', 'site__id', 'site__site_name', 'is_active')

                events_list = [
                    {"id": event['id'], "site_id": event['site__id'], "site_name": event['site__site_name'], "is_active": event['is_active']}
                    for event in associated_events
                ]

                result.append({
                    "community": {"id": community_id, "name": community.name},
                    "Events": events_list,
                    "shortfall": shortfall,
                    "applied_event": applied_event,
                    "availabel_event": available_event  # Per community count of inactive assigned events
                })

        # Search
        search = request.query_params.get('search', None)
        if search:
            result = [item for item in result if search.lower() in item['community']['name'].lower()]

        # Pagination
        paginator = self.pagination_class
        paginated_result = paginator.paginate_queryset(result, request)
        return paginator.get_paginated_response(paginated_result)