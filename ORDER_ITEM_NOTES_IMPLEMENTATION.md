# Order Item Notes Implementation

This document isolates the per-item `notes` feature used when staff add items to an order for a table.

## Goal

Allow staff to attach a special request to each order item, such as:
- `no onion`
- `less spicy`
- `extra sauce`
- `no ice`

These notes must be preserved on the order item itself and must also remain visible on station tickets and in the order panel.

## Backend Behavior

The backend already stores `notes` on `OrderItem`.

Expected behavior:
- `notes` is submitted when creating an order item.
- Two items should only merge into one line when both `menu_item` and `notes` are the same.
- The same menu item with different notes must remain as separate order lines.
- Table merge logic must preserve note-specific order item lines.

## API Contract

### Add Order Item

```http
POST /orders/{orderId}/items/
Content-Type: application/json
```

Request body:

```json
{
  "menu_item": 12,
  "quantity": 1,
  "notes": "no onion"
}
```

Example behavior:
- Adding `Chicken Momo` with `notes: "extra spicy"` and then adding the same item again with the same notes increases quantity.
- Adding `Chicken Momo` with `notes: "no onion"` creates a separate line item.

## Frontend Hook

```typescript
// lib/hooks/useOrderItems.ts
export function useAddOrderItem(orderId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { menu_item: number; quantity: number; notes?: string }) => {
      const { data } = await api.post(`/orders/${orderId}/items/`, payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.orders.items(orderId) });
      qc.invalidateQueries({ queryKey: queryKeys.orders.detail(orderId) });
    },
    onError: (err: AxiosError<ApiError>) => {
      toast.error(err.response?.data?.detail || 'Failed to add item');
    },
  });
}
```

## Order Panel UI

```typescript
// src/app/staff/orders/[tableId]/page.tsx
'use client';

import { useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useOrder } from '@/lib/hooks/useOrders';
import { useMenuItems } from '@/lib/hooks/useMenu';
import { useAddOrderItem } from '@/lib/hooks/useOrderItems';

export default function OrderPanelPage({ params }: { params: { tableId: string } }) {
  const searchParams = useSearchParams();
  const orderId = Number(searchParams.get('orderId'));
  const { data: order } = useOrder(orderId);
  const { data: menuItems } = useMenuItems({ is_available: true });
  const addItem = useAddOrderItem(orderId);
  const [itemNotes, setItemNotes] = useState<Record<number, string>>({});

  return (
    <div className="grid grid-cols-2 gap-6">
      <div>
        <h2>Menu</h2>
        {menuItems?.results.map((item) => (
          <div key={item.id} className="mb-2 rounded border p-3">
            <button
              onClick={() =>
                addItem.mutate({
                  menu_item: item.id,
                  quantity: 1,
                  notes: itemNotes[item.id]?.trim() || undefined,
                })
              }
              disabled={addItem.isPending}
              className="block w-full text-left"
            >
              {item.name} — ${item.price}
            </button>
            <textarea
              value={itemNotes[item.id] || ''}
              onChange={(e) =>
                setItemNotes((current) => ({
                  ...current,
                  [item.id]: e.target.value,
                }))
              }
              placeholder="Special request for this item"
              className="mt-2 w-full rounded border px-2 py-1 text-sm"
              rows={2}
            />
          </div>
        ))}
      </div>

      <div>
        <h2>Order #{orderId}</h2>
        <div className="space-y-2">
          {order?.items.map((item) => (
            <OrderItemRow key={item.id} item={item} orderId={orderId} />
          ))}
        </div>
        <div className="mt-4 font-bold">Subtotal: ${order?.subtotal}</div>
        <BillingButton orderId={orderId} />
      </div>
    </div>
  );
}
```

## Order Item Row Display

```typescript
function OrderItemRow({ item, orderId }: { item: OrderItem; orderId: number }) {
  const [quantity, setQuantity] = useState(item.quantity);
  const updateItem = useUpdateOrderItem(orderId, item.id);
  const deleteItem = useDeleteOrderItem(orderId, item.id);

  const handleUpdate = () => {
    if (quantity === item.quantity) return;
    if (quantity < 1) {
      deleteItem.mutate();
      return;
    }
    updateItem.mutate({ quantity });
  };

  return (
    <div className="flex items-center justify-between p-2 border rounded">
      <div>
        <div className="font-medium">{item.menu_item.name}</div>
        <div className="text-sm text-gray-500">${item.unit_price} each</div>
        {item.notes && <div className="text-xs text-gray-400">Request: {item.notes}</div>}
      </div>
      <div className="flex items-center gap-2">
        <input
          type="number"
          min={1}
          value={quantity}
          onChange={(e) => setQuantity(Number(e.target.value))}
          onBlur={handleUpdate}
          className="w-16 border rounded px-2 py-1"
        />
        <button onClick={() => deleteItem.mutate()} disabled={deleteItem.isPending}>
          Remove
        </button>
      </div>
    </div>
  );
}
```

## Rules

- `notes` is optional, but when present it is part of the identity of the order item.
- Matching `menu_item` plus matching `notes` means quantity should increase.
- Matching `menu_item` with different `notes` means separate rows.
- Notes should flow through station tickets and merged-table orders without being flattened.

## Testing Checklist

1. Add the same menu item twice with the same note and verify quantity increments.
2. Add the same menu item with two different notes and verify two separate lines appear.
3. Send items to kitchen/bar and verify the note appears in the station workflow.
4. Merge two tables that contain the same item with different notes and verify the separate lines remain intact.
5. Generate a bill after adding note-based duplicate items and verify totals remain correct.
