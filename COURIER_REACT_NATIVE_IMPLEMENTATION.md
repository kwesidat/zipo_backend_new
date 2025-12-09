# Courier Service Implementation Guide for React Native App

This guide provides a comprehensive overview of implementing the courier delivery system in your React Native application.

## 📋 Table of Contents

1. [Overview](#overview)
2. [Backend API Endpoints](#backend-api-endpoints)
3. [React Native Implementation](#react-native-implementation)
4. [Screen Designs](#screen-designs)
5. [State Management](#state-management)
6. [Real-time Updates](#real-time-updates)

---

## Overview

The courier service allows:
- **Couriers** to view and accept delivery orders where `useCourierService = true` and `courierServiceStatus = PENDING`
- **Couriers** to track their earnings, deliveries, and dashboard statistics
- **Customers** to track their delivery status in real-time

---

## Backend API Endpoints

### 1. Get Available Deliveries (For Couriers)

**Endpoint:** `GET /api/delivery/available`

**Description:** Fetches all deliveries that have:
- `useCourierService = true` (from Order table)
- `courierServiceStatus = PENDING` (not yet accepted)
- `status = PENDING` (in Delivery table)

**Headers:**
```javascript
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `page` (optional, default: 1)
- `page_size` (optional, default: 20)
- `priority` (optional: STANDARD, EXPRESS, URGENT)

**Response:**
```json
{
  "deliveries": [
    {
      "id": "delivery-uuid",
      "order_id": "order-uuid",
      "pickup_address": {
        "address": "123 Main St",
        "city": "Accra",
        "country": "Ghana",
        "latitude": 5.6037,
        "longitude": -0.1870
      },
      "delivery_address": {
        "address": "456 Oak Ave",
        "city": "Accra",
        "country": "Ghana",
        "latitude": 5.6100,
        "longitude": -0.1950
      },
      "pickup_contact_name": "John Doe",
      "pickup_contact_phone": "0201234567",
      "delivery_contact_name": "Jane Smith",
      "delivery_contact_phone": "0209876543",
      "delivery_fee": 50.00,
      "courier_fee": 35.00,
      "distance_km": 5.2,
      "priority": "STANDARD",
      "scheduled_date": "2025-12-10T14:00:00Z",
      "notes": "Handle with care",
      "created_at": "2025-12-09T10:30:00Z"
    }
  ],
  "total_count": 25,
  "page": 1,
  "page_size": 20,
  "total_pages": 2,
  "has_next": true,
  "has_previous": false
}
```

---

### 2. Accept Delivery

**Endpoint:** `POST /api/delivery/accept`

**Description:** Courier accepts a delivery order. This:
- Updates `Delivery.status` to `ACCEPTED`
- Updates `Order.courierServiceStatus` to `ACCEPTED`
- Assigns courier to the delivery

**Headers:**
```javascript
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "delivery_id": "delivery-uuid",
  "estimated_pickup_time": "2025-12-09T15:00:00Z",
  "estimated_delivery_time": "2025-12-09T16:30:00Z"
}
```

**Response:**
```json
{
  "id": "delivery-uuid",
  "order_id": "order-uuid",
  "courier_id": "courier-uuid",
  "status": "ACCEPTED",
  "courier_fee": 35.00,
  ...
}
```

---

### 3. Get Courier Dashboard

**Endpoint:** `GET /api/delivery/courier/dashboard`

**Description:** Returns courier dashboard statistics including total earnings, completed deliveries, and more.

**Headers:**
```javascript
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "courier_info": {
    "courier_id": "courier-uuid",
    "courier_code": "COU-001",
    "vehicle_type": "MOTORCYCLE",
    "rating": 4.5,
    "is_available": true,
    "is_verified": true
  },
  "statistics": {
    "total_deliveries": 45,
    "completed_deliveries": 40,
    "pending_deliveries": 2,
    "active_deliveries": 3,
    "total_earnings": 1400.00,
    "available_balance": 350.00,
    "average_rating": 4.5
  },
  "status_breakdown": {
    "pending": 2,
    "active": 3,
    "completed": 40,
    "cancelled": 0,
    "failed": 0
  },
  "recent_deliveries": [
    {
      "id": "delivery-uuid",
      "order_id": "order-uuid",
      "delivery_address": {...},
      "delivery_fee": 50.00,
      "courier_fee": 35.00,
      "status": "DELIVERED",
      "priority": "STANDARD",
      "created_at": "2025-12-09T10:00:00Z",
      "updated_at": "2025-12-09T12:30:00Z"
    }
  ]
}
```

---

### 4. Get Courier's Deliveries

**Endpoint:** `GET /api/delivery/courier/my-deliveries`

**Description:** Get all deliveries assigned to the current courier.

**Headers:**
```javascript
Authorization: Bearer {access_token}
```

**Query Parameters:**
- `page` (optional, default: 1)
- `page_size` (optional, default: 20)
- `status` (optional: PENDING, ACCEPTED, PICKED_UP, IN_TRANSIT, DELIVERED, etc.)

**Response:**
```json
{
  "deliveries": [...],
  "total_count": 45,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "has_next": true,
  "has_previous": false
}
```

---

### 5. Update Delivery Status

**Endpoint:** `PUT /api/delivery/{delivery_id}/status`

**Description:** Update delivery status (PICKED_UP, IN_TRANSIT, DELIVERED, etc.)

**Headers:**
```javascript
Authorization: Bearer {access_token}
```

**Request Body:**
```json
{
  "status": "PICKED_UP",
  "notes": "Package picked up successfully",
  "location": {
    "latitude": 5.6037,
    "longitude": -0.1870
  },
  "proof_of_delivery_urls": [],
  "customer_signature": null
}
```

---

## React Native Implementation

### Project Structure

```
src/
├── screens/
│   ├── courier/
│   │   ├── CourierDashboardScreen.tsx
│   │   ├── AvailableDeliveriesScreen.tsx
│   │   ├── MyDeliveriesScreen.tsx
│   │   ├── DeliveryDetailScreen.tsx
│   │   └── DeliveryTrackingScreen.tsx
├── services/
│   ├── api/
│   │   └── deliveryService.ts
├── store/
│   ├── slices/
│   │   └── courierSlice.ts
├── types/
│   └── delivery.types.ts
├── components/
│   ├── courier/
│   │   ├── DeliveryCard.tsx
│   │   ├── DashboardStats.tsx
│   │   └── DeliveryStatusBadge.tsx
└── navigation/
    └── CourierNavigator.tsx
```

---

### 1. Type Definitions

**File:** `src/types/delivery.types.ts`

```typescript
export enum DeliveryStatus {
  PENDING = "PENDING",
  ACCEPTED = "ACCEPTED",
  PICKED_UP = "PICKED_UP",
  IN_TRANSIT = "IN_TRANSIT",
  DELIVERED = "DELIVERED",
  CANCELLED = "CANCELLED",
  FAILED = "FAILED"
}

export enum DeliveryPriority {
  STANDARD = "STANDARD",
  EXPRESS = "EXPRESS",
  URGENT = "URGENT"
}

export interface DeliveryAddress {
  address: string;
  city: string;
  country: string;
  latitude?: number;
  longitude?: number;
  additional_info?: string;
}

export interface AvailableDelivery {
  id: string;
  order_id: string;
  pickup_address: DeliveryAddress;
  delivery_address: DeliveryAddress;
  pickup_contact_name: string;
  pickup_contact_phone: string;
  delivery_contact_name: string;
  delivery_contact_phone: string;
  delivery_fee: number;
  courier_fee: number;
  distance_km?: number;
  priority: DeliveryPriority;
  scheduled_date?: string;
  notes?: string;
  created_at: string;
}

export interface Delivery extends AvailableDelivery {
  courier_id?: string;
  status: DeliveryStatus;
  estimated_pickup_time?: string;
  estimated_delivery_time?: string;
  actual_pickup_time?: string;
  actual_delivery_time?: string;
  courier_notes?: string;
  proof_of_delivery?: string[];
  customer_signature?: string;
  rating?: number;
  review?: string;
  updated_at: string;
}

export interface CourierDashboard {
  courier_info: {
    courier_id: string;
    courier_code: string;
    vehicle_type: string;
    rating: number;
    is_available: boolean;
    is_verified: boolean;
  };
  statistics: {
    total_deliveries: number;
    completed_deliveries: number;
    pending_deliveries: number;
    active_deliveries: number;
    total_earnings: number;
    available_balance: number;
    average_rating: number;
  };
  status_breakdown: {
    pending: number;
    active: number;
    completed: number;
    cancelled: number;
    failed: number;
  };
  recent_deliveries: Delivery[];
}
```

---

### 2. API Service

**File:** `src/services/api/deliveryService.ts`

```typescript
import axios from 'axios';
import { AvailableDelivery, Delivery, CourierDashboard, DeliveryStatus } from '../../types/delivery.types';
import { getAuthToken } from '../authService';

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8080';

const api = axios.create({
  baseURL: `${API_BASE_URL}/api/delivery`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use(async (config) => {
  const token = await getAuthToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const deliveryService = {
  // Get available deliveries for couriers
  getAvailableDeliveries: async (
    page: number = 1,
    pageSize: number = 20,
    priority?: string
  ) => {
    const params = { page, page_size: pageSize, ...(priority && { priority }) };
    const response = await api.get<{
      deliveries: AvailableDelivery[];
      total_count: number;
      page: number;
      page_size: number;
      total_pages: number;
      has_next: boolean;
      has_previous: boolean;
    }>('/available', { params });
    return response.data;
  },

  // Accept a delivery
  acceptDelivery: async (
    deliveryId: string,
    estimatedPickupTime?: string,
    estimatedDeliveryTime?: string
  ) => {
    const response = await api.post<Delivery>('/accept', {
      delivery_id: deliveryId,
      estimated_pickup_time: estimatedPickupTime,
      estimated_delivery_time: estimatedDeliveryTime,
    });
    return response.data;
  },

  // Get courier dashboard
  getCourierDashboard: async () => {
    const response = await api.get<CourierDashboard>('/courier/dashboard');
    return response.data;
  },

  // Get courier's deliveries
  getCourierDeliveries: async (
    page: number = 1,
    pageSize: number = 20,
    status?: DeliveryStatus
  ) => {
    const params = { page, page_size: pageSize, ...(status && { status }) };
    const response = await api.get<{
      deliveries: Delivery[];
      total_count: number;
      page: number;
      page_size: number;
      total_pages: number;
      has_next: boolean;
      has_previous: boolean;
    }>('/courier/my-deliveries', { params });
    return response.data;
  },

  // Get delivery details
  getDeliveryById: async (deliveryId: string) => {
    const response = await api.get<Delivery>(`/${deliveryId}`);
    return response.data;
  },

  // Update delivery status
  updateDeliveryStatus: async (
    deliveryId: string,
    status: DeliveryStatus,
    notes?: string,
    location?: { latitude: number; longitude: number },
    proofOfDeliveryUrls?: string[],
    customerSignature?: string
  ) => {
    const response = await api.put<Delivery>(`/${deliveryId}/status`, {
      status,
      notes,
      location,
      proof_of_delivery_urls: proofOfDeliveryUrls,
      customer_signature: customerSignature,
    });
    return response.data;
  },
};
```

---

### 3. Redux Slice (State Management)

**File:** `src/store/slices/courierSlice.ts`

```typescript
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import { deliveryService } from '../../services/api/deliveryService';
import { AvailableDelivery, Delivery, CourierDashboard } from '../../types/delivery.types';

interface CourierState {
  dashboard: CourierDashboard | null;
  availableDeliveries: AvailableDelivery[];
  myDeliveries: Delivery[];
  selectedDelivery: Delivery | null;
  loading: boolean;
  error: string | null;
  pagination: {
    page: number;
    pageSize: number;
    totalPages: number;
    hasNext: boolean;
  };
}

const initialState: CourierState = {
  dashboard: null,
  availableDeliveries: [],
  myDeliveries: [],
  selectedDelivery: null,
  loading: false,
  error: null,
  pagination: {
    page: 1,
    pageSize: 20,
    totalPages: 1,
    hasNext: false,
  },
};

// Async thunks
export const fetchDashboard = createAsyncThunk(
  'courier/fetchDashboard',
  async () => {
    const data = await deliveryService.getCourierDashboard();
    return data;
  }
);

export const fetchAvailableDeliveries = createAsyncThunk(
  'courier/fetchAvailableDeliveries',
  async ({ page, pageSize, priority }: {
    page?: number;
    pageSize?: number;
    priority?: string
  }) => {
    const data = await deliveryService.getAvailableDeliveries(page, pageSize, priority);
    return data;
  }
);

export const fetchMyDeliveries = createAsyncThunk(
  'courier/fetchMyDeliveries',
  async ({ page, pageSize, status }: {
    page?: number;
    pageSize?: number;
    status?: string
  }) => {
    const data = await deliveryService.getCourierDeliveries(page, pageSize, status as any);
    return data;
  }
);

export const acceptDelivery = createAsyncThunk(
  'courier/acceptDelivery',
  async ({
    deliveryId,
    estimatedPickupTime,
    estimatedDeliveryTime
  }: {
    deliveryId: string;
    estimatedPickupTime?: string;
    estimatedDeliveryTime?: string
  }) => {
    const data = await deliveryService.acceptDelivery(
      deliveryId,
      estimatedPickupTime,
      estimatedDeliveryTime
    );
    return data;
  }
);

const courierSlice = createSlice({
  name: 'courier',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
    setSelectedDelivery: (state, action: PayloadAction<Delivery | null>) => {
      state.selectedDelivery = action.payload;
    },
  },
  extraReducers: (builder) => {
    builder
      // Dashboard
      .addCase(fetchDashboard.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchDashboard.fulfilled, (state, action) => {
        state.loading = false;
        state.dashboard = action.payload;
      })
      .addCase(fetchDashboard.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch dashboard';
      })

      // Available Deliveries
      .addCase(fetchAvailableDeliveries.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchAvailableDeliveries.fulfilled, (state, action) => {
        state.loading = false;
        state.availableDeliveries = action.payload.deliveries;
        state.pagination = {
          page: action.payload.page,
          pageSize: action.payload.page_size,
          totalPages: action.payload.total_pages,
          hasNext: action.payload.has_next,
        };
      })
      .addCase(fetchAvailableDeliveries.rejected, (state, action) => {
        state.loading = false;
        state.error = action.error.message || 'Failed to fetch deliveries';
      })

      // My Deliveries
      .addCase(fetchMyDeliveries.fulfilled, (state, action) => {
        state.loading = false;
        state.myDeliveries = action.payload.deliveries;
      })

      // Accept Delivery
      .addCase(acceptDelivery.fulfilled, (state, action) => {
        state.loading = false;
        // Remove from available deliveries
        state.availableDeliveries = state.availableDeliveries.filter(
          (d) => d.id !== action.payload.id
        );
        // Add to my deliveries
        state.myDeliveries.unshift(action.payload);
      });
  },
});

export const { clearError, setSelectedDelivery } = courierSlice.actions;
export default courierSlice.reducer;
```

---

### 4. Dashboard Screen

**File:** `src/screens/courier/CourierDashboardScreen.tsx`

```typescript
import React, { useEffect } from 'react';
import { View, Text, StyleSheet, ScrollView, RefreshControl, TouchableOpacity } from 'react-native';
import { useDispatch, useSelector } from 'react-redux';
import { fetchDashboard } from '../../store/slices/courierSlice';
import { AppDispatch, RootState } from '../../store';
import { Ionicons } from '@expo/vector-icons';

export const CourierDashboardScreen = ({ navigation }) => {
  const dispatch = useDispatch<AppDispatch>();
  const { dashboard, loading } = useSelector((state: RootState) => state.courier);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = () => {
    dispatch(fetchDashboard());
  };

  if (!dashboard) {
    return (
      <View style={styles.container}>
        <Text>Loading...</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={loading} onRefresh={loadDashboard} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.welcomeText}>Welcome back,</Text>
        <Text style={styles.courierCode}>{dashboard.courier_info.courier_code}</Text>
        <View style={styles.ratingContainer}>
          <Ionicons name="star" size={20} color="#FFD700" />
          <Text style={styles.ratingText}>{dashboard.courier_info.rating.toFixed(1)}</Text>
        </View>
      </View>

      {/* Earnings Card */}
      <View style={styles.earningsCard}>
        <Text style={styles.cardTitle}>Total Earnings</Text>
        <Text style={styles.earningsAmount}>
          GHS {dashboard.statistics.total_earnings.toFixed(2)}
        </Text>
        <View style={styles.balanceRow}>
          <Text style={styles.balanceLabel}>Available Balance:</Text>
          <Text style={styles.balanceAmount}>
            GHS {dashboard.statistics.available_balance.toFixed(2)}
          </Text>
        </View>
      </View>

      {/* Statistics Grid */}
      <View style={styles.statsGrid}>
        <View style={styles.statCard}>
          <Ionicons name="checkmark-circle" size={32} color="#4CAF50" />
          <Text style={styles.statNumber}>{dashboard.statistics.completed_deliveries}</Text>
          <Text style={styles.statLabel}>Completed</Text>
        </View>

        <View style={styles.statCard}>
          <Ionicons name="time" size={32} color="#FF9800" />
          <Text style={styles.statNumber}>{dashboard.statistics.active_deliveries}</Text>
          <Text style={styles.statLabel}>Active</Text>
        </View>

        <View style={styles.statCard}>
          <Ionicons name="list" size={32} color="#2196F3" />
          <Text style={styles.statNumber}>{dashboard.statistics.total_deliveries}</Text>
          <Text style={styles.statLabel}>Total</Text>
        </View>

        <View style={styles.statCard}>
          <Ionicons name="hourglass" size={32} color="#9C27B0" />
          <Text style={styles.statNumber}>{dashboard.statistics.pending_deliveries}</Text>
          <Text style={styles.statLabel}>Pending</Text>
        </View>
      </View>

      {/* Quick Actions */}
      <View style={styles.quickActions}>
        <TouchableOpacity
          style={styles.actionButton}
          onPress={() => navigation.navigate('AvailableDeliveries')}
        >
          <Ionicons name="search" size={24} color="#fff" />
          <Text style={styles.actionButtonText}>Find Deliveries</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionButton, styles.actionButtonSecondary]}
          onPress={() => navigation.navigate('MyDeliveries')}
        >
          <Ionicons name="list-circle" size={24} color="#2196F3" />
          <Text style={[styles.actionButtonText, styles.actionButtonTextSecondary]}>
            My Deliveries
          </Text>
        </TouchableOpacity>
      </View>

      {/* Recent Deliveries */}
      <View style={styles.recentSection}>
        <Text style={styles.sectionTitle}>Recent Deliveries</Text>
        {dashboard.recent_deliveries.map((delivery) => (
          <TouchableOpacity
            key={delivery.id}
            style={styles.deliveryItem}
            onPress={() => navigation.navigate('DeliveryDetail', { deliveryId: delivery.id })}
          >
            <View style={styles.deliveryInfo}>
              <Text style={styles.deliveryAddress}>
                {delivery.delivery_address.city}
              </Text>
              <Text style={styles.deliveryDate}>
                {new Date(delivery.updated_at).toLocaleDateString()}
              </Text>
            </View>
            <View style={styles.deliveryRight}>
              <Text style={styles.deliveryFee}>GHS {delivery.courier_fee.toFixed(2)}</Text>
              <View style={[styles.statusBadge, getStatusColor(delivery.status)]}>
                <Text style={styles.statusText}>{delivery.status}</Text>
              </View>
            </View>
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  );
};

const getStatusColor = (status: string) => {
  switch (status) {
    case 'DELIVERED':
      return { backgroundColor: '#4CAF50' };
    case 'IN_TRANSIT':
      return { backgroundColor: '#2196F3' };
    case 'PICKED_UP':
      return { backgroundColor: '#FF9800' };
    default:
      return { backgroundColor: '#9E9E9E' };
  }
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    backgroundColor: '#2196F3',
    padding: 20,
    paddingTop: 40,
  },
  welcomeText: {
    color: '#fff',
    fontSize: 16,
  },
  courierCode: {
    color: '#fff',
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 5,
  },
  ratingContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
  },
  ratingText: {
    color: '#fff',
    fontSize: 18,
    marginLeft: 5,
    fontWeight: '600',
  },
  earningsCard: {
    backgroundColor: '#fff',
    margin: 15,
    padding: 20,
    borderRadius: 10,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardTitle: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
  },
  earningsAmount: {
    fontSize: 32,
    fontWeight: 'bold',
    color: '#2196F3',
    marginBottom: 10,
  },
  balanceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 10,
  },
  balanceLabel: {
    fontSize: 14,
    color: '#666',
  },
  balanceAmount: {
    fontSize: 16,
    fontWeight: '600',
    color: '#4CAF50',
  },
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    paddingHorizontal: 10,
  },
  statCard: {
    width: '48%',
    backgroundColor: '#fff',
    margin: 5,
    padding: 15,
    borderRadius: 10,
    alignItems: 'center',
    elevation: 2,
  },
  statNumber: {
    fontSize: 24,
    fontWeight: 'bold',
    marginTop: 10,
  },
  statLabel: {
    fontSize: 12,
    color: '#666',
    marginTop: 5,
  },
  quickActions: {
    padding: 15,
    gap: 10,
  },
  actionButton: {
    backgroundColor: '#2196F3',
    padding: 15,
    borderRadius: 10,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  actionButtonSecondary: {
    backgroundColor: '#fff',
    borderWidth: 2,
    borderColor: '#2196F3',
  },
  actionButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  actionButtonTextSecondary: {
    color: '#2196F3',
  },
  recentSection: {
    padding: 15,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 15,
  },
  deliveryItem: {
    backgroundColor: '#fff',
    padding: 15,
    borderRadius: 10,
    marginBottom: 10,
    flexDirection: 'row',
    justifyContent: 'space-between',
    elevation: 2,
  },
  deliveryInfo: {
    flex: 1,
  },
  deliveryAddress: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 5,
  },
  deliveryDate: {
    fontSize: 12,
    color: '#666',
  },
  deliveryRight: {
    alignItems: 'flex-end',
  },
  deliveryFee: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#4CAF50',
    marginBottom: 5,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 12,
  },
  statusText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: '600',
  },
});
```

---

### 5. Available Deliveries Screen

**File:** `src/screens/courier/AvailableDeliveriesScreen.tsx`

```typescript
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { useDispatch, useSelector } from 'react-redux';
import { fetchAvailableDeliveries, acceptDelivery } from '../../store/slices/courierSlice';
import { AppDispatch, RootState } from '../../store';
import { Ionicons } from '@expo/vector-icons';
import { AvailableDelivery, DeliveryPriority } from '../../types/delivery.types';

export const AvailableDeliveriesScreen = ({ navigation }) => {
  const dispatch = useDispatch<AppDispatch>();
  const { availableDeliveries, loading, pagination } = useSelector(
    (state: RootState) => state.courier
  );
  const [selectedPriority, setSelectedPriority] = useState<string | undefined>();
  const [accepting, setAccepting] = useState<string | null>(null);

  useEffect(() => {
    loadDeliveries();
  }, [selectedPriority]);

  const loadDeliveries = () => {
    dispatch(fetchAvailableDeliveries({
      page: 1,
      pageSize: 20,
      priority: selectedPriority
    }));
  };

  const handleAcceptDelivery = async (deliveryId: string) => {
    setAccepting(deliveryId);
    try {
      await dispatch(acceptDelivery({ deliveryId })).unwrap();
      // Navigate to delivery detail or my deliveries
      navigation.navigate('MyDeliveries');
    } catch (error) {
      console.error('Failed to accept delivery:', error);
    } finally {
      setAccepting(null);
    }
  };

  const renderDeliveryCard = ({ item }: { item: AvailableDelivery }) => (
    <View style={styles.deliveryCard}>
      {/* Priority Badge */}
      <View style={[styles.priorityBadge, getPriorityColor(item.priority)]}>
        <Text style={styles.priorityText}>{item.priority}</Text>
      </View>

      {/* Addresses */}
      <View style={styles.addressSection}>
        <View style={styles.addressRow}>
          <Ionicons name="location" size={20} color="#FF9800" />
          <View style={styles.addressText}>
            <Text style={styles.addressLabel}>Pickup</Text>
            <Text style={styles.addressValue}>{item.pickup_address.address}</Text>
            <Text style={styles.addressCity}>{item.pickup_address.city}</Text>
          </View>
        </View>

        <Ionicons name="arrow-down" size={20} color="#999" style={styles.arrowIcon} />

        <View style={styles.addressRow}>
          <Ionicons name="location" size={20} color="#4CAF50" />
          <View style={styles.addressText}>
            <Text style={styles.addressLabel}>Delivery</Text>
            <Text style={styles.addressValue}>{item.delivery_address.address}</Text>
            <Text style={styles.addressCity}>{item.delivery_address.city}</Text>
          </View>
        </View>
      </View>

      {/* Details */}
      <View style={styles.detailsSection}>
        <View style={styles.detailRow}>
          <Ionicons name="cash" size={18} color="#4CAF50" />
          <Text style={styles.detailLabel}>Your Earnings:</Text>
          <Text style={styles.detailValue}>GHS {item.courier_fee.toFixed(2)}</Text>
        </View>

        {item.distance_km && (
          <View style={styles.detailRow}>
            <Ionicons name="navigate" size={18} color="#2196F3" />
            <Text style={styles.detailLabel}>Distance:</Text>
            <Text style={styles.detailValue}>{item.distance_km.toFixed(1)} km</Text>
          </View>
        )}

        {item.notes && (
          <View style={styles.notesRow}>
            <Ionicons name="information-circle" size={18} color="#FF9800" />
            <Text style={styles.notesText}>{item.notes}</Text>
          </View>
        )}
      </View>

      {/* Accept Button */}
      <TouchableOpacity
        style={[
          styles.acceptButton,
          accepting === item.id && styles.acceptButtonDisabled,
        ]}
        onPress={() => handleAcceptDelivery(item.id)}
        disabled={accepting === item.id}
      >
        {accepting === item.id ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <>
            <Ionicons name="checkmark-circle" size={24} color="#fff" />
            <Text style={styles.acceptButtonText}>Accept Delivery</Text>
          </>
        )}
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      {/* Priority Filter */}
      <View style={styles.filterContainer}>
        <TouchableOpacity
          style={[styles.filterButton, !selectedPriority && styles.filterButtonActive]}
          onPress={() => setSelectedPriority(undefined)}
        >
          <Text style={styles.filterButtonText}>All</Text>
        </TouchableOpacity>

        {Object.values(DeliveryPriority).map((priority) => (
          <TouchableOpacity
            key={priority}
            style={[
              styles.filterButton,
              selectedPriority === priority && styles.filterButtonActive,
            ]}
            onPress={() => setSelectedPriority(priority)}
          >
            <Text style={styles.filterButtonText}>{priority}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Deliveries List */}
      <FlatList
        data={availableDeliveries}
        renderItem={renderDeliveryCard}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={loading} onRefresh={loadDeliveries} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="inbox" size={64} color="#ccc" />
            <Text style={styles.emptyText}>No deliveries available</Text>
          </View>
        }
      />
    </View>
  );
};

const getPriorityColor = (priority: DeliveryPriority) => {
  switch (priority) {
    case DeliveryPriority.URGENT:
      return { backgroundColor: '#f44336' };
    case DeliveryPriority.EXPRESS:
      return { backgroundColor: '#FF9800' };
    default:
      return { backgroundColor: '#2196F3' };
  }
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  filterContainer: {
    flexDirection: 'row',
    padding: 10,
    backgroundColor: '#fff',
    gap: 10,
  },
  filterButton: {
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: '#f0f0f0',
  },
  filterButtonActive: {
    backgroundColor: '#2196F3',
  },
  filterButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
  listContainer: {
    padding: 15,
  },
  deliveryCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 15,
    marginBottom: 15,
    elevation: 3,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  priorityBadge: {
    position: 'absolute',
    top: 10,
    right: 10,
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  priorityText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  addressSection: {
    marginBottom: 15,
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  addressText: {
    marginLeft: 10,
    flex: 1,
  },
  addressLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  addressValue: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 2,
  },
  addressCity: {
    fontSize: 12,
    color: '#999',
  },
  arrowIcon: {
    alignSelf: 'center',
    marginVertical: 5,
  },
  detailsSection: {
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 15,
    marginBottom: 15,
  },
  detailRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10,
    gap: 8,
  },
  detailLabel: {
    fontSize: 14,
    color: '#666',
    flex: 1,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  notesRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    backgroundColor: '#FFF3E0',
    padding: 10,
    borderRadius: 8,
    marginTop: 5,
  },
  notesText: {
    fontSize: 13,
    color: '#E65100',
    marginLeft: 8,
    flex: 1,
  },
  acceptButton: {
    backgroundColor: '#4CAF50',
    padding: 15,
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 10,
  },
  acceptButtonDisabled: {
    backgroundColor: '#ccc',
  },
  acceptButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
  emptyContainer: {
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
    marginTop: 15,
  },
});
```

---

## Summary

This implementation provides:

1. ✅ **Backend API** - Complete endpoints for courier operations
2. ✅ **Filtering Logic** - Only shows deliveries with `useCourierService=true` and `courierServiceStatus=PENDING`
3. ✅ **Dashboard Endpoint** - Shows earnings, stats, and recent deliveries
4. ✅ **React Native Components** - Ready-to-use screens for couriers
5. ✅ **State Management** - Redux toolkit setup for courier data
6. ✅ **Type Safety** - Full TypeScript support

### Next Steps:

1. Implement the remaining screens (MyDeliveriesScreen, DeliveryDetailScreen)
2. Add real-time location tracking
3. Integrate push notifications for new deliveries
4. Add proof of delivery image upload
5. Implement customer signature capture
6. Add earnings withdrawal functionality

The backend is ready to use! Test the endpoints with the courier token to ensure everything works correctly.
