# React Native Implementation Guide: My Deliveries Feature

This guide shows how to implement the "My Deliveries" feature in your React Native app to display user's scheduled deliveries.

## API Endpoint

```
GET /delivery/my-deliveries
```

**Base URL**: Your backend API URL (e.g., `https://api.yourapp.com`)

## Authentication

All requests require a Bearer token in the Authorization header:

```javascript
Authorization: Bearer <user_token>
```

## Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | number | No | 1 | Page number (minimum: 1) |
| `page_size` | number | No | 20 | Items per page (1-100) |
| `status` | string | No | - | Filter by status (PENDING, ACCEPTED, PICKED_UP, IN_TRANSIT, DELIVERED, CANCELLED, FAILED) |

## Response Structure

```typescript
{
  deliveries: DeliveryItem[],
  total_count: number,
  page: number,
  page_size: number,
  total_pages: number,
  has_next: boolean,
  has_previous: boolean
}
```

### DeliveryItem Structure

```typescript
interface DeliveryItem {
  id: string;
  order_id: string;
  courier_id: string | null;
  pickup_address: {
    address: string;
    city: string;
    country: string;
    latitude?: number;
    longitude?: number;
    additional_info?: string;
  };
  delivery_address: {
    address: string;
    city: string;
    country: string;
    latitude?: number;
    longitude?: number;
    additional_info?: string;
  };
  pickup_contact_name: string;
  pickup_contact_phone: string;
  delivery_contact_name: string;
  delivery_contact_phone: string;
  scheduled_by_user: string;
  scheduled_by_type: "CUSTOMER" | "SELLER" | "AGENT" | "ADMIN" | "COURIER";
  delivery_fee: string; // Decimal as string
  courier_fee: string; // Decimal as string
  platform_fee: string; // Decimal as string
  distance_km: number | null;
  status: "PENDING" | "ASSIGNED" | "ACCEPTED" | "PICKED_UP" | "IN_TRANSIT" | "DELIVERED" | "CANCELLED" | "FAILED";
  priority: "STANDARD" | "EXPRESS" | "URGENT";
  scheduled_date: string | null; // ISO datetime
  estimated_pickup_time: string | null; // ISO datetime
  estimated_delivery_time: string | null; // ISO datetime
  actual_pickup_time: string | null; // ISO datetime
  actual_delivery_time: string | null; // ISO datetime
  notes: string | null;
  courier_notes: string | null;
  cancellation_reason: string | null;
  proof_of_delivery: string[]; // Array of image URLs
  customer_signature: string | null;
  rating: number | null;
  review: string | null;
  created_at: string; // ISO datetime
  updated_at: string; // ISO datetime
}
```

---

## Implementation

### 1. Create API Service

Create a file: `services/deliveryService.ts`

```typescript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://api.yourapp.com'; // Replace with your API URL

interface GetMyDeliveriesParams {
  page?: number;
  page_size?: number;
  status?: string;
}

export const deliveryService = {
  async getMyDeliveries(params: GetMyDeliveriesParams = {}) {
    try {
      // Get auth token from storage
      const token = await AsyncStorage.getItem('authToken');

      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await axios.get(`${API_BASE_URL}/delivery/my-deliveries`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
        params: {
          page: params.page || 1,
          page_size: params.page_size || 20,
          ...(params.status && { status: params.status }),
        },
      });

      return response.data;
    } catch (error) {
      console.error('Error fetching deliveries:', error);
      throw error;
    }
  },

  async getDeliveryById(deliveryId: string) {
    try {
      const token = await AsyncStorage.getItem('authToken');

      if (!token) {
        throw new Error('No authentication token found');
      }

      const response = await axios.get(`${API_BASE_URL}/delivery/${deliveryId}`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      return response.data;
    } catch (error) {
      console.error('Error fetching delivery details:', error);
      throw error;
    }
  },
};
```

### 2. Create Type Definitions

Create a file: `types/delivery.ts`

```typescript
export type DeliveryStatus =
  | 'PENDING'
  | 'ASSIGNED'
  | 'ACCEPTED'
  | 'PICKED_UP'
  | 'IN_TRANSIT'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'FAILED';

export type DeliveryPriority = 'STANDARD' | 'EXPRESS' | 'URGENT';

export type UserType = 'CUSTOMER' | 'SELLER' | 'AGENT' | 'ADMIN' | 'COURIER';

export interface DeliveryAddress {
  address: string;
  city: string;
  country: string;
  latitude?: number;
  longitude?: number;
  additional_info?: string;
}

export interface DeliveryItem {
  id: string;
  order_id: string;
  courier_id: string | null;
  pickup_address: DeliveryAddress;
  delivery_address: DeliveryAddress;
  pickup_contact_name: string;
  pickup_contact_phone: string;
  delivery_contact_name: string;
  delivery_contact_phone: string;
  scheduled_by_user: string;
  scheduled_by_type: UserType;
  delivery_fee: string;
  courier_fee: string;
  platform_fee: string;
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

export interface MyDeliveriesResponse {
  deliveries: DeliveryItem[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}
```

### 3. Create MyDeliveries Screen

Create a file: `screens/MyDeliveriesScreen.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { deliveryService } from '../services/deliveryService';
import { DeliveryItem, DeliveryStatus } from '../types/delivery';

const MyDeliveriesScreen = ({ navigation }: any) => {
  const [deliveries, setDeliveries] = useState<DeliveryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [selectedStatus, setSelectedStatus] = useState<DeliveryStatus | ''>('');

  const fetchDeliveries = async (pageNum: number = 1, status: string = '') => {
    try {
      setLoading(true);
      const response = await deliveryService.getMyDeliveries({
        page: pageNum,
        page_size: 20,
        ...(status && { status }),
      });

      if (pageNum === 1) {
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
    fetchDeliveries(1, selectedStatus);
  }, [selectedStatus]);

  const onRefresh = () => {
    setRefreshing(true);
    fetchDeliveries(1, selectedStatus);
  };

  const loadMore = () => {
    if (!loading && hasMore) {
      fetchDeliveries(page + 1, selectedStatus);
    }
  };

  const getStatusColor = (status: DeliveryStatus) => {
    const colors: Record<DeliveryStatus, string> = {
      PENDING: '#FFA500',
      ASSIGNED: '#4169E1',
      ACCEPTED: '#4169E1',
      PICKED_UP: '#9370DB',
      IN_TRANSIT: '#1E90FF',
      DELIVERED: '#32CD32',
      CANCELLED: '#DC143C',
      FAILED: '#FF0000',
    };
    return colors[status] || '#808080';
  };

  const getPriorityBadge = (priority: string) => {
    const badges: Record<string, { color: string; text: string }> = {
      URGENT: { color: '#FF0000', text: '🔥 Urgent' },
      EXPRESS: { color: '#FFA500', text: '⚡ Express' },
      STANDARD: { color: '#808080', text: 'Standard' },
    };
    return badges[priority] || badges.STANDARD;
  };

  const renderDeliveryItem = ({ item }: { item: DeliveryItem }) => {
    const priorityBadge = getPriorityBadge(item.priority);

    return (
      <TouchableOpacity
        style={styles.deliveryCard}
        onPress={() => navigation.navigate('DeliveryDetails', { deliveryId: item.id })}
      >
        <View style={styles.cardHeader}>
          <View>
            <Text style={styles.deliveryId}>#{item.id.substring(0, 8)}</Text>
            <Text style={styles.date}>
              {new Date(item.created_at).toLocaleDateString()}
            </Text>
          </View>
          <View style={[styles.statusBadge, { backgroundColor: getStatusColor(item.status) }]}>
            <Text style={styles.statusText}>{item.status.replace('_', ' ')}</Text>
          </View>
        </View>

        <View style={styles.priorityContainer}>
          <View style={[styles.priorityBadge, { backgroundColor: priorityBadge.color }]}>
            <Text style={styles.priorityText}>{priorityBadge.text}</Text>
          </View>
        </View>

        <View style={styles.addressSection}>
          <View style={styles.addressRow}>
            <Text style={styles.addressLabel}>📍 Pickup:</Text>
            <Text style={styles.addressText} numberOfLines={1}>
              {item.pickup_address.address}
            </Text>
          </View>
          <View style={styles.addressRow}>
            <Text style={styles.addressLabel}>📦 Delivery:</Text>
            <Text style={styles.addressText} numberOfLines={1}>
              {item.delivery_address.address}
            </Text>
          </View>
        </View>

        <View style={styles.footer}>
          <Text style={styles.fee}>GHS {parseFloat(item.delivery_fee).toFixed(2)}</Text>
          {item.courier_id && (
            <Text style={styles.courierAssigned}>✓ Courier Assigned</Text>
          )}
        </View>
      </TouchableOpacity>
    );
  };

  const statusFilters: (DeliveryStatus | '')[] = [
    '',
    'PENDING',
    'ACCEPTED',
    'IN_TRANSIT',
    'DELIVERED',
  ];

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>My Deliveries</Text>
      </View>

      <View style={styles.filterContainer}>
        <FlatList
          horizontal
          showsHorizontalScrollIndicator={false}
          data={statusFilters}
          keyExtractor={(item) => item || 'all'}
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[
                styles.filterButton,
                selectedStatus === item && styles.filterButtonActive,
              ]}
              onPress={() => setSelectedStatus(item)}
            >
              <Text
                style={[
                  styles.filterButtonText,
                  selectedStatus === item && styles.filterButtonTextActive,
                ]}
              >
                {item || 'All'}
              </Text>
            </TouchableOpacity>
          )}
        />
      </View>

      {loading && page === 1 ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#4169E1" />
        </View>
      ) : (
        <FlatList
          data={deliveries}
          keyExtractor={(item) => item.id}
          renderItem={renderDeliveryItem}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={
            loading && page > 1 ? (
              <ActivityIndicator size="small" color="#4169E1" style={styles.footerLoader} />
            ) : null
          }
          ListEmptyComponent={
            <View style={styles.emptyContainer}>
              <Text style={styles.emptyText}>No deliveries found</Text>
            </View>
          }
        />
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  header: {
    backgroundColor: '#4169E1',
    padding: 20,
    paddingTop: 50,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  filterContainer: {
    backgroundColor: '#FFFFFF',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: '#E0E0E0',
  },
  filterButton: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    marginHorizontal: 6,
    borderRadius: 20,
    backgroundColor: '#F0F0F0',
  },
  filterButtonActive: {
    backgroundColor: '#4169E1',
  },
  filterButtonText: {
    fontSize: 14,
    color: '#666',
  },
  filterButtonTextActive: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
  },
  deliveryCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  deliveryId: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  date: {
    fontSize: 12,
    color: '#999',
    marginTop: 2,
  },
  statusBadge: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 12,
  },
  statusText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '600',
  },
  priorityContainer: {
    marginBottom: 12,
  },
  priorityBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  priorityText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '600',
  },
  addressSection: {
    marginBottom: 12,
  },
  addressRow: {
    flexDirection: 'row',
    marginBottom: 6,
  },
  addressLabel: {
    fontSize: 14,
    color: '#666',
    width: 80,
  },
  addressText: {
    fontSize: 14,
    color: '#333',
    flex: 1,
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: '#F0F0F0',
    paddingTop: 12,
  },
  fee: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#4169E1',
  },
  courierAssigned: {
    fontSize: 12,
    color: '#32CD32',
    fontWeight: '600',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  footerLoader: {
    marginVertical: 16,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 40,
  },
  emptyText: {
    fontSize: 16,
    color: '#999',
  },
});

export default MyDeliveriesScreen;
```

### 4. Create Delivery Details Screen (Optional)

Create a file: `screens/DeliveryDetailsScreen.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Image,
} from 'react-native';
import { deliveryService } from '../services/deliveryService';
import { DeliveryItem } from '../types/delivery';

const DeliveryDetailsScreen = ({ route }: any) => {
  const { deliveryId } = route.params;
  const [delivery, setDelivery] = useState<DeliveryItem | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeliveryDetails();
  }, []);

  const fetchDeliveryDetails = async () => {
    try {
      const data = await deliveryService.getDeliveryById(deliveryId);
      setDelivery(data);
    } catch (error) {
      console.error('Failed to fetch delivery details:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#4169E1" />
      </View>
    );
  }

  if (!delivery) {
    return (
      <View style={styles.errorContainer}>
        <Text style={styles.errorText}>Delivery not found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Delivery Information</Text>
        <DetailRow label="Delivery ID" value={delivery.id} />
        <DetailRow label="Status" value={delivery.status} />
        <DetailRow label="Priority" value={delivery.priority} />
        <DetailRow label="Fee" value={`GHS ${parseFloat(delivery.delivery_fee).toFixed(2)}`} />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Pickup Details</Text>
        <DetailRow label="Contact" value={delivery.pickup_contact_name} />
        <DetailRow label="Phone" value={delivery.pickup_contact_phone} />
        <DetailRow label="Address" value={delivery.pickup_address.address} />
        <DetailRow label="City" value={delivery.pickup_address.city} />
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Delivery Details</Text>
        <DetailRow label="Contact" value={delivery.delivery_contact_name} />
        <DetailRow label="Phone" value={delivery.delivery_contact_phone} />
        <DetailRow label="Address" value={delivery.delivery_address.address} />
        <DetailRow label="City" value={delivery.delivery_address.city} />
      </View>

      {delivery.notes && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Notes</Text>
          <Text style={styles.notesText}>{delivery.notes}</Text>
        </View>
      )}

      {delivery.courier_notes && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Courier Notes</Text>
          <Text style={styles.notesText}>{delivery.courier_notes}</Text>
        </View>
      )}

      {delivery.proof_of_delivery && delivery.proof_of_delivery.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Proof of Delivery</Text>
          <View style={styles.imageContainer}>
            {delivery.proof_of_delivery.map((url, index) => (
              <Image key={index} source={{ uri: url }} style={styles.proofImage} />
            ))}
          </View>
        </View>
      )}

      {delivery.rating && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Rating</Text>
          <Text style={styles.rating}>{'⭐'.repeat(Math.round(delivery.rating))}</Text>
          {delivery.review && <Text style={styles.review}>{delivery.review}</Text>}
        </View>
      )}
    </ScrollView>
  );
};

const DetailRow = ({ label, value }: { label: string; value: string }) => (
  <View style={styles.detailRow}>
    <Text style={styles.label}>{label}:</Text>
    <Text style={styles.value}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F5F5F5',
  },
  loadingContainer: {
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
    color: '#999',
  },
  section: {
    backgroundColor: '#FFFFFF',
    padding: 16,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  detailRow: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  label: {
    fontSize: 14,
    color: '#666',
    width: 120,
  },
  value: {
    fontSize: 14,
    color: '#333',
    flex: 1,
  },
  notesText: {
    fontSize: 14,
    color: '#333',
    lineHeight: 20,
  },
  imageContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
  },
  proofImage: {
    width: 100,
    height: 100,
    borderRadius: 8,
    marginRight: 8,
    marginBottom: 8,
  },
  rating: {
    fontSize: 24,
    marginBottom: 8,
  },
  review: {
    fontSize: 14,
    color: '#666',
    fontStyle: 'italic',
  },
});

export default DeliveryDetailsScreen;
```

### 5. Add to Navigation

In your navigation file (e.g., `navigation/AppNavigator.tsx`):

```typescript
import MyDeliveriesScreen from '../screens/MyDeliveriesScreen';
import DeliveryDetailsScreen from '../screens/DeliveryDetailsScreen';

// Inside your Stack Navigator
<Stack.Screen
  name="MyDeliveries"
  component={MyDeliveriesScreen}
  options={{ title: 'My Deliveries' }}
/>
<Stack.Screen
  name="DeliveryDetails"
  component={DeliveryDetailsScreen}
  options={{ title: 'Delivery Details' }}
/>
```

---

## Dependencies Required

Install these packages if you haven't already:

```bash
npm install axios @react-native-async-storage/async-storage
# or
yarn add axios @react-native-async-storage/async-storage
```

---

## Error Handling

Common errors and how to handle them:

| Status Code | Error | Solution |
|-------------|-------|----------|
| 401 | Unauthorized | Token expired or invalid - redirect to login |
| 403 | Forbidden | User doesn't have permission |
| 404 | Not Found | Delivery doesn't exist |
| 500 | Server Error | Show error message, retry option |

Example error handling:

```typescript
try {
  const response = await deliveryService.getMyDeliveries();
} catch (error: any) {
  if (error.response) {
    switch (error.response.status) {
      case 401:
        // Redirect to login
        navigation.navigate('Login');
        break;
      case 404:
        Alert.alert('Error', 'Delivery not found');
        break;
      default:
        Alert.alert('Error', 'Something went wrong. Please try again.');
    }
  }
}
```

---

## Testing

Test with different scenarios:

1. **Empty state**: User with no deliveries
2. **Pagination**: User with 20+ deliveries
3. **Filters**: Test each status filter
4. **Pull to refresh**: Verify refresh works
5. **Error states**: Test with invalid token
6. **Loading states**: Verify spinners appear

---

## Additional Features to Consider

1. **Real-time updates**: Use WebSocket for live delivery status updates
2. **Push notifications**: Notify users when delivery status changes
3. **Map view**: Show delivery route on a map
4. **Track delivery**: Real-time courier location tracking
5. **Cancel delivery**: Allow users to cancel pending deliveries
6. **Rate delivery**: Add rating and review after delivery

---

## Example Usage

```typescript
// Navigate to My Deliveries screen
navigation.navigate('MyDeliveries');

// Navigate to specific delivery
navigation.navigate('DeliveryDetails', { deliveryId: 'abc123' });

// Fetch deliveries programmatically
const deliveries = await deliveryService.getMyDeliveries({
  page: 1,
  page_size: 10,
  status: 'PENDING'
});
```
