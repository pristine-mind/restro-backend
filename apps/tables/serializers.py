from rest_framework import serializers

from .models import Table, TableSwitchLog


class TableSerializer(serializers.ModelSerializer):
    active_order_id = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ["id", "table_number", "capacity", "status", "active_order_id", "created_at"]

    def get_active_order_id(self, obj):
        order = obj.active_order
        return order.id if order else None
