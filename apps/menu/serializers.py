from rest_framework import serializers

from .models import Category, MenuItem


class CategorySerializer(serializers.ModelSerializer):
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "name", "display_order", "station", "item_count"]

    def get_item_count(self, obj):
        return obj.items.filter(deleted_at__isnull=True).count()


class MenuItemSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source="category", write_only=True, required=False
    )
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "name",
            "description",
            "price",
            "is_available",
            "category",
            "category_id",
            "image",
            "image_url",
            "created_at",
            "updated_at",
            "deleted_at",
        ]
        read_only_fields = ["deleted_at"]

    def to_internal_value(self, data):
        # Accept `category` as an alias for `category_id` on writes
        if data and "category" in data and "category_id" not in data:
            data = data.copy()
            category_val = data.pop("category")
            # QueryDict.pop returns a list; dict.pop returns a single value
            if isinstance(category_val, list):
                category_val = category_val[0] if category_val else None
            if category_val is not None and category_val != "":
                data["category_id"] = category_val
        return super().to_internal_value(data)

    def get_image_url(self, obj):
        request = self.context.get("request")
        if obj.image and request:
            return request.build_absolute_uri(obj.image.url)
        return None
