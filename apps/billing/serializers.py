from rest_framework import serializers

from .models import Bill, SystemSettings


class BillSerializer(serializers.ModelSerializer):
    order_id = serializers.PrimaryKeyRelatedField(source="order", read_only=True)
    generated_by_name = serializers.CharField(source="generated_by.username", read_only=True)

    class Meta:
        model = Bill
        fields = [
            "id",
            "order",
            "order_id",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "discount_type",
            "discount_value",
            "discount_amount",
            "total",
            "payment_method",
            "customer_name",
            "customer_address",
            "customer_pan",
            "generated_by",
            "generated_by_name",
            "generated_at",
            "paid_at",
        ]
        read_only_fields = [
            "subtotal",
            "tax_rate",
            "tax_amount",
            "discount_amount",
            "total",
            "generated_by",
            "generated_at",
            "paid_at",
        ]


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = ["tax_rate", "restaurant_name", "address", "allow_staff_discount", "updated_at", "updated_by"]
        read_only_fields = ["updated_at", "updated_by"]
