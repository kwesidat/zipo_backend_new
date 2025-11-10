# Courier Feature Implementation Guide - React Native

This comprehensive guide will help you implement all courier-related features in your React Native app, including viewing available deliveries, accepting them, updating status, and allowing users to see courier details.

---

## Table of Contents

1. [Authentication Setup](#1-authentication-setup)
2. [API Service Configuration](#2-api-service-configuration)
3. [Courier Screens](#3-courier-screens)
4. [Customer Screens](#4-customer-screens)
5. [State Management](#5-state-management)
6. [Real-time Updates (Optional)](#6-real-time-updates-optional)
7. [Testing](#7-testing)

---

## 1. Authentication Setup

### Store User Token and Type

After login, make sure to store both the access token and user type:

```typescript
// services/authService.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

export const authService = {
  async login(email: string, password: string) {
    const response = await fetch('YOUR_API_URL/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    const data = await response.json();

    if (response.ok) {
      // Store token and user info
      await AsyncStorage.setItem('access_token', data.access_token);
      await AsyncStorage.setItem('user_type', data.user.user_type);
      await AsyncStorage.setItem('user_data', JSON.stringify(data.user));
      return data;
    }

    throw new Error(data.detail || 'Login failed');
  },

  async getToken() {
    return await AsyncStorage.getItem('access_token');
  },

  async getUserType() {
    return await AsyncStorage.getItem('user_type');
  },

  async logout() {
    await AsyncStorage.multiRemove(['access_token', 'user_type', 'user_data']);
  },
};
```

---

## 2. API Service Configuration

### Create a Delivery Service

```typescript
// services/deliveryService.ts
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL = 'YOUR_API_URL'; // e.g., http://192.168.1.100:8080

export interface Address {
  street: string;
  city: string;
  state: string;
  country: string;
  postal_code?: string;
  latitude?: number;
  longitude?: number;
}

export interface Delivery {
  id: string;
  order_id: string;
  courier_id?: string;
  pickup_address: Address;
  delivery_address: Address;
  pickup_contact_name?: string;
  pickup_contact_phone?: string;
  delivery_contact_name?: string;
  delivery_contact_phone?: string;
  delivery_fee: number;
  courier_fee: number;
  status: 'PENDING' | 'ACCEPTED' | 'PICKED_UP' | 'IN_TRANSIT' | 'DELIVERED' | 'CANCELLED';
  priority: 'STANDARD' | 'EXPRESS' | 'URGENT';
  notes?: string;
  courier_notes?: string;
  created_at: string;
  updated_at: string;
}

export const deliveryService = {
  // Get auth headers
  async getHeaders() {
    const token = await AsyncStorage.getItem('access_token');
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    };
  },

  // COURIER: Get available deliveries
  async getAvailableDeliveries(page = 1, pageSize = 20, priority?: string) {
    const headers = await this.getHeaders();
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      ...(priority && { priority }),
    });

    const response = await fetch(
      `${API_URL}/api/deliveries/available?${params}`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch available deliveries');
    }

    return await response.json();
  },

  // COURIER: Get my accepted deliveries
  async getCourierDeliveries(page = 1, pageSize = 20, status?: string) {
    const headers = await this.getHeaders();
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      ...(status && { status }),
    });

    const response = await fetch(
      `${API_URL}/api/deliveries/courier/my-deliveries?${params}`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch courier deliveries');
    }

    return await response.json();
  },

  // COURIER: Accept a delivery
  async acceptDelivery(
    deliveryId: string,
    estimatedPickupTime?: Date,
    estimatedDeliveryTime?: Date
  ) {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_URL}/api/deliveries/accept`, {
      method: 'POST',
      headers,
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

    return await response.json();
  },

  // COURIER: Update delivery status
  async updateDeliveryStatus(
    deliveryId: string,
    status: 'PICKED_UP' | 'IN_TRANSIT' | 'DELIVERED',
    notes?: string,
    location?: { latitude: number; longitude: number },
    proofOfDeliveryUrls?: string[],
    customerSignature?: string
  ) {
    const headers = await this.getHeaders();
    const response = await fetch(
      `${API_URL}/api/deliveries/${deliveryId}/status`,
      {
        method: 'PUT',
        headers,
        body: JSON.stringify({
          status,
          notes,
          location,
          proof_of_delivery_urls: proofOfDeliveryUrls,
          customer_signature: customerSignature,
        }),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update delivery status');
    }

    return await response.json();
  },

  // CUSTOMER: Get my scheduled deliveries
  async getMyDeliveries(page = 1, pageSize = 20, status?: string) {
    const headers = await this.getHeaders();
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
      ...(status && { status }),
    });

    const response = await fetch(
      `${API_URL}/api/deliveries/my-deliveries?${params}`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch my deliveries');
    }

    return await response.json();
  },

  // CUSTOMER: Get delivery details with courier info
  async getDeliveryDetails(deliveryId: string) {
    const headers = await this.getHeaders();
    const response = await fetch(
      `${API_URL}/api/deliveries/${deliveryId}`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch delivery details');
    }

    return await response.json();
  },

  // CUSTOMER: Get courier details for a delivery
  async getCourierDetails(deliveryId: string) {
    const headers = await this.getHeaders();
    const response = await fetch(
      `${API_URL}/api/deliveries/${deliveryId}/courier`,
      { headers }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to fetch courier details');
    }

    return await response.json();
  },

  // CUSTOMER: Schedule a delivery
  async scheduleDelivery(deliveryData: {
    pickup_address: Address;
    delivery_address: Address;
    pickup_contact_name: string;
    pickup_contact_phone: string;
    delivery_contact_name: string;
    delivery_contact_phone: string;
    priority: 'STANDARD' | 'EXPRESS' | 'URGENT';
    notes?: string;
    scheduled_date?: Date;
  }) {
    const headers = await this.getHeaders();
    const response = await fetch(`${API_URL}/api/deliveries/schedule`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        ...deliveryData,
        scheduled_date: deliveryData.scheduled_date?.toISOString(),
      }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to schedule delivery');
    }

    return await response.json();
  },
};
```

---

## 3. Courier Screens

### 3.1 Available Deliveries Screen (Courier)

```typescript
// screens/courier/AvailableDeliveriesScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  StyleSheet,
  Alert,
} from 'react-native';
import { deliveryService, Delivery } from '../../services/deliveryService';

export default function AvailableDeliveriesScreen({ navigation }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [page, setPage] = useState(1);

  useEffect(() => {
    loadDeliveries();
  }, []);

  const loadDeliveries = async () => {
    try {
      setLoading(true);
      const response = await deliveryService.getAvailableDeliveries(page, 20);
      setDeliveries(response.deliveries || []);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadDeliveries();
    setRefreshing(false);
  };

  const handleAcceptDelivery = async (deliveryId: string) => {
    Alert.alert(
      'Accept Delivery',
      'Are you sure you want to accept this delivery?',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Accept',
          onPress: async () => {
            try {
              await deliveryService.acceptDelivery(deliveryId);
              Alert.alert('Success', 'Delivery accepted successfully!');
              loadDeliveries(); // Refresh list
              navigation.navigate('MyDeliveries');
            } catch (error: any) {
              Alert.alert('Error', error.message);
            }
          },
        },
      ]
    );
  };

  const renderDeliveryCard = ({ item }: { item: Delivery }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate('DeliveryDetails', { deliveryId: item.id })}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.deliveryId}>#{item.id.slice(0, 8)}</Text>
        <View style={[styles.priorityBadge, getPriorityStyle(item.priority)]}>
          <Text style={styles.priorityText}>{item.priority}</Text>
        </View>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>Pickup:</Text>
        <Text style={styles.address}>
          {item.pickup_address.street}, {item.pickup_address.city}
        </Text>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>Delivery:</Text>
        <Text style={styles.address}>
          {item.delivery_address.street}, {item.delivery_address.city}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.fee}>Your Earnings: GHS {item.courier_fee}</Text>
        <TouchableOpacity
          style={styles.acceptButton}
          onPress={() => handleAcceptDelivery(item.id)}
        >
          <Text style={styles.acceptButtonText}>Accept</Text>
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );

  const getPriorityStyle = (priority: string) => {
    switch (priority) {
      case 'URGENT':
        return { backgroundColor: '#ff4444' };
      case 'EXPRESS':
        return { backgroundColor: '#ff9500' };
      default:
        return { backgroundColor: '#4CAF50' };
    }
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={deliveries}
        renderItem={renderDeliveryCard}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No available deliveries</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  card: {
    backgroundColor: 'white',
    margin: 10,
    padding: 15,
    borderRadius: 10,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  deliveryId: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  priorityBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 5,
  },
  priorityText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
  addressContainer: {
    marginBottom: 10,
  },
  label: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  address: {
    fontSize: 14,
    color: '#333',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  fee: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#4CAF50',
  },
  acceptButton: {
    backgroundColor: '#2196F3',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 5,
  },
  acceptButtonText: {
    color: 'white',
    fontWeight: 'bold',
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
  },
});
```

### 3.2 My Deliveries Screen (Courier)

```typescript
// screens/courier/MyDeliveriesScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  StyleSheet,
  Alert,
} from 'react-native';
import { deliveryService, Delivery } from '../../services/deliveryService';

export default function MyDeliveriesScreen({ navigation }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);

  useEffect(() => {
    loadDeliveries();
  }, [filterStatus]);

  const loadDeliveries = async () => {
    try {
      setLoading(true);
      const response = await deliveryService.getCourierDeliveries(1, 20, filterStatus);
      setDeliveries(response.deliveries || []);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadDeliveries();
    setRefreshing(false);
  };

  const handleUpdateStatus = async (
    deliveryId: string,
    currentStatus: string
  ) => {
    let nextStatus: 'PICKED_UP' | 'IN_TRANSIT' | 'DELIVERED';

    if (currentStatus === 'ACCEPTED') {
      nextStatus = 'PICKED_UP';
    } else if (currentStatus === 'PICKED_UP') {
      nextStatus = 'IN_TRANSIT';
    } else if (currentStatus === 'IN_TRANSIT') {
      nextStatus = 'DELIVERED';
    } else {
      return;
    }

    Alert.alert(
      'Update Status',
      `Change status to ${nextStatus}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Update',
          onPress: async () => {
            try {
              await deliveryService.updateDeliveryStatus(deliveryId, nextStatus);
              Alert.alert('Success', 'Status updated successfully!');
              loadDeliveries();
            } catch (error: any) {
              Alert.alert('Error', error.message);
            }
          },
        },
      ]
    );
  };

  const renderDeliveryCard = ({ item }: { item: Delivery }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() => navigation.navigate('DeliveryDetails', { deliveryId: item.id })}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.deliveryId}>#{item.id.slice(0, 8)}</Text>
        <View style={[styles.statusBadge, getStatusStyle(item.status)]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>Pickup:</Text>
        <Text style={styles.address}>
          {item.pickup_address.street}, {item.pickup_address.city}
        </Text>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>Delivery:</Text>
        <Text style={styles.address}>
          {item.delivery_address.street}, {item.delivery_address.city}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.fee}>GHS {item.courier_fee}</Text>
        {item.status !== 'DELIVERED' && item.status !== 'CANCELLED' && (
          <TouchableOpacity
            style={styles.updateButton}
            onPress={() => handleUpdateStatus(item.id, item.status)}
          >
            <Text style={styles.updateButtonText}>Update Status</Text>
          </TouchableOpacity>
        )}
      </View>
    </TouchableOpacity>
  );

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'DELIVERED':
        return { backgroundColor: '#4CAF50' };
      case 'IN_TRANSIT':
        return { backgroundColor: '#2196F3' };
      case 'PICKED_UP':
        return { backgroundColor: '#FF9800' };
      case 'ACCEPTED':
        return { backgroundColor: '#9C27B0' };
      default:
        return { backgroundColor: '#757575' };
    }
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={deliveries}
        renderItem={renderDeliveryCard}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No deliveries yet</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  card: {
    backgroundColor: 'white',
    margin: 10,
    padding: 15,
    borderRadius: 10,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  deliveryId: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 5,
  },
  statusText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
  addressContainer: {
    marginBottom: 10,
  },
  label: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  address: {
    fontSize: 14,
    color: '#333',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  fee: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#4CAF50',
  },
  updateButton: {
    backgroundColor: '#FF9800',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 5,
  },
  updateButtonText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 12,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
  },
});
```

---

## 4. Customer Screens

### 4.1 My Deliveries Screen (Customer)

```typescript
// screens/customer/MyDeliveriesScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  StyleSheet,
  Alert,
} from 'react-native';
import { deliveryService, Delivery } from '../../services/deliveryService';

export default function CustomerDeliveriesScreen({ navigation }) {
  const [deliveries, setDeliveries] = useState<Delivery[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDeliveries();
  }, []);

  const loadDeliveries = async () => {
    try {
      const response = await deliveryService.getMyDeliveries(1, 20);
      setDeliveries(response.deliveries || []);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    }
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadDeliveries();
    setRefreshing(false);
  };

  const renderDeliveryCard = ({ item }: { item: Delivery }) => (
    <TouchableOpacity
      style={styles.card}
      onPress={() =>
        navigation.navigate('DeliveryTracking', { deliveryId: item.id })
      }
    >
      <View style={styles.cardHeader}>
        <Text style={styles.deliveryId}>#{item.id.slice(0, 8)}</Text>
        <View style={[styles.statusBadge, getStatusStyle(item.status)]}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>From:</Text>
        <Text style={styles.address}>
          {item.pickup_address.street}, {item.pickup_address.city}
        </Text>
      </View>

      <View style={styles.addressContainer}>
        <Text style={styles.label}>To:</Text>
        <Text style={styles.address}>
          {item.delivery_address.street}, {item.delivery_address.city}
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.fee}>Fee: GHS {item.delivery_fee}</Text>
        {item.courier_id && (
          <TouchableOpacity
            style={styles.courierButton}
            onPress={() =>
              navigation.navigate('CourierDetails', {
                deliveryId: item.id,
              })
            }
          >
            <Text style={styles.courierButtonText}>View Courier</Text>
          </TouchableOpacity>
        )}
      </View>
    </TouchableOpacity>
  );

  const getStatusStyle = (status: string) => {
    switch (status) {
      case 'DELIVERED':
        return { backgroundColor: '#4CAF50' };
      case 'IN_TRANSIT':
        return { backgroundColor: '#2196F3' };
      case 'PICKED_UP':
        return { backgroundColor: '#FF9800' };
      case 'ACCEPTED':
        return { backgroundColor: '#9C27B0' };
      case 'PENDING':
        return { backgroundColor: '#FFC107' };
      default:
        return { backgroundColor: '#757575' };
    }
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={deliveries}
        renderItem={renderDeliveryCard}
        keyExtractor={(item) => item.id}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No deliveries yet</Text>
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  card: {
    backgroundColor: 'white',
    margin: 10,
    padding: 15,
    borderRadius: 10,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  deliveryId: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#333',
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 5,
  },
  statusText: {
    color: 'white',
    fontSize: 12,
    fontWeight: 'bold',
  },
  addressContainer: {
    marginBottom: 10,
  },
  label: {
    fontSize: 12,
    color: '#666',
    marginBottom: 2,
  },
  address: {
    fontSize: 14,
    color: '#333',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: '#eee',
  },
  fee: {
    fontSize: 16,
    fontWeight: 'bold',
    color: '#666',
  },
  courierButton: {
    backgroundColor: '#2196F3',
    paddingHorizontal: 15,
    paddingVertical: 8,
    borderRadius: 5,
  },
  courierButtonText: {
    color: 'white',
    fontWeight: 'bold',
    fontSize: 12,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
  },
});
```

### 4.2 Courier Details Screen (Customer)

```typescript
// screens/customer/CourierDetailsScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Linking,
  Alert,
} from 'react-native';
import { deliveryService } from '../../services/deliveryService';

export default function CourierDetailsScreen({ route }) {
  const { deliveryId } = route.params;
  const [courierData, setCourierData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCourierDetails();
  }, []);

  const loadCourierDetails = async () => {
    try {
      const data = await deliveryService.getCourierDetails(deliveryId);
      setCourierData(data);
    } catch (error: any) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCall = (phoneNumber: string) => {
    Linking.openURL(`tel:${phoneNumber}`);
  };

  if (loading) {
    return (
      <View style={styles.loadingContainer}>
        <ActivityIndicator size="large" color="#2196F3" />
      </View>
    );
  }

  if (!courierData?.courier_assigned) {
    return (
      <View style={styles.container}>
        <Text style={styles.emptyText}>
          {courierData?.message || 'No courier assigned yet'}
        </Text>
      </View>
    );
  }

  const { courier } = courierData;

  return (
    <View style={styles.container}>
      <View style={styles.card}>
        <View style={styles.header}>
          <Text style={styles.courierCode}>{courier.courier_code}</Text>
          <View style={styles.ratingContainer}>
            <Text style={styles.rating}>⭐ {courier.rating.toFixed(1)}</Text>
          </View>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.label}>Name:</Text>
          <Text style={styles.value}>{courier.name}</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.label}>Vehicle:</Text>
          <Text style={styles.value}>
            {courier.vehicle_type} - {courier.vehicle_number}
          </Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.label}>Experience:</Text>
          <Text style={styles.value}>
            {courier.completed_deliveries} / {courier.total_deliveries} deliveries
          </Text>
        </View>

        <TouchableOpacity
          style={styles.callButton}
          onPress={() => handleCall(courier.phone_number)}
        >
          <Text style={styles.callButtonText}>📞 Call Courier</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
    padding: 15,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  card: {
    backgroundColor: 'white',
    borderRadius: 10,
    padding: 20,
    elevation: 2,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingBottom: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  courierCode: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  ratingContainer: {
    backgroundColor: '#FFC107',
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 5,
  },
  rating: {
    fontSize: 16,
    fontWeight: 'bold',
    color: 'white',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 15,
  },
  label: {
    fontSize: 14,
    color: '#666',
    fontWeight: '500',
  },
  value: {
    fontSize: 14,
    color: '#333',
    fontWeight: 'bold',
  },
  callButton: {
    backgroundColor: '#4CAF50',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 20,
  },
  callButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold',
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginTop: 50,
  },
});
```

---

## 5. State Management

### Using Context API (Optional)

```typescript
// context/DeliveryContext.tsx
import React, { createContext, useState, useContext, useEffect } from 'react';
import { deliveryService, Delivery } from '../services/deliveryService';

interface DeliveryContextType {
  availableDeliveries: Delivery[];
  myDeliveries: Delivery[];
  loading: boolean;
  refreshAvailable: () => Promise<void>;
  refreshMyDeliveries: () => Promise<void>;
  acceptDelivery: (deliveryId: string) => Promise<void>;
  updateStatus: (deliveryId: string, status: string) => Promise<void>;
}

const DeliveryContext = createContext<DeliveryContextType | undefined>(undefined);

export const DeliveryProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [availableDeliveries, setAvailableDeliveries] = useState<Delivery[]>([]);
  const [myDeliveries, setMyDeliveries] = useState<Delivery[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshAvailable = async () => {
    try {
      setLoading(true);
      const response = await deliveryService.getAvailableDeliveries();
      setAvailableDeliveries(response.deliveries || []);
    } catch (error) {
      console.error('Error loading available deliveries:', error);
    } finally {
      setLoading(false);
    }
  };

  const refreshMyDeliveries = async () => {
    try {
      setLoading(true);
      const response = await deliveryService.getCourierDeliveries();
      setMyDeliveries(response.deliveries || []);
    } catch (error) {
      console.error('Error loading my deliveries:', error);
    } finally {
      setLoading(false);
    }
  };

  const acceptDelivery = async (deliveryId: string) => {
    await deliveryService.acceptDelivery(deliveryId);
    await refreshAvailable();
    await refreshMyDeliveries();
  };

  const updateStatus = async (deliveryId: string, status: any) => {
    await deliveryService.updateDeliveryStatus(deliveryId, status);
    await refreshMyDeliveries();
  };

  return (
    <DeliveryContext.Provider
      value={{
        availableDeliveries,
        myDeliveries,
        loading,
        refreshAvailable,
        refreshMyDeliveries,
        acceptDelivery,
        updateStatus,
      }}
    >
      {children}
    </DeliveryContext.Provider>
  );
};

export const useDelivery = () => {
  const context = useContext(DeliveryContext);
  if (!context) {
    throw new Error('useDelivery must be used within DeliveryProvider');
  }
  return context;
};
```

---

## 6. Real-time Updates (Optional)

### Using Polling

```typescript
// hooks/useDeliveryPolling.ts
import { useEffect, useRef } from 'react';

export const useDeliveryPolling = (
  refreshFunction: () => Promise<void>,
  interval = 30000 // 30 seconds
) => {
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Initial fetch
    refreshFunction();

    // Set up polling
    intervalRef.current = setInterval(() => {
      refreshFunction();
    }, interval);

    // Cleanup
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [refreshFunction, interval]);
};

// Usage in component:
// useDeliveryPolling(loadDeliveries, 30000);
```

---

## 7. Testing

### Test Endpoints with your React Native app

1. **Login as Courier**
2. **Navigate to Available Deliveries**
3. **Accept a delivery**
4. **Update delivery status**
5. **Login as Customer**
6. **View your deliveries**
7. **Check courier details**

---

## Summary of All Endpoints

### Courier Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/deliveries/available` | Get available deliveries to accept |
| GET | `/api/deliveries/courier/my-deliveries` | Get courier's accepted deliveries |
| POST | `/api/deliveries/accept` | Accept a delivery |
| PUT | `/api/deliveries/{delivery_id}/status` | Update delivery status |

### Customer Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/deliveries/schedule` | Schedule a new delivery |
| GET | `/api/deliveries/my-deliveries` | Get user's scheduled deliveries |
| GET | `/api/deliveries/{delivery_id}` | Get delivery details |
| GET | `/api/deliveries/{delivery_id}/courier` | Get courier details for delivery |

---

## Next Steps

1. **Install required packages:**
   ```bash
   npm install @react-navigation/native @react-navigation/stack @react-navigation/bottom-tabs
   npm install @react-native-async-storage/async-storage
   npm install react-native-gesture-handler react-native-reanimated react-native-screens
   ```

2. **Update API_URL** in deliveryService.ts with your backend URL (e.g., http://192.168.1.100:8080)

3. **Implement the screens** according to this guide

4. **Test each feature** thoroughly

5. **Consider adding:**
   - Push notifications for status updates
   - Real-time location tracking
   - Photo upload for proof of delivery
   - In-app messaging between courier and customer

---

## Troubleshooting

### Issue: 403 Error "Only couriers can view available deliveries"

**Solution:** The backend now includes user_type from database in the token. Make sure:
1. You're logged in as a courier (check `user_type` in AsyncStorage)
2. The courier profile exists in the database with `user_type` = "COURIER"
3. Token is valid and not expired

### Issue: Empty deliveries list

**Solution:**
1. Create test deliveries using the schedule endpoint or Swagger docs
2. Check network connection (test with `curl` or Postman)
3. Verify API_URL is correct in deliveryService.ts
4. Check backend logs for errors

### Issue: Network request failed

**Solution:**
1. Make sure backend is running
2. Use correct IP address (not localhost on physical device)
3. Check firewall settings
4. For Android emulator, use `10.0.2.2` instead of `localhost`

---

Good luck with your implementation! 🚀
