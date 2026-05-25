from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TableViewSet

router = DefaultRouter()
router.register(r"", TableViewSet, basename="table")

urlpatterns = [
    path("", include(router.urls)),
]
