from django.urls import path
from .views import SiteListCreate, SiteDetail

urlpatterns = [
    path('', SiteListCreate.as_view()),
    path('<uuid:pk>/', SiteDetail.as_view()),
]