from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.tables.models import Table, TableSwitchLog

from .models import Order


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
