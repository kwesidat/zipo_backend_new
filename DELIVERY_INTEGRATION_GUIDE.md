# ZipoHub Delivery System - React Native Integration Guide

## 📱 Overview

This guide shows how to integrate the ZipoHub delivery system into your React Native app. The system supports two delivery cases:

1. **Case 1**: Order with Courier Delivery - Customer buys a product and requests courier delivery
2. **Case 2**: ZipoExpress Standalone Delivery - Customer schedules a delivery/errand without purchasing a product

---

## 🔐 Authentication

All delivery endpoints require authentication. Include the JWT token in the Authorization header:

```javascript
const API_BASE_URL = 'https://your-api-url.com/api';

// Get token from your auth storage
const token = await AsyncStorage.getItem('accessToken');

const headers = {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token}`,
};
```

---

## 📦 Case 1: Order with Courier Delivery

### Step 1: Update Your Checkout Screen

Add courier delivery options to your checkout/buy-now form:

```javascript
import React, { useState } from 'react';
import { View, Text, Switch, Picker } from 'react-native';

const CheckoutScreen = () => {
  const [enableCourierDelivery, setEnableCourierDelivery] = useState(false);
  const [deliveryPriority, setDeliveryPriority] = useState('STANDARD');
  const [deliveryNotes, setDeliveryNotes] = useState('');
  const [shippingAddress, setShippingAddress] = useState({
    name: '',
    phone: '',
    address: '',
    city: '',
    country: '',
    additionalInfo: ''
  });

  return (
    <View>
      {/* Shipping Address Form */}
      <TextInput
        placeholder="Full Name"
        value={shippingAddress.name}
        onChangeText={(text) => setShippingAddress({...shippingAddress, name: text})}
      />
      <TextInput
        placeholder="Phone Number"
        value={shippingAddress.phone}
        onChangeText={(text) => setShippingAddress({...shippingAddress, phone: text})}
      />
      <TextInput
        placeholder="Address"
        value={shippingAddress.address}
        onChangeText={(text) => setShippingAddress({...shippingAddress, address: text})}
      />
      <TextInput
        placeholder="City"
        value={shippingAddress.city}
        onChangeText={(text) => setShippingAddress({...shippingAddress, city: text})}
      />
      <TextInput
        placeholder="Country"
        value={shippingAddress.country}
        onChangeText={(text) => setShippingAddress({...shippingAddress, country: text})}
      />

      {/* Courier Delivery Option */}
      <View style={{ flexDirection: 'row', alignItems: 'center', marginTop: 20 }}>
        <Text>Enable Courier Delivery</Text>
        <Switch
          value={enableCourierDelivery}
          onValueChange={setEnableCourierDelivery}
        />
      </View>

      {enableCourierDelivery && (
        <View>
          <Text>Delivery Priority</Text>
          <Picker
            selectedValue={deliveryPriority}
            onValueChange={(value) => setDeliveryPriority(value)}
          >
            <Picker.Item label="Standard (Normal delivery)" value="STANDARD" />
            <Picker.Item label="Express (Faster delivery)" value="EXPRESS" />
            <Picker.Item label="Urgent (Same day)" value="URGENT" />
          </Picker>

          <TextInput
            placeholder="Delivery Notes (Optional)"
            value={deliveryNotes}
            onChangeText={setDeliveryNotes}
            multiline
          />
        </View>
      )}
    </View>
  );
};
```

### Step 2: Call Buy Now API with Delivery Options

```javascript
const buyNowWithDelivery = async (productId, quantity) => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/buy-now`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        productId: productId,
        quantity: quantity,
        shippingAddress: {
          name: shippingAddress.name,
          phone: shippingAddress.phone,
          address: shippingAddress.address,
          city: shippingAddress.city,
          country: shippingAddress.country,
          additionalInfo: shippingAddress.additionalInfo
        },
        paymentGateway: 'PAYSTACK',
        discountCode: null, // Optional

        // Delivery options
        enableCourierDelivery: enableCourierDelivery,
        deliveryPriority: deliveryPriority, // 'STANDARD', 'EXPRESS', or 'URGENT'
        deliveryNotes: deliveryNotes, // Optional
      }),
    });

    const data = await response.json();

    if (response.ok) {
      // Redirect to Paystack payment page
      const { authorization_url, order_id } = data;

      // Open payment URL in WebView or browser
      navigation.navigate('PaymentWebView', {
        url: authorization_url,
        orderId: order_id
      });
    } else {
      Alert.alert('Error', data.detail || 'Failed to initialize payment');
    }
  } catch (error) {
    console.error('Buy now error:', error);
    Alert.alert('Error', 'Failed to process request');
  }
};
```

### Step 3: Call Checkout API (for cart purchases)

```javascript
const checkoutCartWithDelivery = async () => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/checkout`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        shippingAddress: {
          name: shippingAddress.name,
          phone: shippingAddress.phone,
          address: shippingAddress.address,
          city: shippingAddress.city,
          country: shippingAddress.country,
          additionalInfo: shippingAddress.additionalInfo
        },
        paymentGateway: 'PAYSTACK',
        discountCode: null, // Optional

        // Delivery options
        enableCourierDelivery: enableCourierDelivery,
        deliveryPriority: deliveryPriority,
        deliveryNotes: deliveryNotes,
      }),
    });

    const data = await response.json();

    if (response.ok) {
      // Redirect to Paystack payment page
      const { authorization_url, order_id } = data;

      navigation.navigate('PaymentWebView', {
        url: authorization_url,
        orderId: order_id
      });
    } else {
      Alert.alert('Error', data.detail || 'Failed to checkout');
    }
  } catch (error) {
    console.error('Checkout error:', error);
    Alert.alert('Error', 'Failed to process checkout');
  }
};
```

### Step 4: After Payment, Delivery is Auto-Created

When the customer completes payment, the backend automatically creates a delivery record with status `PENDING`. Couriers can now see this delivery and accept it.

---

## 🚚 Case 2: ZipoExpress Standalone Delivery

### Step 1: Create ZipoExpress Screen

```javascript
import React, { useState } from 'react';
import { View, Text, TextInput, Button, Alert } from 'react-native';

const ZipoExpressScreen = () => {
  const [pickupAddress, setPickupAddress] = useState({
    address: '',
    city: '',
    country: '',
    latitude: null,
    longitude: null,
    additional_info: ''
  });

  const [deliveryAddress, setDeliveryAddress] = useState({
    address: '',
    city: '',
    country: '',
    latitude: null,
    longitude: null,
    additional_info: ''
  });

  const [pickupContactName, setPickupContactName] = useState('');
  const [pickupContactPhone, setPickupContactPhone] = useState('');
  const [deliveryContactName, setDeliveryContactName] = useState('');
  const [deliveryContactPhone, setDeliveryContactPhone] = useState('');
  const [priority, setPriority] = useState('STANDARD');
  const [notes, setNotes] = useState('');
  const [itemDescription, setItemDescription] = useState('');

  return (
    <ScrollView style={{ padding: 20 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 20 }}>
        Schedule a Delivery
      </Text>

      {/* Pickup Details */}
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginTop: 20 }}>
        Pickup Information
      </Text>
      <TextInput
        placeholder="Pickup Contact Name"
        value={pickupContactName}
        onChangeText={setPickupContactName}
      />
      <TextInput
        placeholder="Pickup Contact Phone"
        value={pickupContactPhone}
        onChangeText={setPickupContactPhone}
      />
      <TextInput
        placeholder="Pickup Address"
        value={pickupAddress.address}
        onChangeText={(text) => setPickupAddress({...pickupAddress, address: text})}
      />
      <TextInput
        placeholder="Pickup City"
        value={pickupAddress.city}
        onChangeText={(text) => setPickupAddress({...pickupAddress, city: text})}
      />
      <TextInput
        placeholder="Pickup Country"
        value={pickupAddress.country}
        onChangeText={(text) => setPickupAddress({...pickupAddress, country: text})}
      />

      {/* Delivery Details */}
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginTop: 20 }}>
        Delivery Information
      </Text>
      <TextInput
        placeholder="Delivery Contact Name"
        value={deliveryContactName}
        onChangeText={setDeliveryContactName}
      />
      <TextInput
        placeholder="Delivery Contact Phone"
        value={deliveryContactPhone}
        onChangeText={setDeliveryContactPhone}
      />
      <TextInput
        placeholder="Delivery Address"
        value={deliveryAddress.address}
        onChangeText={(text) => setDeliveryAddress({...deliveryAddress, address: text})}
      />
      <TextInput
        placeholder="Delivery City"
        value={deliveryAddress.city}
        onChangeText={(text) => setDeliveryAddress({...deliveryAddress, city: text})}
      />
      <TextInput
        placeholder="Delivery Country"
        value={deliveryAddress.country}
        onChangeText={(text) => setDeliveryAddress({...deliveryAddress, country: text})}
      />

      {/* Additional Info */}
      <Text style={{ fontSize: 18, fontWeight: 'bold', marginTop: 20 }}>
        Additional Details
      </Text>
      <Picker
        selectedValue={priority}
        onValueChange={(value) => setPriority(value)}
      >
        <Picker.Item label="Standard" value="STANDARD" />
        <Picker.Item label="Express" value="EXPRESS" />
        <Picker.Item label="Urgent" value="URGENT" />
      </Picker>

      <TextInput
        placeholder="Item Description (What are you sending?)"
        value={itemDescription}
        onChangeText={setItemDescription}
      />

      <TextInput
        placeholder="Special Instructions"
        value={notes}
        onChangeText={setNotes}
        multiline
      />

      <Button title="Schedule Delivery" onPress={scheduleDelivery} />
    </ScrollView>
  );
};
```

### Step 2: Call Schedule Delivery API

```javascript
const scheduleDelivery = async () => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/deliveries/schedule`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        pickup_address: {
          address: pickupAddress.address,
          city: pickupAddress.city,
          country: pickupAddress.country,
          latitude: pickupAddress.latitude,
          longitude: pickupAddress.longitude,
          additional_info: pickupAddress.additional_info
        },
        delivery_address: {
          address: deliveryAddress.address,
          city: deliveryAddress.city,
          country: deliveryAddress.country,
          latitude: deliveryAddress.latitude,
          longitude: deliveryAddress.longitude,
          additional_info: deliveryAddress.additional_info
        },
        pickup_contact_name: pickupContactName,
        pickup_contact_phone: pickupContactPhone,
        delivery_contact_name: deliveryContactName,
        delivery_contact_phone: deliveryContactPhone,
        priority: priority, // 'STANDARD', 'EXPRESS', or 'URGENT'
        notes: notes,
        item_description: itemDescription,
        scheduled_date: null, // Optional: ISO datetime string
      }),
    });

    const data = await response.json();

    if (response.ok) {
      Alert.alert(
        'Success',
        `Delivery scheduled! ID: ${data.id}\nFee: GHS ${data.delivery_fee}\nCouriers will be able to see and accept this delivery.`,
        [
          { text: 'OK', onPress: () => navigation.navigate('MyDeliveries') }
        ]
      );
    } else {
      Alert.alert('Error', data.detail || 'Failed to schedule delivery');
    }
  } catch (error) {
    console.error('Schedule delivery error:', error);
    Alert.alert('Error', 'Failed to schedule delivery');
  }
};
```

---

## 🚴 Courier App Features

### View Available Deliveries

```javascript
const fetchAvailableDeliveries = async (page = 1, priority = null) => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    let url = `${API_BASE_URL}/deliveries/available?page=${page}&page_size=20`;
    if (priority) {
      url += `&priority=${priority}`;
    }

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();

    if (response.ok) {
      // data contains: deliveries, total_count, page, total_pages, has_next, has_previous
      setDeliveries(data.deliveries);
      setTotalPages(data.total_pages);
    } else {
      Alert.alert('Error', data.detail || 'Failed to fetch deliveries');
    }
  } catch (error) {
    console.error('Fetch deliveries error:', error);
  }
};
```

### Display Available Deliveries

```javascript
const AvailableDeliveriesScreen = () => {
  const [deliveries, setDeliveries] = useState([]);

  useEffect(() => {
    fetchAvailableDeliveries();
  }, []);

  return (
    <FlatList
      data={deliveries}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => (
        <View style={styles.deliveryCard}>
          <Text style={styles.deliveryId}>Delivery #{item.id.slice(0, 8)}</Text>

          <Text style={styles.label}>Pickup:</Text>
          <Text>{item.pickup_address.address}, {item.pickup_address.city}</Text>
          <Text>Contact: {item.pickup_contact_name} - {item.pickup_contact_phone}</Text>

          <Text style={styles.label}>Delivery:</Text>
          <Text>{item.delivery_address.address}, {item.delivery_address.city}</Text>
          <Text>Contact: {item.delivery_contact_name} - {item.delivery_contact_phone}</Text>

          <Text style={styles.fee}>Fee: GHS {item.delivery_fee}</Text>
          <Text style={styles.courierFee}>You earn: GHS {item.courier_fee}</Text>
          <Text style={styles.priority}>Priority: {item.priority}</Text>

          {item.notes && (
            <Text style={styles.notes}>Notes: {item.notes}</Text>
          )}

          <Button
            title="Accept Delivery"
            onPress={() => acceptDelivery(item.id)}
          />
        </View>
      )}
    />
  );
};
```

### Accept Delivery

```javascript
const acceptDelivery = async (deliveryId) => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/deliveries/accept`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        delivery_id: deliveryId,
        estimated_pickup_time: null, // Optional: ISO datetime
        estimated_delivery_time: null, // Optional: ISO datetime
      }),
    });

    const data = await response.json();

    if (response.ok) {
      Alert.alert(
        'Success',
        'Delivery accepted! You can now proceed to pick up the item.',
        [
          { text: 'View Details', onPress: () => navigation.navigate('DeliveryDetails', { deliveryId }) }
        ]
      );
    } else {
      Alert.alert('Error', data.detail || 'Failed to accept delivery');
    }
  } catch (error) {
    console.error('Accept delivery error:', error);
    Alert.alert('Error', 'Failed to accept delivery');
  }
};
```

### Update Delivery Status

```javascript
const updateDeliveryStatus = async (deliveryId, newStatus, notes = '') => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/deliveries/${deliveryId}/status`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        status: newStatus, // 'PICKED_UP', 'IN_TRANSIT', 'DELIVERED', etc.
        notes: notes,
        location: null, // Optional: { latitude: 6.5, longitude: -1.5 }
        proof_of_delivery_urls: [], // Optional: Array of image URLs
        customer_signature: null, // Optional: Signature image URL
      }),
    });

    const data = await response.json();

    if (response.ok) {
      Alert.alert('Success', `Delivery status updated to ${newStatus}`);
      // Refresh delivery details
      fetchDeliveryDetails(deliveryId);
    } else {
      Alert.alert('Error', data.detail || 'Failed to update status');
    }
  } catch (error) {
    console.error('Update status error:', error);
    Alert.alert('Error', 'Failed to update delivery status');
  }
};
```

### Courier Delivery Flow Component

```javascript
const CourierDeliveryFlow = ({ deliveryId }) => {
  const [delivery, setDelivery] = useState(null);
  const [currentStatus, setCurrentStatus] = useState('ACCEPTED');

  const statusFlow = [
    { status: 'ACCEPTED', label: 'Accepted', action: 'Mark as Picked Up' },
    { status: 'PICKED_UP', label: 'Picked Up', action: 'Start Delivery' },
    { status: 'IN_TRANSIT', label: 'In Transit', action: 'Mark as Delivered' },
    { status: 'DELIVERED', label: 'Delivered', action: 'Complete' },
  ];

  const nextStatus = () => {
    const currentIndex = statusFlow.findIndex(s => s.status === currentStatus);
    if (currentIndex < statusFlow.length - 1) {
      return statusFlow[currentIndex + 1].status;
    }
    return null;
  };

  const handleStatusUpdate = () => {
    const next = nextStatus();
    if (next) {
      updateDeliveryStatus(deliveryId, next, '');
      setCurrentStatus(next);
    }
  };

  return (
    <View>
      <Text>Current Status: {currentStatus}</Text>

      {statusFlow.map((step, index) => (
        <View key={step.status} style={{
          flexDirection: 'row',
          alignItems: 'center',
          opacity: currentStatus === step.status ? 1 : 0.5
        }}>
          <View style={{
            width: 30,
            height: 30,
            borderRadius: 15,
            backgroundColor: currentStatus === step.status ? 'green' : 'gray',
            justifyContent: 'center',
            alignItems: 'center'
          }}>
            <Text style={{ color: 'white' }}>{index + 1}</Text>
          </View>
          <Text style={{ marginLeft: 10 }}>{step.label}</Text>
        </View>
      ))}

      {currentStatus !== 'DELIVERED' && (
        <Button
          title={statusFlow.find(s => s.status === currentStatus)?.action || 'Update'}
          onPress={handleStatusUpdate}
        />
      )}
    </View>
  );
};
```

---

## 📊 Get Delivery Details

```javascript
const fetchDeliveryDetails = async (deliveryId) => {
  try {
    const token = await AsyncStorage.getItem('accessToken');

    const response = await fetch(`${API_BASE_URL}/deliveries/${deliveryId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    const data = await response.json();

    if (response.ok) {
      setDelivery(data);
      // data contains all delivery information including:
      // - id, order_id, courier_id
      // - pickup_address, delivery_address
      // - pickup_contact_name, pickup_contact_phone
      // - delivery_contact_name, delivery_contact_phone
      // - status, priority, delivery_fee, courier_fee
      // - estimated_pickup_time, estimated_delivery_time
      // - actual_pickup_time, actual_delivery_time
      // - notes, courier_notes, proof_of_delivery
    } else {
      Alert.alert('Error', data.detail || 'Failed to fetch delivery details');
    }
  } catch (error) {
    console.error('Fetch delivery details error:', error);
  }
};
```

---

## 📍 Delivery Status Values

```javascript
const DELIVERY_STATUSES = {
  PENDING: 'PENDING',           // Waiting for courier to accept
  ASSIGNED: 'ASSIGNED',         // Reserved (not used currently)
  ACCEPTED: 'ACCEPTED',         // Courier accepted the delivery
  PICKED_UP: 'PICKED_UP',      // Courier picked up from seller/pickup location
  IN_TRANSIT: 'IN_TRANSIT',    // Courier is on the way to delivery
  DELIVERED: 'DELIVERED',       // Successfully delivered
  CANCELLED: 'CANCELLED',       // Delivery cancelled
  FAILED: 'FAILED',            // Delivery failed
};

const DELIVERY_PRIORITIES = {
  STANDARD: 'STANDARD',  // Normal delivery (1x base fee)
  EXPRESS: 'EXPRESS',    // Faster delivery (1.5x base fee)
  URGENT: 'URGENT',      // Same-day delivery (2x base fee)
};
```

---

## 💰 Pricing Information

```javascript
// Delivery Fee Calculation
// Base fee: GHS 10.00
// Distance fee: GHS 2.00 per km (default GHS 20 if no distance)
// Priority multiplier:
//   - STANDARD: 1.0x
//   - EXPRESS: 1.5x
//   - URGENT: 2.0x
//
// Courier gets 70% of delivery fee
// Platform gets 30% of delivery fee

const calculateEstimatedFee = (distanceKm, priority) => {
  const baseFee = 10;
  const distanceFee = distanceKm ? distanceKm * 2 : 20;

  const multipliers = {
    'STANDARD': 1.0,
    'EXPRESS': 1.5,
    'URGENT': 2.0,
  };

  const totalFee = (baseFee + distanceFee) * multipliers[priority];
  const courierFee = totalFee * 0.7;
  const platformFee = totalFee * 0.3;

  return {
    totalFee: totalFee.toFixed(2),
    courierFee: courierFee.toFixed(2),
    platformFee: platformFee.toFixed(2),
  };
};
```

---

## 🎨 Complete Example Component

```javascript
// DeliveryTrackingScreen.js
import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Button, ScrollView } from 'react-native';

const DeliveryTrackingScreen = ({ route }) => {
  const { deliveryId } = route.params;
  const [delivery, setDelivery] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDeliveryDetails();
    // Poll for updates every 30 seconds
    const interval = setInterval(fetchDeliveryDetails, 30000);
    return () => clearInterval(interval);
  }, [deliveryId]);

  const fetchDeliveryDetails = async () => {
    try {
      const token = await AsyncStorage.getItem('accessToken');
      const response = await fetch(`${API_BASE_URL}/deliveries/${deliveryId}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      const data = await response.json();
      if (response.ok) {
        setDelivery(data);
      }
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading || !delivery) {
    return <Text>Loading...</Text>;
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Delivery Tracking</Text>
      <Text style={styles.deliveryId}>#{delivery.id.slice(0, 8)}</Text>

      {/* Status */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Status</Text>
        <Text style={[styles.status, { color: getStatusColor(delivery.status) }]}>
          {delivery.status}
        </Text>
        <Text style={styles.priority}>Priority: {delivery.priority}</Text>
      </View>

      {/* Pickup Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📍 Pickup Location</Text>
        <Text>{delivery.pickup_address.address}</Text>
        <Text>{delivery.pickup_address.city}, {delivery.pickup_address.country}</Text>
        <Text style={styles.contact}>
          Contact: {delivery.pickup_contact_name} - {delivery.pickup_contact_phone}
        </Text>
      </View>

      {/* Delivery Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>📦 Delivery Location</Text>
        <Text>{delivery.delivery_address.address}</Text>
        <Text>{delivery.delivery_address.city}, {delivery.delivery_address.country}</Text>
        <Text style={styles.contact}>
          Contact: {delivery.delivery_contact_name} - {delivery.delivery_contact_phone}
        </Text>
      </View>

      {/* Fee Info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>💰 Fee Information</Text>
        <Text>Delivery Fee: GHS {delivery.delivery_fee}</Text>
        {delivery.courier_fee && (
          <Text>Courier Earnings: GHS {delivery.courier_fee}</Text>
        )}
      </View>

      {/* Timeline */}
      {delivery.actual_pickup_time && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>⏱️ Timeline</Text>
          <Text>Picked up: {new Date(delivery.actual_pickup_time).toLocaleString()}</Text>
          {delivery.actual_delivery_time && (
            <Text>Delivered: {new Date(delivery.actual_delivery_time).toLocaleString()}</Text>
          )}
        </View>
      )}

      {/* Notes */}
      {delivery.notes && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>📝 Notes</Text>
          <Text>{delivery.notes}</Text>
        </View>
      )}
    </ScrollView>
  );
};

const getStatusColor = (status) => {
  const colors = {
    'PENDING': '#FFA500',
    'ACCEPTED': '#4169E1',
    'PICKED_UP': '#9370DB',
    'IN_TRANSIT': '#00BFFF',
    'DELIVERED': '#32CD32',
    'CANCELLED': '#DC143C',
    'FAILED': '#8B0000',
  };
  return colors[status] || '#000000';
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  deliveryId: {
    fontSize: 16,
    color: '#666',
    marginBottom: 20,
  },
  section: {
    marginBottom: 20,
    padding: 15,
    backgroundColor: '#f5f5f5',
    borderRadius: 8,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  status: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 5,
  },
  priority: {
    fontSize: 14,
    color: '#666',
  },
  contact: {
    marginTop: 5,
    fontWeight: '500',
  },
});

export default DeliveryTrackingScreen;
```

---

## 🔔 Best Practices

1. **Error Handling**: Always wrap API calls in try-catch blocks
2. **Loading States**: Show loading indicators during API calls
3. **Token Refresh**: Implement automatic token refresh when it expires
4. **Real-time Updates**: Poll for delivery status updates every 30-60 seconds
5. **Offline Support**: Cache delivery data locally for offline viewing
6. **Push Notifications**: Integrate with Firebase/OneSignal for delivery status updates
7. **Location Tracking**: Use React Native Geolocation for courier location tracking
8. **Image Upload**: For proof of delivery, use image picker and upload to your storage

---

## 📚 API Endpoints Summary

| Method | Endpoint | Description | User Type |
|--------|----------|-------------|-----------|
| POST | `/api/buy-now` | Buy product with optional courier delivery | Customer |
| POST | `/api/checkout` | Checkout cart with optional courier delivery | Customer |
| POST | `/api/deliveries/schedule` | Schedule standalone delivery (ZipoExpress) | Customer |
| GET | `/api/deliveries/available` | View available deliveries | Courier |
| POST | `/api/deliveries/accept` | Accept a delivery | Courier |
| GET | `/api/deliveries/{id}` | Get delivery details | Customer/Courier |
| PUT | `/api/deliveries/{id}/status` | Update delivery status | Courier |

---

## 🎯 Next Steps

1. Implement push notifications for delivery updates
2. Add real-time location tracking for couriers
3. Integrate Google Maps for distance calculation
4. Add image upload for proof of delivery
5. Implement rating system for couriers and customers
6. Add delivery history and analytics screens

---

## 🆘 Support

For any issues or questions, please contact the development team or check the API documentation at `/docs`.
