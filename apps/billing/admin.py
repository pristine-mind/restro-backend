from django.contrib import admin

from .models import Bill, SystemSettings


@admin.register(Bill)
class BillAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "subtotal", "total", "payment_method", "generated_by", "generated_at", "paid_at"]
    list_filter = ["payment_method", "generated_at"]
    search_fields = ["order__table__table_number"]


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ["restaurant_name", "tax_rate", "allow_staff_discount", "updated_at"]
