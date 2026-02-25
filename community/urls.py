from django.urls import path
from .views import CommunityListCreate, CommunityDetail

urlpatterns = [
    path('communities/', CommunityListCreate.as_view(), name='community-list-create'),
    path('communities/<uuid:pk>/', CommunityDetail.as_view(), name='community-detail'),
]