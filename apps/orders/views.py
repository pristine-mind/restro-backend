from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, IsAdminOrStaff
from apps.tables.models import Table

from .models import Order, OrderItem, OrderStationLog
from .pdf import generate_station_pdf
from .serializers import OrderItemSerializer, OrderSerializer
from .services import merge_table_orders, notify_table_status_change, switch_table


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

    def _build_station_delta_snapshot(self, order, station):
        current_items = list(order.items.filter(station=station).select_related("menu_item"))
        if not current_items:
            return []

        sent_quantities = {}
        station_logs = order.station_logs.filter(station=station)
        for log in station_logs:
            for item in log.items_snapshot:
                item_key = (item["menu_item_id"], item.get("notes", ""))
                sent_quantities[item_key] = sent_quantities.get(item_key, 0) + item.get("quantity", 0)

        delta_snapshot = []
        for item in current_items:
            item_key = (item.menu_item_id, item.notes)
            unsent_quantity = item.quantity - sent_quantities.get(item_key, 0)
            if unsent_quantity <= 0:
                continue

            delta_snapshot.append(
                {
                    "menu_item_id": item.menu_item_id,
                    "name": item.menu_item.name,
                    "quantity": unsent_quantity,
                    "notes": item.notes,
                }
            )

        return delta_snapshot

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

    @action(detail=True, methods=["post"], url_path="merge-table")
    def merge_table(self, request, pk=None):
        order = self.get_object()
        to_table_id = request.data.get("to_table")
        if not to_table_id:
            return Response(
                {"detail": "to_table is required.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            merged_order, source_table, destination_table = merge_table_orders(order.pk, int(to_table_id), request.user)
        except ValueError as e:
            return Response(
                {"detail": str(e), "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )

        serializer = self.get_serializer(merged_order)
        return Response(
            {
                "order": serializer.data,
                "from_table": source_table.pk,
                "to_table": destination_table.pk,
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

    @action(detail=True, methods=["post"], url_path="send-to-station")
    def send_to_station(self, request, pk=None):
        """Send only newly added items for a station, create a log, and return PDF bytes."""
        order = self.get_object()
        if order.status != Order.Status.OPEN:
            return Response(
                {"detail": "Only open orders can send station tickets.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        station = request.data.get("station")
        if station not in (OrderItem.Station.KITCHEN, OrderItem.Station.BAR):
            return Response(
                {"detail": "station must be 'kitchen' or 'bar'.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        items_snapshot = self._build_station_delta_snapshot(order, station)

        if not order.items.filter(station=station).exists():
            return Response(
                {"detail": f"No {station} items in this order.", "code": "no_items"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not items_snapshot:
            return Response(
                {"detail": f"No new {station} items to send.", "code": "no_new_items"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        OrderStationLog.objects.create(
            order=order,
            station=station,
            sent_by=request.user,
            items_snapshot=items_snapshot,
        )

        # Generate PDF
        pdf_bytes = generate_station_pdf(order, station, items_snapshot)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{station}_ticket_order_{order.id}.pdf"'
        return response

    @action(detail=True, methods=["get"], url_path="station-logs")
    def station_logs(self, request, pk=None):
        """Return the station ticket history for this order."""
        order = self.get_object()
        logs = order.station_logs.all()
        data = [
            {
                "id": log.id,
                "station": log.station,
                "sent_at": log.sent_at,
                "sent_by": log.sent_by.get_full_name() or log.sent_by.username if log.sent_by else None,
                "items": log.items_snapshot,
            }
            for log in logs
        ]
        return Response(data)

    @action(detail=True, methods=["get"], url_path="station-pdf")
    def station_pdf(self, request, pk=None):
        """Re-generate a PDF from the latest station snapshot (for re-printing)."""
        order = self.get_object()
        station = request.query_params.get("station")
        if station not in (OrderItem.Station.KITCHEN, OrderItem.Station.BAR):
            return Response(
                {"detail": "station must be 'kitchen' or 'bar'.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        log = order.station_logs.filter(station=station).order_by("-sent_at", "-id").first()
        if not log:
            return Response(
                {"detail": f"No {station} ticket found for this order.", "code": "not_found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        pdf_bytes = generate_station_pdf(order, station, log.items_snapshot)

        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{station}_ticket_order_{order.id}.pdf"'
        return response


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
