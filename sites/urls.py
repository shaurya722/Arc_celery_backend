from django.urls import path
from .views import SiteListCreate, SiteDetail, SiteApproveEvents, EventListing, SiteCensusDataImportExport, SiteCensusDataImportTemplate

urlpatterns = [
    # Site Census Data (Flat Format) CRUD
    path('', SiteListCreate.as_view(), name='site-list-create'),
    path('<int:pk>/', SiteDetail.as_view(), name='site-detail'),
    # Event Sites Approval
    path('approve-events/', SiteApproveEvents.as_view(), name='site-approve-events'),
    # Event Listing
    path('event-listing/', EventListing.as_view(), name='event-listing'),
    path('event-listing/<uuid:pk>/', EventListing.as_view(), name='event-listing-detail'),
    # CSV Import/Export
    path('census-data/import-export/', SiteCensusDataImportExport.as_view(), name='site-census-data-import-export'),
    path('census-data/template/', SiteCensusDataImportTemplate.as_view(), name='site-census-data-template'),
]