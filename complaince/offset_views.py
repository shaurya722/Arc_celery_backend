from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from community.models import CensusYear, Community, CommunityCensusData
from .models import DirectServiceOffset, CommunityOffset
from .serializers import DirectServiceOffsetSerializer, CommunityOffsetSerializer
from .utils import calculate_required_sites, _get_direct_service_offset, apply_direct_service_offset


class DirectServiceOffsetListCreate(APIView):
    """
    GET: List all global direct service offsets
    POST: Create a new global direct service offset
    """
    
    def get(self, request):
        census_year_id = request.query_params.get('census_year_id')
        year = request.query_params.get('year')
        program = request.query_params.get('program')
        is_active = request.query_params.get('is_active')
        
        offsets = DirectServiceOffset.objects.all().select_related('census_year').order_by('-created_at')
        
        if census_year_id:
            offsets = offsets.filter(census_year_id=census_year_id)
        if year:
            offsets = offsets.filter(census_year__year=year)
        if program:
            offsets = offsets.filter(program=program)
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            offsets = offsets.filter(is_active=is_active_bool)
        
        serializer = DirectServiceOffsetSerializer(offsets, many=True)
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        })
    
    def post(self, request):
        """
        Create or update a global direct service offset (upsert behavior).

        Body:
        {
            "census_year": <census_year_id>,
            "program": "Paint",
            "percentage": 10,
            "is_active": true
        }
        """
        # First, check if offset already exists for this census_year + program
        census_year_id = request.data.get('census_year')
        program = request.data.get('program')

        if not census_year_id or not program:
            return Response(
                {'error': 'census_year and program are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing = DirectServiceOffset.objects.filter(
            census_year_id=census_year_id,
            program=program
        ).first()

        if existing:
            # Update existing offset - bypass serializer validation for unique_together
            serializer = DirectServiceOffsetSerializer(existing, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data,
                    status=status.HTTP_200_OK
                )
        else:
            # Create new offset
            serializer = DirectServiceOffsetSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DirectServiceOffsetDetail(APIView):
    """
    GET: Retrieve a specific direct service offset
    PUT/PATCH: Update a direct service offset
    DELETE: Delete a direct service offset
    """
    
    def get_object(self, pk):
        try:
            return DirectServiceOffset.objects.select_related('census_year').get(pk=pk)
        except DirectServiceOffset.DoesNotExist:
            return None
    
    def get(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Direct service offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DirectServiceOffsetSerializer(offset)
        return Response(serializer.data)
    
    def put(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Direct service offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DirectServiceOffsetSerializer(offset, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Direct service offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = DirectServiceOffsetSerializer(offset, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Direct service offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        offset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CommunityOffsetListCreate(APIView):
    """
    GET: List all community-specific offsets
    POST: Create a new community-specific offset
    """
    
    def get(self, request):
        census_year_id = request.query_params.get('census_year_id')
        year = request.query_params.get('year')
        program = request.query_params.get('program')
        community_id = request.query_params.get('community_id')
        is_active = request.query_params.get('is_active')
        
        offsets = CommunityOffset.objects.all().select_related('census_year', 'community').order_by('-created_at')
        
        if census_year_id:
            offsets = offsets.filter(census_year_id=census_year_id)
        if year:
            offsets = offsets.filter(census_year__year=year)
        if program:
            offsets = offsets.filter(program=program)
        if community_id:
            offsets = offsets.filter(community_id=community_id)
        if is_active is not None:
            is_active_bool = is_active.lower() in ['true', '1', 'yes']
            offsets = offsets.filter(is_active=is_active_bool)
        
        serializer = CommunityOffsetSerializer(offsets, many=True)
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        })
    
    def post(self, request):
        """
        Create or update a community-specific offset (upsert behavior).

        Body:
        {
            "census_year": <census_year_id>,
            "program": "Paint",
            "community": "<community_uuid>",
            "percentage": 15,
            "is_active": true
        }
        """
        # First, check if offset already exists for this census_year + program + community
        census_year_id = request.data.get('census_year')
        program = request.data.get('program')
        community_id = request.data.get('community')

        if not census_year_id or not program or not community_id:
            return Response(
                {'error': 'census_year, program, and community are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        existing = CommunityOffset.objects.filter(
            census_year_id=census_year_id,
            program=program,
            community_id=community_id
        ).first()

        if existing:
            # Update existing offset - bypass serializer validation for unique_together
            serializer = CommunityOffsetSerializer(existing, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data,
                    status=status.HTTP_200_OK
                )
        else:
            # Create new offset
            serializer = CommunityOffsetSerializer(data=request.data)
            if serializer.is_valid():
                serializer.save()
                return Response(
                    serializer.data,
                    status=status.HTTP_201_CREATED
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CommunityOffsetDetail(APIView):
    """
    GET: Retrieve a specific community offset
    PUT/PATCH: Update a community offset
    DELETE: Delete a community offset
    """
    
    def get_object(self, pk):
        try:
            return CommunityOffset.objects.select_related('census_year', 'community').get(pk=pk)
        except CommunityOffset.DoesNotExist:
            return None
    
    def get(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Community offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CommunityOffsetSerializer(offset)
        return Response(serializer.data)
    
    def put(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Community offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CommunityOffsetSerializer(offset, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Community offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = CommunityOffsetSerializer(offset, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk):
        offset = self.get_object(pk)
        if not offset:
            return Response(
                {'error': 'Community offset not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        offset.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DirectServiceOffsetPreview(APIView):
    """
    GET: Preview how direct service offset affects all communities

    Shows a table view with:
    - Community name and population
    - Base required sites (before offset)
    - Offset percentage (global or community-specific)
    - New required sites (after offset)

    POST: Create or update a community-specific offset override

    Required query params: census_year_id, program
    POST body: community_id, percentage, is_active (optional)
    """
    
    def get(self, request):
        census_year_id = request.query_params.get('census_year_id')
        program = request.query_params.get('program')
        # Pagination params
        try:
            page = int(request.query_params.get('page', 1))
        except (TypeError, ValueError):
            page = 1
        try:
            limit = int(request.query_params.get('limit', 20))
        except (TypeError, ValueError):
            limit = 20
        if page < 1:
            page = 1
        if limit < 1:
            limit = 20
        
        if not census_year_id or not program:
            return Response(
                {'error': 'census_year_id and program are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            census_year = CensusYear.objects.get(id=census_year_id)
        except CensusYear.DoesNotExist:
            return Response(
                {'error': f'Census year {census_year_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all active communities for this census year
        community_census_data = CommunityCensusData.objects.filter(
            census_year=census_year,
            is_active=True
        ).select_related('community').order_by('community__name')
        
        results = []
        
        for community_data in community_census_data:
            community = community_data.community
            
            # Calculate base required sites (before offset)
            base_required = calculate_required_sites(community, program, census_year)
            
            # Get offset percentage and source
            offset_percentage, offset_source = _get_direct_service_offset(
                community, program, census_year
            )
            
            # Calculate new required sites (after offset)
            new_required = apply_direct_service_offset(base_required, offset_percentage)
            
            # Check if this community has a specific override
            has_community_override = CommunityOffset.objects.filter(
                community=community,
                census_year=census_year,
                program=program,
                is_active=True
            ).exists()
            
            results.append({
                'community_id': str(community.id),
                'community_name': community.name,
                'population': community_data.population,
                'base_required_sites': base_required,
                'offset_percentage': offset_percentage,
                'offset_source': offset_source,
                'new_required_sites': new_required,
                'has_community_override': has_community_override,
            })
        # Apply pagination
        total = len(results)
        start = (page - 1) * limit
        end = start + limit
        paginated = results[start:end]
        total_pages = (total + limit - 1) // limit if limit else 1

        return Response({
            'census_year': {
                'id': census_year.id,
                'year': census_year.year
            },
            'program': program,
            'communities': paginated,
            'total_communities': total,
            'page': page,
            'limit': limit,
            'total_pages': total_pages,
        })

    def post(self, request):
        """
        Create or update a community-specific offset override.

        Query params: census_year_id, program (required)
        Body: community_id, percentage, is_active (optional, defaults to True)
        """
        census_year_id = request.query_params.get('census_year_id')
        program = request.query_params.get('program')
        community_id = request.data.get('community_id')
        percentage = request.data.get('percentage')
        is_active = request.data.get('is_active', True)

        if not census_year_id or not program:
            return Response(
                {'error': 'census_year_id and program are required query params'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not community_id:
            return Response(
                {'error': 'community_id is required in request body'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if percentage is None:
            return Response(
                {'error': 'percentage is required in request body'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            percentage = int(percentage)
            if not (0 <= percentage <= 100):
                raise ValueError()
        except (TypeError, ValueError):
            return Response(
                {'error': 'percentage must be an integer between 0 and 100'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            census_year = CensusYear.objects.get(id=census_year_id)
        except CensusYear.DoesNotExist:
            return Response(
                {'error': f'Census year {census_year_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            community = Community.objects.get(id=community_id)
        except Community.DoesNotExist:
            return Response(
                {'error': f'Community {community_id} not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check if offset already exists for this census_year + program + community
        existing = CommunityOffset.objects.filter(
            census_year=census_year,
            program=program,
            community=community
        ).first()

        if existing:
            # Update existing offset
            existing.percentage = percentage
            existing.is_active = is_active
            existing.save()
            message = 'Community offset updated'
        else:
            # Create new offset
            CommunityOffset.objects.create(
                census_year=census_year,
                program=program,
                community=community,
                percentage=percentage,
                is_active=is_active
            )
            message = 'Community offset created'

        return Response({
            'message': message,
            'community_id': str(community.id),
            'community_name': community.name,
            'program': program,
            'census_year': census_year.year,
            'percentage': percentage,
            'is_active': is_active
        }, status=status.HTTP_200_OK)
