from django.contrib import admin

from .models import Table, TableSwitchLog


@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    list_display = ["table_number", "capacity", "status", "created_at"]
    list_filter = ["status"]
    search_fields = ["table_number"]


@admin.register(TableSwitchLog)
class TableSwitchLogAdmin(admin.ModelAdmin):
    list_display = ["order", "from_table", "to_table", "switched_by", "switched_at"]
    list_filter = ["switched_at"]
