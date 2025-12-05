# Courier Service Implementation Guide for React Native

This guide explains how to implement the courier service toggle feature in your React Native e-commerce app.

## Overview

The backend now supports courier delivery service for orders. When users checkout or buy products, they can optionally enable courier pickup and delivery service with different priority levels (STANDARD, EXPRESS, URGENT).

## Database Schema

The `Order` model includes these courier-related fields:

```prisma
model Order {
  // ... other fields
  useCourierService    Boolean               @default(false)
  courierServiceStatus CourierServiceStatus? @default(PENDING)
  deliveryFee          Decimal               @default(0) @db.Decimal(10, 2)
  deliveryBreakdown    Json?
  // ... other fields
}
```

**CourierServiceStatus enum values:**
- `PENDING` - Courier service requested but not yet assigned
- `ACCEPTED` - Courier has accepted the delivery
- `REJECTED` - Courier service request was rejected
- `ASSIGNED` - Courier has been assigned to the delivery

## API Integration

### 1. Buy Now Endpoint

**Endpoint:** `POST /api/orders/buy-now`

**Request Body:**
```typescript
{
  productId: string;
  quantity: number;
  discountCode?: string;
  shippingAddress: {
    name: string;
    phone: string;
    address: string;
    city: string;
    country: string;
    additionalInfo?: string;
  };
  paymentGateway: "PAYSTACK" | "STRIPE";
  enableCourierDelivery: boolean;      // NEW FIELD
  deliveryPriority?: "STANDARD" | "EXPRESS" | "URGENT";  // NEW FIELD
  deliveryNotes?: string;              // NEW FIELD
}
```

### 2. Checkout Endpoint

**Endpoint:** `POST /api/orders/checkout`

**Request Body:**
```typescript
{
  shippingAddress: {
    name: string;
    phone: string;
    address: string;
    city: string;
    country: string;
    additionalInfo?: string;
  };
  discountCode?: string;
  paymentGateway: "PAYSTACK" | "STRIPE";
  enableCourierDelivery: boolean;      // NEW FIELD
  deliveryPriority?: "STANDARD" | "EXPRESS" | "URGENT";  // NEW FIELD
  deliveryNotes?: string;              // NEW FIELD
}
```

## React Native Implementation

### Step 1: Update Type Definitions

Create or update `types/order.ts`:

```typescript
export type DeliveryPriority = 'STANDARD' | 'EXPRESS' | 'URGENT';

export interface CourierDeliveryOptions {
  enableCourierDelivery: boolean;
  deliveryPriority?: DeliveryPriority;
  deliveryNotes?: string;
}

export interface BuyNowRequest extends CourierDeliveryOptions {
  productId: string;
  quantity: number;
  discountCode?: string;
  shippingAddress: ShippingAddress;
  paymentGateway: 'PAYSTACK' | 'STRIPE';
}

export interface CheckoutRequest extends CourierDeliveryOptions {
  shippingAddress: ShippingAddress;
  discountCode?: string;
  paymentGateway: 'PAYSTACK' | 'STRIPE';
}
```

### Step 2: Create Courier Service Toggle Component

Create `components/CourierServiceToggle.tsx`:

```typescript
import React, { useState } from 'react';
import { View, Text, Switch, StyleSheet } from 'react-native';
import { Picker } from '@react-native-picker/picker';
import { TextInput } from 'react-native-gesture-handler';

interface CourierServiceToggleProps {
  onToggle: (enabled: boolean, priority: string, notes: string) => void;
}

export const CourierServiceToggle: React.FC<CourierServiceToggleProps> = ({
  onToggle
}) => {
  const [enabled, setEnabled] = useState(false);
  const [priority, setPriority] = useState<'STANDARD' | 'EXPRESS' | 'URGENT'>('STANDARD');
  const [notes, setNotes] = useState('');

  const handleToggle = (value: boolean) => {
    setEnabled(value);
    onToggle(value, priority, notes);
  };

  const handlePriorityChange = (value: string) => {
    setPriority(value as any);
    onToggle(enabled, value, notes);
  };

  const handleNotesChange = (value: string) => {
    setNotes(value);
    onToggle(enabled, priority, value);
  };

  return (
    <View style={styles.container}>
      <View style={styles.toggleRow}>
        <View style={styles.labelContainer}>
          <Text style={styles.label}>Enable Courier Delivery</Text>
          <Text style={styles.subtitle}>
            Our courier will pick up from seller and deliver to you
          </Text>
        </View>
        <Switch
          value={enabled}
          onValueChange={handleToggle}
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={enabled ? '#2196F3' : '#f4f3f4'}
        />
      </View>

      {enabled && (
        <>
          <View style={styles.optionContainer}>
            <Text style={styles.optionLabel}>Delivery Priority</Text>
            <Picker
              selectedValue={priority}
              onValueChange={handlePriorityChange}
              style={styles.picker}
            >
              <Picker.Item label="Standard (2-3 days)" value="STANDARD" />
              <Picker.Item label="Express (1-2 days)" value="EXPRESS" />
              <Picker.Item label="Urgent (Same day)" value="URGENT" />
            </Picker>

            <View style={styles.feeContainer}>
              <Text style={styles.feeLabel}>Estimated Fee:</Text>
              <Text style={styles.feeAmount}>
                {priority === 'STANDARD' && 'GHS 30-50'}
                {priority === 'EXPRESS' && 'GHS 45-75'}
                {priority === 'URGENT' && 'GHS 60-100'}
              </Text>
            </View>
          </View>

          <View style={styles.notesContainer}>
            <Text style={styles.optionLabel}>Delivery Notes (Optional)</Text>
            <TextInput
              value={notes}
              onChangeText={handleNotesChange}
              placeholder="Special instructions for the courier..."
              multiline
              numberOfLines={3}
              style={styles.notesInput}
            />
          </View>
        </>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 16,
    marginVertical: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  labelContainer: {
    flex: 1,
    marginRight: 12,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 12,
    color: '#666',
  },
  optionContainer: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  optionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  picker: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    marginBottom: 12,
  },
  feeContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: '#f0f8ff',
    padding: 12,
    borderRadius: 8,
  },
  feeLabel: {
    fontSize: 14,
    color: '#666',
  },
  feeAmount: {
    fontSize: 14,
    fontWeight: '600',
    color: '#2196F3',
  },
  notesContainer: {
    marginTop: 16,
  },
  notesInput: {
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    minHeight: 80,
    textAlignVertical: 'top',
  },
});
```

### Step 3: Integrate into Checkout Screen

Update your `screens/CheckoutScreen.tsx`:

```typescript
import React, { useState } from 'react';
import { View, ScrollView, StyleSheet } from 'react-native';
import { CourierServiceToggle } from '../components/CourierServiceToggle';

export const CheckoutScreen = () => {
  const [courierOptions, setCourierOptions] = useState({
    enableCourierDelivery: false,
    deliveryPriority: 'STANDARD' as const,
    deliveryNotes: '',
  });

  const handleCourierToggle = (
    enabled: boolean,
    priority: string,
    notes: string
  ) => {
    setCourierOptions({
      enableCourierDelivery: enabled,
      deliveryPriority: priority as any,
      deliveryNotes: notes,
    });
  };

  const handleCheckout = async () => {
    try {
      const response = await fetch('YOUR_API_URL/api/orders/checkout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${yourAuthToken}`,
        },
        body: JSON.stringify({
          shippingAddress: {
            name: 'John Doe',
            phone: '+233123456789',
            address: '123 Main St',
            city: 'Accra',
            country: 'Ghana',
            additionalInfo: 'Near landmark',
          },
          paymentGateway: 'PAYSTACK',
          ...courierOptions,  // Spread courier options
        }),
      });

      const data = await response.json();

      if (data.authorization_url) {
        // Open payment URL
        // Navigate to payment screen or open browser
      }
    } catch (error) {
      console.error('Checkout error:', error);
    }
  };

  return (
    <ScrollView style={styles.container}>
      {/* Your existing shipping address form */}

      {/* Add courier service toggle */}
      <CourierServiceToggle onToggle={handleCourierToggle} />

      {/* Your checkout button */}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
});
```

### Step 4: Update Buy Now Flow

Similarly, update your `screens/ProductDetailScreen.tsx`:

```typescript
const handleBuyNow = async () => {
  try {
    const response = await fetch('YOUR_API_URL/api/orders/buy-now', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${yourAuthToken}`,
      },
      body: JSON.stringify({
        productId: product.id,
        quantity: selectedQuantity,
        shippingAddress: shippingAddress,
        paymentGateway: 'PAYSTACK',
        enableCourierDelivery: courierOptions.enableCourierDelivery,
        deliveryPriority: courierOptions.deliveryPriority,
        deliveryNotes: courierOptions.deliveryNotes,
      }),
    });

    const data = await response.json();

    if (data.authorization_url) {
      // Handle payment
    }
  } catch (error) {
    console.error('Buy now error:', error);
  }
};
```

## Delivery Fee Calculation

The backend automatically calculates delivery fees based on:
- **Base fee:** GHS 10.00
- **Distance fee:** GHS 2.00 per km (or GHS 20.00 default)
- **Priority multipliers:**
  - STANDARD: 1.0x
  - EXPRESS: 1.5x
  - URGENT: 2.0x

**Example calculations:**
- Standard delivery (30km): (10 + 30×2) × 1.0 = GHS 70.00
- Express delivery (30km): (10 + 30×2) × 1.5 = GHS 105.00
- Urgent delivery (30km): (10 + 30×2) × 2.0 = GHS 140.00

## Order Response with Courier Service

When fetching orders, the response includes courier information:

```typescript
{
  id: string;
  userId: string;
  total: number;
  status: 'PENDING' | 'CONFIRMED' | 'PROCESSING' | 'SHIPPED' | 'DELIVERED';
  useCourierService: boolean;
  courierServiceStatus?: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'ASSIGNED';
  deliveryFee: number;
  shippingAddress: {
    // ... address fields
    deliveryMetadata?: {
      enableCourierDelivery: boolean;
      deliveryPriority: string;
      deliveryNotes?: string;
    }
  };
  // ... other fields
}
```

## Display Courier Status in Order Details

Create `components/CourierStatusBadge.tsx`:

```typescript
import React from 'react';
import { View, Text, StyleSheet } from 'react-native';

interface CourierStatusBadgeProps {
  useCourierService: boolean;
  status?: 'PENDING' | 'ACCEPTED' | 'REJECTED' | 'ASSIGNED';
}

export const CourierStatusBadge: React.FC<CourierStatusBadgeProps> = ({
  useCourierService,
  status,
}) => {
  if (!useCourierService) {
    return (
      <View style={[styles.badge, styles.standardBadge]}>
        <Text style={styles.badgeText}>Standard Delivery</Text>
      </View>
    );
  }

  const getStatusStyle = () => {
    switch (status) {
      case 'PENDING':
        return { bg: '#FFF3CD', text: '#856404', label: 'Courier Pending' };
      case 'ACCEPTED':
        return { bg: '#D1ECF1', text: '#0C5460', label: 'Courier Accepted' };
      case 'ASSIGNED':
        return { bg: '#D4EDDA', text: '#155724', label: 'Courier Assigned' };
      case 'REJECTED':
        return { bg: '#F8D7DA', text: '#721C24', label: 'Courier Declined' };
      default:
        return { bg: '#E2E3E5', text: '#383D41', label: 'Courier Service' };
    }
  };

  const statusStyle = getStatusStyle();

  return (
    <View style={[styles.badge, { backgroundColor: statusStyle.bg }]}>
      <Text style={[styles.badgeText, { color: statusStyle.text }]}>
        {statusStyle.label}
      </Text>
    </View>
  );
};

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
    alignSelf: 'flex-start',
  },
  standardBadge: {
    backgroundColor: '#E2E3E5',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '600',
  },
});
```

## Testing Checklist

- [ ] Courier toggle appears on checkout screen
- [ ] Courier toggle appears on buy now flow
- [ ] Priority selector shows correct options
- [ ] Delivery notes input accepts text
- [ ] Order is created with `useCourierService: true` when enabled
- [ ] Order is created with `useCourierService: false` when disabled
- [ ] `courierServiceStatus` is set to `PENDING` when enabled
- [ ] Delivery metadata is stored in `shippingAddress`
- [ ] Order details screen shows courier status badge
- [ ] Delivery record is created in database when courier service is enabled

## Additional Features to Consider

1. **Real-time Courier Tracking**
   - Integrate with courier location API
   - Show courier on map
   - Real-time status updates via WebSocket

2. **Delivery Fee Display**
   - Show estimated delivery fee before checkout
   - Integrate Google Maps Distance Matrix API for accurate distance calculation

3. **Courier Rating**
   - Allow customers to rate courier service after delivery
   - Store ratings in `Delivery` table

4. **Push Notifications**
   - Notify customer when courier is assigned
   - Notify when courier picks up package
   - Notify when courier is nearby

5. **Delivery History**
   - Show past deliveries with courier details
   - Track delivery performance metrics

## Support

For questions or issues, please contact the backend team or refer to the API documentation.
