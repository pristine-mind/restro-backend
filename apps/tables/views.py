from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrReadOnly, IsStaff
from apps.orders.models import Order
from apps.orders.services import notify_admin_bill_request

from .models import Table
from .serializers import TableSerializer


class TableViewSet(viewsets.ModelViewSet):
    queryset = Table.objects.all().order_by("table_number")
    serializer_class = TableSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_permissions(self):
        if self.action in ["update", "partial_update"]:
            return [IsAdminOrReadOnly()]
        return super().get_permissions()

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # Staff can only update status
        if request.user.role == "staff" and not request.user.is_admin:
            if set(request.data.keys()) != {"status"}:
                return Response(
                    {"detail": "Staff can only update the status field.", "code": "permission_denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        table = self.get_object()
        if table.orders.filter(status=Order.Status.OPEN).exists():
            return Response(
                {"detail": "Cannot delete table with an open order.", "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="request-bill", permission_classes=[IsStaff])
    def request_bill(self, request, pk=None):
        table = self.get_object()
        order = table.orders.filter(status=Order.Status.OPEN).first()

        if order is None:
            return Response(
                {"detail": "No open order found for this table.", "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )
        if not order.items.exists():
            return Response(
                {"detail": "Cannot request a bill for an empty order.", "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )
        if hasattr(order, "bill"):
            return Response(
                {"detail": "A bill has already been generated for this order.", "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )

        notify_admin_bill_request(table, order, request.user)

        return Response(
            {
                "detail": "Bill request sent to admin.",
                "code": "bill_request_sent",
                "table_id": table.pk,
                "order_id": order.pk,
            }
        )
