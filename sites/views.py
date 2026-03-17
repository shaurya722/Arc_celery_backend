from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from django.http import HttpResponse
from .models import Site, SiteCensusData
from .serializers import SiteSerializer, SiteCensusDataSerializer
from complaince.utils import calculate_required_events
from community.models import Community, CensusYear
import uuid
import csv
import io
from datetime import datetime
from django.utils import timezone


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


class SiteCensusDataImportExport(APIView):
    """
    API for importing and exporting SiteCensusData via CSV.
    
    POST: Import SiteCensusData from CSV file upload
    GET: Export SiteCensusData to CSV (optional filter by census_year)
    """
    
    # Expected CSV headers
    CSV_HEADERS = [
        'site_name', 'census_year', 'community_name', 'site_type', 'operator_type', 'service_partner',
        'address_line_1', 'address_line_2', 'address_city', 'address_postal_code', 'region', 'service_area',
        'address_latitude', 'address_longitude', 'latitude', 'longitude', 'is_active', 'event_approved',
        'site_start_date', 'site_end_date', 'program_paint', 'program_paint_start_date', 'program_paint_end_date',
        'program_lights', 'program_lights_start_date', 'program_lights_end_date', 'program_solvents',
        'program_solvents_start_date', 'program_solvents_end_date', 'program_pesticides', 'program_pesticides_start_date',
        'program_pesticides_end_date', 'program_fertilizers', 'program_fertilizers_start_date', 'program_fertilizers_end_date'
    ]
    
    # Site type choices
    SITE_TYPE_CHOICES = [
        'Collection Site', 'Event', 'Municipal Depot', 'Seasonal Depot',
        'Return to Retail', 'Private Depot'
    ]
    
    # Operator type choices
    OPERATOR_TYPE_CHOICES = [
        'Retailer', 'Distributor', 'Municipal', 'First Nation/Indigenous',
        'Private Depot', 'Product Care', 'Regional District',
        'Regional Service Commission', 'Other'
    ]
    
    def post(self, request):
        """Import SiteCensusData from CSV file upload"""
        csv_file = request.FILES.get('file')
        
        if not csv_file:
            return Response(
                {'error': 'No file provided. Please upload a CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not csv_file.name.endswith('.csv'):
            return Response(
                {'error': 'Invalid file format. Please upload a CSV file.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            csv_content = csv_file.read().decode('utf-8')
            # Unescape newlines if they were escaped during file transfer
            csv_content = csv_content.replace('\\n', '\n').replace('\\r', '\r')
            # Normalize line endings
            csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n')
            reader = csv.DictReader(csv_content.splitlines())
        except Exception as e:
            return Response(
                {'error': f'Error reading CSV file: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate headers
        if not reader.fieldnames:
            return Response(
                {'error': 'CSV file is empty or has no headers.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check required headers
        required_headers = [
            'site_name', 'census_year', 'site_type', 'address_line_1',
            'address_city', 'region'
        ]
        missing_headers = [h for h in required_headers if h not in reader.fieldnames]
        if missing_headers:
            return Response({
                'error': f'Missing required headers: {", ".join(missing_headers)}',
                'expected_headers': self.CSV_HEADERS,
                'provided_headers': list(reader.fieldnames)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        errors = []
        imported_count = 0
        updated_count = 0
        row_number = 0
        
        for row in reader:
            row_number += 1
            row_errors = self._validate_row(row, row_number)
            
            if row_errors:
                errors.extend(row_errors)
                continue
            
            try:
                result = self._import_row(row)
                if result == 'created':
                    imported_count += 1
                elif result == 'updated':
                    updated_count += 1
            except Exception as e:
                errors.append({
                    'row': row_number,
                    'site': row.get('site_name', 'Unknown'),
                    'error': f'Import failed: {str(e)}'
                })
        
        response_data = {
            'success': len(errors) == 0,
            'imported': imported_count,
            'updated': updated_count,
            'errors': errors,
            'total_rows': row_number
        }
        
        if errors:
            response_data['error_count'] = len(errors)
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def get(self, request):
        """Export SiteCensusData to CSV (optional filter by census_year)"""
        census_year_filter = request.GET.get('census_year')
        
        queryset = SiteCensusData.objects.select_related('site', 'census_year', 'community').all()
        
        if census_year_filter:
            try:
                year = int(census_year_filter)
                queryset = queryset.filter(census_year__year=year)
            except ValueError:
                return Response(
                    {'error': f'Invalid census year: {census_year_filter}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create CSV response
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(self.CSV_HEADERS)
        
        # Write data rows
        for data in queryset:
            row = [
                data.site.site_name,
                data.census_year.year,
                data.community.name if data.community else '',
                data.site_type,
                data.operator_type or '',
                data.service_partner or '',
                data.address_line_1,
                data.address_line_2 or '',
                data.address_city,
                data.address_postal_code or '',
                data.region,
                data.service_area or '',
                data.address_latitude or '',
                data.address_longitude or '',
                data.latitude or '',
                data.longitude or '',
                'true' if data.is_active else 'false',
                'true' if data.event_approved else 'false',
                data.site_start_date.isoformat() if data.site_start_date else '',
                data.site_end_date.isoformat() if data.site_end_date else '',
                'true' if data.program_paint else 'false',
                data.program_paint_start_date.isoformat() if data.program_paint_start_date else '',
                data.program_paint_end_date.isoformat() if data.program_paint_end_date else '',
                'true' if data.program_lights else 'false',
                data.program_lights_start_date.isoformat() if data.program_lights_start_date else '',
                data.program_lights_end_date.isoformat() if data.program_lights_end_date else '',
                'true' if data.program_solvents else 'false',
                data.program_solvents_start_date.isoformat() if data.program_solvents_start_date else '',
                data.program_solvents_end_date.isoformat() if data.program_solvents_end_date else '',
                'true' if data.program_pesticides else 'false',
                data.program_pesticides_start_date.isoformat() if data.program_pesticides_start_date else '',
                data.program_pesticides_end_date.isoformat() if data.program_pesticides_end_date else '',
                'true' if data.program_fertilizers else 'false',
                data.program_fertilizers_start_date.isoformat() if data.program_fertilizers_start_date else '',
                data.program_fertilizers_end_date.isoformat() if data.program_fertilizers_end_date else ''
            ]
            writer.writerow(row)
        
        output.seek(0)
        csv_content = output.getvalue()
        
        response = HttpResponse(
            csv_content,
            content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = f'attachment; filename="site_census_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return response
    
    def _validate_row(self, row, row_number):
        """Validate a single CSV row and return list of errors"""
        errors = []
        
        # Required field validations
        site_name = row.get('site_name', '').strip()
        if not site_name:
            errors.append({'row': row_number, 'field': 'site_name', 'error': 'Site name is required'})
        
        census_year_str = row.get('census_year', '').strip()
        if not census_year_str:
            errors.append({'row': row_number, 'field': 'census_year', 'error': 'Census year is required'})
        else:
            try:
                year = int(census_year_str)
                if year < 1900 or year > 2100:
                    errors.append({'row': row_number, 'field': 'census_year', 'error': f'Census year must be between 1900 and 2100'})
            except ValueError:
                errors.append({'row': row_number, 'field': 'census_year', 'error': f'Invalid census year: {census_year_str}'})
        
        # Site type validation
        site_type = row.get('site_type', '').strip()
        if not site_type:
            errors.append({'row': row_number, 'field': 'site_type', 'error': 'Site type is required'})
        elif site_type not in self.SITE_TYPE_CHOICES:
            errors.append({'row': row_number, 'field': 'site_type', 'error': f'Invalid site type: {site_type}. Must be one of: {", ".join(self.SITE_TYPE_CHOICES)}'})
        
        # Address validations
        address_line_1 = row.get('address_line_1', '').strip()
        if not address_line_1:
            errors.append({'row': row_number, 'field': 'address_line_1', 'error': 'Address line 1 is required'})
        
        address_city = row.get('address_city', '').strip()
        if not address_city:
            errors.append({'row': row_number, 'field': 'address_city', 'error': 'Address city is required'})
        
        region = row.get('region', '').strip()
        if not region:
            errors.append({'row': row_number, 'field': 'region', 'error': 'Region is required'})
        
        # Operator type validation
        operator_type = row.get('operator_type', '').strip()
        if operator_type and operator_type not in self.OPERATOR_TYPE_CHOICES:
            errors.append({'row': row_number, 'field': 'operator_type', 'error': f'Invalid operator type: {operator_type}'})
        
        # Coordinate validations
        for coord_field in ['address_latitude', 'address_longitude', 'latitude', 'longitude']:
            coord_str = row.get(coord_field, '').strip()
            if coord_str:
                try:
                    coord = float(coord_str)
                    if coord_field in ['latitude'] and (coord < -90 or coord > 90):
                        errors.append({'row': row_number, 'field': coord_field, 'error': f'{coord_field} must be between -90 and 90'})
                    if coord_field in ['longitude'] and (coord < -180 or coord > 180):
                        errors.append({'row': row_number, 'field': coord_field, 'error': f'{coord_field} must be between -180 and 180'})
                except ValueError:
                    errors.append({'row': row_number, 'field': coord_field, 'error': f'Invalid {coord_field}: {coord_str}'})
        
        # Boolean field validations
        bool_fields = ['is_active', 'event_approved', 'program_paint', 'program_lights', 'program_solvents', 'program_pesticides', 'program_fertilizers']
        for field in bool_fields:
            value = row.get(field, '').strip().lower()
            if value and value not in ['true', 'false', '1', '0', 'yes', 'no', '']:
                errors.append({'row': row_number, 'field': field, 'error': f'Invalid boolean value for {field}: {value}'})
        
        # Date validations
        date_fields = [
            'site_start_date', 'site_end_date', 'program_paint_start_date', 'program_paint_end_date',
            'program_lights_start_date', 'program_lights_end_date', 'program_solvents_start_date',
            'program_solvents_end_date', 'program_pesticides_start_date', 'program_pesticides_end_date',
            'program_fertilizers_start_date', 'program_fertilizers_end_date'
        ]
        for date_field in date_fields:
            date_str = row.get(date_field, '').strip()
            if date_str:
                try:
                    datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    errors.append({'row': row_number, 'field': date_field, 'error': f'Invalid date format: {date_str}'})
        
        # Check census year exists
        if census_year_str and not errors:
            try:
                year = int(census_year_str)
                if not CensusYear.objects.filter(year=year).exists():
                    errors.append({'row': row_number, 'field': 'census_year', 'error': f'Census year {year} does not exist'})
            except ValueError:
                pass
        
        return errors
    
    def _import_row(self, row):
        """Import a single validated row. Returns 'created', 'updated', or raises exception."""
        site_name = row['site_name'].strip()
        census_year = int(row['census_year'].strip())
        
        # Get or create site
        site, _ = Site.objects.get_or_create(site_name=site_name)
        
        # Get census year
        census_year_obj = CensusYear.objects.get(year=census_year)
        
        # Get or create community if provided
        community = None
        community_name = row.get('community_name', '').strip()
        if community_name:
            community, _ = Community.objects.get_or_create(name=community_name)
        
        # Parse boolean values
        def parse_bool(value):
            if not value:
                return False
            return value.strip().lower() in ['true', '1', 'yes']
        
        # Parse optional decimal values
        def parse_decimal(value):
            if not value or value.strip() == '':
                return None
            try:
                return float(value.strip())
            except ValueError:
                return None
        
        # Parse optional datetime
        def parse_datetime(value):
            if not value or value.strip() == '':
                return None
            try:
                # Parse ISO format and make timezone-aware
                dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
                if dt.tzinfo is None:
                    dt = timezone.make_aware(dt)
                return dt
            except ValueError:
                return None
        
        # Check if record exists
        existing = SiteCensusData.objects.filter(
            site=site,
            census_year=census_year_obj
        ).first()
        
        data = {
            'site': site,
            'census_year': census_year_obj,
            'community': community,
            'site_type': row.get('site_type', '').strip(),
            'operator_type': row.get('operator_type', '').strip() or None,
            'service_partner': row.get('service_partner', '').strip() or None,
            'address_line_1': row.get('address_line_1', '').strip(),
            'address_line_2': row.get('address_line_2', '').strip() or None,
            'address_city': row.get('address_city', '').strip(),
            'address_postal_code': row.get('address_postal_code', '').strip() or None,
            'region': row.get('region', '').strip(),
            'service_area': row.get('service_area', '').strip() or None,
            'address_latitude': parse_decimal(row.get('address_latitude', '')),
            'address_longitude': parse_decimal(row.get('address_longitude', '')),
            'latitude': parse_decimal(row.get('latitude', '')),
            'longitude': parse_decimal(row.get('longitude', '')),
            'is_active': parse_bool(row.get('is_active', 'true')),
            'event_approved': parse_bool(row.get('event_approved', 'false')),
            'site_start_date': parse_datetime(row.get('site_start_date', '')),
            'site_end_date': parse_datetime(row.get('site_end_date', '')),
            'program_paint': parse_bool(row.get('program_paint', '')),
            'program_paint_start_date': parse_datetime(row.get('program_paint_start_date', '')),
            'program_paint_end_date': parse_datetime(row.get('program_paint_end_date', '')),
            'program_lights': parse_bool(row.get('program_lights', '')),
            'program_lights_start_date': parse_datetime(row.get('program_lights_start_date', '')),
            'program_lights_end_date': parse_datetime(row.get('program_lights_end_date', '')),
            'program_solvents': parse_bool(row.get('program_solvents', '')),
            'program_solvents_start_date': parse_datetime(row.get('program_solvents_start_date', '')),
            'program_solvents_end_date': parse_datetime(row.get('program_solvents_end_date', '')),
            'program_pesticides': parse_bool(row.get('program_pesticides', '')),
            'program_pesticides_start_date': parse_datetime(row.get('program_pesticides_start_date', '')),
            'program_pesticides_end_date': parse_datetime(row.get('program_pesticides_end_date', '')),
            'program_fertilizers': parse_bool(row.get('program_fertilizers', '')),
            'program_fertilizers_start_date': parse_datetime(row.get('program_fertilizers_start_date', '')),
            'program_fertilizers_end_date': parse_datetime(row.get('program_fertilizers_end_date', ''))
        }
        
        if existing:
            # Update existing record
            for key, value in data.items():
                setattr(existing, key, value)
            existing.save()
            return 'updated'
        else:
            # Create new record
            SiteCensusData.objects.create(**data)
            return 'created'


class SiteCensusDataImportTemplate(APIView):
    """
    API to download a CSV template for importing SiteCensusData.
    """
    
    def get(self, request):
        """Download CSV template with sample data from file"""
        try:
            import os
            from django.conf import settings
            
            template_path = os.path.join(settings.BASE_DIR, 'static', 'templates', 'site_census_data_template.csv')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    csv_content = f.read()
            else:
                raise FileNotFoundError("Template file not found")
                
        except Exception:
            # Fallback to hardcoded template
            headers = [
                'site_name', 'census_year', 'community_name', 'site_type', 'operator_type', 'service_partner',
                'address_line_1', 'address_line_2', 'address_city', 'address_postal_code', 'region', 'service_area',
                'address_latitude', 'address_longitude', 'latitude', 'longitude', 'is_active', 'event_approved',
                'site_start_date', 'site_end_date', 'program_paint', 'program_paint_start_date', 'program_paint_end_date',
                'program_lights', 'program_lights_start_date', 'program_lights_end_date', 'program_solvents',
                'program_solvents_start_date', 'program_solvents_end_date', 'program_pesticides', 'program_pesticides_start_date',
                'program_pesticides_end_date', 'program_fertilizers', 'program_fertilizers_start_date', 'program_fertilizers_end_date'
            ]
            sample_data = [
                ['Sample Collection Site', '2030', 'Toronto', 'Collection Site', 'Retailer', 'Partner A',
                 '123 Main St', '', 'Toronto', 'M5V 3A8', 'Central', 'Downtown',
                 '43.6532', '-79.3832', '43.6532', '-79.3832', 'true', 'false',
                 '2030-01-01T00:00:00', '', 'true', '2030-01-01T00:00:00', '2030-12-31T23:59:59',
                 'true', '2030-01-01T00:00:00', '', 'false', '', '', 'false', '', '', 'false', '', ''],
                ['Sample Event Site', '2030', 'Vancouver', 'Event', 'Municipal', '',
                 '456 Event Ave', 'Suite 100', 'Vancouver', 'V6B 1A1', 'West', 'Metro',
                 '49.2827', '-123.1207', '49.2827', '-123.1207', 'true', 'true',
                 '2030-06-01T00:00:00', '2030-06-30T23:59:59', 'true', '2030-06-01T00:00:00', '2030-06-30T23:59:59',
                 'false', '', '', 'true', '2030-06-01T00:00:00', '2030-06-30T23:59:59', 'false', '', '', 'false', '', ''],
                ['Sample Depot', '2030', 'Montreal', 'Municipal Depot', 'Municipal', 'City Services',
                 '789 Depot Rd', '', 'Montreal', 'H3A 0G4', 'East', 'City Center',
                 '45.5017', '-73.5673', '45.5017', '-73.5673', 'true', 'false',
                 '2030-01-01T00:00:00', '', 'true', '2030-01-01T00:00:00', '',
                 'true', '2030-01-01T00:00:00', '', 'true', '2030-01-01T00:00:00', '', 'true', '2030-01-01T00:00:00', '', 'true', '2030-01-01T00:00:00', '']
            ]
            
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='\n')
            writer.writerow(headers)
            writer.writerows(sample_data)
            output.seek(0)
            csv_content = output.getvalue()
        
        # Ensure proper encoding and line endings
        csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n')
        
        response = HttpResponse(
            csv_content,
            content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="site_census_data_template.csv"'
        return response