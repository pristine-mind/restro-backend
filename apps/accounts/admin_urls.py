from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import StaffManagementViewSet

router = DefaultRouter()
router.register(r"staff", StaffManagementViewSet, basename="admin-staff")

urlpatterns = [
    path("", include(router.urls)),
]
