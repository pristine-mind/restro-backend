from django.db import models


class Category(models.Model):
    class Station(models.TextChoices):
        KITCHEN = "kitchen", "Kitchen"
        BAR = "bar", "Bar"

    name = models.CharField(max_length=100, unique=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    station = models.CharField(max_length=10, choices=Station.choices, default=Station.KITCHEN)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "rms_categories"
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class MenuItem(models.Model):
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name="items")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, help_text="Maximum Retail Price (MRP). If blank, price is used.")
    is_available = models.BooleanField(default=True, db_index=True)
    image = models.ImageField(upload_to="menu/images/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)  # soft delete

    class Meta:
        db_table = "rms_menu_items"
        indexes = [
            models.Index(fields=["category", "is_available"]),
            models.Index(fields=["deleted_at"]),
        ]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __str__(self):
        return self.name
