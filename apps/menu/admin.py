from django.contrib import admin

from .models import Category, MenuItem


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "display_order", "created_at"]
    ordering = ["display_order", "name"]


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ["name", "category", "price", "is_available", "deleted_at", "created_at"]
    list_filter = ["is_available", "category"]
    search_fields = ["name", "description"]
