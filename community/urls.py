from django.urls import path
from .views import (
    CommunityListCreate,
    CommunityDetail,
    CommunityCensusDataListCreate,
    CommunityCensusDataDetail,
    CensusYearListCreate,
    CensusYearDetail,
    YearData,
    YearDropdown,
    CommunityDropdown,
    CommunityModelDropdown,
    AdjacentCommunityReallocationListCreate,
    AdjacentCommunityReallocationDetail,
    MapDataView,
    CommunityCensusDataImportExport,
    CommunityCensusDataImportTemplate,
    CommunityMapBoundaryListCreate,
    CommunityMapBoundaryDetail,
    CommunityMapAvailableForAssignment,
    CommunityBaseListCreate,
    CommunityBaseDetail,
)

urlpatterns = [
    # Community (base model) CRUD
    path('base-communities/', CommunityBaseListCreate.as_view(), name='community-base-list-create'),
    path('base-communities/<uuid:pk>/', CommunityBaseDetail.as_view(), name='community-base-detail'),

    # Community Census Data (Flat Format) CRUD
    path('communities/', CommunityListCreate.as_view(), name='community-list-create'),
    path('communities/<int:pk>/', CommunityDetail.as_view(), name='community-detail'),
    
    # CSV Import/Export for Community Census Data (MUST be before community-census-data/ patterns)
    path('community-census-data/import-export/', CommunityCensusDataImportExport.as_view(), name='community-census-data-import-export'),
    path('community-census-data/template/', CommunityCensusDataImportTemplate.as_view(), name='community-census-data-template'),
    
    # Community Census Data (Alternative endpoint) CRUD
    path('community-census-data/', CommunityCensusDataListCreate.as_view(), name='community-census-data-list-create'),
    path('community-census-data/<int:pk>/', CommunityCensusDataDetail.as_view(), name='community-census-data-detail'),
    
    # Year Dropdown with CRUD
    path('years/', YearDropdown.as_view(), name='year-dropdown'),
    path('year-data/', YearData.as_view(), name='year-data'),
    path('years/<int:pk>/', YearDropdown.as_view(), name='year-dropdown-detail'),

    # Community dropdown API
    path('communities/dropdown/', CommunityDropdown.as_view(), name='community-dropdown'),
    path('communities/model-dropdown/', CommunityModelDropdown.as_view(), name='community-model-dropdown'),
    
    # Census Year CRUD
    path('census-years/', CensusYearListCreate.as_view(), name='census-year-list-create'),
    path('census-years/<int:pk>/', CensusYearDetail.as_view(), name='census-year-detail'),

    # Adjacent Community Reallocation APIs
    path('adjacent-communities-reallocation/', AdjacentCommunityReallocationListCreate.as_view(), name='adjacent-community-reallocation-list-create'),
    path('adjacent-communities-reallocation/<int:pk>/', AdjacentCommunityReallocationDetail.as_view(), name='adjacent-community-reallocation-detail'),

    # Map Data API
    path('map-data/', MapDataView.as_view(), name='map-data'),

    # PostGIS boundaries + adjacency (Leaflet draw → neighbors)
    path(
        'map-communities/available/',
        CommunityMapAvailableForAssignment.as_view(),
        name='community-map-available',
    ),
    path('map-communities/', CommunityMapBoundaryListCreate.as_view(), name='community-map-boundaries'),
    path(
        'map-communities/<uuid:pk>/',
        CommunityMapBoundaryDetail.as_view(),
        name='community-map-boundary-detail',
    ),
]