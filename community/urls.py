from django.urls import path
from .views import (
    CommunityListCreate, 
    CommunityDetail, 
    CommunityCensusDataListCreate,
    CommunityCensusDataDetail,
    CensusYearListCreate,
    CensusYearDetail
)

urlpatterns = [
    # Community Census Data (Flat Format) CRUD
    path('communities/', CommunityListCreate.as_view(), name='community-list-create'),
    path('communities/<int:pk>/', CommunityDetail.as_view(), name='community-detail'),
    
    # Community Census Data (Alternative endpoint) CRUD
    path('community-census-data/', CommunityCensusDataListCreate.as_view(), name='community-census-data-list-create'),
    path('community-census-data/<int:pk>/', CommunityCensusDataDetail.as_view(), name='community-census-data-detail'),
    
    # Census Year CRUD
    path('census-years/', CensusYearListCreate.as_view(), name='census-year-list-create'),
    path('census-years/<int:pk>/', CensusYearDetail.as_view(), name='census-year-detail'),
]