# Delivery Fee Calculation Guide - Free Delivery & Distance-Based Fees

## Overview
This guide explains how to implement delivery fee calculations in your React Native app based on:
- **Product `free_delivery` status**: Free delivery if `true`, calculated fee if `false`
- **Distance calculation**: Using vendor and customer latitude/longitude
- **Rate**: **GHS 20 per kilometer**

---

## Business Logic

### Delivery Fee Rules

1. **If product has `free_delivery = true`**
   - Delivery fee = **GHS 0**
   - No distance calculation needed

2. **If product has `free_delivery = false`**
   - Calculate distance between vendor and customer using their lat/long
   - Delivery fee = **Distance (km) × GHS 20**
   - Example: 3.5 km × GHS 20 = **GHS 70**

3. **Multi-seller orders**
   - Calculate delivery fee per seller/vendor
   - Each vendor's location is used for their products
   - Total delivery fee = Sum of all vendor delivery fees

---

## Backend Implementation

### 1. Delivery Utilities Created ✓

**File:** `app/utils/delivery_utils.py`

Key functions:
```python
# Calculate distance using Haversine formula
def calculate_distance_haversine(lat1, lon1, lat2, lon2) -> float

# Calculate delivery fee for single product
def calculate_delivery_fee_for_product(
    product_free_delivery,
    vendor_lat, vendor_lon,
    customer_lat, customer_lon
) -> Tuple[Decimal, Optional[float]]

# Calculate delivery fees for entire order
def calculate_order_delivery_fees(
    cart_items,
    customer_lat,
    customer_lon
) -> dict

# Fetch vendor location from database
def get_vendor_location_from_db(supabase_client, seller_id) -> Tuple[lat, lon]
```

### 2. Distance Calculation Formula

Uses **Haversine Formula** to calculate great-circle distance between two points on Earth:

```python
def calculate_distance_haversine(lat1, lon1, lat2, lon2):
    R = 6371.0  # Earth's radius in km

    # Convert to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Calculate differences
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = sin(dlat/2)² + cos(lat1) * cos(lat2) * sin(dlon/2)²
    c = 2 * atan2(√a, √(1-a))

    distance = R * c  # in kilometers
    return round(distance, 2)
```

### 3. Example Calculations

#### Example 1: Free Delivery Product
```python
product_free_delivery = True
vendor_lat = 5.603717
vendor_lon = -0.186964
customer_lat = 5.614717
customer_lon = -0.196964

fee, distance = calculate_delivery_fee_for_product(
    product_free_delivery=True,
    vendor_lat=vendor_lat,
    vendor_lon=vendor_lon,
    customer_lat=customer_lat,
    customer_lon=customer_lon
)

# Result: fee = GHS 0.00, distance = 0.0 km
```

#### Example 2: Paid Delivery Product
```python
product_free_delivery = False
vendor_lat = 5.603717   # Vendor in Accra
vendor_lon = -0.186964
customer_lat = 5.614717  # Customer 1.5 km away
customer_lon = -0.196964

fee, distance = calculate_delivery_fee_for_product(
    product_free_delivery=False,
    vendor_lat=vendor_lat,
    vendor_lon=vendor_lon,
    customer_lat=customer_lat,
    customer_lon=customer_lon
)

# Result: fee = GHS 30.00, distance = 1.5 km
# Calculation: 1.5 km × GHS 20 = GHS 30.00
```

---

## React Native Implementation

### 1. Update TypeScript Interfaces

**types/delivery.ts:**
```typescript
export interface DeliveryLocation {
  latitude: number;
  longitude: number;
  address?: string;
}

export interface DeliveryFeeCalculation {
  product_free_delivery: boolean;
  vendor_latitude: number;
  vendor_longitude: number;
  customer_latitude: number;
  customer_longitude: number;
}

export interface DeliveryFeeResponse {
  delivery_fee: number;
  distance_km: number | null;
  free_delivery: boolean;
  currency: string;
}

export interface OrderDeliveryBreakdown {
  total_delivery_fee: number;
  sellers_breakdown: {
    [seller_id: string]: {
      delivery_fee: number;
      distance_km: number | null;
      free_delivery: boolean;
      items: any[];
      seller_name: string;
    };
  };
  currency: string;
}
```

### 2. Create Delivery Calculation Hook

**hooks/useDeliveryFee.ts:**
```typescript
import { useState } from 'react';
import axios from 'axios';

interface DeliveryFeeParams {
  cartItems: any[];
  customerLatitude: number;
  customerLongitude: number;
}

export const useDeliveryFee = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const calculateDeliveryFee = async (params: DeliveryFeeParams) => {
    setLoading(true);
    setError(null);

    try {
      // Client-side calculation preview (optional)
      // You can implement Haversine formula on client side too

      // Or fetch from backend
      const response = await axios.post(
        'YOUR_API_URL/calculate-delivery',
        params
      );

      return response.data;
    } catch (err) {
      setError('Failed to calculate delivery fee');
      console.error('Delivery calculation error:', err);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return { calculateDeliveryFee, loading, error };
};
```

### 3. Client-Side Distance Calculation (Optional)

**utils/distance.ts:**
```typescript
/**
 * Calculate distance between two coordinates using Haversine formula
 * @param lat1 Latitude of point 1 (vendor)
 * @param lon1 Longitude of point 1 (vendor)
 * @param lat2 Latitude of point 2 (customer)
 * @param lon2 Longitude of point 2 (customer)
 * @returns Distance in kilometers
 */
export function calculateDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371; // Earth's radius in km

  const toRad = (value: number) => (value * Math.PI) / 180;

  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const distance = R * c;

  return Math.round(distance * 100) / 100; // Round to 2 decimals
}

/**
 * Calculate delivery fee based on distance
 * @param distance Distance in kilometers
 * @param freeDelivery Whether product offers free delivery
 * @returns Delivery fee in GHS
 */
export function calculateDeliveryFee(
  distance: number,
  freeDelivery: boolean
): number {
  if (freeDelivery) {
    return 0;
  }

  const RATE_PER_KM = 20; // GHS 20 per km
  return Math.round(distance * RATE_PER_KM * 100) / 100;
}
```

### 4. Checkout Screen with Delivery Calculation

**screens/CheckoutScreen.tsx:**
```typescript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  StyleSheet,
  Alert
} from 'react-native';
import * as Location from 'expo-location';
import { calculateDistance, calculateDeliveryFee } from '../utils/distance';

interface CartItem {
  id: string;
  productId: string;
  name: string;
  price: number;
  quantity: number;
  free_delivery: boolean;
  sellerId: string;
  sellerName: string;
  vendor_latitude?: number;
  vendor_longitude?: number;
}

const CheckoutScreen = ({ route, navigation }) => {
  const { cartItems } = route.params;

  const [customerLocation, setCustomerLocation] = useState<{
    latitude: number;
    longitude: number;
  } | null>(null);

  const [deliveryBreakdown, setDeliveryBreakdown] = useState<any>(null);
  const [loadingLocation, setLoadingLocation] = useState(false);
  const [subtotal, setSubtotal] = useState(0);
  const [totalDeliveryFee, setTotalDeliveryFee] = useState(0);

  useEffect(() => {
    calculateSubtotal();
  }, [cartItems]);

  useEffect(() => {
    if (customerLocation) {
      calculateDeliveryFees();
    }
  }, [customerLocation, cartItems]);

  const calculateSubtotal = () => {
    const total = cartItems.reduce(
      (sum, item) => sum + item.price * item.quantity,
      0
    );
    setSubtotal(total);
  };

  const getCurrentLocation = async () => {
    setLoadingLocation(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();

      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to calculate delivery fees');
        setLoadingLocation(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      setCustomerLocation({
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      });
    } catch (error) {
      console.error('Location error:', error);
      Alert.alert('Error', 'Failed to get your location');
    } finally {
      setLoadingLocation(false);
    }
  };

  const calculateDeliveryFees = () => {
    if (!customerLocation) return;

    // Group items by seller
    const sellerGroups: { [key: string]: CartItem[] } = {};

    cartItems.forEach((item: CartItem) => {
      if (!sellerGroups[item.sellerId]) {
        sellerGroups[item.sellerId] = [];
      }
      sellerGroups[item.sellerId].push(item);
    });

    let totalFee = 0;
    const breakdown: any = {};

    // Calculate fee for each seller
    Object.entries(sellerGroups).forEach(([sellerId, items]) => {
      const firstItem = items[0];

      // Check if all items from this seller have free delivery
      const allFreeDelivery = items.every(item => item.free_delivery);

      if (allFreeDelivery) {
        breakdown[sellerId] = {
          seller_name: firstItem.sellerName,
          delivery_fee: 0,
          distance_km: 0,
          free_delivery: true,
          items: items.length,
        };
      } else {
        // Calculate distance if vendor has coordinates
        if (firstItem.vendor_latitude && firstItem.vendor_longitude) {
          const distance = calculateDistance(
            firstItem.vendor_latitude,
            firstItem.vendor_longitude,
            customerLocation.latitude,
            customerLocation.longitude
          );

          const fee = calculateDeliveryFee(distance, false);
          totalFee += fee;

          breakdown[sellerId] = {
            seller_name: firstItem.sellerName,
            delivery_fee: fee,
            distance_km: distance,
            free_delivery: false,
            items: items.length,
          };
        } else {
          // Default fee if no vendor location
          const defaultFee = 40; // ~2km distance
          totalFee += defaultFee;

          breakdown[sellerId] = {
            seller_name: firstItem.sellerName,
            delivery_fee: defaultFee,
            distance_km: null,
            free_delivery: false,
            items: items.length,
          };
        }
      }
    });

    setTotalDeliveryFee(totalFee);
    setDeliveryBreakdown(breakdown);
  };

  const grandTotal = subtotal + totalDeliveryFee;

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Checkout</Text>

      {/* Order Items Summary */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Order Summary</Text>
        {cartItems.map((item: CartItem) => (
          <View key={item.id} style={styles.orderItem}>
            <Text style={styles.itemName}>{item.name}</Text>
            <Text style={styles.itemPrice}>
              GHS {(item.price * item.quantity).toFixed(2)} ({item.quantity}x)
            </Text>
            {item.free_delivery && (
              <Text style={styles.freeDeliveryTag}>🚚 Free Delivery</Text>
            )}
          </View>
        ))}
      </View>

      {/* Location Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Delivery Location</Text>

        {!customerLocation ? (
          <TouchableOpacity
            style={styles.locationButton}
            onPress={getCurrentLocation}
            disabled={loadingLocation}
          >
            {loadingLocation ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.locationButtonText}>
                📍 Use Current Location
              </Text>
            )}
          </TouchableOpacity>
        ) : (
          <View style={styles.locationInfo}>
            <Text style={styles.locationText}>
              ✓ Location captured
            </Text>
            <Text style={styles.locationCoords}>
              {customerLocation.latitude.toFixed(6)}, {customerLocation.longitude.toFixed(6)}
            </Text>
            <TouchableOpacity onPress={getCurrentLocation}>
              <Text style={styles.updateLocationText}>Update Location</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>

      {/* Delivery Breakdown */}
      {deliveryBreakdown && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Delivery Fees Breakdown</Text>
          {Object.entries(deliveryBreakdown).map(([sellerId, info]: [string, any]) => (
            <View key={sellerId} style={styles.deliveryItem}>
              <View style={styles.deliveryInfo}>
                <Text style={styles.sellerName}>{info.seller_name}</Text>
                <Text style={styles.deliveryMeta}>
                  {info.free_delivery ? (
                    '🎉 Free Delivery'
                  ) : (
                    <>
                      {info.distance_km ? `${info.distance_km} km` : 'Distance unknown'}
                      {' • '}
                      {info.items} {info.items === 1 ? 'item' : 'items'}
                    </>
                  )}
                </Text>
              </View>
              <Text style={styles.deliveryFee}>
                GHS {info.delivery_fee.toFixed(2)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Price Breakdown */}
      <View style={styles.section}>
        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Subtotal:</Text>
          <Text style={styles.priceValue}>GHS {subtotal.toFixed(2)}</Text>
        </View>

        <View style={styles.priceRow}>
          <Text style={styles.priceLabel}>Delivery Fee:</Text>
          <Text style={styles.priceValue}>
            {totalDeliveryFee === 0 ? 'FREE' : `GHS ${totalDeliveryFee.toFixed(2)}`}
          </Text>
        </View>

        <View style={[styles.priceRow, styles.totalRow]}>
          <Text style={styles.totalLabel}>Total:</Text>
          <Text style={styles.totalValue}>GHS {grandTotal.toFixed(2)}</Text>
        </View>
      </View>

      {/* Checkout Button */}
      <TouchableOpacity
        style={[
          styles.checkoutButton,
          !customerLocation && styles.checkoutButtonDisabled
        ]}
        onPress={() => {
          if (!customerLocation) {
            Alert.alert('Location Required', 'Please provide your delivery location');
            return;
          }
          // Proceed to payment
          navigation.navigate('Payment', {
            subtotal,
            deliveryFee: totalDeliveryFee,
            total: grandTotal,
            deliveryBreakdown,
            customerLocation,
          });
        }}
        disabled={!customerLocation}
      >
        <Text style={styles.checkoutButtonText}>
          Proceed to Payment - GHS {grandTotal.toFixed(2)}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    padding: 20,
    backgroundColor: '#fff',
  },
  section: {
    backgroundColor: '#fff',
    padding: 20,
    marginTop: 10,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 15,
    color: '#333',
  },
  orderItem: {
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  itemName: {
    fontSize: 16,
    color: '#333',
    marginBottom: 4,
  },
  itemPrice: {
    fontSize: 14,
    color: '#666',
  },
  freeDeliveryTag: {
    fontSize: 12,
    color: '#2E7D32',
    marginTop: 4,
  },
  locationButton: {
    backgroundColor: '#007AFF',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center',
  },
  locationButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  locationInfo: {
    padding: 15,
    backgroundColor: '#E8F5E9',
    borderRadius: 8,
  },
  locationText: {
    fontSize: 16,
    color: '#2E7D32',
    fontWeight: '600',
    marginBottom: 4,
  },
  locationCoords: {
    fontSize: 12,
    color: '#666',
    marginBottom: 8,
  },
  updateLocationText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '600',
  },
  deliveryItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  deliveryInfo: {
    flex: 1,
  },
  sellerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  deliveryMeta: {
    fontSize: 13,
    color: '#666',
  },
  deliveryFee: {
    fontSize: 16,
    fontWeight: '600',
    color: '#007AFF',
  },
  priceRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 10,
  },
  priceLabel: {
    fontSize: 16,
    color: '#666',
  },
  priceValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  totalRow: {
    borderTopWidth: 2,
    borderTopColor: '#ddd',
    marginTop: 10,
    paddingTop: 15,
  },
  totalLabel: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  totalValue: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#007AFF',
  },
  checkoutButton: {
    backgroundColor: '#007AFF',
    padding: 18,
    margin: 20,
    borderRadius: 12,
    alignItems: 'center',
  },
  checkoutButtonDisabled: {
    backgroundColor: '#ccc',
  },
  checkoutButtonText: {
    color: '#fff',
    fontSize: 18,
    fontWeight: 'bold',
  },
});

export default CheckoutScreen;
```

### 5. Display Delivery Info in Product Card

**components/ProductCard.tsx:**
```typescript
import React from 'react';
import { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';

interface Product {
  id: string;
  name: string;
  price: number;
  currency: string;
  photos: string[];
  free_delivery: boolean;
  quantity: number;
}

const ProductCard: React.FC<{ product: Product; onPress: () => void }> = ({
  product,
  onPress,
}) => {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress}>
      <Image
        source={{ uri: product.photos[0] || 'https://via.placeholder.com/150' }}
        style={styles.image}
      />
      <View style={styles.infoContainer}>
        <Text style={styles.name} numberOfLines={2}>
          {product.name}
        </Text>
        <Text style={styles.price}>
          {product.currency} {product.price.toFixed(2)}
        </Text>

        {/* Delivery Badge */}
        {product.free_delivery ? (
          <View style={styles.freeDeliveryBadge}>
            <Text style={styles.freeDeliveryText}>🚚 Free Delivery</Text>
          </View>
        ) : (
          <View style={styles.paidDeliveryBadge}>
            <Text style={styles.paidDeliveryText}>📦 Delivery: GHS 20/km</Text>
          </View>
        )}

        <Text style={styles.quantity}>Stock: {product.quantity}</Text>
      </View>
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  image: {
    width: 100,
    height: 100,
    borderRadius: 8,
  },
  infoContainer: {
    flex: 1,
    marginLeft: 12,
    justifyContent: 'space-between',
  },
  name: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  price: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 8,
  },
  freeDeliveryBadge: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginBottom: 4,
  },
  freeDeliveryText: {
    fontSize: 12,
    color: '#2E7D32',
    fontWeight: '600',
  },
  paidDeliveryBadge: {
    backgroundColor: '#FFF3E0',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginBottom: 4,
  },
  paidDeliveryText: {
    fontSize: 11,
    color: '#E65100',
    fontWeight: '600',
  },
  quantity: {
    fontSize: 12,
    color: '#666',
  },
});

export default ProductCard;
```

---

## API Integration Example

### Calculate Delivery Fees Endpoint

**Request:**
```typescript
POST /api/calculate-delivery-fees

{
  "cart_items": [
    {
      "product_id": "uuid1",
      "seller_id": "vendor-uuid1",
      "free_delivery": false,
      "vendor_latitude": 5.603717,
      "vendor_longitude": -0.186964,
      "quantity": 2,
      "price": 100.00
    },
    {
      "product_id": "uuid2",
      "seller_id": "vendor-uuid2",
      "free_delivery": true,
      "vendor_latitude": 5.610000,
      "vendor_longitude": -0.190000,
      "quantity": 1,
      "price": 50.00
    }
  ],
  "customer_latitude": 5.614717,
  "customer_longitude": -0.196964
}
```

**Response:**
```json
{
  "total_delivery_fee": 30.00,
  "sellers_breakdown": {
    "vendor-uuid1": {
      "delivery_fee": 30.00,
      "distance_km": 1.5,
      "free_delivery": false,
      "items": 1,
      "seller_name": "Tech Store Ghana"
    },
    "vendor-uuid2": {
      "delivery_fee": 0.00,
      "distance_km": 0.0,
      "free_delivery": true,
      "items": 1,
      "seller_name": "Fashion Hub"
    }
  },
  "currency": "GHS"
}
```

---

## Testing Examples

### Test Case 1: Free Delivery Product
```
Vendor: Lat 5.603717, Lon -0.186964
Customer: Lat 5.614717, Lon -0.196964
Product free_delivery: true

Expected Result:
- Distance: ~1.5 km (calculated but not used)
- Delivery Fee: GHS 0.00
```

### Test Case 2: Paid Delivery - Short Distance
```
Vendor: Lat 5.603717, Lon -0.186964
Customer: Lat 5.614717, Lon -0.196964
Product free_delivery: false

Distance: 1.5 km
Expected Delivery Fee: 1.5 × 20 = GHS 30.00
```

### Test Case 3: Paid Delivery - Medium Distance
```
Vendor: Lat 5.603717, Lon -0.186964
Customer: Lat 5.650000, Lon -0.220000
Product free_delivery: false

Distance: ~6.2 km
Expected Delivery Fee: 6.2 × 20 = GHS 124.00
```

### Test Case 4: Multi-Seller Order
```
Cart Items:
1. Vendor A (free_delivery: true) - 2 items
2. Vendor B (free_delivery: false, 3 km away) - 1 item
3. Vendor C (free_delivery: false, 2 km away) - 3 items

Expected:
- Vendor A: GHS 0.00
- Vendor B: 3 × 20 = GHS 60.00
- Vendor C: 2 × 20 = GHS 40.00
- Total Delivery Fee: GHS 100.00
```

---

## Important Notes

### 1. **Vendor Location Required**
- All vendors must have `latitude` and `longitude` in their profile
- This was added in the vendor signup update
- Ensure vendors complete their location during registration

### 2. **Customer Location**
- Must be captured at checkout
- Use device GPS or allow manual address selection with geocoding
- Store in shipping address for order record

### 3. **Distance Calculation Accuracy**
- Haversine formula provides "as-the-crow-flies" distance
- Actual driving distance may be longer
- Consider adding buffer or using Google Maps Distance Matrix API for more accuracy

### 4. **Edge Cases to Handle**
- Missing vendor coordinates → Use default fee (e.g., GHS 40)
- Missing customer coordinates → Cannot calculate, require location
- Very long distances (>50km) → Consider maximum delivery radius
- Free shipping threshold → E.g., orders over GHS 500 get free delivery

---

## Database Requirements

### Ensure These Fields Exist:

**Users Table:**
- ✓ `latitude` (Float, nullable)
- ✓ `longitude` (Float, nullable)

**Products Table:**
- ✓ `free_delivery` (Boolean, default: true)

**Order Table:**
- ✓ `deliveryFee` (Decimal)
- ✓ `deliveryBreakdown` (JSON) - stores per-seller breakdown
- ✓ `shippingAddress` (JSON) - includes customer lat/long

---

## Migration Steps

1. **Backend:**
   - ✓ Add `delivery_utils.py` with calculation functions
   - Update order creation to use new delivery calculation
   - Add delivery fee breakdown to order response

2. **Frontend:**
   - Request location permission in checkout
   - Capture customer location
   - Display delivery fee breakdown by seller
   - Show distance and calculation to user
   - Add delivery info badges to product cards

3. **Testing:**
   - Test with various distances
   - Test free delivery products
   - Test multi-seller carts
   - Test edge cases (missing coordinates)

---

## FAQ

**Q: What if vendor doesn't have location set?**
A: Use a default fee (e.g., GHS 40 for ~2km) or prompt vendor to update their location.

**Q: Can I use Google Maps for more accurate distance?**
A: Yes! Use Google Maps Distance Matrix API for road distance instead of straight-line distance.

**Q: How to handle orders with both free and paid delivery?**
A: Calculate per seller. Some sellers charge, others don't. Total delivery fee is the sum.

**Q: Should I charge delivery per item or per seller?**
A: **Per seller** - Group items by seller, calculate one delivery fee per seller location.

**Q: What about minimum order for free delivery?**
A: You can add business logic: If order total > GHS 500, override free_delivery to true.

---

## Next Steps

1. Implement location capture in vendor signup (already done)
2. Implement location capture in checkout
3. Integrate delivery fee calculation in order creation
4. Display delivery breakdown clearly to users
5. Add delivery tracking for paid deliveries
6. Consider implementing delivery zones or maximum radius

---

## Support

For issues:
- Check vendor has latitude/longitude set
- Verify customer location is being captured
- Review delivery fee calculation logs
- Test with known coordinates and calculate manually
