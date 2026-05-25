from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAdminOrReadOnly

from .filters import MenuItemFilter
from .models import Category, MenuItem
from .serializers import CategorySerializer, MenuItemSerializer
from .services import soft_delete_menu_item


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all().order_by("display_order", "name")
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.filter(deleted_at__isnull=True).order_by("name")
    serializer_class = MenuItemSerializer
    permission_classes = [IsAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = MenuItemFilter
    ordering_fields = ["price", "name", "created_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("include_deleted"):
            if self.request.user.role == "admin":
                qs = MenuItem.objects.all().order_by("name")
        return qs

    @action(detail=True, methods=["delete"], permission_classes=[IsAdmin])
    def soft_delete(self, request, pk=None):
        item = self.get_object()
        soft_delete_menu_item(item.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def destroy(self, request, *args, **kwargs):
        """Override DELETE to perform soft delete."""
        item = self.get_object()
        soft_delete_menu_item(item.pk)
        return Response(status=status.HTTP_204_NO_CONTENT)
