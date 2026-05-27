from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from emissions.views import (
    CompanyViewSet, DataSourceViewSet, IngestionJobViewSet,
    EmissionViewSet, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'companies', CompanyViewSet)
router.register(r'data-sources', DataSourceViewSet)
router.register(r'ingestion-jobs', IngestionJobViewSet)
router.register(r'emissions', EmissionViewSet)
router.register(r'audit-logs', AuditLogViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
]