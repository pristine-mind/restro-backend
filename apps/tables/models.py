from django.db import models


class Table(models.Model):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        OCCUPIED = "occupied", "Occupied"
        RESERVED = "reserved", "Reserved"
        CLEANING = "cleaning", "Cleaning"

    table_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rms_tables"
        ordering = ["table_number"]

    @property
    def active_order(self):
        from apps.orders.models import Order

        return self.orders.filter(status=Order.Status.OPEN).first()

    def __str__(self):
        return self.table_number


class TableSwitchLog(models.Model):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="switch_logs")
    from_table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, related_name="switches_from")
    to_table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, related_name="switches_to")
    switched_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)
    switched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rms_table_switch_logs"
