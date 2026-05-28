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
    station = serializers.CharField(read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "order", "menu_item", "menu_item_id", "quantity", "unit_price", "notes", "station"]
        read_only_fields = ["order", "unit_price", "station"]

    def create(self, validated_data):
        order = self.context["order"]
        menu_item = validated_data["menu_item"]
        quantity = validated_data["quantity"]
        notes = validated_data.get("notes", "")

        # Merge only when both the menu item and special request notes match.
        existing = order.items.filter(menu_item=menu_item, notes=notes).first()
        if existing:
            existing.quantity += quantity
            existing.save(update_fields=["quantity"])
            return existing

        unit_price = menu_item.price
        station = menu_item.category.station if menu_item.category else OrderItem.Station.KITCHEN
        return OrderItem.objects.create(
            order=order,
            menu_item=menu_item,
            quantity=quantity,
            unit_price=unit_price,
            notes=notes,
            station=station,
        )


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    table_id = serializers.PrimaryKeyRelatedField(
        queryset=Table.objects.all(),
        source="table",
        write_only=True,
    )
    staff_name = serializers.CharField(source="staff.username", read_only=True)
    station_logs = serializers.SerializerMethodField()

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
            "station_logs",
        ]
        read_only_fields = ["table", "staff", "status", "subtotal", "created_at", "closed_at", "station_logs"]

    def get_station_logs(self, obj):
        logs = obj.station_logs.all()
        return [
            {
                "id": log.id,
                "station": log.station,
                "sent_at": log.sent_at,
                "sent_by": log.sent_by.get_full_name() or log.sent_by.username if log.sent_by else None,
                "items_count": len(log.items_snapshot),
            }
            for log in logs
        ]
