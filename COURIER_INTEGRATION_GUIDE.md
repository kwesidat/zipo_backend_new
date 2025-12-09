# Courier Service Integration Guide - React Native

This guide will help you integrate courier functionality into your React Native app for both **customers** and **couriers**.

---

## Table of Contents

1. [Customer Flow - Enable Courier Delivery](#1-customer-flow---enable-courier-delivery)
2. [Courier Flow - View & Accept Deliveries](#2-courier-flow---view--accept-deliveries)
3. [Courier Flow - Update Delivery Status](#3-courier-flow---update-delivery-status)
4. [Customer Flow - Track Delivery](#4-customer-flow---track-delivery)
5. [API Endpoints Reference](#5-api-endpoints-reference)
6. [Data Models](#6-data-models)
7. [Code Examples](#7-code-examples)

---

## 1. Customer Flow - Enable Courier Delivery

### Step 1.1: Add Courier Service Toggle to Checkout

In your checkout screen, add a toggle/switch for customers to enable courier service:

```typescript
const [enableCourierDelivery, setEnableCourierDelivery] = useState(false);
const [deliveryPriority, setDeliveryPriority] = useState<'STANDARD' | 'EXPRESS' | 'URGENT'>('STANDARD');
const [deliveryNotes, setDeliveryNotes] = useState('');
```

### Step 1.2: Calculate Delivery Fee (Optional)

Call this endpoint to show estimated delivery fee before checkout:

```typescript
const calculateDeliveryFee = async (distanceKm?: number, priority: string = 'STANDARD') => {
  try {
    const response = await fetch(`${API_BASE_URL}/delivery/delivery/calculate-fee`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        distance_km: distanceKm,
        priority: priority,
      }),
    });

    const data = await response.json();
    // data = { delivery_fee, courier_fee, platform_fee, distance_km, priority }
    return data.delivery_fee;
  } catch (error) {
    console.error('Error calculating delivery fee:', error);
    return null;
  }
};
```

### Step 1.3: Include Courier Options in Checkout Request

When calling checkout or buy-now endpoints, include the courier service options:

```typescript
const checkoutWithCourier = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/orders/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        shippingAddress: {
          address: '123 Main St',
          city: 'Accra',
          country: 'Ghana',
          fullName: 'John Doe',
          phone: '+233123456789',
          // ... other address fields
        },
        paymentGateway: 'PAYSTACK',
        enableCourierDelivery: enableCourierDelivery, // ✅ Enable courier service
        deliveryPriority: deliveryPriority,           // ✅ STANDARD, EXPRESS, or URGENT
        deliveryNotes: deliveryNotes,                 // ✅ Special instructions
        calculatedDeliveryFee: deliveryFee,           // ✅ Fee from calculation
      }),
    });

    const data = await response.json();
    // Proceed to payment with data.authorization_url
  } catch (error) {
    console.error('Checkout error:', error);
  }
};
```

### Step 1.4: After Payment - View Your Deliveries

After successful payment, customers can view their scheduled deliveries:

```typescript
const getMyDeliveries = async (page = 1, status?: string) => {
  try {
    const url = new URL(`${API_BASE_URL}/delivery/my-deliveries`);
    url.searchParams.append('page', page.toString());
    url.searchParams.append('page_size', '20');
    if (status) url.searchParams.append('status', status);

    const response = await fetch(url.toString(), {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();
    // data = { deliveries: [...], total_count, page, page_size, total_pages, has_next, has_previous }
    return data.deliveries;
  } catch (error) {
    console.error('Error fetching deliveries:', error);
  }
};
```

---

## 2. Courier Flow - View & Accept Deliveries

### Step 2.1: View Available Deliveries

Create a screen to show available deliveries that couriers can accept:

```typescript
const getAvailableDeliveries = async (page = 1, priority?: string) => {
  try {
    const url = new URL(`${API_BASE_URL}/delivery/available`);
    url.searchParams.append('page', page.toString());
    url.searchParams.append('page_size', '20');
    if (priority) url.searchParams.append('priority', priority);

    const response = await fetch(url.toString(), {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    if (!response.ok) {
      throw new Error('Failed to fetch deliveries');
    }

    const data = await response.json();
    // data = { deliveries: [...], total_count, page, page_size, total_pages, has_next, has_previous }
    return data;
  } catch (error) {
    console.error('Error fetching available deliveries:', error);
  }
};
```

### Step 2.2: Display Delivery Card Component

Create a component to display each delivery:

```typescript
interface DeliveryCardProps {
  delivery: AvailableDelivery;
  onAccept: (deliveryId: string) => void;
}

const DeliveryCard = ({ delivery, onAccept }: DeliveryCardProps) => {
  return (
    <View style={styles.card}>
      <Text style={styles.priority}>{delivery.priority}</Text>

      <View style={styles.addressSection}>
        <Text style={styles.label}>📍 Pickup:</Text>
        <Text>{delivery.pickup_address.address}, {delivery.pickup_address.city}</Text>
        <Text>Contact: {delivery.pickup_contact_name} - {delivery.pickup_contact_phone}</Text>
      </View>

      <View style={styles.addressSection}>
        <Text style={styles.label}>📍 Delivery:</Text>
        <Text>{delivery.delivery_address.address}, {delivery.delivery_address.city}</Text>
        <Text>Contact: {delivery.delivery_contact_name} - {delivery.delivery_contact_phone}</Text>
      </View>

      <View style={styles.feeSection}>
        <Text style={styles.fee}>💰 Your Earnings: GHS {delivery.courier_fee}</Text>
        {delivery.distance_km && (
          <Text>Distance: ~{delivery.distance_km} km</Text>
        )}
        {delivery.scheduled_date && (
          <Text>⏰ Scheduled: {new Date(delivery.scheduled_date).toLocaleString()}</Text>
        )}
      </View>

      {delivery.notes && (
        <View style={styles.notesSection}>
          <Text style={styles.label}>📝 Notes:</Text>
          <Text>{delivery.notes}</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.acceptButton}
        onPress={() => onAccept(delivery.id)}
      >
        <Text style={styles.acceptButtonText}>Accept Delivery</Text>
      </TouchableOpacity>
    </View>
  );
};
```

### Step 2.3: Accept Delivery

When courier clicks "Accept Delivery":

```typescript
const acceptDelivery = async (
  deliveryId: string,
  estimatedPickupTime?: Date,
  estimatedDeliveryTime?: Date
) => {
  try {
    const response = await fetch(`${API_BASE_URL}/delivery/accept`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${accessToken}`,
      },
      body: JSON.stringify({
        delivery_id: deliveryId,
        estimated_pickup_time: estimatedPickupTime?.toISOString(),
        estimated_delivery_time: estimatedDeliveryTime?.toISOString(),
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to accept delivery');
    }

    const delivery = await response.json();
    // Success! Delivery is now assigned to courier
    Alert.alert('Success', 'Delivery accepted successfully!');
    // Navigate to "My Deliveries" screen
    return delivery;
  } catch (error) {
    console.error('Error accepting delivery:', error);
    Alert.alert('Error', error.message);
  }
};
```

### Step 2.4: View My Accepted Deliveries

Create a screen to show the courier's accepted deliveries:

```typescript
const getMyAcceptedDeliveries = async (page = 1, status?: string) => {
  try {
    const url = new URL(`${API_BASE_URL}/delivery/courier/my-deliveries`);
    url.searchParams.append('page', page.toString());
    url.searchParams.append('page_size', '20');
    if (status) url.searchParams.append('status', status);

    const response = await fetch(url.toString(), {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();
    return data;
  } catch (error) {
    console.error('Error fetching my deliveries:', error);
  }
};
```

---

## 3. Courier Flow - Update Delivery Status

### Step 3.1: Update Status Component

Create buttons for different delivery statuses:

```typescript
const DeliveryStatusUpdater = ({ deliveryId, currentStatus }: Props) => {
  const [notes, setNotes] = useState('');
  const [proofOfDeliveryUrls, setProofOfDeliveryUrls] = useState<string[]>([]);

  const updateStatus = async (newStatus: DeliveryStatus) => {
    try {
      const response = await fetch(`${API_BASE_URL}/delivery/${deliveryId}/status`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          status: newStatus,
          notes: notes || undefined,
          proof_of_delivery_urls: proofOfDeliveryUrls.length > 0 ? proofOfDeliveryUrls : undefined,
        }),
      });

      const data = await response.json();
      Alert.alert('Success', `Status updated to ${newStatus}`);
      return data;
    } catch (error) {
      console.error('Error updating status:', error);
      Alert.alert('Error', 'Failed to update status');
    }
  };

  return (
    <View>
      <Text>Current Status: {currentStatus}</Text>

      {currentStatus === 'ACCEPTED' && (
        <Button title="📦 Mark as Picked Up" onPress={() => updateStatus('PICKED_UP')} />
      )}

      {currentStatus === 'PICKED_UP' && (
        <Button title="🚚 Mark as In Transit" onPress={() => updateStatus('IN_TRANSIT')} />
      )}

      {currentStatus === 'IN_TRANSIT' && (
        <>
          <TextInput
            placeholder="Add delivery notes (optional)"
            value={notes}
            onChangeText={setNotes}
          />
          <Button title="Upload Proof of Delivery" onPress={uploadProof} />
          <Button title="✅ Mark as Delivered" onPress={() => updateStatus('DELIVERED')} />
        </>
      )}
    </View>
  );
};
```

### Step 3.2: Status Flow

The typical delivery status flow is:

1. **PENDING** → Order created, waiting for courier
2. **ACCEPTED** → Courier accepted the delivery
3. **PICKED_UP** → Courier picked up the package
4. **IN_TRANSIT** → Courier is delivering
5. **DELIVERED** → Delivery completed ✅

You can also use:
- **CANCELLED** - Delivery was cancelled
- **FAILED** - Delivery failed

---

## 4. Customer Flow - Track Delivery

### Step 4.1: View Delivery Details

Customers can track their delivery status:

```typescript
const getDeliveryDetails = async (deliveryId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/delivery/${deliveryId}`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    const delivery = await response.json();
    return delivery;
  } catch (error) {
    console.error('Error fetching delivery details:', error);
  }
};
```

### Step 4.2: View Courier Details

Once a courier is assigned, customers can view courier information:

```typescript
const getCourierDetails = async (deliveryId: string) => {
  try {
    const response = await fetch(`${API_BASE_URL}/delivery/${deliveryId}/courier`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`,
      },
    });

    const data = await response.json();

    if (data.courier_assigned) {
      const courier = data.courier;
      // Display: name, phone_number, vehicle_type, rating, etc.
      return courier;
    } else {
      // No courier assigned yet
      return null;
    }
  } catch (error) {
    console.error('Error fetching courier details:', error);
  }
};
```

### Step 4.3: Track Delivery Screen Component

```typescript
const TrackDeliveryScreen = ({ deliveryId }: Props) => {
  const [delivery, setDelivery] = useState<Delivery | null>(null);
  const [courier, setCourier] = useState<Courier | null>(null);

  useEffect(() => {
    loadDeliveryDetails();
    // Poll every 30 seconds for updates
    const interval = setInterval(loadDeliveryDetails, 30000);
    return () => clearInterval(interval);
  }, [deliveryId]);

  const loadDeliveryDetails = async () => {
    const deliveryData = await getDeliveryDetails(deliveryId);
    setDelivery(deliveryData);

    if (deliveryData.courier_id) {
      const courierData = await getCourierDetails(deliveryId);
      setCourier(courierData);
    }
  };

  return (
    <ScrollView>
      {/* Status Timeline */}
      <StatusTimeline status={delivery?.status} />

      {/* Courier Info */}
      {courier && (
        <View style={styles.courierCard}>
          <Text style={styles.title}>Your Courier</Text>
          <Text>👤 {courier.name}</Text>
          <Text>📞 {courier.phone_number}</Text>
          <Text>🚗 {courier.vehicle_type} - {courier.vehicle_number}</Text>
          <Text>⭐ Rating: {courier.rating}/5 ({courier.completed_deliveries} deliveries)</Text>
          <Button title="Call Courier" onPress={() => Linking.openURL(`tel:${courier.phone_number}`)} />
        </View>
      )}

      {/* Delivery Details */}
      <View style={styles.detailsCard}>
        <Text style={styles.sectionTitle}>Pickup Location</Text>
        <Text>{delivery?.pickup_address.address}</Text>
        <Text>{delivery?.pickup_contact_name} - {delivery?.pickup_contact_phone}</Text>

        <Text style={styles.sectionTitle}>Delivery Location</Text>
        <Text>{delivery?.delivery_address.address}</Text>
        <Text>{delivery?.delivery_contact_name} - {delivery?.delivery_contact_phone}</Text>

        {delivery?.notes && (
          <>
            <Text style={styles.sectionTitle}>Notes</Text>
            <Text>{delivery.notes}</Text>
          </>
        )}

        {delivery?.courier_notes && (
          <>
            <Text style={styles.sectionTitle}>Courier Notes</Text>
            <Text>{delivery.courier_notes}</Text>
          </>
        )}
      </View>

      {/* Proof of Delivery */}
      {delivery?.status === 'DELIVERED' && delivery?.proof_of_delivery?.length > 0 && (
        <View style={styles.proofSection}>
          <Text style={styles.sectionTitle}>Proof of Delivery</Text>
          {delivery.proof_of_delivery.map((url, index) => (
            <Image key={index} source={{ uri: url }} style={styles.proofImage} />
          ))}
        </View>
      )}
    </ScrollView>
  );
};
```

---

## 5. API Endpoints Reference

### Base URL
```
https://your-api-domain.com/api
```

### Customer Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/orders/checkout` | POST | Checkout with courier service option | Yes |
| `/orders/buy-now` | POST | Buy now with courier service option | Yes |
| `/delivery/my-deliveries` | GET | Get all my scheduled deliveries | Yes |
| `/delivery/{delivery_id}` | GET | Get delivery details | Yes |
| `/delivery/{delivery_id}/courier` | GET | Get courier details for delivery | Yes |
| `/delivery/delivery/calculate-fee` | POST | Calculate delivery fee | Yes |

### Courier Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/delivery/available` | GET | Get available deliveries to accept | Yes (Courier only) |
| `/delivery/accept` | POST | Accept a delivery | Yes (Courier only) |
| `/delivery/courier/my-deliveries` | GET | Get my accepted deliveries | Yes (Courier only) |
| `/delivery/{delivery_id}/status` | PUT | Update delivery status | Yes (Courier only) |

### Query Parameters

**Pagination:**
- `page` (default: 1)
- `page_size` (default: 20, max: 100)

**Filters:**
- `status` - Filter by delivery status (PENDING, ACCEPTED, PICKED_UP, IN_TRANSIT, DELIVERED, CANCELLED, FAILED)
- `priority` - Filter by priority (STANDARD, EXPRESS, URGENT)

---

## 6. Data Models

### Delivery Priority
```typescript
enum DeliveryPriority {
  STANDARD = 'STANDARD',  // Normal delivery
  EXPRESS = 'EXPRESS',    // Faster delivery (1.5x fee)
  URGENT = 'URGENT',      // Immediate delivery (2x fee)
}
```

### Delivery Status
```typescript
enum DeliveryStatus {
  PENDING = 'PENDING',           // Waiting for courier
  ASSIGNED = 'ASSIGNED',         // System assigned (not used currently)
  ACCEPTED = 'ACCEPTED',         // Courier accepted
  PICKED_UP = 'PICKED_UP',       // Courier picked up package
  IN_TRANSIT = 'IN_TRANSIT',     // Courier is delivering
  DELIVERED = 'DELIVERED',       // Delivery completed
  CANCELLED = 'CANCELLED',       // Delivery cancelled
  FAILED = 'FAILED',             // Delivery failed
}
```

### Delivery Response
```typescript
interface Delivery {
  id: string;
  order_id: string;
  courier_id: string | null;
  pickup_address: Address;
  delivery_address: Address;
  pickup_contact_name: string;
  pickup_contact_phone: string;
  delivery_contact_name: string;
  delivery_contact_phone: string;
  scheduled_by_user: string;
  scheduled_by_type: 'CUSTOMER' | 'SELLER' | 'AGENT' | 'ADMIN' | 'COURIER';
  delivery_fee: number;
  courier_fee: number;
  platform_fee: number;
  distance_km: number | null;
  status: DeliveryStatus;
  priority: DeliveryPriority;
  scheduled_date: string | null;
  estimated_pickup_time: string | null;
  estimated_delivery_time: string | null;
  actual_pickup_time: string | null;
  actual_delivery_time: string | null;
  notes: string | null;
  courier_notes: string | null;
  cancellation_reason: string | null;
  proof_of_delivery: string[];
  customer_signature: string | null;
  rating: number | null;
  review: string | null;
  created_at: string;
  updated_at: string;
}

interface Address {
  address: string;
  city: string;
  country: string;
  latitude?: number;
  longitude?: number;
  additional_info?: string;
}
```

### Courier Response
```typescript
interface Courier {
  courier_id: string;
  courier_code: string;
  name: string;
  phone_number: string;
  vehicle_type: 'BICYCLE' | 'MOTORCYCLE' | 'CAR' | 'VAN' | 'TRUCK';
  vehicle_number: string;
  rating: number;
  total_deliveries: number;
  completed_deliveries: number;
}
```

---

## 7. Code Examples

### Complete Courier Available Deliveries Screen

```typescript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  Alert,
  StyleSheet,
} from 'react-native';
import { useAuth } from '../context/AuthContext';

const CourierAvailableDeliveriesScreen = ({ navigation }) => {
  const { accessToken } = useAuth();
  const [deliveries, setDeliveries] = useState([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [selectedPriority, setSelectedPriority] = useState<string | null>(null);

  useEffect(() => {
    loadDeliveries();
  }, [page, selectedPriority]);

  const loadDeliveries = async () => {
    if (loading) return;
    setLoading(true);

    try {
      const url = new URL(`${process.env.API_BASE_URL}/delivery/available`);
      url.searchParams.append('page', page.toString());
      url.searchParams.append('page_size', '20');
      if (selectedPriority) {
        url.searchParams.append('priority', selectedPriority);
      }

      const response = await fetch(url.toString(), {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
        },
      });

      if (!response.ok) throw new Error('Failed to load deliveries');

      const data = await response.json();

      if (page === 1) {
        setDeliveries(data.deliveries);
      } else {
        setDeliveries(prev => [...prev, ...data.deliveries]);
      }

      setHasMore(data.has_next);
    } catch (error) {
      console.error('Error loading deliveries:', error);
      Alert.alert('Error', 'Failed to load deliveries');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    setPage(1);
    loadDeliveries();
  };

  const handleLoadMore = () => {
    if (hasMore && !loading) {
      setPage(prev => prev + 1);
    }
  };

  const handleAccept = async (deliveryId: string) => {
    try {
      const response = await fetch(`${process.env.API_BASE_URL}/delivery/accept`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${accessToken}`,
        },
        body: JSON.stringify({
          delivery_id: deliveryId,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to accept delivery');
      }

      Alert.alert(
        'Success!',
        'Delivery accepted successfully!',
        [
          { text: 'OK', onPress: () => navigation.navigate('MyDeliveries') }
        ]
      );

      // Refresh the list
      handleRefresh();
    } catch (error) {
      console.error('Error accepting delivery:', error);
      Alert.alert('Error', error.message);
    }
  };

  const renderDeliveryCard = ({ item }) => (
    <View style={styles.card}>
      <View style={styles.priorityBadge}>
        <Text style={[
          styles.priorityText,
          item.priority === 'URGENT' && styles.urgent,
          item.priority === 'EXPRESS' && styles.express,
        ]}>
          {item.priority}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📍 Pickup Location</Text>
        <Text style={styles.address}>{item.pickup_address.address}</Text>
        <Text style={styles.contact}>
          {item.pickup_contact_name} • {item.pickup_contact_phone}
        </Text>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📍 Delivery Location</Text>
        <Text style={styles.address}>{item.delivery_address.address}</Text>
        <Text style={styles.contact}>
          {item.delivery_contact_name} • {item.delivery_contact_phone}
        </Text>
      </View>

      <View style={styles.infoRow}>
        <View style={styles.infoItem}>
          <Text style={styles.infoLabel}>Your Earnings</Text>
          <Text style={styles.infoValue}>GHS {item.courier_fee}</Text>
        </View>
        {item.distance_km && (
          <View style={styles.infoItem}>
            <Text style={styles.infoLabel}>Distance</Text>
            <Text style={styles.infoValue}>{item.distance_km} km</Text>
          </View>
        )}
      </View>

      {item.scheduled_date && (
        <View style={styles.scheduledSection}>
          <Text style={styles.scheduledText}>
            ⏰ Scheduled: {new Date(item.scheduled_date).toLocaleString()}
          </Text>
        </View>
      )}

      {item.notes && (
        <View style={styles.notesSection}>
          <Text style={styles.notesLabel}>📝 Customer Notes:</Text>
          <Text style={styles.notesText}>{item.notes}</Text>
        </View>
      )}

      <TouchableOpacity
        style={styles.acceptButton}
        onPress={() => {
          Alert.alert(
            'Accept Delivery',
            'Are you sure you want to accept this delivery?',
            [
              { text: 'Cancel', style: 'cancel' },
              { text: 'Accept', onPress: () => handleAccept(item.id) },
            ]
          );
        }}
      >
        <Text style={styles.acceptButtonText}>Accept Delivery</Text>
      </TouchableOpacity>
    </View>
  );

  return (
    <View style={styles.container}>
      <View style={styles.filterBar}>
        <TouchableOpacity
          style={[styles.filterButton, !selectedPriority && styles.filterActive]}
          onPress={() => setSelectedPriority(null)}
        >
          <Text>All</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, selectedPriority === 'URGENT' && styles.filterActive]}
          onPress={() => setSelectedPriority('URGENT')}
        >
          <Text>Urgent</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, selectedPriority === 'EXPRESS' && styles.filterActive]}
          onPress={() => setSelectedPriority('EXPRESS')}
        >
          <Text>Express</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={[styles.filterButton, selectedPriority === 'STANDARD' && styles.filterActive]}
          onPress={() => setSelectedPriority('STANDARD')}
        >
          <Text>Standard</Text>
        </TouchableOpacity>
      </View>

      <FlatList
        data={deliveries}
        renderItem={renderDeliveryCard}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={handleRefresh} />
        }
        onEndReached={handleLoadMore}
        onEndReachedThreshold={0.5}
        ListEmptyComponent={
          <View style={styles.emptyState}>
            <Text style={styles.emptyText}>
              {loading ? 'Loading deliveries...' : 'No deliveries available at the moment'}
            </Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  filterBar: {
    flexDirection: 'row',
    padding: 10,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  filterButton: {
    paddingHorizontal: 15,
    paddingVertical: 8,
    marginRight: 10,
    borderRadius: 20,
    backgroundColor: '#f0f0f0',
  },
  filterActive: {
    backgroundColor: '#007AFF',
  },
  card: {
    backgroundColor: 'white',
    margin: 10,
    padding: 15,
    borderRadius: 10,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  priorityBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 15,
    backgroundColor: '#e8f5e9',
    marginBottom: 10,
  },
  priorityText: {
    fontWeight: 'bold',
    color: '#4caf50',
  },
  urgent: {
    color: '#f44336',
    backgroundColor: '#ffebee',
  },
  express: {
    color: '#ff9800',
    backgroundColor: '#fff3e0',
  },
  section: {
    marginBottom: 15,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#666',
    marginBottom: 5,
  },
  address: {
    fontSize: 16,
    color: '#333',
    marginBottom: 3,
  },
  contact: {
    fontSize: 14,
    color: '#999',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  infoItem: {
    flex: 1,
  },
  infoLabel: {
    fontSize: 12,
    color: '#999',
  },
  infoValue: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4caf50',
  },
  scheduledSection: {
    backgroundColor: '#fff3e0',
    padding: 10,
    borderRadius: 5,
    marginBottom: 10,
  },
  scheduledText: {
    color: '#ff9800',
    fontSize: 14,
  },
  notesSection: {
    backgroundColor: '#f5f5f5',
    padding: 10,
    borderRadius: 5,
    marginBottom: 10,
  },
  notesLabel: {
    fontSize: 12,
    color: '#666',
    marginBottom: 3,
  },
  notesText: {
    fontSize: 14,
    color: '#333',
  },
  acceptButton: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
  },
  acceptButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  emptyState: {
    padding: 40,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
    textAlign: 'center',
  },
});

export default CourierAvailableDeliveriesScreen;
```

---

## Testing Checklist

### Customer Testing
- [ ] Enable courier delivery toggle appears in checkout
- [ ] Calculate delivery fee before payment
- [ ] Complete checkout with courier service enabled
- [ ] View my deliveries list
- [ ] Track individual delivery status
- [ ] View courier details when assigned
- [ ] Receive notifications when courier accepts delivery

### Courier Testing
- [ ] View available deliveries (only shows orders with useCourierService=true)
- [ ] Filter by priority (STANDARD, EXPRESS, URGENT)
- [ ] Accept a delivery
- [ ] View my accepted deliveries
- [ ] Update delivery status (PICKED_UP → IN_TRANSIT → DELIVERED)
- [ ] Upload proof of delivery
- [ ] View earnings for each delivery

---

## Support

For questions or issues, please contact the development team or open an issue in the repository.

**Happy Coding! 🚀**
