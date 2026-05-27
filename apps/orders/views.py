from django.db import transaction
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAdminOrStaff
from apps.tables.models import Table

from .models import Order, OrderItem
from .serializers import OrderItemSerializer, OrderSerializer
from .services import notify_table_status_change, switch_table


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all().order_by("-created_at")
    serializer_class = OrderSerializer
    permission_classes = [IsAdminOrStaff]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status", "table", "staff"]

    def get_queryset(self):
        user = self.request.user
        qs = (
            Order.objects.select_related("table", "staff")
            .prefetch_related("items__menu_item__category")
            .order_by("-created_at")
        )
        if user.role == "staff":
            qs = qs.filter(staff=user)
        return qs.filter(status__in=[Order.Status.OPEN, Order.Status.BILLED])

    def get_permissions(self):
        return [IsAdminOrStaff()]

    def perform_create(self, serializer):
        table = serializer.validated_data["table"]
        if table.status != Table.Status.AVAILABLE:
            raise ValueError("Table is not available.")
        with transaction.atomic():
            order = serializer.save(staff=self.request.user)
            table.status = Table.Status.OCCUPIED
            table.save(update_fields=["status"])
            notify_table_status_change(table)
        return order

    @action(detail=True, methods=["post"], url_path="switch-table")
    def switch_table(self, request, pk=None):
        order = self.get_object()
        to_table_id = request.data.get("to_table")
        if not to_table_id:
            return Response(
                {"detail": "to_table is required.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            order = switch_table(order.pk, int(to_table_id), request.user)
        except ValueError as e:
            return Response(
                {"detail": str(e), "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(order)
        return Response(
            {
                "order": serializer.data,
                "from_table": order.switch_logs.latest("switched_at").from_table_id,
                "to_table": order.switch_logs.latest("switched_at").to_table_id,
            }
        )

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        if order.status != Order.Status.OPEN:
            raise ValueError("Only open orders can be cancelled.")
        if hasattr(order, "bill"):
            raise ValueError("Cannot cancel an order with a generated bill.")
        with transaction.atomic():
            order.status = Order.Status.CANCELLED
            order.closed_at = timezone.now()
            order.save(update_fields=["status", "closed_at"])
            order.table.status = Table.Status.AVAILABLE
            order.table.save(update_fields=["status"])
            notify_table_status_change(order.table)
        return Response(self.get_serializer(order).data)


class OrderItemViewSet(viewsets.ModelViewSet):
    serializer_class = OrderItemSerializer
    permission_classes = [IsAdminOrStaff]

    def get_queryset(self):
        return OrderItem.objects.filter(order_id=self.kwargs["order_pk"]).select_related("menu_item")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["order"] = Order.objects.get(pk=self.kwargs["order_pk"])
        return context

    def perform_create(self, serializer):
        order = Order.objects.get(pk=self.kwargs["order_pk"])
        if order.status != Order.Status.OPEN:
            raise ValueError("Cannot add items to a non-open order.")
        serializer.context["order"] = order
        return serializer.save()

    def perform_update(self, serializer):
        order = serializer.instance.order
        if order.status != Order.Status.OPEN:
            raise ValueError("Cannot update items in a non-open order.")
        return serializer.save()

    def perform_destroy(self, instance):
        if instance.order.status != Order.Status.OPEN:
            raise ValueError("Cannot remove items from a non-open order.")
        instance.delete()
