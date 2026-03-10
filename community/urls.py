from django.urls import path
from .views import (
    CommunityListCreate,
    CommunityDetail,
    CommunityCensusDataListCreate,
    CommunityCensusDataDetail,
    CensusYearListCreate,
    CensusYearDetail,
    YearDropdown,
    AdjacentCommunityReallocationListCreate,
    AdjacentCommunityReallocationDetail,
    MapDataView
)

urlpatterns = [
    # Community Census Data (Flat Format) CRUD
    path('communities/', CommunityListCreate.as_view(), name='community-list-create'),
    path('communities/<int:pk>/', CommunityDetail.as_view(), name='community-detail'),
    
    # Community Census Data (Alternative endpoint) CRUD
    path('community-census-data/', CommunityCensusDataListCreate.as_view(), name='community-census-data-list-create'),
    path('community-census-data/<int:pk>/', CommunityCensusDataDetail.as_view(), name='community-census-data-detail'),
    
    # Year Dropdown with CRUD
    path('years/', YearDropdown.as_view(), name='year-dropdown'),
    path('years/<int:pk>/', YearDropdown.as_view(), name='year-dropdown-detail'),
    
    # Census Year CRUD
    path('census-years/', CensusYearListCreate.as_view(), name='census-year-list-create'),
    path('census-years/<int:pk>/', CensusYearDetail.as_view(), name='census-year-detail'),

    # Adjacent Community Reallocation APIs
    path('adjacent-communities-reallocation/', AdjacentCommunityReallocationListCreate.as_view(), name='adjacent-community-reallocation-list-create'),
    path('adjacent-communities-reallocation/<int:pk>/', AdjacentCommunityReallocationDetail.as_view(), name='adjacent-community-reallocation-detail'),

    # Map Data API
    path('map-data/', MapDataView.as_view(), name='map-data'),
]