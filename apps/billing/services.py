from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services import notify_table_status_change
from apps.tables.models import Table

from .models import Bill, SystemSettings


def generate_bill(order, discount_type, discount_value, payment_method, generated_by):
    """
    Atomically generates a bill for an open order.
    Raises ValueError for all constraint violations.
    """
    with transaction.atomic():
        # Lock the order row to prevent concurrent bill generation
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.status != Order.Status.OPEN:
            raise ValueError("Order is not open.")
        if not order.items.exists():
            raise ValueError("Cannot bill an empty order.")
        if hasattr(order, "bill"):
            raise ValueError("Bill already exists for this order.")

        settings = SystemSettings.objects.get(pk=1)
        tax_rate = settings.tax_rate

        # Calculate subtotal: sum(quantity * unit_price) per item
        subtotal = sum(item.quantity * item.unit_price for item in order.items.all())

        # Calculate discount
        discount_amount = Decimal("0")
        if discount_type == Bill.DiscountType.PERCENTAGE:
            discount_amount = (subtotal * discount_value / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        elif discount_type == Bill.DiscountType.FIXED:
            discount_amount = min(discount_value, subtotal)  # cannot discount below 0

        taxable_amount = subtotal - discount_amount
        tax_amount = (taxable_amount * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total = taxable_amount + tax_amount

        bill = Bill.objects.create(
            order=order,
            subtotal=subtotal,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            discount_type=discount_type,
            discount_value=discount_value,
            discount_amount=discount_amount,
            total=total,
            payment_method=payment_method,
            generated_by=generated_by,
        )

        order.status = Order.Status.BILLED
        order.closed_at = timezone.now()
        order.save(update_fields=["status", "closed_at"])

        # Free the table
        order.table.status = Table.Status.AVAILABLE
        order.table.save(update_fields=["status"])

        # Notify WebSocket clients
        notify_table_status_change(order.table)

    return bill
