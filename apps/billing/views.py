from django.db import transaction
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin, IsAdminOrStaff
from apps.orders.models import Order, OrderItem
from apps.tables.models import Table

from .models import Bill, SystemSettings
from .pdf import generate_bill_pdf
from .serializers import BillSerializer, SystemSettingsSerializer
from .services import generate_bill


class BillViewSet(viewsets.ModelViewSet):
    queryset = Bill.objects.all().order_by("-generated_at")
    serializer_class = BillSerializer
    permission_classes = [IsAdminOrStaff]

    def create(self, request, *args, **kwargs):
        order_id = request.data.get("order")
        discount_type = request.data.get("discount_type", Bill.DiscountType.NONE)
        discount_value = request.data.get("discount_value", 0)
        payment_method = request.data.get("payment_method")
        customer_name = request.data.get("customer_name", "")
        customer_address = request.data.get("customer_address", "")
        customer_pan = request.data.get("customer_pan", "")

        if not order_id or not payment_method:
            return Response(
                {"detail": "order and payment_method are required.", "code": "validation_error"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order = get_object_or_404(Order, pk=order_id)
        try:
            bill = generate_bill(
                order,
                discount_type,
                discount_value,
                payment_method,
                request.user,
                customer_name=customer_name,
                customer_address=customer_address,
                customer_pan=customer_pan,
            )
        except ValueError as e:
            return Response(
                {"detail": str(e), "code": "business_rule_violation"},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = self.get_serializer(bill)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        bill = self.get_object()
        if bill.paid_at:
            raise ValueError("Bill is already paid.")
        with transaction.atomic():
            bill.paid_at = timezone.now()
            bill.save(update_fields=["paid_at"])
            bill.order.status = Order.Status.PAID
            bill.order.save(update_fields=["status"])
        return Response(self.get_serializer(bill).data)


class BillPDFView(APIView):
    permission_classes = [IsAdminOrStaff]

    def get(self, request, pk):
        bill = get_object_or_404(Bill, pk=pk)
        pdf_bytes = generate_bill_pdf(bill)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="bill_{bill.pk}.pdf"'
        return response


class SystemSettingsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        return Response(SystemSettingsSerializer(settings_obj).data)

    def put(self, request):
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        serializer = SystemSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class DailyReportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        date_str = request.query_params.get("date")
        if not date_str:
            date = timezone.now().date()
        else:
            from datetime import datetime

            date = datetime.strptime(date_str, "%Y-%m-%d").date()

        bills = Bill.objects.filter(generated_at__date=date)
        total_revenue = bills.aggregate(total=Sum("total"))["total"] or 0
        revenue_by_payment_method = {payment_method: 0 for payment_method, _ in Bill.PaymentMethod.choices}
        revenue_by_payment_method.update(
            {
                entry["payment_method"]: entry["total_revenue"] or 0
                for entry in bills.values("payment_method").annotate(total_revenue=Sum("total"))
            }
        )
        total_bills = bills.count()
        total_orders = Order.objects.filter(created_at__date=date).count()

        return Response(
            {
                "date": date.isoformat(),
                "total_revenue": total_revenue,
                "revenue_by_payment_method": revenue_by_payment_method,
                "total_bills": total_bills,
                "total_orders": total_orders,
            }
        )


class ItemPopularityReportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        from_date = request.query_params.get("from")
        to_date = request.query_params.get("to")

        queryset = OrderItem.objects.all()
        if from_date:
            queryset = queryset.filter(order__created_at__date__gte=from_date)
        if to_date:
            queryset = queryset.filter(order__created_at__date__lte=to_date)

        data = (
            queryset.values("menu_item__name")
            .annotate(total_quantity=Sum("quantity"), total_revenue=Sum(F("quantity") * F("unit_price")))
            .order_by("-total_quantity")
        )

        return Response(list(data))
