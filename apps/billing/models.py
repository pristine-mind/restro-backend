from django.db import models


class SystemSettings(models.Model):
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=13.00)
    restaurant_name = models.CharField(max_length=200, default="My Restaurant")
    address = models.TextField(blank=True)
    allow_staff_discount = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = "rms_system_settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # singleton pattern
        super().save(*args, **kwargs)


class Bill(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        WALLET = "wallet", "Digital Wallet"

    class DiscountType(models.TextChoices):
        NONE = "none", "None"
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    order = models.OneToOneField("orders.Order", on_delete=models.PROTECT, related_name="bill")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2)  # snapshot at bill time
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices, default=DiscountType.NONE)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    generated_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True, related_name="generated_bills")
    generated_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "rms_bills"
