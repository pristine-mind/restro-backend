from django.utils import timezone

from .models import MenuItem


def soft_delete_menu_item(item_id):
    """
    Marks a MenuItem as deleted without removing the DB row.
    Preserves referential integrity for historical OrderItems.
    Does NOT affect existing open order items.
    """
    item = MenuItem.objects.get(pk=item_id, deleted_at__isnull=True)
    item.is_available = False
    item.deleted_at = timezone.now()
    item.save(update_fields=["is_available", "deleted_at"])
    return item
