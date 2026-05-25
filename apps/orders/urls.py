from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_nested.routers import NestedDefaultRouter

from .views import OrderItemViewSet, OrderViewSet

router = DefaultRouter()
router.register(r"", OrderViewSet, basename="order")

order_router = NestedDefaultRouter(router, r"", lookup="order")
order_router.register(r"items", OrderItemViewSet, basename="order-item")

urlpatterns = [
    path("", include(router.urls)),
    path("", include(order_router.urls)),
]
