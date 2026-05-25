from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        BILLED = "billed", "Billed"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    table = models.ForeignKey("tables.Table", on_delete=models.PROTECT, related_name="orders")
    staff = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN, db_index=True)
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rms_orders"
        indexes = [models.Index(fields=["table", "status"])]

    @property
    def subtotal(self):
        from django.db.models import F, Sum

        result = self.items.aggregate(total=Sum(F("quantity") * F("unit_price")))
        return result["total"] or 0

    def __str__(self):
        return f"Order #{self.id} - Table {self.table.table_number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    menu_item = models.ForeignKey("menu.MenuItem", on_delete=models.PROTECT)
    quantity = models.PositiveSmallIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price snapshot
    notes = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        db_table = "rms_order_items"
        constraints = [models.UniqueConstraint(fields=["order", "menu_item"], name="unique_order_item")]

    def __str__(self):
        return f"{self.quantity}x {self.menu_item.name}"
