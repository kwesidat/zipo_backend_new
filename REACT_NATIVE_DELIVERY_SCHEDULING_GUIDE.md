# React Native Delivery Scheduling Implementation Guide

## Overview
This guide shows how to implement the delivery scheduling feature in your React Native mobile app for ZipoExpress standalone deliveries.

## API Endpoint
```
POST /api/deliveries/schedule
```

## Required Request Body

### TypeScript Interfaces

```typescript
interface DeliveryAddress {
  address: string;        // Required: Full address
  city: string;          // Required: City name
  country: string;       // Required: Country (e.g., "Ghana")
  latitude?: number;     // Optional: GPS coordinates
  longitude?: number;    // Optional: GPS coordinates
  additional_info?: string; // Optional: Landmarks, directions
}

interface ScheduleDeliveryRequest {
  pickup_address: DeliveryAddress;
  delivery_address: DeliveryAddress;
  pickup_contact_name: string;     // Required
  pickup_contact_phone: string;    // Required
  delivery_contact_name: string;   // Required
  delivery_contact_phone: string;  // Required
  priority: "STANDARD" | "EXPRESS" | "URGENT";  // Required
  scheduled_date?: string;         // Optional: ISO datetime
  notes?: string;                  // Optional: Special instructions
  item_description?: string;       // Optional: What's being delivered
}
```

## React Native Implementation

### 1. API Service Function

```typescript
// services/deliveryService.ts
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://your-api-url.com';

export const scheduleDelivery = async (deliveryData: ScheduleDeliveryRequest) => {
  try {
    // Get auth token
    const token = await AsyncStorage.getItem('authToken');

    if (!token) {
      throw new Error('Authentication required');
    }

    const response = await axios.post(
      `${API_BASE_URL}/api/deliveries/schedule`,
      deliveryData,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      // 422 Validation Error
      if (error.response?.status === 422) {
        throw new Error('Please fill in all required fields correctly');
      }
      // 401 Unauthorized
      if (error.response?.status === 401) {
        throw new Error('Please log in to schedule a delivery');
      }
      throw new Error(error.response?.data?.detail || 'Failed to schedule delivery');
    }
    throw error;
  }
};
```

### 2. Complete Screen Example

```typescript
// screens/ScheduleDeliveryScreen.tsx
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';
import { scheduleDelivery } from '../services/deliveryService';

const ScheduleDeliveryScreen = ({ navigation }) => {
  const [loading, setLoading] = useState(false);

  // Pickup details
  const [pickupAddress, setPickupAddress] = useState('');
  const [pickupCity, setPickupCity] = useState('');
  const [pickupContactName, setPickupContactName] = useState('');
  const [pickupContactPhone, setPickupContactPhone] = useState('');
  const [pickupLandmark, setPickupLandmark] = useState('');

  // Delivery details
  const [deliveryAddress, setDeliveryAddress] = useState('');
  const [deliveryCity, setDeliveryCity] = useState('');
  const [deliveryContactName, setDeliveryContactName] = useState('');
  const [deliveryContactPhone, setDeliveryContactPhone] = useState('');
  const [deliveryLandmark, setDeliveryLandmark] = useState('');

  // Other details
  const [priority, setPriority] = useState<'STANDARD' | 'EXPRESS' | 'URGENT'>('STANDARD');
  const [notes, setNotes] = useState('');
  const [itemDescription, setItemDescription] = useState('');

  const handleScheduleDelivery = async () => {
    // Validation
    if (!pickupAddress || !pickupCity || !pickupContactName || !pickupContactPhone) {
      Alert.alert('Error', 'Please fill in all pickup details');
      return;
    }

    if (!deliveryAddress || !deliveryCity || !deliveryContactName || !deliveryContactPhone) {
      Alert.alert('Error', 'Please fill in all delivery details');
      return;
    }

    setLoading(true);

    try {
      const deliveryData: ScheduleDeliveryRequest = {
        pickup_address: {
          address: pickupAddress,
          city: pickupCity,
          country: 'Ghana',
          additional_info: pickupLandmark || undefined,
        },
        delivery_address: {
          address: deliveryAddress,
          city: deliveryCity,
          country: 'Ghana',
          additional_info: deliveryLandmark || undefined,
        },
        pickup_contact_name: pickupContactName,
        pickup_contact_phone: pickupContactPhone,
        delivery_contact_name: deliveryContactName,
        delivery_contact_phone: deliveryContactPhone,
        priority: priority,
        notes: notes || undefined,
        item_description: itemDescription || undefined,
      };

      const result = await scheduleDelivery(deliveryData);

      Alert.alert(
        'Success',
        `Delivery scheduled successfully!\nDelivery Fee: GHS ${result.delivery_fee}`,
        [
          {
            text: 'OK',
            onPress: () => navigation.navigate('MyDeliveries'),
          },
        ]
      );
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to schedule delivery');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.sectionTitle}>Pickup Information</Text>

      <TextInput
        style={styles.input}
        placeholder="Pickup Address *"
        value={pickupAddress}
        onChangeText={setPickupAddress}
      />

      <TextInput
        style={styles.input}
        placeholder="City *"
        value={pickupCity}
        onChangeText={setPickupCity}
      />

      <TextInput
        style={styles.input}
        placeholder="Landmark (Optional)"
        value={pickupLandmark}
        onChangeText={setPickupLandmark}
      />

      <TextInput
        style={styles.input}
        placeholder="Contact Name *"
        value={pickupContactName}
        onChangeText={setPickupContactName}
      />

      <TextInput
        style={styles.input}
        placeholder="Contact Phone *"
        value={pickupContactPhone}
        onChangeText={setPickupContactPhone}
        keyboardType="phone-pad"
      />

      <Text style={styles.sectionTitle}>Delivery Information</Text>

      <TextInput
        style={styles.input}
        placeholder="Delivery Address *"
        value={deliveryAddress}
        onChangeText={setDeliveryAddress}
      />

      <TextInput
        style={styles.input}
        placeholder="City *"
        value={deliveryCity}
        onChangeText={setDeliveryCity}
      />

      <TextInput
        style={styles.input}
        placeholder="Landmark (Optional)"
        value={deliveryLandmark}
        onChangeText={setDeliveryLandmark}
      />

      <TextInput
        style={styles.input}
        placeholder="Contact Name *"
        value={deliveryContactName}
        onChangeText={setDeliveryContactName}
      />

      <TextInput
        style={styles.input}
        placeholder="Contact Phone *"
        value={deliveryContactPhone}
        onChangeText={setDeliveryContactPhone}
        keyboardType="phone-pad"
      />

      <Text style={styles.sectionTitle}>Delivery Options</Text>

      <View style={styles.priorityContainer}>
        <Text style={styles.label}>Priority:</Text>
        {(['STANDARD', 'EXPRESS', 'URGENT'] as const).map((p) => (
          <TouchableOpacity
            key={p}
            style={[
              styles.priorityButton,
              priority === p && styles.priorityButtonActive,
            ]}
            onPress={() => setPriority(p)}
          >
            <Text
              style={[
                styles.priorityText,
                priority === p && styles.priorityTextActive,
              ]}
            >
              {p}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <TextInput
        style={styles.input}
        placeholder="Item Description (Optional)"
        value={itemDescription}
        onChangeText={setItemDescription}
      />

      <TextInput
        style={[styles.input, styles.textArea]}
        placeholder="Special Instructions (Optional)"
        value={notes}
        onChangeText={setNotes}
        multiline
        numberOfLines={4}
      />

      <TouchableOpacity
        style={[styles.submitButton, loading && styles.submitButtonDisabled]}
        onPress={handleScheduleDelivery}
        disabled={loading}
      >
        {loading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.submitButtonText}>Schedule Delivery</Text>
        )}
      </TouchableOpacity>

      <View style={styles.priceInfo}>
        <Text style={styles.priceText}>💡 Pricing:</Text>
        <Text style={styles.priceDetail}>• Standard: Base rate</Text>
        <Text style={styles.priceDetail}>• Express: 1.5x base rate</Text>
        <Text style={styles.priceDetail}>• Urgent: 2x base rate</Text>
        <Text style={styles.priceDetail}>• Base: GHS 10 + GHS 2/km</Text>
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 16,
    backgroundColor: '#fff',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginTop: 20,
    marginBottom: 12,
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    fontSize: 16,
  },
  textArea: {
    height: 100,
    textAlignVertical: 'top',
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
    color: '#333',
  },
  priorityContainer: {
    marginBottom: 16,
  },
  priorityButton: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    marginBottom: 8,
    alignItems: 'center',
  },
  priorityButtonActive: {
    backgroundColor: '#007AFF',
    borderColor: '#007AFF',
  },
  priorityText: {
    fontSize: 16,
    color: '#333',
  },
  priorityTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
  submitButton: {
    backgroundColor: '#007AFF',
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 20,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
  priceInfo: {
    backgroundColor: '#f5f5f5',
    padding: 16,
    borderRadius: 8,
    marginBottom: 30,
  },
  priceText: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 8,
  },
  priceDetail: {
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
});

export default ScheduleDeliveryScreen;
```

### 3. With Google Places Autocomplete (Enhanced)

```typescript
// Install: npm install react-native-google-places-autocomplete

import { GooglePlacesAutocomplete } from 'react-native-google-places-autocomplete';

// Replace TextInput for address with:
<GooglePlacesAutocomplete
  placeholder="Pickup Address *"
  onPress={(data, details = null) => {
    setPickupAddress(data.description);
    if (details?.geometry?.location) {
      setPickupLatitude(details.geometry.location.lat);
      setPickupLongitude(details.geometry.location.lng);
    }
  }}
  query={{
    key: 'YOUR_GOOGLE_MAPS_API_KEY',
    language: 'en',
    components: 'country:gh', // Restrict to Ghana
  }}
  fetchDetails={true}
  styles={{
    textInput: styles.input,
  }}
/>
```

## API Response Example

```json
{
  "id": "uuid-delivery-id",
  "order_id": "uuid-order-id",
  "courier_id": null,
  "pickup_address": {
    "address": "123 Main St",
    "city": "Accra",
    "country": "Ghana",
    "additional_info": "Near Shell Station"
  },
  "delivery_address": {
    "address": "456 Oak Ave",
    "city": "Kumasi",
    "country": "Ghana"
  },
  "pickup_contact_name": "John Doe",
  "pickup_contact_phone": "+233241234567",
  "delivery_contact_name": "Jane Smith",
  "delivery_contact_phone": "+233241234568",
  "scheduled_by_user": "user-uuid",
  "scheduled_by_type": "CUSTOMER",
  "delivery_fee": 30.00,
  "courier_fee": 21.00,
  "platform_fee": 9.00,
  "distance_km": null,
  "status": "PENDING",
  "priority": "STANDARD",
  "scheduled_date": null,
  "notes": "Handle with care",
  "created_at": "2025-11-20T20:50:47.123Z",
  "updated_at": "2025-11-20T20:50:47.123Z"
}
```

## Common Error Codes

| Status Code | Meaning | Solution |
|-------------|---------|----------|
| 422 | Validation Error | Check all required fields are filled |
| 401 | Unauthorized | User not logged in or token expired |
| 500 | Server Error | Backend issue, try again later |

## Tracking Deliveries

After scheduling, users can track their deliveries using:

```typescript
// GET /api/deliveries/my-deliveries
const getMyDeliveries = async () => {
  const token = await AsyncStorage.getItem('authToken');

  const response = await axios.get(
    `${API_BASE_URL}/api/deliveries/my-deliveries?page=1&page_size=20`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    }
  );

  return response.data;
};
```

## Payment Integration (REQUIRED)

### ⚠️ IMPORTANT: Current Implementation Does NOT Include Payment

The backend currently creates deliveries with `paymentStatus: "PENDING"`. You **MUST** add payment before scheduling.

### Payment Flow

```
1. User fills form → 2. Calculate fee → 3. Pay via Paystack → 4. Schedule delivery
```

### Step 1: Add Payment Endpoints to Backend

First, you need to add these endpoints to your backend:

```python
# app/routes/delivery.py - ADD THESE ENDPOINTS

@router.post("/delivery/calculate-fee")
async def calculate_delivery_fee_endpoint(
    request: CalculateDeliveryFeeRequest,
    current_user=Depends(get_current_user)
):
    """Calculate delivery fee before payment"""
    try:
        # You can integrate Google Maps Distance API here
        distance_km = request.distance_km  # or calculate using addresses

        fee = calculate_delivery_fee(distance_km, request.priority)
        courier_fee, platform_fee = calculate_courier_and_platform_fees(fee)

        return {
            "delivery_fee": float(fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": distance_km,
            "priority": request.priority
        }
    except Exception as e:
        logger.error(f"Error calculating delivery fee: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate delivery fee"
        )


@router.post("/delivery/initialize-payment")
async def initialize_delivery_payment(
    request: ScheduleDeliveryRequest,
    current_user=Depends(get_current_user)
):
    """Initialize Paystack payment for delivery"""
    try:
        user_id = current_user["user_id"]
        user_email = current_user.get("email")

        # Calculate delivery fee
        distance_km = None  # Calculate from addresses if needed
        delivery_fee = calculate_delivery_fee(distance_km, request.priority.value)
        courier_fee, platform_fee = calculate_courier_and_platform_fees(delivery_fee)

        # Convert to kobo
        amount_in_kobo = int(float(delivery_fee) * 100)

        # Store delivery data temporarily (you'll need this after payment)
        temp_delivery_id = str(uuid.uuid4())

        metadata = {
            "userId": user_id,
            "transactionType": "delivery",
            "tempDeliveryId": temp_delivery_id,
            "deliveryData": {
                "pickup_address": request.pickup_address.dict(),
                "delivery_address": request.delivery_address.dict(),
                "pickup_contact_name": request.pickup_contact_name,
                "pickup_contact_phone": request.pickup_contact_phone,
                "delivery_contact_name": request.delivery_contact_name,
                "delivery_contact_phone": request.delivery_contact_phone,
                "priority": request.priority.value,
                "scheduled_date": request.scheduled_date.isoformat() if request.scheduled_date else None,
                "notes": request.notes,
                "item_description": request.item_description,
            },
            "deliveryFee": float(delivery_fee),
            "courierFee": float(courier_fee),
            "platformFee": float(platform_fee),
        }

        # Initialize Paystack payment
        callback_url = f"{os.getenv('NEXT_PUBLIC_BASE_URL')}/api/payment-callback"

        paystack_data = {
            "email": user_email,
            "amount": amount_in_kobo,
            "callback_url": callback_url,
            "channels": ["card", "bank", "ussd", "qr", "mobile_money", "bank_transfer"],
            "metadata": metadata
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{os.getenv('PAYSTACK_BASE_URL')}/transaction/initialize",
                json=paystack_data,
                headers={
                    "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to initialize payment"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment initialization failed"
            )

        data = paystack_response["data"]

        return {
            "authorization_url": data["authorization_url"],
            "access_code": data["access_code"],
            "reference": data["reference"],
            "delivery_fee": float(delivery_fee)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initializing delivery payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize payment"
        )


@router.post("/delivery/verify-and-schedule")
async def verify_payment_and_schedule_delivery(
    reference: str = Query(...),
    current_user=Depends(get_current_user)
):
    """Verify payment and create delivery after successful payment"""
    try:
        user_id = current_user["user_id"]

        # Verify payment with Paystack
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{os.getenv('PAYSTACK_BASE_URL')}/transaction/verify/{reference}",
                headers={
                    "Authorization": f"Bearer {os.getenv('PAYSTACK_SECRET_KEY')}"
                },
                timeout=30.0
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Payment verification failed"
            )

        paystack_response = response.json()

        if not paystack_response.get("status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment verification failed"
            )

        data = paystack_response["data"]

        if data["status"] != "success":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment was not successful"
            )

        # Get delivery data from metadata
        metadata = data.get("metadata", {})
        delivery_data = metadata.get("deliveryData", {})

        if metadata.get("userId") != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Unauthorized"
            )

        # Now create the delivery (similar to original schedule_delivery)
        order_id = str(uuid.uuid4())
        delivery_fee = Decimal(str(metadata["deliveryFee"]))
        courier_fee = Decimal(str(metadata["courierFee"]))
        platform_fee = Decimal(str(metadata["platformFee"]))

        # Create order with PAID status
        order_data = {
            "id": order_id,
            "userId": user_id,
            "subtotal": 0,
            "discountAmount": 0,
            "tax": 0,
            "deliveryFee": float(delivery_fee),
            "total": float(delivery_fee),
            "status": "PENDING",
            "paymentStatus": "PAID",  # ✅ Mark as PAID
            "currency": "GHS",
            "shippingAddress": delivery_data["delivery_address"],
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }

        order_response = supabase.table("Order").insert(order_data).execute()

        if not order_response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create order"
            )

        # Create delivery record
        delivery_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        delivery_record = {
            "id": delivery_id,
            "order_id": order_id,
            "pickup_address": delivery_data["pickup_address"],
            "delivery_address": delivery_data["delivery_address"],
            "pickup_contact_name": delivery_data["pickup_contact_name"],
            "pickup_contact_phone": delivery_data["pickup_contact_phone"],
            "delivery_contact_name": delivery_data["delivery_contact_name"],
            "delivery_contact_phone": delivery_data["delivery_contact_phone"],
            "scheduled_by_user": user_id,
            "scheduled_by_type": current_user.get("user_type", "CUSTOMER"),
            "delivery_fee": float(delivery_fee),
            "courier_fee": float(courier_fee),
            "platform_fee": float(platform_fee),
            "distance_km": None,
            "status": "PENDING",
            "priority": delivery_data["priority"],
            "scheduled_date": delivery_data.get("scheduled_date"),
            "notes": delivery_data.get("notes"),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        delivery_response = supabase.table("Delivery").insert(delivery_record).execute()

        if not delivery_response.data:
            # Rollback order
            supabase.table("Order").delete().eq("id", order_id).execute()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create delivery"
            )

        delivery = delivery_response.data[0]

        logger.info(f"✅ Paid delivery {delivery_id} created for user {user_id}")

        return {
            "delivery": delivery,
            "payment": {
                "reference": reference,
                "amount": data["amount"] / 100,
                "status": data["status"]
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying payment and scheduling: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process delivery"
        )
```

Add this model to `app/models/delivery.py`:

```python
class CalculateDeliveryFeeRequest(BaseModel):
    priority: DeliveryPriority = DeliveryPriority.STANDARD
    distance_km: Optional[float] = None
```

### Step 2: Update React Native Implementation

```typescript
// services/deliveryService.ts - UPDATED WITH PAYMENT

import { Linking } from 'react-native';

export const scheduleDeliveryWithPayment = async (deliveryData: ScheduleDeliveryRequest) => {
  try {
    const token = await AsyncStorage.getItem('authToken');

    if (!token) {
      throw new Error('Authentication required');
    }

    // Step 1: Initialize payment
    const paymentResponse = await axios.post(
      `${API_BASE_URL}/api/deliveries/delivery/initialize-payment`,
      deliveryData,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    const { authorization_url, reference, delivery_fee } = paymentResponse.data;

    // Step 2: Open Paystack payment page
    const supported = await Linking.canOpenURL(authorization_url);

    if (!supported) {
      throw new Error('Cannot open payment page');
    }

    await Linking.openURL(authorization_url);

    // Return payment details for verification later
    return {
      reference,
      delivery_fee,
      authorization_url,
    };

  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Failed to initialize payment');
    }
    throw error;
  }
};

export const verifyDeliveryPayment = async (reference: string) => {
  try {
    const token = await AsyncStorage.getItem('authToken');

    const response = await axios.post(
      `${API_BASE_URL}/api/deliveries/delivery/verify-and-schedule?reference=${reference}`,
      {},
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(error.response?.data?.detail || 'Payment verification failed');
    }
    throw error;
  }
};
```

### Step 3: Update Screen with Payment Flow

```typescript
// screens/ScheduleDeliveryScreen.tsx - UPDATED

const handleScheduleDelivery = async () => {
  // ... validation code ...

  setLoading(true);

  try {
    const deliveryData: ScheduleDeliveryRequest = {
      // ... same as before ...
    };

    // Initialize payment and get Paystack URL
    const paymentData = await scheduleDeliveryWithPayment(deliveryData);

    // Save reference for later verification
    await AsyncStorage.setItem('pending_delivery_reference', paymentData.reference);

    Alert.alert(
      'Payment Required',
      `Delivery Fee: GHS ${paymentData.delivery_fee}\n\nYou will be redirected to Paystack to complete payment.`,
      [
        {
          text: 'Cancel',
          style: 'cancel',
        },
        {
          text: 'Pay Now',
          onPress: () => {
            // Payment page already opened via Linking
            // Navigate to payment verification screen
            navigation.navigate('VerifyDeliveryPayment', {
              reference: paymentData.reference,
            });
          },
        },
      ]
    );
  } catch (error: any) {
    Alert.alert('Error', error.message || 'Failed to initialize payment');
  } finally {
    setLoading(false);
  }
};
```

### Step 4: Add Payment Verification Screen

```typescript
// screens/VerifyDeliveryPaymentScreen.tsx - NEW SCREEN

import React, { useEffect, useState } from 'react';
import { View, Text, ActivityIndicator, StyleSheet, Alert } from 'react-native';
import { verifyDeliveryPayment } from '../services/deliveryService';

const VerifyDeliveryPaymentScreen = ({ route, navigation }) => {
  const { reference } = route.params;
  const [verifying, setVerifying] = useState(true);

  useEffect(() => {
    verifyPayment();
  }, []);

  const verifyPayment = async () => {
    try {
      // Wait a bit for Paystack webhook to process
      await new Promise(resolve => setTimeout(resolve, 3000));

      const result = await verifyDeliveryPayment(reference);

      if (result.payment.status === 'success') {
        Alert.alert(
          'Success!',
          `Your delivery has been scheduled successfully!\n\nDelivery ID: ${result.delivery.id}\nPaid: GHS ${result.payment.amount}`,
          [
            {
              text: 'View Delivery',
              onPress: () => navigation.navigate('MyDeliveries'),
            },
          ]
        );
      } else {
        Alert.alert('Payment Failed', 'Your payment was not successful. Please try again.');
        navigation.goBack();
      }
    } catch (error: any) {
      Alert.alert('Error', error.message || 'Failed to verify payment');
      navigation.goBack();
    } finally {
      setVerifying(false);
    }
  };

  return (
    <View style={styles.container}>
      <ActivityIndicator size="large" color="#007AFF" />
      <Text style={styles.text}>Verifying payment...</Text>
      <Text style={styles.subtext}>Please wait</Text>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#fff',
  },
  text: {
    marginTop: 20,
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
  },
  subtext: {
    marginTop: 8,
    fontSize: 14,
    color: '#666',
  },
});

export default VerifyDeliveryPaymentScreen;
```

## Updated Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ 1. User fills delivery form                                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Click "Schedule & Pay" → Initialize Payment              │
│    POST /api/deliveries/delivery/initialize-payment         │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Open Paystack payment page in browser                    │
│    User completes payment (card/mobile money/bank)          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Verify payment & create delivery                         │
│    POST /api/deliveries/delivery/verify-and-schedule        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. Delivery created with paymentStatus: "PAID"              │
│    Status: "PENDING" (waiting for courier)                  │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

1. **Track Delivery Status** - Show real-time delivery status updates
2. **Courier Info** - Display assigned courier details
3. **GPS Tracking** - Show courier location on map
4. **Push Notifications** - Notify users of status changes

## Pricing Calculation

The backend calculates fees as:
- **Base Fee**: GHS 10
- **Distance Fee**: GHS 2 per km (if distance calculated)
- **Priority Multiplier**:
  - STANDARD: 1.0x
  - EXPRESS: 1.5x
  - URGENT: 2.0x
- **Courier Fee**: 70% of total
- **Platform Fee**: 30% of total

**Example**: 10km delivery with EXPRESS priority
- Base: GHS 10
- Distance: GHS 20 (10km × 2)
- Subtotal: GHS 30
- With EXPRESS: GHS 45 (30 × 1.5)
- Courier gets: GHS 31.50
- Platform gets: GHS 13.50
