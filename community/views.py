from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from uuid import UUID
from .models import Community, CommunityCensusData, CensusYear, AdjacentCommunity
from .serializers import CommunitySerializer, CommunityCensusDataSerializer, CensusYearSerializer, CensusYearWithDataSerializer, AdjacentCommunitySerializer, AdjacentCommunityReallocationSerializer, MapDataSerializer
from .geo_utils import extract_geojson_geometry, normalize_polygon_geojson
from .spatial_sql import community_ids_touching_polygon
from .map_serializers import CommunityMapListSerializer


class CommunityPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'limit'
    page_query_param = 'page'
    max_page_size = 100


class CommunityListCreate(APIView):
    """
    API for Community static identity with nested census data.
    Returns communities with their census_years as nested arrays.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        # Query Community objects with prefetch_related for census data
        queryset = Community.objects.prefetch_related('census_data__census_year').all()

        # Search by name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(name__icontains=search))

        # Filters for census data (will filter communities that have matching census data)
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_data__census_year__year=year)

        tier = request.query_params.get('tier', None)
        if tier:
            queryset = queryset.filter(census_data__tier=tier)

        region = request.query_params.get('region', None)
        if region:
            queryset = queryset.filter(census_data__region=region)

        is_active = request.query_params.get('is_active', None)
        if is_active:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            queryset = queryset.filter(census_data__is_active=is_active_bool)

        # Sort
        sort = request.query_params.get('sort', 'name')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunitySerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        # Create new census data record
        serializer = CommunityCensusDataSerializer(data=request.data)
        if serializer.is_valid():
            census_data = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityCensusDataListCreate(APIView):
    """
    API for year-specific community data.
    Use this for filtering by population, tier, region, is_active, etc.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        queryset = CommunityCensusData.objects.select_related('community', 'census_year').all()

        # Search by community name
        search = request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(Q(community__name__icontains=search))

        # Filters for year-specific data
        year = request.query_params.get('year', None)
        if year:
            queryset = queryset.filter(census_year__year=year)

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

        # Sort - handle valid field names
        sort_by = request.query_params.get('sort', 'community__name')  # Default sort by community name
        
        # Map of allowed sort fields to prevent FieldError
        valid_sort_fields = {
            # Direct model fields
            'id': 'id',
            '-id': '-id',
            'population': 'population',
            '-population': '-population',
            'tier': 'tier',
            '-tier': '-tier',
            'region': 'region',
            '-region': '-region',
            'zone': 'zone',
            '-zone': '-zone',
            'province': 'province',
            '-province': '-province',
            'is_active': 'is_active',
            '-is_active': '-is_active',
            'created_at': 'created_at',
            '-created_at': '-created_at',
            'updated_at': 'updated_at',
            '-updated_at': '-updated_at',
            'start_date': 'start_date',
            '-start_date': '-start_date',
            'end_date': 'end_date',
            '-end_date': '-end_date',
            
            # Related field sorting
            'name': 'community__name',
            '-name': '-community__name',
            'year': 'census_year__year',
            '-year': '-census_year__year',
        }
        
        # Use valid sort field or default to 'community__name'
        sort_field = valid_sort_fields.get(sort_by, 'community__name')
        queryset = queryset.order_by(sort_field)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CommunityCensusDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        serializer = CommunityCensusDataSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityDetail(APIView):
    """CRUD operations for single census data record"""
    
    def get_object(self, pk):
        try:
            return CommunityCensusData.objects.select_related('community', 'census_year').get(pk=pk)
        except CommunityCensusData.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Census data not found"}, status=status.HTTP_404_NOT_FOUND)
        census_data.delete()
        return Response({"message": "Census data deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class CommunityCensusDataDetail(APIView):
    """CRUD operations for year-specific community data"""
    
    def get_object(self, pk):
        try:
            return CommunityCensusData.objects.select_related('community', 'census_year').get(pk=pk)
        except CommunityCensusData.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single community census data record"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update community census data for a specific year"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CommunityCensusDataSerializer(census_data, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            census_data = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete community census data for a specific year"""
        census_data = self.get_object(pk)
        if not census_data:
            return Response({"error": "Community census data not found"}, status=status.HTTP_404_NOT_FOUND)
        census_data.delete()
        return Response({"message": "Community census data deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class CommunityDropdown(APIView):
    """Community dropdown API returning active communities for a census year"""

    def get(self, request):
        """List active communities filtered by census year"""
        census_year_id = request.query_params.get('census_year')
        year_value = request.query_params.get('year')

        if not census_year_id and not year_value:
            return Response(
                {"error": "Provide either 'census_year' (ID) or 'year' (value) query parameter"},
                status=status.HTTP_400_BAD_REQUEST
            )

        queryset = CommunityCensusData.objects.filter(is_active=True)

        if census_year_id:
            try:
                queryset = queryset.filter(census_year__id=int(census_year_id))
            except (TypeError, ValueError):
                return Response({"error": "census_year must be a valid integer ID"}, status=status.HTTP_400_BAD_REQUEST)

        if year_value:
            try:
                queryset = queryset.filter(census_year__year=int(year_value))
            except (TypeError, ValueError):
                return Response({"error": "year must be a valid integer"}, status=status.HTTP_400_BAD_REQUEST)

        communities = queryset.values('community__id', 'community__name').distinct().order_by('community__name')

        results = [
            {
                'id': str(item['community__id']),
                'name': item['community__name'],
            }
            for item in communities
        ]

        return Response({
            'communities': results,
            'total': len(results)
        })

class YearData(APIView):
    """
    API for Year data with pagination.
    Returns paginated year list.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        """Get years for dropdown with DRF pagination"""
        queryset = CensusYear.objects.order_by('-year')
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        years = list(paginated_queryset.values('id', 'year', 'start_date', 'end_date')) if hasattr(paginated_queryset, 'values') else [
            {'id': y.id, 'year': y.year, 'start_date': y.start_date, 'end_date': y.end_date} for y in paginated_queryset
        ]
        return paginator.get_paginated_response(years)

class YearDropdown(APIView):
    """
    API for Year dropdown with CRUD operations.
    Returns simple year list for dropdowns and supports full CRUD.
    """
    pagination_class = CommunityPagination()

    def get(self, request):
        """Get all years for dropdown"""
        years = CensusYear.objects.values('id', 'year', 'start_date', 'end_date').order_by('-year')
        return Response({
            'years': list(years),
            'total': len(years)
        })

    def post(self, request):
        """Create a new year"""
        serializer = CensusYearSerializer(data=request.data)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response({
                'id': census_year.id,
                'year': census_year.year,
                'start_date': census_year.start_date,
                'end_date': census_year.end_date,
                'message': f'Year {census_year.year} created successfully'
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, pk=None):
        """Update a year"""
        try:
            census_year = CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return Response({"error": "Year not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = CensusYearSerializer(census_year, data=request.data, partial=True)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response({
                'id': census_year.id,
                'year': census_year.year,
                'start_date': census_year.start_date,
                'end_date': census_year.end_date,
                'message': f'Year {census_year.year} updated successfully'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk=None):
        """Delete a year"""
        try:
            census_year = CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return Response({"error": "Year not found"}, status=status.HTTP_404_NOT_FOUND)

        year_value = census_year.year
        census_year.delete()
        return Response({
            'message': f'Year {year_value} deleted successfully'
        }, status=status.HTTP_204_NO_CONTENT)


class CensusYearListCreate(APIView):
    pagination_class = CommunityPagination()

    def get(self, request):
        # Query CensusYear with prefetch_related for efficiency
        queryset = CensusYear.objects.prefetch_related(
            'community_data__community',
            'site_data__site',
            'site_data__community',
            'regulatory_rule_data__regulatory_rule'
        ).all()

        # Sort
        sort = request.query_params.get('sort', '-year')
        queryset = queryset.order_by(sort)

        # Pagination
        paginator = self.pagination_class
        paginated_queryset = paginator.paginate_queryset(queryset, request)
        serializer = CensusYearWithDataSerializer(paginated_queryset, many=True)
        return paginator.get_paginated_response(serializer.data)

    def post(self, request):
        """Create a new census year"""
        serializer = CensusYearSerializer(data=request.data)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CensusYearDetail(APIView):
    """CRUD operations for individual census year"""
    
    def get_object(self, pk):
        try:
            return CensusYear.objects.get(pk=pk)
        except CensusYear.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a single census year"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CensusYearSerializer(census_year)
        return Response(serializer.data)

    def put(self, request, pk):
        """Update a census year"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = CensusYearSerializer(census_year, data=request.data, partial=True)
        if serializer.is_valid():
            census_year = serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete a census year and all associated data"""
        census_year = self.get_object(pk)
        if not census_year:
            return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        census_year.delete()
        return Response({"message": "Census year deleted successfully"}, status=status.HTTP_204_NO_CONTENT)


class AdjacentCommunityReallocationListCreate(APIView):
    """List all adjacent communities with reallocation data or create new ones"""

    def get(self, request):
        """List all adjacent communities with detailed reallocation information"""
        adjacencies = AdjacentCommunity.objects.select_related(
            'from_community', 'census_year'
        ).prefetch_related('to_communities').all()

        # Filters
        from_community = request.query_params.get('from_community')
        if from_community:
            # Check if it's a UUID or name
            try:
                # Try to parse as UUID
                UUID(from_community)
                # If successful, filter by ID
                adjacencies = adjacencies.filter(from_community__id=from_community)
            except ValueError:
                # Not a UUID, filter by name
                adjacencies = adjacencies.filter(from_community__name__icontains=from_community)

        census_year = request.query_params.get('census_year')
        if census_year:
            adjacencies = adjacencies.filter(census_year__year=census_year)

        serializer = AdjacentCommunityReallocationSerializer(adjacencies, many=True)
        return Response(serializer.data)

    def post(self, request):
        """Create new adjacent community with basic adjacency info"""
        serializer = AdjacentCommunitySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AdjacentCommunityReallocationDetail(APIView):
    """Get detailed reallocation information for a specific adjacency"""

    def get_object(self, pk):
        try:
            return AdjacentCommunity.objects.select_related(
                'from_community', 'census_year'
            ).prefetch_related('to_communities').get(pk=pk)
        except AdjacentCommunity.DoesNotExist:
            return None

    def get(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunityReallocationSerializer(adjacency)
        return Response(serializer.data)

    def put(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunitySerializer(adjacency, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdjacentCommunitySerializer(adjacency, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        adjacency = self.get_object(pk)
        if not adjacency:
            return Response({'error': 'Adjacent community not found'}, status=status.HTTP_404_NOT_FOUND)

        adjacency.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


import csv
import io
from datetime import datetime
from rest_framework.parsers import MultiPartParser, FormParser


class CommunityCensusDataImportExport(APIView):
    """
    API for importing and exporting CommunityCensusData via CSV.
    
    POST /community-census-data/import-export/ - Upload CSV file for import
    GET /community-census-data/import-export/?census_year=2024 - Export CSV data
    """
    parser_classes = [MultiPartParser, FormParser]

    # Expected CSV headers
    CSV_HEADERS = [
        'community_name', 'census_year', 'population', 'tier',
        'region', 'zone', 'province', 'is_active',
        'start_date', 'end_date'
    ]

    def get(self, request):
        """Export CommunityCensusData to CSV"""
        census_year_param = request.query_params.get('census_year')
        
        queryset = CommunityCensusData.objects.select_related(
            'community', 'census_year'
        ).all()
        
        if census_year_param:
            queryset = queryset.filter(census_year__year=census_year_param)
        
        # Create CSV response
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(self.CSV_HEADERS)
        
        # Write data rows
        for data in queryset:
            row = [
                data.community.name,
                data.census_year.year,
                data.population,
                data.tier,
                data.region,
                data.zone,
                data.province,
                data.is_active,
                data.start_date.isoformat() if data.start_date else '',
                data.end_date.isoformat() if data.end_date else '',
            ]
            writer.writerow(row)
        
        # Prepare response
        output.seek(0)
        response = Response(
            output.getvalue(),
            content_type='text/csv'
        )
        response['Content-Disposition'] = f'attachment; filename="community_census_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        return response

    def post(self, request):
        """Import CommunityCensusData from CSV file"""
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
            decoded_file = csv_file.read().decode('utf-8')
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)
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
        
        missing_headers = set(self.CSV_HEADERS) - set(reader.fieldnames)
        if missing_headers:
            return Response(
                {
                    'error': f'Missing required headers: {", ".join(missing_headers)}',
                    'expected_headers': self.CSV_HEADERS,
                    'provided_headers': list(reader.fieldnames)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        errors = []
        imported_count = 0
        updated_count = 0
        row_number = 1  # Start at 1 (header is row 0)
        
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
                    'community': row.get('community_name', 'Unknown'),
                    'error': f'Import failed: {str(e)}'
                })
        
        response_data = {
            'success': len(errors) == 0,
            'imported': imported_count,
            'updated': updated_count,
            'errors': errors,
            'total_rows': row_number - 1
        }
        
        if errors:
            response_data['error_count'] = len(errors)
            return Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def _validate_row(self, row, row_number):
        """Validate a single CSV row and return list of errors"""
        errors = []
        
        # Required field validations
        community_name = row.get('community_name', '').strip()
        if not community_name:
            errors.append({
                'row': row_number,
                'field': 'community_name',
                'error': 'Community name is required'
            })
        
        # Census year validation
        census_year_str = row.get('census_year', '').strip()
        if not census_year_str:
            errors.append({
                'row': row_number,
                'field': 'census_year',
                'error': 'Census year is required'
            })
        else:
            try:
                year = int(census_year_str)
                if year < 1900 or year > 2100:
                    errors.append({
                        'row': row_number,
                        'field': 'census_year',
                        'error': f'Census year must be between 1900 and 2100, got {year}'
                    })
            except ValueError:
                errors.append({
                    'row': row_number,
                    'field': 'census_year',
                    'error': f'Invalid census year: "{census_year_str}". Must be a valid integer.'
                })
        
        # Population validation
        population_str = row.get('population', '').strip()
        if not population_str:
            errors.append({
                'row': row_number,
                'field': 'population',
                'error': 'Population is required'
            })
        else:
            try:
                population = int(population_str)
                if population < 0:
                    errors.append({
                        'row': row_number,
                        'field': 'population',
                        'error': f'Population must be a positive integer, got {population}'
                    })
            except ValueError:
                errors.append({
                    'row': row_number,
                    'field': 'population',
                    'error': f'Invalid population: "{population_str}". Must be a valid integer.'
                })
        
        # Tier validation
        tier = row.get('tier', '').strip()
        if not tier:
            errors.append({
                'row': row_number,
                'field': 'tier',
                'error': 'Tier is required'
            })
        elif len(tier) > 50:
            errors.append({
                'row': row_number,
                'field': 'tier',
                'error': f'Tier must be 50 characters or less, got {len(tier)} characters'
            })
        
        # Region validation
        region = row.get('region', '').strip()
        if not region:
            errors.append({
                'row': row_number,
                'field': 'region',
                'error': 'Region is required'
            })
        elif len(region) > 50:
            errors.append({
                'row': row_number,
                'field': 'region',
                'error': f'Region must be 50 characters or less, got {len(region)} characters'
            })
        
        # Zone validation
        zone = row.get('zone', '').strip()
        if not zone:
            errors.append({
                'row': row_number,
                'field': 'zone',
                'error': 'Zone is required'
            })
        elif len(zone) > 50:
            errors.append({
                'row': row_number,
                'field': 'zone',
                'error': f'Zone must be 50 characters or less, got {len(zone)} characters'
            })
        
        # Province validation
        province = row.get('province', '').strip()
        if not province:
            errors.append({
                'row': row_number,
                'field': 'province',
                'error': 'Province is required'
            })
        elif len(province) > 50:
            errors.append({
                'row': row_number,
                'field': 'province',
                'error': f'Province must be 50 characters or less, got {len(province)} characters'
            })
        
        # Is active validation - optional field with default true
        is_active_str = row.get('is_active', '').strip().lower()
        if is_active_str and is_active_str not in ['true', 'false', '1', '0', 'yes', 'no']:
            errors.append({
                'row': row_number,
                'field': 'is_active',
                'error': f'Invalid is_active value: "{is_active_str}". Must be true/false, 1/0, or yes/no.'
            })
        
        # Date validations
        for date_field in ['start_date', 'end_date']:
            date_str = row.get(date_field, '').strip()
            if date_str:
                try:
                    datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except ValueError:
                    errors.append({
                        'row': row_number,
                        'field': date_field,
                        'error': f'Invalid date format: "{date_str}". Use ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).'
                    })
        
        # Check if census year exists
        if census_year_str and not errors:
            try:
                year = int(census_year_str)
                if not CensusYear.objects.filter(year=year).exists():
                    errors.append({
                        'row': row_number,
                        'field': 'census_year',
                        'error': f'Census year {year} does not exist in the system. Please create it first.'
                    })
            except ValueError:
                pass  # Already handled above
        
        return errors
    
    def _import_row(self, row):
        """Import a single validated row. Returns 'created', 'updated', or raises exception."""
        community_name = row['community_name'].strip()
        census_year = int(row['census_year'].strip())
        population = int(row['population'].strip())
        tier = row['tier'].strip()
        region = row['region'].strip()
        zone = row['zone'].strip()
        province = row['province'].strip()
        
        # Parse is_active
        is_active_str = row.get('is_active', 'true').strip().lower()
        is_active = is_active_str in ['true', '1', 'yes', '']
        
        # Parse dates
        start_date = None
        end_date = None
        
        if row.get('start_date', '').strip():
            start_date = datetime.fromisoformat(row['start_date'].strip().replace('Z', '+00:00'))
        if row.get('end_date', '').strip():
            end_date = datetime.fromisoformat(row['end_date'].strip().replace('Z', '+00:00'))
        
        # Get or create community
        community, _ = Community.objects.get_or_create(name=community_name)
        
        # Get census year object
        census_year_obj = CensusYear.objects.get(year=census_year)
        
        # Check if record exists
        existing = CommunityCensusData.objects.filter(
            community=community,
            census_year=census_year_obj
        ).first()
        
        if existing:
            # Update existing record
            existing.population = population
            existing.tier = tier
            existing.region = region
            existing.zone = zone
            existing.province = province
            existing.is_active = is_active
            existing.start_date = start_date
            existing.end_date = end_date
            existing.save()
            return 'updated'
        else:
            # Create new record
            CommunityCensusData.objects.create(
                community=community,
                census_year=census_year_obj,
                population=population,
                tier=tier,
                region=region,
                zone=zone,
                province=province,
                is_active=is_active,
                start_date=start_date,
                end_date=end_date
            )
            return 'created'


class CommunityCensusDataImportTemplate(APIView):
    """
    API to download a CSV template for importing CommunityCensusData.
    """
    
    def get(self, request):
        """Download CSV template with sample data from file"""
        try:
            # Read from static/templates directory
            import os
            from django.conf import settings
            
            template_path = os.path.join(settings.BASE_DIR, 'static', 'templates', 'community_census_data_template.csv')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    csv_content = f.read()
            else:
                raise FileNotFoundError("Template file not found")
                
        except Exception as e:
            # Fallback to hardcoded template if file not found
            import csv
            import io
            
            headers = [
                'community_name', 'census_year', 'population', 'tier',
                'region', 'zone', 'province', 'is_active',
                'start_date', 'end_date'
            ]
            sample_data = [
                ['Toronto', '2030', '2930000', 'Tier 1', 'Central', 'Zone A', 'Ontario', 'true', '2030-01-01T00:00:00', ''],
                ['Vancouver', '2030', '675218', 'Tier 1', 'West', 'Zone B', 'British Columbia', 'true', '2030-01-01T00:00:00', ''],
                ['Montreal', '2030', '1762949', 'Tier 1', 'East', 'Zone C', 'Quebec', 'true', '2030-01-01T00:00:00', ''],
            ]
            
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='\n')  # Force Unix line endings
            writer.writerow(headers)
            writer.writerows(sample_data)
            output.seek(0)
            csv_content = output.getvalue()
        
        # Ensure proper encoding and line endings for CSV response
        csv_content = csv_content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Use HttpResponse instead of DRF Response to avoid JSON escaping
        from django.http import HttpResponse
        response = HttpResponse(
            csv_content,
            content_type='text/csv; charset=utf-8'
        )
        response['Content-Disposition'] = 'attachment; filename="community_census_data_template.csv"'
        return response


class MapDataView(APIView):
    """API view for map data providing sites and municipalities for the React component"""

    def get(self, request):
        """Get map data (sites and municipalities) for the React component"""
        serializer = MapDataSerializer({}, context={'request': request})
        return Response(serializer.data)


class MapFilterOptionsView(APIView):
    """API view to get all available filter options for map data"""

    def get(self, request):
        """Get all available filter options"""
        from sites.models import SiteCensusData

        # Get census year from query params or use latest
        year = request.query_params.get('year')
        if year:
            try:
                from community.models import CensusYear
                census_year = CensusYear.objects.get(year=year)
            except CensusYear.DoesNotExist:
                return Response({"error": "Census year not found"}, status=status.HTTP_404_NOT_FOUND)
        else:
            from community.models import CensusYear
            census_year = CensusYear.objects.order_by('-year').first()
            if not census_year:
                return Response({"error": "No census year found"}, status=status.HTTP_404_NOT_FOUND)

        # Get distinct values for filters
        sites_queryset = SiteCensusData.objects.filter(census_year=census_year)

        # Get unique operator types
        operator_types = sites_queryset.exclude(operator_type__isnull=True).exclude(operator_type='').values_list('operator_type', flat=True).distinct().order_by('operator_type')

        # Get unique site types
        site_types = sites_queryset.exclude(site_type__isnull=True).exclude(site_type='').values_list('site_type', flat=True).distinct().order_by('site_type')

        # Get unique community names
        community_names = sites_queryset.exclude(community__isnull=True).values_list('community__name', flat=True).distinct().order_by('community__name')

        # Get unique site names (for search suggestions)
        site_names = sites_queryset.values_list('site__site_name', flat=True).distinct().order_by('site__site_name')[:100]  # Limit to 100 for performance

        # Get programs (from model choices)
        programs = ['Paint', 'Lighting', 'Solvents', 'Pesticides', 'Fertilizers']

        # Get status options
        status_options = ['Active', 'Inactive']

        return Response({
            'operator_types': list(operator_types),
            'site_types': list(site_types),
            'communities': list(community_names),
            'site_names': list(site_names),
            'programs': programs,
            'status': status_options,
            'census_year': {
                'id': census_year.id,
                'year': census_year.year,
            }
        })


def _save_community_map_boundary(community, geom_dict):
    """Persist polygon, recompute map adjacency (touch/overlap/intersect/near), sync symmetrical M2M."""
    neighbor_ids = community_ids_touching_polygon(geom_dict, exclude_id=community.pk)
    community.boundary = geom_dict
    community.save(update_fields=['boundary', 'updated_at'])
    neighbors = Community.objects.filter(pk__in=neighbor_ids)
    community.adjacent.set(neighbors)
    return neighbor_ids


class CommunityMapAvailableForAssignment(APIView):
    """
    Communities that already exist in the DB — use `id` as `community_id` when POSTing a drawn boundary.

    Query: ?search=foo&limit=500 (limit capped at 2000).
    """

    def get(self, request):
        qs = Community.objects.order_by('name').only('id', 'name', 'boundary')
        search = request.query_params.get('search')
        if search and str(search).strip():
            qs = qs.filter(name__icontains=str(search).strip())

        try:
            limit = int(request.query_params.get('limit', 500))
        except (TypeError, ValueError):
            limit = 500
        limit = max(1, min(limit, 2000))

        total = qs.count()
        communities = [
            {
                'id': str(c.id),
                'name': c.name,
                'has_boundary': c.boundary is not None,
            }
            for c in qs[:limit]
        ]

        return Response(
            {
                'communities': communities,
                'total': total,
                'returned': len(communities),
            }
        )


class CommunityMapBoundaryListCreate(APIView):
    """
    Leaflet / map flow: list communities with boundaries, or POST GeoJSON.

    Use GET …/map-communities/available/ to list DB communities; copy `id` into POST `community_id`.

    POST body (choose one):
    - community_id + boundary — set boundary on an existing community (map draw → that row).
    - name + boundary — create a new community (legacy / onboarding).
    """

    def get(self, request):
        qs = (
            Community.objects.filter(boundary__isnull=False)
            .prefetch_related('adjacent')
            .order_by('name')
        )
        return Response(CommunityMapListSerializer(qs, many=True).data)

    def post(self, request):
        community_id = request.data.get('community_id')
        name = request.data.get('name')
        boundary = request.data.get('boundary')

        if boundary is None:
            return Response(
                {'error': 'boundary is required (GeoJSON Polygon, Feature, or FeatureCollection)'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            geom_dict = extract_geojson_geometry(boundary)
            geom_dict = normalize_polygon_geojson(geom_dict)
        except ValueError as e:
            return Response(
                {'error': 'Invalid geometry', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if community_id is not None and str(community_id).strip() != '':
            try:
                pk = UUID(str(community_id).strip())
            except ValueError:
                return Response(
                    {'error': 'community_id must be a valid UUID'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                community = Community.objects.get(pk=pk)
            except Community.DoesNotExist:
                return Response(
                    {'error': 'Community not found'},
                    status=status.HTTP_404_NOT_FOUND,
                )

            neighbor_ids = _save_community_map_boundary(community, geom_dict)

            return Response(
                {
                    'id': str(community.id),
                    'name': community.name,
                    'adjacent_ids': list(neighbor_ids),
                    'boundary': community.boundary,
                },
                status=status.HTTP_200_OK,
            )

        if not name or not str(name).strip():
            return Response(
                {
                    'error': 'Provide community_id (existing community) or name (create new).',
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        clean_name = str(name).strip()
        if Community.objects.filter(name__iexact=clean_name).exists():
            return Response(
                {'error': 'A community with this name already exists'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        neighbor_ids = community_ids_touching_polygon(geom_dict)
        community = Community.objects.create(name=clean_name, boundary=geom_dict)
        neighbors = Community.objects.filter(pk__in=neighbor_ids)
        community.adjacent.set(neighbors)

        return Response(
            {
                'id': str(community.id),
                'name': community.name,
                'adjacent_ids': list(neighbor_ids),
                'boundary': community.boundary,
            },
            status=status.HTTP_201_CREATED,
        )


class CommunityMapBoundaryDetail(APIView):
    """
    Single community map geometry by UUID in the URL.

    GET    — id, name, boundary, adjacent_ids (boundary may be null).
    PUT/PATCH — body: { boundary } (GeoJSON); same response as POST update.
    DELETE — remove boundary from map, clear adjacency links (community row kept).
    """

    def get_object(self, pk):
        try:
            return Community.objects.prefetch_related('adjacent').get(pk=pk)
        except Community.DoesNotExist:
            return None

    def get(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response(
                {'error': 'Community not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(CommunityMapListSerializer(community).data)

    def put(self, request, pk):
        return self._update(request, pk)

    def patch(self, request, pk):
        return self._update(request, pk)

    def _update(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response(
                {'error': 'Community not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        boundary = request.data.get('boundary')
        if boundary is None:
            return Response(
                {'error': 'boundary is required (GeoJSON Polygon, Feature, or FeatureCollection)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            geom_dict = extract_geojson_geometry(boundary)
            geom_dict = normalize_polygon_geojson(geom_dict)
        except ValueError as e:
            return Response(
                {'error': 'Invalid geometry', 'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        neighbor_ids = _save_community_map_boundary(community, geom_dict)
        return Response(
            {
                'id': str(community.id),
                'name': community.name,
                'adjacent_ids': list(neighbor_ids),
                'boundary': community.boundary,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, pk):
        community = self.get_object(pk)
        if not community:
            return Response(
                {'error': 'Community not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        community.adjacent.clear()
        community.boundary = None
        community.save(update_fields=['boundary', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)
