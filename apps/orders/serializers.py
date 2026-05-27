from rest_framework import serializers

from apps.menu.models import MenuItem
from apps.menu.serializers import MenuItemSerializer
from apps.tables.models import Table

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItem.objects.filter(deleted_at__isnull=True, is_available=True),
        source="menu_item",
        write_only=True,
    )

    class Meta:
        model = OrderItem
        fields = ["id", "order", "menu_item", "menu_item_id", "quantity", "unit_price", "notes"]
        read_only_fields = ["order", "unit_price"]

    def create(self, validated_data):
        order = self.context["order"]
        menu_item = validated_data["menu_item"]
        quantity = validated_data["quantity"]
        notes = validated_data.get("notes", "")

        # Check if menu_item already exists in order
        existing = order.items.filter(menu_item=menu_item).first()
        if existing:
            existing.quantity += quantity
            existing.save(update_fields=["quantity"])
            return existing

        unit_price = menu_item.price
        return OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=quantity,
            unit_price=unit_price,
            notes=notes,
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    table_id = serializers.PrimaryKeyRelatedField(
        queryset=Table.objects.all(),
        source="table",
        write_only=True,
    )
    staff_name = serializers.CharField(source="staff.username", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "table",
            "table_id",
            "staff",
            "staff_name",
            "status",
            "notes",
            "subtotal",
            "created_at",
            "closed_at",
            "items",
        ]
        read_only_fields = ["table", "staff", "status", "subtotal", "created_at", "closed_at"]
