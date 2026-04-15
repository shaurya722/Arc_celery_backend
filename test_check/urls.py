from django.urls import path
from .views import CommunityListCreateAPIView, CommunityDetailAPIView, CensusYearListCreateAPIView, SiteListAPIView

urlpatterns = [
    path('communities/', CommunityListCreateAPIView.as_view(), name='community-list-create'),
    path('communities/<uuid:pk>/', CommunityDetailAPIView.as_view(), name='community-detail'),
    path('census-years/', CensusYearListCreateAPIView.as_view(), name='census-year-list-create'),
    path('sites/', SiteListAPIView.as_view(), name='site-list'),
]
