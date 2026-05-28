from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from django.utils import timezone

from apps.tables.models import Table, TableSwitchLog

from .models import Order, OrderItem, OrderStationLog


def notify_table_status_change(table):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "tables_floor",
        {
            "type": "table.status.update",
            "table_id": table.pk,
            "status": table.status,
            "table_number": table.table_number,
        },
    )


def notify_admin_bill_request(table, order, requested_by):
    channel_layer = get_channel_layer()
    requested_by_name = requested_by.get_full_name() or requested_by.username
    event = {
        "type": "bill_request_notification",
        "table_id": table.pk,
        "table_number": table.table_number,
        "order_id": order.pk,
        "requested_by": requested_by_name,
        "requested_by_id": requested_by.pk,
        "requested_at": timezone.now().isoformat(),
        "audience": "admin",
    }
    async_to_sync(channel_layer.group_send)("admins_billing", event)
    async_to_sync(channel_layer.group_send)("tables_floor", event)


def switch_table(order_id, to_table_id, switched_by):
    """
    Atomically transfers an open order from its current table to to_table.

    Pre-conditions (raises ValueError if violated):
      1. order exists and status == OPEN
      2. to_table exists and status == AVAILABLE
      3. to_table != current table

    Atomic operations (all succeed or none):
      1. Lock both table rows with SELECT FOR UPDATE (ordered by id to prevent deadlock)
      2. Lock the order row
      3. Set from_table.status = AVAILABLE
      4. Set to_table.status   = OCCUPIED
      5. Set order.table       = to_table
      6. Create TableSwitchLog entry
      7. Broadcast table status changes over WebSocket
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("table").get(pk=order_id, status=Order.Status.OPEN)
        from_table = order.table

        # Lock tables ordered by id to prevent deadlock
        tables = list(Table.objects.select_for_update().filter(pk__in=[from_table.pk, to_table_id]).order_by("pk"))
        to_table = next((t for t in tables if t.pk == to_table_id), None)
        if to_table is None:
            raise ValueError("Destination table does not exist.")

        # Validation
        if from_table.pk == to_table.pk:
            raise ValueError("Source and destination tables are the same.")
        if to_table.status != Table.Status.AVAILABLE:
            raise ValueError(f"Table {to_table.table_number} is not available.")

        # State mutations
        from_table.status = Table.Status.AVAILABLE
        from_table.save(update_fields=["status"])

        to_table.status = Table.Status.OCCUPIED
        to_table.save(update_fields=["status"])

        order.table = to_table
        order.save(update_fields=["table"])

        TableSwitchLog.objects.create(
            order=order,
            from_table=from_table,
            to_table=to_table,
            switched_by=switched_by,
        )

    # WebSocket broadcast outside transaction (non-critical)
    notify_table_status_change(from_table)
    notify_table_status_change(to_table)

    return order


def merge_table_orders(order_id, to_table_id, merged_by):
    """
    Atomically merges one open order into another open order on a different table.

    The destination order survives and remains attached to its current table.
    The source order is closed and its table becomes available.
    """
    with transaction.atomic():
        source_order = (
            Order.objects.select_for_update()
            .select_related("table")
            .prefetch_related("items", "station_logs")
            .get(pk=order_id, status=Order.Status.OPEN)
        )
        source_table = source_order.table

        tables = list(Table.objects.select_for_update().filter(pk__in=[source_table.pk, to_table_id]).order_by("pk"))
        destination_table = next((table for table in tables if table.pk == to_table_id), None)
        if destination_table is None:
            raise ValueError("Destination table does not exist.")
        if source_table.pk == destination_table.pk:
            raise ValueError("Source and destination tables are the same.")

        destination_order = (
            Order.objects.select_for_update()
            .select_related("table")
            .prefetch_related("items", "station_logs")
            .filter(table_id=to_table_id, status=Order.Status.OPEN)
            .first()
        )
        if destination_order is None:
            raise ValueError("Destination table does not have an open order to merge into.")
        if hasattr(source_order, "bill") or hasattr(destination_order, "bill"):
            raise ValueError("Cannot merge orders that already have a generated bill.")

        destination_items_by_key = {(item.menu_item_id, item.notes): item for item in destination_order.items.all()}
        source_items = list(source_order.items.all())

        for source_item in source_items:
            item_key = (source_item.menu_item_id, source_item.notes)
            destination_item = destination_items_by_key.get(item_key)
            if destination_item is None:
                source_item.order = destination_order
                source_item.save(update_fields=["order"])
                destination_items_by_key[item_key] = source_item
                continue

            if destination_item.unit_price != source_item.unit_price:
                raise ValueError(f"Cannot merge {source_item.menu_item.name} because the item prices differ between tables.")

            destination_item.quantity += source_item.quantity
            destination_item.save(update_fields=["quantity"])
            source_item.delete()

        OrderStationLog.objects.filter(order=source_order).update(order=destination_order)

        merged_notes = [note for note in [destination_order.notes, source_order.notes] if note]
        destination_order.notes = "\n".join(dict.fromkeys(merged_notes))
        if destination_order.staff_id is None and merged_by is not None:
            destination_order.staff = merged_by
        destination_order.save(update_fields=["notes", "staff"])

        source_order.status = Order.Status.CANCELLED
        source_order.closed_at = timezone.now()
        source_order.notes = (
            f"{source_order.notes}\nMerged into Order #{destination_order.pk} on table {destination_table.table_number}."
        ).strip()
        source_order.save(update_fields=["status", "closed_at", "notes"])

        source_table.status = Table.Status.AVAILABLE
        source_table.save(update_fields=["status"])

        destination_table.status = Table.Status.OCCUPIED
        destination_table.save(update_fields=["status"])

    notify_table_status_change(source_table)
    notify_table_status_change(destination_table)

    refreshed_destination_order = (
        Order.objects.select_related("table", "staff")
        .prefetch_related("items__menu_item__category", "station_logs")
        .get(pk=destination_order.pk)
    )

    return refreshed_destination_order, source_table, destination_table
