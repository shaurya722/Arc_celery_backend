from django.urls import path
from .views import SiteListCreate, SiteDetail

urlpatterns = [
    # Site Census Data (Flat Format) CRUD
    path('', SiteListCreate.as_view(), name='site-list-create'),
    path('<int:pk>/', SiteDetail.as_view(), name='site-detail'),
]