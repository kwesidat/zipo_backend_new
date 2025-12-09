# React Native Implementation Guide: Enhanced Delivery & Order Features

This guide covers how to implement the new backend features in your React Native app.

## Table of Contents
1. [Overview of Changes](#overview-of-changes)
2. [Type Definitions](#type-definitions)
3. [API Integration](#api-integration)
4. [UI Components](#ui-components)
5. [Implementation Steps](#implementation-steps)

---

## Overview of Changes

### What's New:
1. **Order Delivery Fee Fix** - Orders now correctly store and display `deliveryFee` in database
2. **Order Address Extraction** - Orders API now returns structured `pickup_address` and `delivery_address`
3. **Enhanced Delivery Listings** - Available deliveries now include complete order details with multi-vendor support

---

## Type Definitions

### Step 1: Update/Create TypeScript Types

Create or update `types/delivery.ts`:

```typescript
// types/delivery.ts

export interface Address {
  street: string;
  city: string;
  country: string;
}

export interface OrderItemSummary {
  id: string;
  product_id: string;
  title: string;
  image?: string;
  quantity: number;
  price: number;
  seller_id: string;
  seller_name: string;
  condition?: string;
}

export interface OrderSummary {
  id: string;
  subtotal: number;
  total: number;
  currency: string;
  payment_status: string;
  items: OrderItemSummary[];
  item_count: number;
  is_multi_vendor: boolean;
}

export interface AvailableDelivery {
  id: string;
  order_id: string;
  pickup_address: Address;
  delivery_address: Address;
  pickup_contact_name?: string;
  pickup_contact_phone?: string;
  delivery_contact_name?: string;
  delivery_contact_phone?: string;
  delivery_fee: number;
  courier_fee: number;
  distance_km?: number;
  priority: 'STANDARD' | 'EXPRESS' | 'URGENT';
  scheduled_date?: string;
  estimated_pickup_time?: string;
  estimated_delivery_time?: string;
  notes?: string;
  created_at: string;
  order?: OrderSummary; // NEW: Complete order details
}

export interface AvailableDeliveriesResponse {
  deliveries: AvailableDelivery[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}
```

Update `types/order.ts`:

```typescript
// types/order.ts

export interface Order {
  id: string;
  userId: string;
  subtotal: number;
  discountAmount: number;
  tax: number;
  deliveryFee?: number; // NEW: Now properly populated
  total: number;
  status: string;
  paymentStatus: string;
  currency: string;
  shippingAddress: any;
  pickup_address?: Address; // NEW: Structured pickup address
  delivery_address?: Address; // NEW: Structured delivery address
  trackingNumber?: string;
  paymentMethod?: string;
  paymentGateway?: string;
  createdAt: string;
  updatedAt: string;
  items: OrderItem[];
  appliedDiscounts: any[];
}

export interface OrderItem {
  id: string;
  productId: string;
  title: string;
  image?: string;
  quantity: number;
  price: number;
  subtotal: number;
  sellerId: string;
  sellerName: string;
  condition?: string;
  location?: string;
}
```

---

## API Integration

### Step 2: Create/Update API Service

Create or update `services/deliveryService.ts`:

```typescript
// services/deliveryService.ts
import axios from 'axios';
import { AvailableDeliveriesResponse } from '../types/delivery';

const API_BASE_URL = 'https://zipobackendnew-kwesidat802-px1elcxp.leapcell.dev/api';

export const deliveryService = {
  /**
   * Fetch available deliveries for couriers
   * Now includes complete order details with multi-vendor info
   */
  async getAvailableDeliveries(
    token: string,
    page: number = 1,
    pageSize: number = 20,
    priority?: 'STANDARD' | 'EXPRESS' | 'URGENT'
  ): Promise<AvailableDeliveriesResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });

    if (priority) {
      params.append('priority', priority);
    }

    const response = await axios.get(
      `${API_BASE_URL}/deliveries/available?${params.toString()}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    return response.data;
  },

  /**
   * Accept a delivery
   */
  async acceptDelivery(
    token: string,
    deliveryId: string,
    estimatedPickupTime?: string,
    estimatedDeliveryTime?: string
  ) {
    const response = await axios.post(
      `${API_BASE_URL}/deliveries/accept`,
      {
        delivery_id: deliveryId,
        estimated_pickup_time: estimatedPickupTime,
        estimated_delivery_time: estimatedDeliveryTime,
      },
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    return response.data;
  },
};
```

Update `services/orderService.ts`:

```typescript
// services/orderService.ts
import axios from 'axios';
import { Order } from '../types/order';

const API_BASE_URL = 'https://zipobackendnew-kwesidat802-px1elcxp.leapcell.dev/api';

export const orderService = {
  /**
   * Fetch user's orders
   * Now includes pickup_address and delivery_address
   */
  async getUserOrders(
    token: string,
    status?: string,
    limit: number = 20,
    offset: number = 0
  ): Promise<Order[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    if (status) {
      params.append('order_status', status);
    }

    const response = await axios.get(
      `${API_BASE_URL}/orders?${params.toString()}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    return response.data;
  },

  /**
   * Get single order by ID
   */
  async getOrderById(token: string, orderId: string): Promise<Order> {
    const response = await axios.get(
      `${API_BASE_URL}/orders/${orderId}`,
      {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }
    );

    return response.data;
  },
};
```

---

## UI Components

### Step 3: Create Delivery Card Component

Create `components/DeliveryCard.tsx`:

```typescript
// components/DeliveryCard.tsx
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Image } from 'react-native';
import { AvailableDelivery } from '../types/delivery';
import { Ionicons } from '@expo/vector-icons';

interface DeliveryCardProps {
  delivery: AvailableDelivery;
  onPress: (delivery: AvailableDelivery) => void;
}

export const DeliveryCard: React.FC<DeliveryCardProps> = ({ delivery, onPress }) => {
  const { order, pickup_address, delivery_address, delivery_fee, courier_fee, priority } = delivery;

  // Helper to get priority color
  const getPriorityColor = () => {
    switch (priority) {
      case 'URGENT':
        return '#EF4444'; // red
      case 'EXPRESS':
        return '#F59E0B'; // orange
      default:
        return '#10B981'; // green
    }
  };

  // Helper to get priority badge
  const renderPriorityBadge = () => (
    <View style={[styles.priorityBadge, { backgroundColor: getPriorityColor() }]}>
      <Text style={styles.priorityText}>{priority}</Text>
    </View>
  );

  // Helper to render multi-vendor badge
  const renderMultiVendorBadge = () => {
    if (!order?.is_multi_vendor) return null;

    return (
      <View style={styles.multiVendorBadge}>
        <Ionicons name="people-outline" size={14} color="#fff" />
        <Text style={styles.multiVendorText}>Multi-Vendor</Text>
      </View>
    );
  };

  return (
    <TouchableOpacity style={styles.container} onPress={() => onPress(delivery)}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.orderId}>Order #{delivery.order_id.slice(0, 8)}</Text>
          {renderPriorityBadge()}
          {renderMultiVendorBadge()}
        </View>
        <View style={styles.earnings}>
          <Text style={styles.earningsLabel}>You earn</Text>
          <Text style={styles.earningsAmount}>
            {order?.currency || 'GHS'} {courier_fee.toFixed(2)}
          </Text>
        </View>
      </View>

      {/* Addresses */}
      <View style={styles.addressSection}>
        {/* Pickup Address */}
        <View style={styles.addressRow}>
          <View style={styles.iconContainer}>
            <Ionicons name="location-outline" size={20} color="#10B981" />
          </View>
          <View style={styles.addressInfo}>
            <Text style={styles.addressLabel}>Pickup from</Text>
            <Text style={styles.addressText}>
              {pickup_address.street}, {pickup_address.city}
            </Text>
            {delivery.pickup_contact_name && (
              <Text style={styles.contactText}>{delivery.pickup_contact_name}</Text>
            )}
          </View>
        </View>

        {/* Divider Line */}
        <View style={styles.routeLine} />

        {/* Delivery Address */}
        <View style={styles.addressRow}>
          <View style={styles.iconContainer}>
            <Ionicons name="flag-outline" size={20} color="#EF4444" />
          </View>
          <View style={styles.addressInfo}>
            <Text style={styles.addressLabel}>Deliver to</Text>
            <Text style={styles.addressText}>
              {delivery_address.street}, {delivery_address.city}
            </Text>
            {delivery.delivery_contact_name && (
              <Text style={styles.contactText}>{delivery.delivery_contact_name}</Text>
            )}
          </View>
        </View>
      </View>

      {/* Order Items Summary */}
      {order && order.items.length > 0 && (
        <View style={styles.itemsSection}>
          <Text style={styles.itemsHeader}>
            {order.item_count} item(s) • {order.currency} {order.total.toFixed(2)}
          </Text>
          <View style={styles.itemsList}>
            {order.items.slice(0, 3).map((item, index) => (
              <View key={item.id} style={styles.itemRow}>
                {item.image && (
                  <Image source={{ uri: item.image }} style={styles.itemImage} />
                )}
                <View style={styles.itemInfo}>
                  <Text style={styles.itemTitle} numberOfLines={1}>
                    {item.quantity}x {item.title}
                  </Text>
                  <Text style={styles.itemSeller} numberOfLines={1}>
                    {item.seller_name}
                  </Text>
                </View>
                <Text style={styles.itemPrice}>
                  {order.currency} {(item.price * item.quantity).toFixed(2)}
                </Text>
              </View>
            ))}
            {order.item_count > 3 && (
              <Text style={styles.moreItems}>
                +{order.item_count - 3} more item(s)
              </Text>
            )}
          </View>
        </View>
      )}

      {/* Footer */}
      <View style={styles.footer}>
        <View style={styles.feeInfo}>
          <Text style={styles.feeLabel}>Delivery Fee:</Text>
          <Text style={styles.feeAmount}>
            {order?.currency || 'GHS'} {delivery_fee.toFixed(2)}
          </Text>
        </View>
        <TouchableOpacity style={styles.acceptButton} onPress={() => onPress(delivery)}>
          <Text style={styles.acceptButtonText}>Accept Delivery</Text>
          <Ionicons name="arrow-forward" size={18} color="#fff" />
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    flexWrap: 'wrap',
    gap: 8,
  },
  orderId: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#fff',
    textTransform: 'uppercase',
  },
  multiVendorBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    backgroundColor: '#8B5CF6',
  },
  multiVendorText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#fff',
  },
  earnings: {
    alignItems: 'flex-end',
  },
  earningsLabel: {
    fontSize: 12,
    color: '#6B7280',
  },
  earningsAmount: {
    fontSize: 18,
    fontWeight: '700',
    color: '#10B981',
  },
  addressSection: {
    marginBottom: 16,
  },
  addressRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#F3F4F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  addressInfo: {
    flex: 1,
  },
  addressLabel: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 4,
  },
  addressText: {
    fontSize: 14,
    fontWeight: '500',
    color: '#1F2937',
    marginBottom: 2,
  },
  contactText: {
    fontSize: 12,
    color: '#6B7280',
  },
  routeLine: {
    width: 2,
    height: 20,
    backgroundColor: '#E5E7EB',
    marginLeft: 15,
    marginVertical: 4,
  },
  itemsSection: {
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  itemsHeader: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 12,
  },
  itemsList: {
    gap: 8,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  itemImage: {
    width: 40,
    height: 40,
    borderRadius: 6,
    backgroundColor: '#E5E7EB',
  },
  itemInfo: {
    flex: 1,
  },
  itemTitle: {
    fontSize: 13,
    fontWeight: '500',
    color: '#1F2937',
    marginBottom: 2,
  },
  itemSeller: {
    fontSize: 11,
    color: '#6B7280',
  },
  itemPrice: {
    fontSize: 13,
    fontWeight: '600',
    color: '#1F2937',
  },
  moreItems: {
    fontSize: 12,
    color: '#6B7280',
    fontStyle: 'italic',
    marginTop: 4,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  feeInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  feeLabel: {
    fontSize: 13,
    color: '#6B7280',
  },
  feeAmount: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1F2937',
  },
  acceptButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: '#10B981',
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 8,
  },
  acceptButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#fff',
  },
});
```

### Step 4: Create Order Address Component

Create `components/OrderAddressView.tsx`:

```typescript
// components/OrderAddressView.tsx
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { Address } from '../types/delivery';

interface OrderAddressViewProps {
  pickupAddress?: Address;
  deliveryAddress?: Address;
}

export const OrderAddressView: React.FC<OrderAddressViewProps> = ({
  pickupAddress,
  deliveryAddress,
}) => {
  if (!pickupAddress && !deliveryAddress) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Delivery Information</Text>

      {pickupAddress && (
        <View style={styles.addressCard}>
          <View style={styles.iconContainer}>
            <Ionicons name="location" size={20} color="#10B981" />
          </View>
          <View style={styles.addressContent}>
            <Text style={styles.label}>Pickup Address</Text>
            <Text style={styles.addressText}>
              {pickupAddress.street}
            </Text>
            <Text style={styles.cityText}>
              {pickupAddress.city}, {pickupAddress.country}
            </Text>
          </View>
        </View>
      )}

      {deliveryAddress && (
        <View style={styles.addressCard}>
          <View style={styles.iconContainer}>
            <Ionicons name="flag" size={20} color="#EF4444" />
          </View>
          <View style={styles.addressContent}>
            <Text style={styles.label}>Delivery Address</Text>
            <Text style={styles.addressText}>
              {deliveryAddress.street}
            </Text>
            <Text style={styles.cityText}>
              {deliveryAddress.city}, {deliveryAddress.country}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    marginVertical: 16,
  },
  title: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 12,
  },
  addressCard: {
    flexDirection: 'row',
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  iconContainer: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  addressContent: {
    flex: 1,
  },
  label: {
    fontSize: 12,
    fontWeight: '600',
    color: '#6B7280',
    marginBottom: 4,
  },
  addressText: {
    fontSize: 14,
    color: '#1F2937',
    marginBottom: 2,
  },
  cityText: {
    fontSize: 13,
    color: '#6B7280',
  },
});
```

---

## Implementation Steps

### Step 5: Update Available Deliveries Screen

Update your courier deliveries screen:

```typescript
// screens/CourierAvailableDeliveriesScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  FlatList,
  StyleSheet,
  RefreshControl,
  Text,
  ActivityIndicator,
} from 'react-native';
import { DeliveryCard } from '../components/DeliveryCard';
import { deliveryService } from '../services/deliveryService';
import { AvailableDelivery } from '../types/delivery';
import { useAuth } from '../context/AuthContext'; // Your auth context

export const CourierAvailableDeliveriesScreen = ({ navigation }) => {
  const { token } = useAuth();
  const [deliveries, setDeliveries] = useState<AvailableDelivery[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);

  const fetchDeliveries = async (pageNum: number = 1, refresh: boolean = false) => {
    try {
      if (refresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      const response = await deliveryService.getAvailableDeliveries(
        token,
        pageNum,
        20
      );

      if (refresh || pageNum === 1) {
        setDeliveries(response.deliveries);
      } else {
        setDeliveries(prev => [...prev, ...response.deliveries]);
      }

      setHasMore(response.has_next);
      setPage(pageNum);
    } catch (error) {
      console.error('Failed to fetch deliveries:', error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchDeliveries(1);
  }, []);

  const handleRefresh = () => {
    fetchDeliveries(1, true);
  };

  const handleLoadMore = () => {
    if (!loading && hasMore) {
      fetchDeliveries(page + 1);
    }
  };

  const handleDeliveryPress = (delivery: AvailableDelivery) => {
    navigation.navigate('DeliveryDetails', { delivery });
  };

  const renderEmpty = () => (
    <View style={styles.emptyContainer}>
      <Text style={styles.emptyText}>No available deliveries at the moment</Text>
      <Text style={styles.emptySubtext}>
        Pull down to refresh and check for new deliveries
      </Text>
    </View>
  );

  const renderFooter = () => {
    if (!loading || page === 1) return null;
    return (
      <View style={styles.footerLoader}>
        <ActivityIndicator size="small" color="#10B981" />
      </View>
    );
  };

  if (loading && page === 1) {
    return (
      <View style={styles.loaderContainer}>
        <ActivityIndicator size="large" color="#10B981" />
        <Text style={styles.loadingText}>Loading deliveries...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={deliveries}
        renderItem={({ item }) => (
          <DeliveryCard delivery={item} onPress={handleDeliveryPress} />
        )}
        keyExtractor={item => item.id}
        contentContainerStyle={styles.listContent}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={handleRefresh}
            colors={['#10B981']}
          />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.5}
        ListFooterComponent={renderFooter}
        ListEmptyComponent={renderEmpty}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  listContent: {
    padding: 16,
  },
  loaderContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#F3F4F6',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
    color: '#6B7280',
  },
  emptyContainer: {
    alignItems: 'center',
    paddingVertical: 60,
  },
  emptyText: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 8,
  },
  emptySubtext: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
  },
  footerLoader: {
    paddingVertical: 20,
    alignItems: 'center',
  },
});
```

### Step 6: Update Order Details Screen

Update your order details screen to show the new address fields:

```typescript
// screens/OrderDetailsScreen.tsx
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { OrderAddressView } from '../components/OrderAddressView';
import { orderService } from '../services/orderService';
import { Order } from '../types/order';
import { useAuth } from '../context/AuthContext';

export const OrderDetailsScreen = ({ route }) => {
  const { orderId } = route.params;
  const { token } = useAuth();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOrderDetails();
  }, [orderId]);

  const fetchOrderDetails = async () => {
    try {
      setLoading(true);
      const data = await orderService.getOrderById(token, orderId);
      setOrder(data);
    } catch (error) {
      console.error('Failed to fetch order:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loaderContainer}>
        <ActivityIndicator size="large" color="#10B981" />
      </View>
    );
  }

  if (!order) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Order not found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      {/* Order Header */}
      <View style={styles.header}>
        <Text style={styles.orderId}>Order #{order.id.slice(0, 8)}</Text>
        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>{order.status}</Text>
        </View>
      </View>

      {/* Order Summary */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Order Summary</Text>
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Subtotal:</Text>
          <Text style={styles.summaryValue}>
            {order.currency} {order.subtotal.toFixed(2)}
          </Text>
        </View>
        {order.deliveryFee && order.deliveryFee > 0 && (
          <View style={styles.summaryRow}>
            <Text style={styles.summaryLabel}>Delivery Fee:</Text>
            <Text style={styles.summaryValue}>
              {order.currency} {order.deliveryFee.toFixed(2)}
            </Text>
          </View>
        )}
        <View style={styles.summaryRow}>
          <Text style={styles.summaryLabel}>Tax:</Text>
          <Text style={styles.summaryValue}>
            {order.currency} {order.tax.toFixed(2)}
          </Text>
        </View>
        {order.discountAmount > 0 && (
          <View style={styles.summaryRow}>
            <Text style={[styles.summaryLabel, styles.discountText]}>Discount:</Text>
            <Text style={[styles.summaryValue, styles.discountText]}>
              -{order.currency} {order.discountAmount.toFixed(2)}
            </Text>
          </View>
        )}
        <View style={[styles.summaryRow, styles.totalRow]}>
          <Text style={styles.totalLabel}>Total:</Text>
          <Text style={styles.totalValue}>
            {order.currency} {order.total.toFixed(2)}
          </Text>
        </View>
      </View>

      {/* Delivery Addresses - NEW */}
      <OrderAddressView
        pickupAddress={order.pickup_address}
        deliveryAddress={order.delivery_address}
      />

      {/* Order Items */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Items ({order.items.length})</Text>
        {order.items.map(item => (
          <View key={item.id} style={styles.itemCard}>
            <View style={styles.itemHeader}>
              <Text style={styles.itemTitle}>{item.title}</Text>
              <Text style={styles.itemPrice}>
                {order.currency} {item.subtotal.toFixed(2)}
              </Text>
            </View>
            <Text style={styles.itemSeller}>Sold by: {item.sellerName}</Text>
            <Text style={styles.itemQuantity}>
              {item.quantity}x @ {order.currency} {item.price.toFixed(2)}
            </Text>
          </View>
        ))}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F3F4F6',
  },
  loaderContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    fontSize: 16,
    color: '#EF4444',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 16,
    backgroundColor: '#fff',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  orderId: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    backgroundColor: '#10B981',
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#fff',
    textTransform: 'uppercase',
  },
  section: {
    backgroundColor: '#fff',
    marginTop: 12,
    padding: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1F2937',
    marginBottom: 12,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  summaryLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  summaryValue: {
    fontSize: 14,
    fontWeight: '500',
    color: '#1F2937',
  },
  discountText: {
    color: '#10B981',
  },
  totalRow: {
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
    marginTop: 8,
    paddingTop: 12,
  },
  totalLabel: {
    fontSize: 16,
    fontWeight: '700',
    color: '#1F2937',
  },
  totalValue: {
    fontSize: 18,
    fontWeight: '700',
    color: '#1F2937',
  },
  itemCard: {
    backgroundColor: '#F9FAFB',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
  },
  itemHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  itemTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#1F2937',
    flex: 1,
  },
  itemPrice: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1F2937',
  },
  itemSeller: {
    fontSize: 12,
    color: '#6B7280',
    marginBottom: 2,
  },
  itemQuantity: {
    fontSize: 12,
    color: '#6B7280',
  },
});
```

---

## Testing Checklist

### For Courier App:
- [ ] Available deliveries list shows all deliveries with order details
- [ ] Multi-vendor badge appears for orders with multiple sellers
- [ ] Priority badges (URGENT, EXPRESS, STANDARD) display correctly
- [ ] Order items list shows correct product names, quantities, and prices
- [ ] Pickup and delivery addresses display correctly
- [ ] Courier fee displays accurately
- [ ] Accept delivery button works
- [ ] Pagination and pull-to-refresh work

### For Customer/Seller App:
- [ ] Order details show delivery fee correctly (not 0 or incorrect)
- [ ] Pickup address displays for courier deliveries
- [ ] Delivery address displays for all orders
- [ ] Order summary calculations are correct
- [ ] Multi-item orders display all items

---

## Additional Features to Consider

### 1. Filter by Priority
```typescript
// Add to CourierAvailableDeliveriesScreen
const [selectedPriority, setSelectedPriority] = useState<string | undefined>();

// Add filter buttons in UI
<View style={styles.filterBar}>
  <TouchableOpacity
    style={[styles.filterButton, !selectedPriority && styles.activeFilter]}
    onPress={() => {
      setSelectedPriority(undefined);
      fetchDeliveries(1, true);
    }}
  >
    <Text>All</Text>
  </TouchableOpacity>
  <TouchableOpacity
    style={[styles.filterButton, selectedPriority === 'URGENT' && styles.activeFilter]}
    onPress={() => {
      setSelectedPriority('URGENT');
      // Fetch with priority filter
    }}
  >
    <Text>Urgent</Text>
  </TouchableOpacity>
  {/* Add EXPRESS and STANDARD buttons */}
</View>
```

### 2. Map View
Consider adding a map view showing pickup and delivery locations if you have latitude/longitude data.

### 3. Push Notifications
Set up push notifications when:
- New deliveries become available (for couriers)
- Courier accepts delivery (for customers)
- Delivery status changes

---

## Troubleshooting

### Issue: Delivery fee showing as 0
**Solution**: Make sure you're passing `calculatedDeliveryFee` in your checkout request:
```typescript
const checkoutData = {
  shippingAddress: address,
  paymentGateway: 'PAYSTACK',
  enableCourierDelivery: true,
  calculatedDeliveryFee: 200.00, // Make sure this is included!
};
```

### Issue: Addresses not showing
**Solution**: Addresses are only populated for orders with courier delivery enabled. Check:
```typescript
if (order.useCourierService && order.pickup_address) {
  // Show addresses
}
```

### Issue: Order items not loading
**Solution**: Check your API response in the network tab. Ensure the backend is returning the `order` object with `items` array.

---

## Support

If you encounter any issues:
1. Check the backend logs for errors
2. Verify your auth token is valid
3. Ensure API endpoint URLs are correct
4. Test API endpoints directly using Postman/Thunder Client

For backend issues, refer to the backend implementation or contact your backend team.

---

**Happy Coding! 🚀**
