# Restaurant Management System — Frontend Implementation Guide

**Target:** Senior Engineer  
**Stack:** Next.js 14 (App Router) · TypeScript · Tailwind CSS · shadcn/ui · TanStack Query · Zustand · Axios · React Hook Form · Zod  
**Backend:** Django 5.x · DRF · WebSocket (`/ws/tables/`)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [TypeScript Types & Contracts](#2-typescript-types--contracts)
3. [API Client & Authentication](#3-api-client--authentication)
4. [State Management (Zustand)](#4-state-management-zustand)
5. [TanStack Query Patterns](#5-tanstack-query-patterns)
6. [WebSocket Integration](#6-websocket-integration)
7. [Feature Implementations](#7-feature-implementations)
8. [Error Handling & Edge Cases](#8-error-handling--edge-cases)
9. [Testing Strategy](#9-testing-strategy)
10. [Performance & Security](#10-performance--security)

---

## 1. Architecture Overview

### 1.1 App Router Structure

```
src/app/
├── (auth)/
│   └── login/page.tsx
├── admin/
│   ├── layout.tsx
│   ├── page.tsx                 # Dashboard
│   ├── menu/
│   │   ├── page.tsx             # Menu list
│   │   └── [id]/page.tsx        # Create / Edit
│   ├── tables/page.tsx
│   ├── staff/page.tsx
│   ├── reports/page.tsx
│   └── settings/page.tsx
├── staff/
│   ├── layout.tsx
│   ├── floor/page.tsx           # Live floor map
│   ├── orders/
│   │   └── [tableId]/page.tsx   # Order panel
│   └── billing/
│       └── [orderId]/page.tsx   # Bill preview
├── layout.tsx
└── middleware.ts
```

### 1.2 Environment Variables

```env
NEXT_PUBLIC_API_URL=http://localhost:8006/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8007
```

**CRITICAL:** Never prefix sensitive variables with `NEXT_PUBLIC_`. `NEXT_PUBLIC_` is ONLY for the browser bundle.

---

## 2. TypeScript Types & Contracts

Mirror the Django models exactly. Keep these in `src/types/index.ts`.

```typescript
// ── Enums ───────────────────────────────────────────────

export type UserRole = 'admin' | 'staff';

export type TableStatus = 'available' | 'occupied' | 'reserved' | 'cleaning';

export type OrderStatus = 'open' | 'billed' | 'paid' | 'cancelled';

export type PaymentMethod = 'cash' | 'card' | 'wallet';

export type DiscountType = 'none' | 'percentage' | 'fixed';

// ── Core Models ─────────────────────────────────────────

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: UserRole;
}

export type Station = 'kitchen' | 'bar';

export interface Category {
  id: number;
  name: string;
  display_order: number;
  station: Station;
  item_count: number;
}

export interface MenuItem {
  id: number;
  name: string;
  description: string;
  price: number;
  is_available: boolean;
  category: Category | null;
  category_id: number;
  image_url: string | null;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface Table {
  id: number;
  table_number: string;
  capacity: number;
  status: TableStatus;
  active_order_id: number | null;
  created_at: string;
}

export interface Order {
  id: number;
  table: number;           // table ID
  table_id: number;        // write-only
  staff: number | null;
  staff_name: string;
  status: OrderStatus;
  notes: string;
  subtotal: string;        // Decimal from backend
  created_at: string;
  closed_at: string | null;
  items: OrderItem[];
  station_logs: OrderStationLog[];
}

export interface OrderItem {
  id: number;
  order: number;
  menu_item: MenuItem;
  menu_item_id: number;
  quantity: number;
  unit_price: string;
  notes: string;
  station: Station;
}

export interface OrderStationLog {
  id: number;
  station: Station;
  sent_at: string;
  sent_by: string | null;
  items_count: number;
}

export interface Bill {
  id: number;
  order: number;
  order_id: number;
  subtotal: string;
  tax_rate: string;
  tax_amount: string;
  discount_type: DiscountType;
  discount_value: string;
  discount_amount: string;
  total: string;
  payment_method: PaymentMethod;
  generated_by: number | null;
  generated_by_name: string;
  generated_at: string;
  paid_at: string | null;
}

export interface SystemSettings {
  tax_rate: string;
  restaurant_name: string;
  address: string;
  allow_staff_discount: boolean;
  updated_at: string;
  updated_by: number | null;
}

export interface TableSwitchLog {
  id: number;
  order: number;
  from_table: number | null;
  to_table: number | null;
  switched_by: number | null;
  switched_at: string;
}

// ── API Response Wrappers ───────────────────────────────

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ApiError {
  detail: string;
  code?: string;
}
```

### 2.1 Decimal Handling

Django returns `DecimalField` as **strings** in JSON. Never use `parseFloat` for monetary calculations — use a dedicated decimal library or convert to cents (integer) for display math.

```typescript
// lib/money.ts
export function formatMoney(value: string | number): string {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format(num);
}

export function calculateLineTotal(quantity: number, unitPrice: string): string {
  return (quantity * parseFloat(unitPrice)).toFixed(2);
}
```

---

## 3. API Client & Authentication

### 3.1 Axios Instance

```typescript
// lib/api/client.ts
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
import { useAuthStore } from '@/lib/store/authStore';

const api = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 10000,
});

// ── Request Interceptor ─────────────────────────────────

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = useAuthStore.getState().accessToken;
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ── Response Interceptor (Token Refresh) ────────────────

let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    if (error.response?.status === 401 && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        // Queue the request until refresh completes
        return new Promise((resolve) => {
          refreshSubscribers.push((token: string) => {
            originalRequest.headers.Authorization = `Bearer ${token}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // NOTE: Refresh is handled via httpOnly cookie to Next.js API route,
        // or directly if you expose Django refresh endpoint
        const refreshToken = useAuthStore.getState().refreshToken;
        if (!refreshToken) throw new Error('No refresh token');

        const { data } = await axios.post(
          `${process.env.NEXT_PUBLIC_API_URL}/auth/token/refresh/`,
          { refresh: refreshToken }
        );

        useAuthStore.getState().setAccessToken(data.access);
        onRefreshed(data.access);

        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return api(originalRequest);
      } catch (refreshError) {
        useAuthStore.getState().clearAuth();
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

### 3.2 Auth Store (Zustand)

```typescript
// lib/store/authStore.ts
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { User } from '@/types';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  setAuth: (user: User, access: string, refresh: string) => void;
  setAccessToken: (token: string) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      setAuth: (user, access, refresh) =>
        set({ user, accessToken: access, refreshToken: refresh }),
      setAccessToken: (token) => set({ accessToken: token }),
      clearAuth: () =>
        set({ user: null, accessToken: null, refreshToken: null }),
    }),
    {
      name: 'rms-auth',
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        // NEVER persist accessToken in localStorage in production
        // This is development-only; use httpOnly cookies for refresh
        user: state.user,
        refreshToken: state.refreshToken,
      }),
    }
  )
);
```

**SECURITY WARNING:** For production, `accessToken` must be stored **in-memory only** (Zustand without persist). The `refreshToken` should live in an `httpOnly` cookie set by a Next.js API route. The store above is simplified for development clarity.

### 3.3 Next.js Middleware (Role Guard)

```typescript
// middleware.ts
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const token = request.cookies.get('refreshToken')?.value;
  const role = request.cookies.get('userRole')?.value;
  const pathname = request.nextUrl.pathname;

  // Public routes
  if (pathname === '/login') {
    if (token) {
      return NextResponse.redirect(new URL(role === 'admin' ? '/admin' : '/staff/floor', request.url));
    }
    return NextResponse.next();
  }

  // Protected routes
  if (!token) {
    return NextResponse.redirect(new URL('/login', request.url));
  }

  // Role-based access
  if (pathname.startsWith('/admin') && role !== 'admin') {
    return NextResponse.redirect(new URL('/staff/floor', request.url));
  }
  if (pathname.startsWith('/staff') && role !== 'staff') {
    return NextResponse.redirect(new URL('/admin', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/admin/:path*', '/staff/:path*', '/login'],
};
```

---

## 4. State Management (Zustand)

### 4.1 Order Store (Client State)

```typescript
// lib/store/orderStore.ts
import { create } from 'zustand';

interface OrderState {
  activeTableId: number | null;
  activeOrderId: number | null;
  setActiveTable: (tableId: number | null) => void;
  setActiveOrder: (orderId: number | null) => void;
  reset: () => void;
}

export const useOrderStore = create<OrderState>((set) => ({
  activeTableId: null,
  activeOrderId: null,
  setActiveTable: (tableId) => set({ activeTableId: tableId }),
  setActiveOrder: (orderId) => set({ activeOrderId: orderId }),
  reset: () => set({ activeTableId: null, activeOrderId: null }),
}));
```

### 4.2 Floor Store (WebSocket Sync)

```typescript
// lib/store/floorStore.ts
import { create } from 'zustand';
import { Table } from '@/types';

interface FloorState {
  tables: Table[];
  isConnected: boolean;
  updateTableStatus: (tableId: number, status: Table['status']) => void;
  setTables: (tables: Table[]) => void;
  setConnected: (connected: boolean) => void;
}

export const useFloorStore = create<FloorState>((set) => ({
  tables: [],
  isConnected: false,
  updateTableStatus: (tableId, status) =>
    set((state) => ({
      tables: state.tables.map((t) =>
        t.id === tableId ? { ...t, status } : t
      ),
    })),
  setTables: (tables) => set({ tables }),
  setConnected: (connected) => set({ isConnected: connected }),
}));
```

---

## 5. TanStack Query Patterns

### 5.1 Query Keys Convention

```typescript
// lib/api/keys.ts
export const queryKeys = {
  auth: {
    me: ['auth', 'me'] as const,
  },
  menu: {
    categories: ['menu', 'categories'] as const,
    items: (filters?: Record<string, unknown>) => ['menu', 'items', filters] as const,
    item: (id: number) => ['menu', 'items', id] as const,
  },
  tables: {
    all: ['tables'] as const,
    detail: (id: number) => ['tables', id] as const,
  },
  orders: {
    all: (filters?: Record<string, unknown>) => ['orders', filters] as const,
    detail: (id: number) => ['orders', id] as const,
    items: (orderId: number) => ['orders', orderId, 'items'] as const,
    stationLogs: (orderId: number) => ['orders', orderId, 'station-logs'] as const,
  },
  bills: {
    all: ['bills'] as const,
    detail: (id: number) => ['bills', id] as const,
  },
  settings: ['settings'] as const,
  reports: {
    daily: (date?: string) => ['reports', 'daily', date] as const,
    items: (from?: string, to?: string) => ['reports', 'items', { from, to }] as const,
  },
};
```

### 5.2 Standard Query Hook Pattern

```typescript
// lib/hooks/useTables.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api/client';
import { queryKeys } from '@/lib/api/keys';
import { Table, Order } from '@/types';
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';

export function useTables() {
  return useQuery({
    queryKey: queryKeys.tables.all,
    queryFn: async () => {
      const { data } = await api.get<Table[]>('/tables/');
      return data;
    },
    staleTime: 30_000, // 30s; WebSocket is the source of truth
    refetchOnWindowFocus: false,
  });
}

export function useCreateOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (tableId: number) => {
      const { data } = await api.post<Order>('/orders/', { table: tableId });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.tables.all });
      qc.invalidateQueries({ queryKey: queryKeys.orders.all() });
    },
    onError: (error: AxiosError<ApiError>) => {
      toast.error(error.response?.data?.detail || 'Failed to create order');
    },
  });
}
```

### 5.3 Optimistic Updates

```typescript
// Example: Switch Table
export function useSwitchTable() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ orderId, toTableId }: { orderId: number; toTableId: number }) => {
      const { data } = await api.post(`/orders/${orderId}/switch-table/`, {
        to_table: toTableId,
      });
      return data;
    },
    onMutate: async ({ orderId, toTableId }) => {
      await qc.cancelQueries({ queryKey: queryKeys.tables.all });
      await qc.cancelQueries({ queryKey: queryKeys.orders.detail(orderId) });

      const previousTables = qc.getQueryData<Table[]>(queryKeys.tables.all);
      const previousOrder = qc.getQueryData<Order>(queryKeys.orders.detail(orderId));

      // Optimistically update table statuses
      qc.setQueryData<Table[]>(queryKeys.tables.all, (old) => {
        if (!old) return old;
        const fromTableId = previousOrder?.table;
        return old.map((t) => {
          if (t.id === fromTableId) return { ...t, status: 'available' };
          if (t.id === toTableId) return { ...t, status: 'occupied' };
          return t;
        });
      });

      return { previousTables, previousOrder };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousTables) {
        qc.setQueryData(queryKeys.tables.all, context.previousTables);
      }
      toast.error('Table switch failed. Reverted.');
    },
    onSettled: (_data, _err, { orderId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.tables.all });
      qc.invalidateQueries({ queryKey: queryKeys.orders.detail(orderId) });
    },
  });
}

export function useMergeTableOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ orderId, toTableId }: { orderId: number; toTableId: number }) => {
      const { data } = await api.post(`/orders/${orderId}/merge-table/`, {
        to_table: toTableId,
      });
      return data;
    },
    onSuccess: (_data, { orderId }) => {
      qc.invalidateQueries({ queryKey: queryKeys.tables.all });
      qc.invalidateQueries({ queryKey: queryKeys.orders.all() });
      qc.invalidateQueries({ queryKey: queryKeys.orders.detail(orderId) });
    },
    onError: (err: AxiosError<ApiError>) => {
      toast.error(err.response?.data?.detail || 'Table merge failed');
    },
  });
}
```

---

## 6. WebSocket Integration

### 6.1 Hook: useTableSocket

```typescript
// hooks/useTableSocket.ts
import { useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '@/lib/store/authStore';
import { useFloorStore } from '@/lib/store/floorStore';
import { queryKeys } from '@/lib/api/keys';
import { Table } from '@/types';

const RECONNECT_DELAY = 3000;
const MAX_RECONNECT_ATTEMPTS = 10;

export function useTableSocket() {
  const qc = useQueryClient();
  const { accessToken } = useAuthStore();
  const setConnected = useFloorStore((s) => s.setConnected);
  const updateTableStatus = useFloorStore((s) => s.updateTableStatus);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!accessToken) return;

    function connect() {
      const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}/ws/tables/?token=${accessToken}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        reconnectAttempts.current = 0;
        setConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'table.status.update') {
            // Update Zustand store
            updateTableStatus(msg.table_id, msg.status);

            // Update TanStack Query cache
            qc.setQueryData<Table[]>(queryKeys.tables.all, (old) => {
              if (!old) return old;
              return old.map((t) =>
                t.id === msg.table_id ? { ...t, status: msg.status } : t
              );
            });
          }

          if (msg.type === 'billing.bill_request') {
            // Admin clients can show a toast, badge, or invalidate a notifications query here.
            qc.invalidateQueries({ queryKey: queryKeys.orders.all });
          }
        } catch {
          // Ignore malformed messages
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        setConnected(false);
        wsRef.current = null;

        if (reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttempts.current += 1;
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
        }
      };
    }

    connect();

    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnection on unmount
        wsRef.current.close();
      }
    };
  }, [accessToken, qc, setConnected, updateTableStatus]);
}
```

### 6.2 Connection Status Indicator

```typescript
// components/tables/ConnectionBadge.tsx
import { useFloorStore } from '@/lib/store/floorStore';

export function ConnectionBadge() {
  const isConnected = useFloorStore((s) => s.isConnected);
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
        isConnected
          ? 'bg-green-100 text-green-700'
          : 'bg-red-100 text-red-700'
      }`}
    >
      {isConnected ? 'Live' : 'Reconnecting...'}
    </span>
  );
}
```

---

## 7. Feature Implementations

### 7.1 Authentication Flow

**Login Page (`src/app/(auth)/login/page.tsx`)**

```typescript
'use client';

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store/authStore';
import api from '@/lib/api/client';
import toast from 'react-hot-toast';

const loginSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  password: z.string().min(1, 'Password is required'),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  });

  const onSubmit = async (data: LoginForm) => {
    try {
      const res = await api.post('/auth/login/', data);
      const { access, refresh, user } = res.data;

      useAuthStore.getState().setAuth(user, access, refresh);

      // Set role cookie for middleware
      document.cookie = `userRole=${user.role}; path=/; SameSite=Strict`;

      router.push(user.role === 'admin' ? '/admin' : '/staff/floor');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Login failed');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('username')} placeholder="Username" />
      {errors.username && <span>{errors.username.message}</span>}

      <input type="password" {...register('password')} placeholder="Password" />
      {errors.password && <span>{errors.password.message}</span>}

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Logging in...' : 'Login'}
      </button>
    </form>
  );
}
```

**Logout Handler**

```typescript
async function logout() {
  const refreshToken = useAuthStore.getState().refreshToken;
  try {
    await api.post('/auth/logout/', { refresh: refreshToken });
  } catch {
    // Ignore logout errors — clear locally regardless
  }
  useAuthStore.getState().clearAuth();
  document.cookie = 'userRole=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT';
  window.location.href = '/login';
}
```

---

### 7.2 Menu Management (Admin)

**Menu Item Form with Image Upload**

```typescript
const menuItemSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().max(1000).optional(),
  price: z.number().positive().multipleOf(0.01),
  category_id: z.number({ required_error: 'Category is required' }),
  is_available: z.boolean().default(true),
});

type MenuItemForm = z.infer<typeof menuItemSchema>;

// Create / Update
async function createMenuItem(data: MenuItemForm, imageFile?: File) {
  const formData = new FormData();
  formData.append('name', data.name);
  formData.append('description', data.description || '');
  formData.append('price', data.price.toString());
  formData.append('category', data.category_id.toString());
  formData.append('is_available', data.is_available.toString());
  if (imageFile) formData.append('image', imageFile);

  const res = await api.post('/menu/items/', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return res.data;
}
```

**Soft Delete with Confirmation**

```typescript
function useDeleteMenuItem() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/menu/items/${id}/`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.menu.items() });
      toast.success('Item deleted');
    },
  });
}

// Edge case: Soft-deleted items still appear in historical orders.
// The UI should filter them from the menu picker but keep them visible
// in order history with a "[DELETED]" badge.
```

---

### 7.3 Floor Map (Staff)

```typescript
// src/app/staff/floor/page.tsx
'use client';

import { useTables } from '@/lib/hooks/useTables';
import { useTableSocket } from '@/hooks/useTableSocket';
import { useOrderStore } from '@/lib/store/orderStore';
import { useCreateOrder } from '@/lib/hooks/useOrders';
import { TableStatus } from '@/types';

const statusColors: Record<TableStatus, string> = {
  available: 'bg-green-500',
  occupied: 'bg-red-500',
  reserved: 'bg-yellow-500',
  cleaning: 'bg-blue-500',
};

export default function FloorPage() {
  const { data: tables, isLoading } = useTables();
  useTableSocket(); // Subscribe to live updates

  const createOrder = useCreateOrder();
  const setActiveTable = useOrderStore((s) => s.setActiveTable);

  async function handleTableClick(table: Table) {
    if (table.status === 'available') {
      const order = await createOrder.mutateAsync(table.id);
      setActiveTable(table.id);
      // Navigate to order panel
      window.location.href = `/staff/orders/${table.id}?orderId=${order.id}`;
    } else if (table.status === 'occupied' && table.active_order_id) {
      setActiveTable(table.id);
      window.location.href = `/staff/orders/${table.id}?orderId=${table.active_order_id}`;
    }
  }

  if (isLoading) return <div>Loading tables...</div>;

  return (
    <div className="grid grid-cols-4 gap-4">
      {tables?.map((table) => (
        <button
          key={table.id}
          onClick={() => handleTableClick(table)}
          disabled={createOrder.isPending}
          className={`p-4 rounded-lg text-white ${statusColors[table.status]}`}
        >
          <div className="text-lg font-bold">{table.table_number}</div>
          <div className="text-sm">Capacity: {table.capacity}</div>
          <div className="text-xs capitalize">{table.status}</div>
        </button>
      ))}
    </div>
  );
}
```

**Edge Cases:**
- Double-click protection: `disabled={createOrder.isPending}` prevents duplicate order creation.
- If two staff click the same available table simultaneously, backend returns 409. Catch it and refresh the floor map.
- WebSocket disconnect: TanStack Query `staleTime` + `refetchInterval: 30000` as fallback polling.

---

### 7.4 Order Panel

**Add Item with Duplicate Detection**

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

**Order Panel UI**

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
      {/* Menu Picker */}
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

      {/* Current Order */}
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

**Order Item Row with Edit/Delete**

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

**Item Notes Rules:**
- `notes` is the per-item special request field for instructions like `no onion`, `less spicy`, or `extra sauce`.
- The backend only combines quantities when both `menu_item` and `notes` match.
- The same menu item with different notes stays as separate order lines so station tickets preserve the request correctly.

---

### 7.5 Station Tickets (Kitchen / Bar)

**Order Panel with Station Buttons**

```typescript
// lib/hooks/useStationTickets.ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api/client';
import { queryKeys } from '@/lib/api/keys';
import toast from 'react-hot-toast';

export function useSendToStation(orderId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (station: 'kitchen' | 'bar') => {
      const { data } = await api.post(
        `/orders/${orderId}/send-to-station/`,
        { station },
        { responseType: 'blob' }
      );
      return { blob: data as Blob, station };
    },
    onSuccess: ({ blob, station }) => {
      // Open PDF in new tab for printing
      const url = URL.createObjectURL(blob);
      const printWindow = window.open(url, '_blank');
      if (printWindow) {
        printWindow.onload = () => {
          printWindow.print();
        };
      }
      qc.invalidateQueries({ queryKey: queryKeys.orders.detail(orderId) });
      toast.success(`${station === 'kitchen' ? 'Kitchen' : 'Bar'} ticket sent`);
    },
    onError: (err: any) => {
      toast.error(err.response?.data?.detail || 'Failed to send ticket');
    },
  });
}

export function useStationLogs(orderId: number) {
  return useQuery({
    queryKey: ['orders', orderId, 'station-logs'],
    queryFn: async () => {
      const { data } = await api.get(`/orders/${orderId}/station-logs/`);
      return data as { id: number; station: string; sent_at: string; sent_by: string | null; items: any[] }[];
    },
  });
}
```

**Station Buttons in Order Panel**

```typescript
function StationButtons({ order }: { order: Order }) {
  const sendToStation = useSendToStation(order.id);

  const kitchenItems = order.items.filter((i) => i.station === 'kitchen');
  const barItems = order.items.filter((i) => i.station === 'bar');

  const hasKitchenLog = order.station_logs.some((l) => l.station === 'kitchen');
  const hasBarLog = order.station_logs.some((l) => l.station === 'bar');

  return (
    <div className="flex gap-2 mt-4">
      <button
        onClick={() => sendToStation.mutate('kitchen')}
        disabled={kitchenItems.length === 0 || sendToStation.isPending}
        className={`flex-1 py-2 rounded font-medium ${
          kitchenItems.length === 0
            ? 'bg-gray-200 text-gray-400'
            : hasKitchenLog
            ? 'bg-orange-100 text-orange-700 border border-orange-300'
            : 'bg-orange-600 text-white'
        }`}
      >
        {sendToStation.isPending && sendToStation.variables === 'kitchen'
          ? 'Printing...'
          : hasKitchenLog
          ? '🍽️ Re-print Kitchen'
          : '🍽️ Send to Kitchen'}
      </button>

      <button
        onClick={() => sendToStation.mutate('bar')}
        disabled={barItems.length === 0 || sendToStation.isPending}
        className={`flex-1 py-2 rounded font-medium ${
          barItems.length === 0
            ? 'bg-gray-200 text-gray-400'
            : hasBarLog
            ? 'bg-purple-100 text-purple-700 border border-purple-300'
            : 'bg-purple-600 text-white'
        }`}
      >
        {sendToStation.isPending && sendToStation.variables === 'bar'
          ? 'Printing...'
          : hasBarLog
          ? '🍸 Re-print Bar'
          : '🍸 Send to Bar'}
      </button>
    </div>
  );
}
```

**Item Station Badge**

```typescript
function OrderItemRow({ item, orderId }: { item: OrderItem; orderId: number }) {
  const stationColor = item.station === 'kitchen'
    ? 'bg-orange-100 text-orange-700'
    : 'bg-purple-100 text-purple-700';

  return (
    <div className="flex items-center justify-between p-2 border rounded">
      <div>
        <div className="font-medium">{item.menu_item.name}</div>
        <div className="text-sm text-gray-500">${item.unit_price} each</div>
        {item.notes && <div className="text-xs text-gray-400">* {item.notes}</div>}
      </div>
      <div className="flex items-center gap-2">
        <span className={`text-xs px-2 py-0.5 rounded ${stationColor}`}>
          {item.station}
        </span>
        {/* quantity controls */}
      </div>
    </div>
  );
}
```

**Edge Cases:**
- Empty station: Button disabled with gray style. Backend returns 400 if no items.
- Re-print: Button style changes after first send. `station_logs` on Order tells you what's been sent.
- Browser print: PDF opens in new tab. Staff selects the correct thermal printer (Kitchen or Bar) from the print dialog.
- Multi-send: Staff can click "Send to Kitchen" multiple times. Each click creates a new log and prints a fresh ticket with all current kitchen items.

---

### 7.6 Table Switch Dialog

```typescript
// components/tables/SwitchDialog.tsx
import { useState } from 'react';
import { useTables } from '@/lib/hooks/useTables';
import { useSwitchTable } from '@/lib/hooks/useOrders';

interface Props {
  orderId: number;
  currentTableId: number;
  onClose: () => void;
}

export function SwitchDialog({ orderId, currentTableId, onClose }: Props) {
  const { data: tables } = useTables();
  const switchTable = useSwitchTable();
  const [selectedTable, setSelectedTable] = useState<number | null>(null);

  const availableTables = tables?.filter(
    (t) => t.id !== currentTableId && t.status === 'available'
  );

  async function handleSwitch() {
    if (!selectedTable) return;
    await switchTable.mutateAsync({ orderId, toTableId: selectedTable });
    onClose();
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg w-96">
        <h2 className="text-lg font-bold mb-4">Switch Table</h2>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {availableTables?.map((table) => (
            <button
              key={table.id}
              onClick={() => setSelectedTable(table.id)}
              className={`w-full p-3 rounded border text-left ${
                selectedTable === table.id ? 'border-blue-500 bg-blue-50' : ''
              }`}
            >
              {table.table_number} (Capacity: {table.capacity})
            </button>
          ))}
          {availableTables?.length === 0 && (
            <p className="text-gray-500">No available tables.</p>
          )}
        </div>
        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose}>Cancel</button>
          <button
            onClick={handleSwitch}
            disabled={!selectedTable || switchTable.isPending}
          >
            {switchTable.isPending ? 'Switching...' : 'Switch'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Edge Cases:**
- Dialog must filter out occupied/reserved/cleaning tables.
- If another staff bills the order WHILE the dialog is open, the switch will fail with 409. Show error and close dialog.
- Optimistic update immediately shows the new table occupied and old table available.

### 7.6A Table Merge

Use this when two occupied tables should be billed together under a single surviving order.

```typescript
// components/tables/MergeDialog.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTables } from '@/lib/hooks/useTables';
import { useMergeTableOrder } from '@/lib/hooks/useOrders';
import { useOrder } from '@/lib/hooks/useOrders';
import { Table } from '@/types';

interface Props {
  orderId: number;
  currentTableId: number;
  onClose: () => void;
}

export function MergeDialog({ orderId, currentTableId, onClose }: Props) {
  const router = useRouter();
  const { data: tables } = useTables();
  const { data: currentOrder } = useOrder(orderId);
  const mergeTableOrder = useMergeTableOrder();
  const [selectedTableId, setSelectedTableId] = useState<number | null>(null);

  const mergeCandidates = tables?.filter((table) => {
    if (table.id === currentTableId) return false;
    if (table.status !== 'occupied') return false;
    if (!table.active_order_id) return false;
    return table.active_order_id !== orderId;
  });

  async function handleMerge() {
    if (!selectedTableId || !currentOrder) return;

    const result = await mergeTableOrder.mutateAsync({
      orderId,
      toTableId: selectedTableId,
    });

    onClose();
    router.push(`/staff/orders/${result.to_table}?orderId=${result.order.id}`);
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center">
      <div className="bg-white p-6 rounded-lg w-96">
        <h2 className="text-lg font-bold mb-2">Merge Tables</h2>
        <p className="text-sm text-gray-500 mb-4">
          Merge this table&apos;s open order into another occupied table so both tables can be billed together.
        </p>

        <div className="space-y-2 max-h-64 overflow-y-auto">
          {mergeCandidates?.map((table: Table) => (
            <button
              key={table.id}
              onClick={() => setSelectedTableId(table.id)}
              className={`w-full p-3 rounded border text-left ${
                selectedTableId === table.id ? 'border-emerald-600 bg-emerald-50' : 'border-gray-200'
              }`}
            >
              <div className="font-medium">{table.table_number}</div>
              <div className="text-sm text-gray-500">Capacity: {table.capacity}</div>
            </button>
          ))}

          {mergeCandidates?.length === 0 && (
            <p className="text-sm text-gray-500">No occupied tables with an open order are available to merge into.</p>
          )}
        </div>

        <div className="flex justify-end gap-2 mt-4">
          <button onClick={onClose}>Cancel</button>
          <button
            onClick={handleMerge}
            disabled={!selectedTableId || mergeTableOrder.isPending}
            className="bg-emerald-600 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {mergeTableOrder.isPending ? 'Merging...' : 'Merge Orders'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

```typescript
// Example trigger inside the order panel
function OrderActions({ order }: { order: Order }) {
  const [showMergeDialog, setShowMergeDialog] = useState(false);

  return (
    <>
      <div className="flex gap-2 mt-4">
        <button
          onClick={() => setShowMergeDialog(true)}
          className="rounded bg-emerald-600 px-4 py-2 text-white"
        >
          Merge Table
        </button>
      </div>

      {showMergeDialog && (
        <MergeDialog
          orderId={order.id}
          currentTableId={order.table}
          onClose={() => setShowMergeDialog(false)}
        />
      )}
    </>
  );
}
```

**Behavior:**
- The source order is merged into the destination table's open order.
- The destination order remains the single order to bill.
- The source table becomes `available` and the destination table stays `occupied`.
- If the same menu item exists on both orders with different price snapshots, backend returns `409` to avoid corrupting totals.
- The response contains the surviving order and destination table, so the UI should redirect to that returned order before billing.

**Edge Cases:**
- Destination table must already have an open order.
- Orders with an already-generated bill cannot be merged.
- After merge, generate the bill from the returned surviving order only.
- Do not offer available, reserved, or cleaning tables in the merge picker.
- If another staff member bills either table while the dialog is open, backend returns `409`; show the error toast and refetch tables.

---

### 7.7 Billing Screen

```typescript
// src/app/staff/billing/[orderId]/page.tsx
'use client';

import { useParams } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { useOrder } from '@/lib/hooks/useOrders';
import { useSystemSettings } from '@/lib/hooks/useSettings';
import { useGenerateBill, usePayBill } from '@/lib/hooks/useBills';
import { formatMoney } from '@/lib/money';

const billSchema = z.object({
  discount_type: z.enum(['none', 'percentage', 'fixed']),
  discount_value: z.number().min(0).optional(),
  payment_method: z.enum(['cash', 'card', 'wallet']),
}).refine(
  (data) => data.discount_type === 'none' || (data.discount_value !== undefined && data.discount_value > 0),
  { message: 'Discount value required', path: ['discount_value'] }
);

type BillForm = z.infer<typeof billSchema>;

export default function BillingPage() {
  const { orderId } = useParams();
  const { data: order } = useOrder(Number(orderId));
  const { data: settings } = useSystemSettings();

  const generateBill = useGenerateBill();
  const payBill = usePayBill();

  const { register, watch, handleSubmit, formState: { errors } } = useForm<BillForm>({
    resolver: zodResolver(billSchema),
    defaultValues: { discount_type: 'none', payment_method: 'cash' },
  });

  const discountType = watch('discount_type');
  const discountValue = watch('discount_value') || 0;

  // Client-side calculation preview (must match backend logic exactly)
  const subtotal = parseFloat(order?.subtotal || '0');
  let discountAmount = 0;
  if (discountType === 'percentage') discountAmount = subtotal * (discountValue / 100);
  if (discountType === 'fixed') discountAmount = Math.min(discountValue, subtotal);
  const taxable = subtotal - discountAmount;
  const taxRate = parseFloat(settings?.tax_rate || '13');
  const taxAmount = taxable * (taxRate / 100);
  const total = taxable + taxAmount;

  const onSubmit = async (data: BillForm) => {
    const bill = await generateBill.mutateAsync({
      order: Number(orderId),
      ...data,
    });
    // Optionally auto-print or show PDF
    window.open(`/api/v1/bills/${bill.id}/pdf/`, '_blank');
  };

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Bill</h1>

      <div className="space-y-2 mb-4">
        {order?.items.map((item) => (
          <div key={item.id} className="flex justify-between">
            <span>{item.quantity}x {item.menu_item.name}</span>
            <span>{formatMoney(parseFloat(item.unit_price) * item.quantity)}</span>
          </div>
        ))}
      </div>

      <div className="border-t pt-4 space-y-2">
        <div className="flex justify-between"><span>Subtotal</span><span>{formatMoney(subtotal)}</span></div>
        {discountAmount > 0 && (
          <div className="flex justify-between text-red-600">
            <span>Discount</span>
            <span>-{formatMoney(discountAmount)}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span>Tax ({taxRate}%)</span>
          <span>{formatMoney(taxAmount)}</span>
        </div>
        <div className="flex justify-between text-xl font-bold">
          <span>Total</span>
          <span>{formatMoney(total)}</span>
        </div>
      </div>

      <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
        <select {...register('discount_type')}>
          <option value="none">No Discount</option>
          <option value="percentage">Percentage</option>
          <option value="fixed">Fixed Amount</option>
        </select>

        {discountType !== 'none' && (
          <input
            type="number"
            step="0.01"
            {...register('discount_value', { valueAsNumber: true })}
            placeholder="Discount value"
          />
        )}
        {errors.discount_value && <span>{errors.discount_value.message}</span>}

        <select {...register('payment_method')}>
          <option value="cash">Cash</option>
          <option value="card">Card</option>
          <option value="wallet">Digital Wallet</option>
        </select>

        <button type="submit" disabled={generateBill.isPending}>
          {generateBill.isPending ? 'Generating...' : 'Generate Bill'}
        </button>
      </form>
    </div>
  );
}
```

**Pay Button (after bill generation)**

```typescript
function PayButton({ billId }: { billId: number }) {
  const payBill = usePayBill();
  return (
    <button
      onClick={() => payBill.mutate(billId)}
      disabled={payBill.isPending}
      className="w-full bg-green-600 text-white py-2 rounded"
    >
      {payBill.isPending ? 'Processing...' : 'Mark as Paid'}
    </button>
  );
}
```

**Edge Cases:**
- Bill calculation preview on frontend **must** match backend logic to avoid surprises. Use the same rounding rules (`ROUND_HALF_UP`).
- If another staff generates a bill for the same order simultaneously, backend returns 409. Show specific error.
- Empty orders cannot be billed — disable the button if `order.items.length === 0`.
- After payment, the table status changes to `available` via WebSocket. The floor map updates automatically.

---

### 7.8 Admin Dashboard

**Daily Report**

```typescript
// lib/hooks/useReports.ts
export function useDailyReport(date?: string) {
  return useQuery({
    queryKey: queryKeys.reports.daily(date),
    queryFn: async () => {
      const { data } = await api.get('/bills/reports/daily/', {
        params: date ? { date } : undefined,
      });
      return data as {
        date: string;
        total_revenue: string;
        revenue_by_payment_method: Record<string, string>;
        total_bills: number;
        total_orders: number;
      };
    },
  });
}
```

**Staff Management**

```typescript
// lib/hooks/useStaff.ts
export function useStaff() {
  return useQuery({
    queryKey: ['admin', 'staff'],
    queryFn: async () => {
      const { data } = await api.get('/admin/staff/');
      return data.results as User[];
    },
  });
}

export function useCreateStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      username: string;
      email: string;
      password: string;
      first_name?: string;
      last_name?: string;
      role: 'admin' | 'staff';
    }) => {
      const { data } = await api.post('/admin/staff/', payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin', 'staff'] });
      toast.success('Staff created');
    },
    onError: (err: AxiosError<ApiError>) => {
      toast.error(err.response?.data?.detail || 'Failed to create staff');
    },
  });
}
```

---

## 8. Error Handling & Edge Cases

### 8.1 HTTP Status → User Action Mapping

| Status | When | Frontend Action |
|---|---|---|
| 400 | Validation failure | Show field errors inline via React Hook Form |
| 401 | Expired/missing token | Trigger silent refresh → retry. If refresh fails, redirect to login |
| 403 | Insufficient role | Show "Access denied" toast. Do NOT retry |
| 404 | Resource not found | Show 404 page or "Not found" toast |
| 409 | Business rule violation | Show specific error toast with `response.data.detail` |
| 500 | Server error | Show generic error toast; log to Sentry/console |

### 8.2 Comprehensive Error Handler

```typescript
// lib/api/handleError.ts
import { AxiosError } from 'axios';
import toast from 'react-hot-toast';

export function handleApiError(error: unknown) {
  if (error instanceof AxiosError) {
    const detail = error.response?.data?.detail;
    const code = error.response?.data?.code;
    const status = error.response?.status;

    switch (status) {
      case 400:
        toast.error(detail || 'Invalid input. Please check your form.');
        break;
      case 401:
        // Handled by interceptor
        break;
      case 403:
        toast.error('You do not have permission for this action.');
        break;
      case 404:
        toast.error('Resource not found.');
        break;
      case 409:
        toast.error(detail || 'Operation not allowed.');
        break;
      case 422:
        toast.error(detail || 'Validation failed.');
        break;
      default:
        toast.error('Something went wrong. Please try again.');
    }

    // Log for debugging
    console.error({ status, code, detail, url: error.config?.url });
    return;
  }

  if (error instanceof Error && error.message === 'Network Error') {
    toast.error('Network error. Check your connection.');
    return;
  }

  toast.error('An unexpected error occurred.');
}
```

### 8.3 Edge Case Checklist

| Scenario | Mitigation |
|---|---|
| **Token expires mid-request** | Axios interceptor queues requests, refreshes token, retries all |
| **Refresh token expired** | Clear auth state, redirect to `/login` |
| **WebSocket disconnect** | Auto-reconnect with exponential backoff (max 10 attempts). Fallback to 30s polling |
| **Staff double-clicks "Create Order"** | Disable button during `isPending`. Backend 409 if table already occupied |
| **Adding item while another staff deletes the menu item** | Backend validates `menu_item` is available & not soft-deleted. Returns 400 if invalid |
| **Switching table that just got occupied** | Backend `SELECT FOR UPDATE` guarantees atomicity. Returns 409 if not available |
| **Billing an empty order** | Frontend disables button. Backend returns 409 if no items |
| **Concurrent bill generation** | Backend locks order row. Returns 409 if bill already exists |
| **Image upload fails** | Show upload progress. On failure, allow retry without re-entering form data |
| **Staff tries to access `/admin`** | Next.js middleware redirects to `/staff/floor` |
| **Admin tries to access `/staff`** | Next.js middleware redirects to `/admin` |
| **Page refresh loses in-memory token** | For production: use httpOnly cookie strategy. For dev: accept re-login |
| **Order item quantity set to 0** | Frontend: on blur, if `quantity < 1`, trigger delete mutation instead of update |
| **Discount > subtotal (fixed)** | Backend caps discount at subtotal. Frontend preview should match |
| **Menu item price changed after order opened** | Backend snapshots `unit_price` at add time. Historical orders are unaffected |
| **Soft-deleted item in open order** | Display normally (name preserved). Show "[UNAVAILABLE]" badge if needed |

---

## 9. Testing Strategy

### 9.1 Unit Tests (Jest + React Testing Library)

```typescript
// __tests__/components/FloorMap.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { FloorMap } from '@/components/tables/FloorMap';

const mockTables = [
  { id: 1, table_number: 'T1', capacity: 4, status: 'available', active_order_id: null },
  { id: 2, table_number: 'T2', capacity: 2, status: 'occupied', active_order_id: 5 },
];

describe('FloorMap', () => {
  it('renders all tables', () => {
    render(<FloorMap tables={mockTables} />);
    expect(screen.getByText('T1')).toBeInTheDocument();
    expect(screen.getByText('T2')).toBeInTheDocument();
  });

  it('shows occupied status in red', () => {
    render(<FloorMap tables={mockTables} />);
    const t2 = screen.getByText('T2').closest('button');
    expect(t2).toHaveClass('bg-red-500');
  });

  it('disables create order button while pending', () => {
    render(<FloorMap tables={mockTables} isCreatingOrder={true} />);
    const t1 = screen.getByText('T1').closest('button');
    expect(t1).toBeDisabled();
  });
});
```

### 9.2 MSW (Mock Service Worker)

```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/v1/tables/', () => {
    return HttpResponse.json([
      { id: 1, table_number: 'T1', capacity: 4, status: 'available', active_order_id: null },
    ]);
  }),

  http.post('/api/v1/orders/', async ({ request }) => {
    const body = (await request.json()) as { table: number };
    if (body.table === 99) {
      return HttpResponse.json({ detail: 'Table is not available.' }, { status: 409 });
    }
    return HttpResponse.json({ id: 1, table: body.table, status: 'open', items: [] });
  }),
];
```

### 9.3 E2E (Playwright)

```typescript
// e2e/order-flow.spec.ts
import { test, expect } from '@playwright/test';

test('full order flow', async ({ page }) => {
  // Login
  await page.goto('/login');
  await page.fill('input[name="username"]', 'staff1');
  await page.fill('input[name="password"]', 'password');
  await page.click('button[type="submit"]');

  // Open table
  await page.waitForURL('/staff/floor');
  await page.click('text=T1');

  // Add item
  await page.waitForURL(/\/staff\/orders\/\d+/);
  await page.click('text=Burger');

  // Generate bill
  await page.click('text=Bill');
  await page.selectOption('select[name="payment_method"]', 'cash');
  await page.click('text=Generate Bill');

  // Pay
  await page.click('text=Mark as Paid');
  await expect(page.locator('text=Paid')).toBeVisible();
});
```

---

## 10. Performance & Security

### 10.1 Performance Checklist

- [ ] Use `select_related` / `prefetch_related` equivalents via TanStack Query (already handled by backend)
- [ ] `staleTime: 30_000` on tables to reduce API calls (WebSocket is source of truth)
- [ ] `refetchOnWindowFocus: false` for floor map and order panels
- [ ] Lazy load heavy components (reports, charts) with `next/dynamic`
- [ ] Image optimization: use `next/image` with `width/height` to prevent CLS
- [ ] Debounce search inputs in menu filter (300ms)
- [ ] Use `React.memo` for TableCard components to prevent re-renders on floor map

### 10.2 Security Checklist

- [ ] `accessToken` stored in memory only (Zustand without persist)
- [ ] `refreshToken` in `httpOnly; Secure; SameSite=Strict` cookie
- [ ] XSS: No `dangerouslySetInnerHTML`. All user input escaped by React
- [ ] CSRF: Not applicable for JWT-based API, but cookies must be `SameSite=Strict`
- [ ] CORS whitelist enforced on backend
- [ ] File upload: Restrict to images only (`accept="image/*"`), max 5MB
- [ ] Role guard in middleware + backend double-checks on every write endpoint
- [ ] No sensitive data in URL params (order IDs are okay, but never tokens)
- [ ] PDF bills served inline — ensure filename is sanitized

---

## Appendix A: Zod Schemas Reference

```typescript
// lib/schemas/index.ts
import { z } from 'zod';

export const loginSchema = z.object({
  username: z.string().min(1),
  password: z.string().min(1),
});

export const menuItemSchema = z.object({
  name: z.string().min(1).max(200),
  description: z.string().max(1000).optional(),
  price: z.number().positive().multipleOf(0.01),
  category_id: z.number(),
  is_available: z.boolean().default(true),
});

export const sendToStationSchema = z.object({
  station: z.enum(['kitchen', 'bar']),
});

export const tableSchema = z.object({
  table_number: z.string().min(1).max(20),
  capacity: z.number().int().positive().max(100),
});

export const orderItemSchema = z.object({
  menu_item: z.number(),
  quantity: z.number().int().positive().max(99),
  notes: z.string().max(255).optional(),
});

export const switchTableSchema = z.object({
  to_table: z.number(),
});

export const mergeTableSchema = z.object({
  to_table: z.number(),
});

export const billSchema = z.object({
  discount_type: z.enum(['none', 'percentage', 'fixed']),
  discount_value: z.number().min(0).optional(),
  payment_method: z.enum(['cash', 'card', 'wallet']),
}).refine(
  (data) => data.discount_type === 'none' || (data.discount_value !== undefined && data.discount_value > 0),
  { message: 'Discount value required', path: ['discount_value'] }
);

export const staffSchema = z.object({
  username: z.string().min(3).max(150),
  email: z.string().email(),
  password: z.string().min(6),
  first_name: z.string().optional(),
  last_name: z.string().optional(),
  role: z.enum(['admin', 'staff']),
});

export const categorySchema = z.object({
  name: z.string().min(1).max(100),
  display_order: z.number().int().min(0).default(0),
  station: z.enum(['kitchen', 'bar']).default('kitchen'),
});

export const systemSettingsSchema = z.object({
  tax_rate: z.number().min(0).max(100).multipleOf(0.01),
  restaurant_name: z.string().min(1).max(200),
  address: z.string().optional(),
  allow_staff_discount: z.boolean(),
});
```

---

## Appendix B: API Endpoint Quick Reference

| Method | Endpoint | Auth | Body | Notes |
|---|---|---|---|---|
| POST | `/auth/login/` | Public | `{username, password}` | Returns `{access, refresh, user}` |
| POST | `/auth/token/refresh/` | Public | `{refresh}` | Returns `{access}` |
| POST | `/auth/logout/` | Any | `{refresh}` | Blacklists token |
| GET | `/auth/me/` | Any | — | Current user |
| GET/POST | `/menu/categories/` | Any / Admin | `{name, display_order}` | |
| GET/POST | `/menu/items/` | Any / Admin | `{name, price, category_id...}` | Multipart for image |
| GET/PUT/PATCH/DELETE | `/menu/items/{id}/` | Any / Admin | — | DELETE = soft delete |
| GET/POST | `/tables/` | Any / Admin | `{table_number, capacity}` | |
| PATCH/DELETE | `/tables/{id}/` | Any / Admin | `{status}` | Staff can only PATCH status |
| GET/POST | `/orders/` | Admin/Staff | `{table: id}` | Auto-sets table→occupied |
| GET | `/orders/{id}/` | Admin/Staff | — | |
| POST | `/orders/{id}/items/` | Admin/Staff | `{menu_item, quantity, notes}` | Duplicates increment qty |
| PATCH/DELETE | `/orders/{id}/items/{item_id}/` | Admin/Staff | `{quantity}` | |
| POST | `/orders/{id}/switch-table/` | Admin/Staff | `{to_table: id}` | Atomic |
| POST | `/orders/{id}/merge-table/` | Admin/Staff | `{to_table: id}` | Merges this open order into the destination table's open order |
| POST | `/orders/{id}/cancel/` | Admin | — | Requires open + no bill |
| POST | `/orders/{id}/send-to-station/` | Admin/Staff | `{station: 'kitchen' \| 'bar'}` | Returns PDF ticket inline |
| GET | `/orders/{id}/station-logs/` | Admin/Staff | — | Ticket history for order |
| GET | `/orders/{id}/station-pdf/?station=...` | Admin/Staff | — | Re-print latest ticket |
| POST | `/bills/` | Admin/Staff | `{order, discount_type...}` | Returns bill with totals |
| GET | `/bills/{id}/` | Admin/Staff | — | |
| POST | `/bills/{id}/pay/` | Admin/Staff | — | Marks paid |
| GET | `/bills/{id}/pdf/` | Admin/Staff | — | `application/pdf` inline |
| GET/PUT | `/bills/settings/` | Admin | `{tax_rate, restaurant_name...}` | Singleton |
| GET | `/bills/reports/daily/?date=YYYY-MM-DD` | Admin | — | |
| GET | `/bills/reports/items/?from=...&to=...` | Admin | — | |
| POST | `/tables/{id}/request-bill/` | Staff | — | Notifies admins that a bill should be issued for the table |
| GET/POST | `/admin/staff/` | Admin | `{username, email, password, role}` | DELETE = deactivate |
| WS | `/ws/tables/?token=<jwt>` | Any | — | Real-time table status updates; admin clients also receive `billing.bill_request` events |
