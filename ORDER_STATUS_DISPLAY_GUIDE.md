# Order Status Display Guide for React Native

## Overview

This guide explains how to display the correct order status in your React Native app for both customers and vendors, based on whether the order uses courier service or not.

## Background

Orders in the system can be fulfilled in two ways:
1. **With Courier Service** (`useCourierService = true`) - A courier picks up from vendor and delivers to customer
2. **Self Pickup** (`useCourierService = false`) - Customer picks up the order themselves

The status field to display depends on which method is used.

---

## API Response Structure

When fetching order details, you'll receive:

```typescript
interface Order {
  id: string;
  userId: string;
  subtotal: number;
  total: number;
  status: string;              // Regular order status
  paymentStatus: string;
  useCourierService: boolean;  // ✨ NEW: Indicates if courier is used
  courierServiceStatus: string | null;  // ✨ NEW: Courier delivery status
  items: OrderItem[];
  // ... other fields
}
```

---

## Decision Logic: Which Status to Display?

Use this simple rule:

```typescript
const displayStatus = order.useCourierService
  ? order.courierServiceStatus
  : order.status;
```

### Explanation:
- **If `useCourierService = true`**: Show `courierServiceStatus` (reflects courier delivery progress)
- **If `useCourierService = false`**: Show `status` (regular order status)

---

## Status Values Reference

### Courier Service Status (`courierServiceStatus`)
Used when `useCourierService = true`:

| Status | Meaning | Customer View | Vendor View |
|--------|---------|---------------|-------------|
| `PENDING` | Waiting for courier assignment | "Waiting for courier" | "Assign courier to ship" |
| `ACCEPTED` | Courier accepted delivery | "Courier assigned" | "Courier assigned" |
| `PICKED_UP` | Courier picked up from vendor | "Order picked up, on the way" | "Order picked up by courier" |
| `IN_TRANSIT` | On the way to customer | "Order in transit" | "Order in transit" |
| `DELIVERED` | Successfully delivered | "Delivered ✓" | "Delivered ✓" |
| `CANCELLED` | Delivery cancelled | "Delivery cancelled" | "Delivery cancelled" |
| `FAILED` | Delivery attempt failed | "Delivery failed" | "Delivery failed" |

### Regular Order Status (`status`)
Used when `useCourierService = false`:

| Status | Meaning | Customer View | Vendor View |
|--------|---------|---------------|-------------|
| `PENDING` | Payment pending | "Payment pending" | "Payment pending" |
| `CONFIRMED` | Payment completed | "Order confirmed, awaiting pickup" | "Order confirmed, prepare for pickup" |
| `PROCESSING` | Being prepared | "Order being prepared" | "Prepare order" |
| `SHIPPED` | Ready for pickup | "Ready for pickup" | "Ready for customer pickup" |
| `DELIVERED` | Customer picked up | "Picked up ✓" | "Customer picked up ✓" |
| `CANCELLED` | Order cancelled | "Cancelled" | "Cancelled" |

---

## React Native Implementation

### 1. Create Status Helper Functions

```typescript
// utils/orderStatus.ts

export type OrderStatus =
  | 'PENDING'
  | 'CONFIRMED'
  | 'PROCESSING'
  | 'SHIPPED'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'REFUNDED';

export type CourierStatus =
  | 'PENDING'
  | 'ACCEPTED'
  | 'PICKED_UP'
  | 'IN_TRANSIT'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'FAILED';

export interface Order {
  id: string;
  status: OrderStatus;
  useCourierService: boolean;
  courierServiceStatus: CourierStatus | null;
  // ... other fields
}

/**
 * Get the status to display based on order type
 */
export const getDisplayStatus = (order: Order): string => {
  return order.useCourierService
    ? order.courierServiceStatus || 'PENDING'
    : order.status;
};

/**
 * Get user-friendly status label for customers
 */
export const getCustomerStatusLabel = (order: Order): string => {
  const status = getDisplayStatus(order);

  if (order.useCourierService) {
    // Courier delivery status labels
    const courierLabels: Record<CourierStatus, string> = {
      PENDING: 'Waiting for courier',
      ACCEPTED: 'Courier assigned',
      PICKED_UP: 'Order picked up, on the way',
      IN_TRANSIT: 'Order in transit',
      DELIVERED: 'Delivered ✓',
      CANCELLED: 'Delivery cancelled',
      FAILED: 'Delivery failed',
    };
    return courierLabels[status as CourierStatus] || status;
  } else {
    // Self-pickup status labels
    const regularLabels: Record<OrderStatus, string> = {
      PENDING: 'Payment pending',
      CONFIRMED: 'Order confirmed, awaiting pickup',
      PROCESSING: 'Order being prepared',
      SHIPPED: 'Ready for pickup',
      DELIVERED: 'Picked up ✓',
      CANCELLED: 'Cancelled',
      REFUNDED: 'Refunded',
    };
    return regularLabels[status as OrderStatus] || status;
  }
};

/**
 * Get user-friendly status label for vendors
 */
export const getVendorStatusLabel = (order: Order): string => {
  const status = getDisplayStatus(order);

  if (order.useCourierService) {
    // Courier delivery status labels for vendors
    const courierLabels: Record<CourierStatus, string> = {
      PENDING: 'Assign courier to ship',
      ACCEPTED: 'Courier assigned',
      PICKED_UP: 'Order picked up by courier',
      IN_TRANSIT: 'Order in transit',
      DELIVERED: 'Delivered ✓',
      CANCELLED: 'Delivery cancelled',
      FAILED: 'Delivery failed',
    };
    return courierLabels[status as CourierStatus] || status;
  } else {
    // Self-pickup status labels for vendors
    const regularLabels: Record<OrderStatus, string> = {
      PENDING: 'Payment pending',
      CONFIRMED: 'Order confirmed, prepare for pickup',
      PROCESSING: 'Prepare order',
      SHIPPED: 'Ready for customer pickup',
      DELIVERED: 'Customer picked up ✓',
      CANCELLED: 'Cancelled',
      REFUNDED: 'Refunded',
    };
    return regularLabels[status as OrderStatus] || status;
  }
};

/**
 * Get status color for UI
 */
export const getStatusColor = (order: Order): string => {
  const status = getDisplayStatus(order);

  // Map status to colors
  const colorMap: Record<string, string> = {
    PENDING: '#FFA500',      // Orange
    ACCEPTED: '#4169E1',     // Blue
    CONFIRMED: '#4169E1',    // Blue
    PROCESSING: '#4169E1',   // Blue
    PICKED_UP: '#9370DB',    // Purple
    IN_TRANSIT: '#9370DB',   // Purple
    SHIPPED: '#32CD32',      // Green
    DELIVERED: '#228B22',    // Dark Green
    CANCELLED: '#DC143C',    // Red
    FAILED: '#DC143C',       // Red
    REFUNDED: '#808080',     // Gray
  };

  return colorMap[status] || '#808080';
};

/**
 * Get status icon name (using Ionicons)
 */
export const getStatusIcon = (order: Order): string => {
  const status = getDisplayStatus(order);

  const iconMap: Record<string, string> = {
    PENDING: 'time-outline',
    ACCEPTED: 'checkmark-circle-outline',
    CONFIRMED: 'checkmark-circle-outline',
    PROCESSING: 'construct-outline',
    PICKED_UP: 'cube-outline',
    IN_TRANSIT: 'car-outline',
    SHIPPED: 'cube-outline',
    DELIVERED: 'checkmark-done-circle',
    CANCELLED: 'close-circle-outline',
    FAILED: 'alert-circle-outline',
    REFUNDED: 'arrow-back-circle-outline',
  };

  return iconMap[status] || 'help-circle-outline';
};
```

---

### 2. Customer Order Details Screen

```typescript
// screens/CustomerOrderDetailScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getDisplayStatus,
  getCustomerStatusLabel,
  getStatusColor,
  getStatusIcon,
  Order,
} from '../utils/orderStatus';

interface Props {
  order: Order;
}

const CustomerOrderDetailScreen: React.FC<Props> = ({ order }) => {
  const statusLabel = getCustomerStatusLabel(order);
  const statusColor = getStatusColor(order);
  const statusIcon = getStatusIcon(order);
  const rawStatus = getDisplayStatus(order);

  return (
    <ScrollView style={styles.container}>
      {/* Order Header */}
      <View style={styles.header}>
        <Text style={styles.orderId}>Order #{order.id.slice(0, 8)}</Text>

        {/* Status Badge */}
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Ionicons name={statusIcon} size={16} color="white" />
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
      </View>

      {/* Delivery Type Indicator */}
      <View style={styles.deliveryTypeSection}>
        <Ionicons
          name={order.useCourierService ? 'bicycle-outline' : 'walk-outline'}
          size={24}
          color="#666"
        />
        <Text style={styles.deliveryTypeText}>
          {order.useCourierService
            ? 'Courier Delivery'
            : 'Self Pickup'}
        </Text>
      </View>

      {/* Status Timeline - Only for courier deliveries */}
      {order.useCourierService && (
        <StatusTimeline
          currentStatus={rawStatus}
          statuses={['PENDING', 'ACCEPTED', 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED']}
        />
      )}

      {/* Order Items */}
      <View style={styles.itemsSection}>
        <Text style={styles.sectionTitle}>Order Items</Text>
        {order.items.map((item) => (
          <OrderItemCard key={item.id} item={item} />
        ))}
      </View>

      {/* Action Button based on status */}
      {renderActionButton(order)}
    </ScrollView>
  );
};

// Helper component for status timeline
const StatusTimeline: React.FC<{ currentStatus: string; statuses: string[] }> = ({
  currentStatus,
  statuses
}) => {
  const currentIndex = statuses.indexOf(currentStatus);

  return (
    <View style={styles.timeline}>
      {statuses.map((status, index) => (
        <View key={status} style={styles.timelineItem}>
          <View
            style={[
              styles.timelineDot,
              index <= currentIndex && styles.timelineDotActive
            ]}
          />
          {index < statuses.length - 1 && (
            <View
              style={[
                styles.timelineLine,
                index < currentIndex && styles.timelineLineActive
              ]}
            />
          )}
          <Text style={styles.timelineLabel}>
            {status.replace('_', ' ')}
          </Text>
        </View>
      ))}
    </View>
  );
};

// Helper to render action buttons based on status
const renderActionButton = (order: Order) => {
  const status = getDisplayStatus(order);

  if (order.useCourierService) {
    // Courier delivery actions
    if (status === 'IN_TRANSIT') {
      return (
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>Track Courier</Text>
        </TouchableOpacity>
      );
    }
    if (status === 'DELIVERED') {
      return (
        <TouchableOpacity style={styles.actionButton}>
          <Text style={styles.actionButtonText}>View Receipt</Text>
        </TouchableOpacity>
      );
    }
  } else {
    // Self-pickup actions
    if (status === 'SHIPPED') {
      return (
        <View style={styles.pickupInfo}>
          <Text style={styles.pickupTitle}>Ready for Pickup!</Text>
          <Text style={styles.pickupAddress}>
            Pickup Address: {order.items[0]?.location}
          </Text>
        </View>
      );
    }
  }

  return null;
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  orderId: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 6,
  },
  statusText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 14,
  },
  deliveryTypeSection: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    backgroundColor: 'white',
    marginTop: 8,
    gap: 8,
  },
  deliveryTypeText: {
    fontSize: 16,
    fontWeight: '500',
    color: '#666',
  },
  timeline: {
    padding: 16,
    backgroundColor: 'white',
    marginTop: 8,
  },
  timelineItem: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  timelineDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
    backgroundColor: '#e0e0e0',
  },
  timelineDotActive: {
    backgroundColor: '#4CAF50',
  },
  timelineLine: {
    width: 2,
    height: 20,
    backgroundColor: '#e0e0e0',
    marginLeft: 5,
  },
  timelineLineActive: {
    backgroundColor: '#4CAF50',
  },
  timelineLabel: {
    marginLeft: 12,
    fontSize: 14,
    color: '#666',
  },
  itemsSection: {
    padding: 16,
    backgroundColor: 'white',
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  actionButton: {
    margin: 16,
    padding: 16,
    backgroundColor: '#007AFF',
    borderRadius: 8,
    alignItems: 'center',
  },
  actionButtonText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 16,
  },
  pickupInfo: {
    margin: 16,
    padding: 16,
    backgroundColor: '#E8F5E9',
    borderRadius: 8,
  },
  pickupTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#2E7D32',
    marginBottom: 8,
  },
  pickupAddress: {
    fontSize: 14,
    color: '#555',
  },
});

export default CustomerOrderDetailScreen;
```

---

### 3. Vendor Order Details Screen

```typescript
// screens/VendorOrderDetailScreen.tsx
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, ScrollView } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getDisplayStatus,
  getVendorStatusLabel,
  getStatusColor,
  getStatusIcon,
  Order,
} from '../utils/orderStatus';

interface Props {
  order: Order;
}

const VendorOrderDetailScreen: React.FC<Props> = ({ order }) => {
  const statusLabel = getVendorStatusLabel(order);
  const statusColor = getStatusColor(order);
  const statusIcon = getStatusIcon(order);
  const rawStatus = getDisplayStatus(order);

  const handleUpdateStatus = () => {
    // Implement status update logic based on delivery type
    if (order.useCourierService) {
      // For courier: Can only update until picked up
      // After PICKED_UP, courier updates the status
      console.log('Update courier delivery status');
    } else {
      // For self-pickup: Vendor updates status
      console.log('Update order status');
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Order Header */}
      <View style={styles.header}>
        <Text style={styles.orderId}>Order #{order.id.slice(0, 8)}</Text>

        {/* Status Badge */}
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Ionicons name={statusIcon} size={16} color="white" />
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>

        {/* Customer Info */}
        <View style={styles.customerInfo}>
          <Text style={styles.customerName}>{order.customerName}</Text>
          <Text style={styles.customerPhone}>{order.customerPhone}</Text>
        </View>
      </View>

      {/* Delivery Type Indicator */}
      <View style={styles.deliveryTypeSection}>
        <Ionicons
          name={order.useCourierService ? 'bicycle-outline' : 'walk-outline'}
          size={24}
          color="#666"
        />
        <View style={styles.deliveryTypeInfo}>
          <Text style={styles.deliveryTypeTitle}>
            {order.useCourierService ? 'Courier Delivery' : 'Customer Self-Pickup'}
          </Text>
          <Text style={styles.deliveryTypeSubtitle}>
            {order.useCourierService
              ? 'A courier will pick up this order'
              : 'Customer will pick up from your location'}
          </Text>
        </View>
      </View>

      {/* Order Items */}
      <View style={styles.itemsSection}>
        <Text style={styles.sectionTitle}>Items to Prepare</Text>
        {order.items.map((item) => (
          <VendorOrderItemCard key={item.id} item={item} />
        ))}
      </View>

      {/* Revenue Info */}
      <View style={styles.revenueSection}>
        <Text style={styles.revenueLabel}>Your Revenue</Text>
        <Text style={styles.revenueAmount}>
          {order.currency} {order.sellerRevenue.toFixed(2)}
        </Text>
      </View>

      {/* Action Buttons based on status */}
      {renderVendorActions(order, handleUpdateStatus)}
    </ScrollView>
  );
};

// Helper to render vendor action buttons
const renderVendorActions = (
  order: Order,
  onUpdateStatus: () => void
) => {
  const status = getDisplayStatus(order);

  if (order.useCourierService) {
    // Courier delivery actions
    switch (status) {
      case 'CONFIRMED':
      case 'PENDING':
        return (
          <TouchableOpacity
            style={styles.actionButton}
            onPress={onUpdateStatus}
          >
            <Text style={styles.actionButtonText}>Mark as Ready for Pickup</Text>
          </TouchableOpacity>
        );
      case 'PROCESSING':
        return (
          <View style={styles.infoBox}>
            <Ionicons name="information-circle" size={20} color="#1976D2" />
            <Text style={styles.infoText}>
              Prepare items for courier pickup
            </Text>
          </View>
        );
      case 'PICKED_UP':
      case 'IN_TRANSIT':
        return (
          <View style={styles.infoBox}>
            <Ionicons name="checkmark-circle" size={20} color="#388E3C" />
            <Text style={styles.infoText}>
              Courier is delivering to customer
            </Text>
          </View>
        );
      default:
        return null;
    }
  } else {
    // Self-pickup actions
    switch (status) {
      case 'CONFIRMED':
        return (
          <TouchableOpacity
            style={styles.actionButton}
            onPress={onUpdateStatus}
          >
            <Text style={styles.actionButtonText}>Start Preparing Order</Text>
          </TouchableOpacity>
        );
      case 'PROCESSING':
        return (
          <TouchableOpacity
            style={styles.actionButton}
            onPress={onUpdateStatus}
          >
            <Text style={styles.actionButtonText}>Mark as Ready for Pickup</Text>
          </TouchableOpacity>
        );
      case 'SHIPPED':
        return (
          <View>
            <View style={styles.infoBox}>
              <Ionicons name="information-circle" size={20} color="#1976D2" />
              <Text style={styles.infoText}>
                Waiting for customer to pick up
              </Text>
            </View>
            <TouchableOpacity
              style={[styles.actionButton, styles.actionButtonSecondary]}
              onPress={onUpdateStatus}
            >
              <Text style={styles.actionButtonText}>Customer Picked Up</Text>
            </TouchableOpacity>
          </View>
        );
      default:
        return null;
    }
  }
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  orderId: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    gap: 6,
    marginBottom: 12,
  },
  statusText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 14,
  },
  customerInfo: {
    marginTop: 8,
  },
  customerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  customerPhone: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  deliveryTypeSection: {
    flexDirection: 'row',
    padding: 16,
    backgroundColor: 'white',
    marginTop: 8,
    gap: 12,
  },
  deliveryTypeInfo: {
    flex: 1,
  },
  deliveryTypeTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  deliveryTypeSubtitle: {
    fontSize: 14,
    color: '#666',
  },
  itemsSection: {
    padding: 16,
    backgroundColor: 'white',
    marginTop: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 12,
  },
  revenueSection: {
    padding: 16,
    backgroundColor: '#E8F5E9',
    marginTop: 8,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  revenueLabel: {
    fontSize: 14,
    color: '#2E7D32',
    fontWeight: '500',
  },
  revenueAmount: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#1B5E20',
  },
  actionButton: {
    margin: 16,
    padding: 16,
    backgroundColor: '#007AFF',
    borderRadius: 8,
    alignItems: 'center',
  },
  actionButtonSecondary: {
    backgroundColor: '#4CAF50',
    marginTop: 0,
  },
  actionButtonText: {
    color: 'white',
    fontWeight: '600',
    fontSize: 16,
  },
  infoBox: {
    margin: 16,
    padding: 16,
    backgroundColor: '#E3F2FD',
    borderRadius: 8,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  infoText: {
    fontSize: 14,
    color: '#1565C0',
    flex: 1,
  },
});

export default VendorOrderDetailScreen;
```

---

### 4. Order List Item Component (Reusable)

```typescript
// components/OrderListItem.tsx
import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  getCustomerStatusLabel,
  getVendorStatusLabel,
  getStatusColor,
  getStatusIcon,
  Order,
} from '../utils/orderStatus';

interface Props {
  order: Order;
  userType: 'customer' | 'vendor';
  onPress: () => void;
}

const OrderListItem: React.FC<Props> = ({ order, userType, onPress }) => {
  const statusLabel = userType === 'customer'
    ? getCustomerStatusLabel(order)
    : getVendorStatusLabel(order);
  const statusColor = getStatusColor(order);
  const statusIcon = getStatusIcon(order);

  return (
    <TouchableOpacity style={styles.container} onPress={onPress}>
      <View style={styles.header}>
        <Text style={styles.orderId}>Order #{order.id.slice(0, 8)}</Text>
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Ionicons name={statusIcon} size={12} color="white" />
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
      </View>

      {/* Delivery type icon */}
      <View style={styles.deliveryType}>
        <Ionicons
          name={order.useCourierService ? 'bicycle' : 'walk'}
          size={16}
          color="#666"
        />
        <Text style={styles.deliveryTypeText}>
          {order.useCourierService ? 'Courier Delivery' : 'Self Pickup'}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.itemCount}>{order.items.length} items</Text>
        <Text style={styles.total}>
          {order.currency} {order.total.toFixed(2)}
        </Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: 'white',
    padding: 16,
    marginVertical: 4,
    marginHorizontal: 8,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
    elevation: 2,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  orderId: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  statusBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
    gap: 4,
  },
  statusText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '600',
  },
  deliveryType: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 8,
  },
  deliveryTypeText: {
    fontSize: 13,
    color: '#666',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#f0f0f0',
  },
  itemCount: {
    fontSize: 14,
    color: '#666',
  },
  total: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
});

export default OrderListItem;
```

---

## API Endpoints to Use

### For Customers:
```typescript
// Get all orders
GET /orders?status=CONFIRMED

// Get single order details
GET /orders/{order_id}
```

### For Vendors:
```typescript
// Get all vendor orders
GET /seller/orders?status=CONFIRMED

// Get single order details (use customer endpoint with proper auth)
GET /orders/{order_id}
```

---

## Testing Checklist

- [ ] Customer can see courier status for orders with `useCourierService = true`
- [ ] Customer can see regular status for orders with `useCourierService = false`
- [ ] Vendor can see courier status for orders with `useCourierService = true`
- [ ] Vendor can see regular status for orders with `useCourierService = false`
- [ ] Status colors and icons display correctly
- [ ] Status labels are user-friendly and contextual
- [ ] Order list shows correct status badge
- [ ] Order details show appropriate action buttons based on status
- [ ] Delivery type indicator shows correctly

---

## Common Issues & Solutions

### Issue 1: Status shows as `null` or `undefined`
**Solution**: Check that the API response includes both `useCourierService` and `courierServiceStatus` fields. The backend has been updated to include these.

### Issue 2: Wrong status displayed
**Solution**: Ensure you're using the `getDisplayStatus()` helper function instead of directly accessing `order.status`.

### Issue 3: Status labels not updating
**Solution**: Make sure to refetch order data after status updates. Consider using React Query or SWR for automatic refetching.

---

## Best Practices

1. **Always use helper functions** - Don't hardcode status logic in components
2. **Show delivery type clearly** - Users should immediately see if it's courier or self-pickup
3. **Provide contextual actions** - Show relevant buttons based on current status
4. **Use visual indicators** - Colors, icons, and badges improve UX
5. **Handle loading states** - Show skeleton loaders while fetching order data
6. **Error handling** - Gracefully handle missing or invalid status values
7. **Real-time updates** - Consider WebSocket or polling for live status updates

---

## Next Steps

1. Implement the helper functions in your React Native project
2. Update your order list and detail screens to use the new status display logic
3. Test with both courier and self-pickup orders
4. Add real-time status updates (optional, using WebSocket or polling)
5. Implement push notifications for status changes

---

## Support

For issues or questions, refer to:
- `COURIER_STATUS_UPDATES_AND_NOTIFICATIONS.md` - Backend courier status documentation
- Backend API: `/orders` and `/seller/orders` endpoints
