from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, MenuItemViewSet

router = DefaultRouter()
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"items", MenuItemViewSet, basename="menuitem")

urlpatterns = [
    path("", include(router.urls)),
]
