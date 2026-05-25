import django_filters

from .models import MenuItem


class MenuItemFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category__id")
    is_available = django_filters.BooleanFilter(field_name="is_available")
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")

    class Meta:
        model = MenuItem
        fields = ["category", "is_available"]
