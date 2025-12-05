# Location Fields Update Guide - Latitude & Longitude for Vendor Signup

## Overview
This guide covers how to update your React Native app to capture and send **latitude** and **longitude** coordinates when vendors sign up, following the backend schema update.

---

## Backend Changes (Already Done ✓)

### Schema Update
```prisma
model users {
  // ... other fields
  latitude             Float?
  longitude            Float?
  // ... rest of fields
}
```

### API Models Updated
The backend `SignUpRequest` and `UserResponse` models need to include latitude/longitude fields.

---

## Backend Updates Required

### 1. Update `app/models/auth.py`

Add latitude and longitude to the `SignUpRequest` model:

```python
class SignUpRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None          # ADD THIS
    longitude: Optional[float] = None         # ADD THIS
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    role: str = "client"
    user_type: Optional[UserType] = None
```

Add to `UserResponse` model:

```python
class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str
    phone_number: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    address: Optional[str] = None
    latitude: Optional[float] = None          # ADD THIS
    longitude: Optional[float] = None         # ADD THIS
    business_name: Optional[str] = None
    business_description: Optional[str] = None
    verified: bool = False
    role: str
    user_type: Optional[str] = None
    courier_profile: Optional[CourierProfileData] = None
```

### 2. Update `app/routes/auth.py`

#### Update `/signup` endpoint (line 73)

In the Supabase Auth metadata options:
```python
auth_response = supabase.auth.sign_up({
    "email": user_data.email,
    "password": user_data.password,
    "options": {
        "data": {
            "name": user_data.name,
            "phone_number": user_data.phone_number,
            "country": user_data.country,
            "city": user_data.city,
            "address": user_data.address,
            "latitude": user_data.latitude,           # ADD THIS
            "longitude": user_data.longitude,         # ADD THIS
            "business_name": user_data.business_name,
            "business_description": user_data.business_description,
            "role": user_data.role,
            "user_type": user_data.user_type.value if user_data.user_type else None,
            "verified": False
        }
    }
})
```

In the database insertion fields:
```python
fields = {
    "user_id": user.id,
    "name": user_data.name,
    "email": user_data.email,
    "phone_number": user_data.phone_number,
    "country": user_data.country,
    "city": user_data.city,
    "address": user_data.address,
    "latitude": user_data.latitude,           # ADD THIS
    "longitude": user_data.longitude,         # ADD THIS
    "business_name": user_data.business_name,
    "business_description": user_data.business_description,
    "role": user_data.role,
    "user_type": user_data.user_type.value if user_data.user_type else None,
    "verified": False
}
```

In the UserResponse construction:
```python
user_response = UserResponse(
    user_id=user.id,
    name=user_data.name,
    email=user_data.email,
    phone_number=user_data.phone_number,
    country=user_data.country,
    city=user_data.city,
    address=user_data.address,
    latitude=user_data.latitude,              # ADD THIS
    longitude=user_data.longitude,            # ADD THIS
    business_name=user_data.business_name,
    business_description=user_data.business_description,
    verified=False,
    role=user_data.role,
    user_type=user_data.user_type.value if user_data.user_type else None
)
```

#### Update `/mobile/signup` endpoint (line 359)

Apply the same changes as above in:
1. Supabase auth metadata options (line 391)
2. Database fields dictionary (line 418)
3. UserResponse construction (line 456)

#### Update `fetch_user_with_profile` helper function (line 20)

```python
return UserResponse(
    user_id=user_db["user_id"],
    name=user_db["name"],
    email=user_db["email"],
    phone_number=user_db.get("phone_number"),
    country=user_db.get("country"),
    city=user_db.get("city"),
    address=user_db.get("address"),
    latitude=user_db.get("latitude"),         # ADD THIS
    longitude=user_db.get("longitude"),       # ADD THIS
    business_name=user_db.get("business_name"),
    business_description=user_db.get("business_description"),
    verified=user_db.get("verified", False),
    role=user_db.get("role", "client"),
    user_type=user_db.get("user_type"),
    courier_profile=courier_profile
)
```

### 3. Run Prisma Migration

After updating the schema:

```bash
# Generate Prisma client
npx prisma generate

# Apply migration to database
npx prisma migrate dev --name add_user_location_fields

# Or if in production
npx prisma migrate deploy
```

---

## React Native App Updates

### 1. Install Required Packages

```bash
npm install expo-location
# or
yarn add expo-location
```

For bare React Native:
```bash
npm install @react-native-community/geolocation
# or
yarn add @react-native-community/geolocation
```

### 2. Request Location Permissions

#### For Expo:

**app.json / app.config.js:**
```json
{
  "expo": {
    "plugins": [
      [
        "expo-location",
        {
          "locationAlwaysAndWhenInUsePermission": "Allow $(PRODUCT_NAME) to use your location to show nearby vendors."
        }
      ]
    ]
  }
}
```

#### For Bare React Native:

**iOS (ios/YourApp/Info.plist):**
```xml
<key>NSLocationWhenInUseUsageDescription</key>
<string>We need your location to connect you with nearby services</string>
<key>NSLocationAlwaysUsageDescription</key>
<string>We need your location to connect you with nearby services</string>
```

**Android (android/app/src/main/AndroidManifest.xml):**
```xml
<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION" />
<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION" />
```

### 3. Create Location Hook (Recommended)

**hooks/useLocation.js:**
```javascript
import { useState, useEffect } from 'react';
import * as Location from 'expo-location';

export const useLocation = () => {
  const [location, setLocation] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const requestLocation = async () => {
    setLoading(true);
    setError(null);

    try {
      // Request permission
      const { status } = await Location.requestForegroundPermissionsAsync();

      if (status !== 'granted') {
        setError('Location permission denied');
        setLoading(false);
        return null;
      }

      // Get current location
      const currentLocation = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      const locationData = {
        latitude: currentLocation.coords.latitude,
        longitude: currentLocation.coords.longitude,
      };

      setLocation(locationData);
      setLoading(false);
      return locationData;

    } catch (err) {
      setError(err.message);
      setLoading(false);
      return null;
    }
  };

  return { location, loading, error, requestLocation };
};
```

### 4. Update Signup Screen

**screens/VendorSignupScreen.js:**

```javascript
import React, { useState } from 'react';
import { View, TextInput, Button, Text, ActivityIndicator, Alert } from 'react-native';
import { useLocation } from '../hooks/useLocation';
import axios from 'axios';

const VendorSignupScreen = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    phone_number: '',
    country: '',
    city: '',
    address: '',
    business_name: '',
    business_description: '',
  });

  const { location, loading: locationLoading, error: locationError, requestLocation } = useLocation();
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Request location when component mounts or when user taps a button
  const handleGetLocation = async () => {
    const loc = await requestLocation();
    if (loc) {
      Alert.alert('Success', 'Location captured successfully!');
    } else if (locationError) {
      Alert.alert('Error', locationError);
    }
  };

  const handleSignup = async () => {
    // Validate form
    if (!formData.email || !formData.password || !formData.name) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    // Request location if not already captured
    let currentLocation = location;
    if (!currentLocation) {
      currentLocation = await requestLocation();
    }

    if (!currentLocation) {
      Alert.alert(
        'Location Required',
        'We need your location to complete vendor registration. Please enable location services.'
      );
      return;
    }

    setIsSubmitting(true);

    try {
      const signupData = {
        ...formData,
        latitude: currentLocation.latitude,
        longitude: currentLocation.longitude,
        role: 'seller',
        user_type: 'SELLER',
      };

      const response = await axios.post(
        'YOUR_API_URL/auth/mobile/signup',
        signupData
      );

      if (response.data.user) {
        Alert.alert('Success', 'Vendor account created successfully!');
        // Navigate to next screen or login
      }

    } catch (error) {
      console.error('Signup error:', error);
      Alert.alert(
        'Signup Failed',
        error.response?.data?.detail || 'An error occurred during signup'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <View style={{ padding: 20 }}>
      <Text style={{ fontSize: 24, fontWeight: 'bold', marginBottom: 20 }}>
        Vendor Signup
      </Text>

      <TextInput
        placeholder="Full Name *"
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
        style={styles.input}
      />

      <TextInput
        placeholder="Email *"
        value={formData.email}
        onChangeText={(text) => setFormData({ ...formData, email: text })}
        keyboardType="email-address"
        autoCapitalize="none"
        style={styles.input}
      />

      <TextInput
        placeholder="Password *"
        value={formData.password}
        onChangeText={(text) => setFormData({ ...formData, password: text })}
        secureTextEntry
        style={styles.input}
      />

      <TextInput
        placeholder="Phone Number"
        value={formData.phone_number}
        onChangeText={(text) => setFormData({ ...formData, phone_number: text })}
        keyboardType="phone-pad"
        style={styles.input}
      />

      <TextInput
        placeholder="Business Name"
        value={formData.business_name}
        onChangeText={(text) => setFormData({ ...formData, business_name: text })}
        style={styles.input}
      />

      <TextInput
        placeholder="Business Description"
        value={formData.business_description}
        onChangeText={(text) => setFormData({ ...formData, business_description: text })}
        multiline
        numberOfLines={4}
        style={styles.input}
      />

      <TextInput
        placeholder="Address"
        value={formData.address}
        onChangeText={(text) => setFormData({ ...formData, address: text })}
        style={styles.input}
      />

      <TextInput
        placeholder="City"
        value={formData.city}
        onChangeText={(text) => setFormData({ ...formData, city: text })}
        style={styles.input}
      />

      <TextInput
        placeholder="Country"
        value={formData.country}
        onChangeText={(text) => setFormData({ ...formData, country: text })}
        style={styles.input}
      />

      {/* Location Section */}
      <View style={{ marginVertical: 20, padding: 15, backgroundColor: '#f5f5f5', borderRadius: 8 }}>
        <Text style={{ fontSize: 16, fontWeight: '600', marginBottom: 10 }}>
          Location Information
        </Text>

        {location ? (
          <View>
            <Text style={{ color: 'green' }}>✓ Location Captured</Text>
            <Text style={{ fontSize: 12, color: '#666', marginTop: 5 }}>
              Lat: {location.latitude.toFixed(6)}, Lng: {location.longitude.toFixed(6)}
            </Text>
          </View>
        ) : (
          <Button
            title={locationLoading ? "Getting Location..." : "Capture Location"}
            onPress={handleGetLocation}
            disabled={locationLoading}
          />
        )}

        {locationError && (
          <Text style={{ color: 'red', marginTop: 10 }}>
            Error: {locationError}
          </Text>
        )}
      </View>

      {/* Submit Button */}
      <Button
        title={isSubmitting ? "Creating Account..." : "Sign Up as Vendor"}
        onPress={handleSignup}
        disabled={isSubmitting || locationLoading}
      />

      {isSubmitting && (
        <ActivityIndicator style={{ marginTop: 20 }} size="large" color="#0000ff" />
      )}
    </View>
  );
};

const styles = {
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 12,
    marginBottom: 15,
    borderRadius: 8,
    fontSize: 16,
  },
};

export default VendorSignupScreen;
```

### 5. Alternative: Auto-Capture Location on Screen Load

```javascript
useEffect(() => {
  // Auto-request location when component mounts
  requestLocation();
}, []);
```

### 6. Add Map Preview (Optional Enhancement)

```bash
npm install react-native-maps
```

```javascript
import MapView, { Marker } from 'react-native-maps';

// In your component
{location && (
  <MapView
    style={{ height: 200, marginVertical: 10 }}
    region={{
      latitude: location.latitude,
      longitude: location.longitude,
      latitudeDelta: 0.01,
      longitudeDelta: 0.01,
    }}
  >
    <Marker coordinate={location} title="Your Location" />
  </MapView>
)}
```

---

## Testing Checklist

### Backend Testing
- [ ] Run Prisma migration successfully
- [ ] Test `/auth/signup` endpoint with latitude/longitude
- [ ] Test `/auth/mobile/signup` endpoint
- [ ] Verify data is stored in database with location fields
- [ ] Check UserResponse includes latitude/longitude

### Frontend Testing
- [ ] Location permission request works on iOS
- [ ] Location permission request works on Android
- [ ] Location coordinates are captured accurately
- [ ] Signup succeeds with location data
- [ ] Signup fails gracefully if location is denied
- [ ] Loading states display correctly
- [ ] Error handling works properly

---

## API Request Example

**Signup Request:**
```json
POST /auth/mobile/signup

{
  "name": "John's Electronics",
  "email": "john@example.com",
  "password": "SecurePass123!",
  "phone_number": "+1234567890",
  "business_name": "John's Electronics",
  "business_description": "Quality electronics and gadgets",
  "address": "123 Main Street",
  "city": "Accra",
  "country": "Ghana",
  "latitude": 5.603717,
  "longitude": -0.186964,
  "role": "seller",
  "user_type": "SELLER"
}
```

**Response:**
```json
{
  "user": {
    "user_id": "uuid-here",
    "name": "John's Electronics",
    "email": "john@example.com",
    "latitude": 5.603717,
    "longitude": -0.186964,
    "business_name": "John's Electronics",
    "role": "seller",
    "user_type": "SELLER",
    "verified": false
  },
  "session": { ... },
  "supabase_tokens": { ... },
  "message": "Account created successfully. Please check your email for verification."
}
```

---

## Common Issues & Solutions

### Issue: "Location permission denied"
**Solution:** Guide users to device settings to enable location permissions.

### Issue: Location takes too long to capture
**Solution:** Use `Location.Accuracy.Balanced` instead of `High` for faster results.

### Issue: Location not working on Android
**Solution:** Ensure Google Play Services is installed and location services are enabled on the device.

### Issue: iOS simulator location not working
**Solution:** In iOS Simulator menu: Features → Location → Custom Location or Apple (for testing).

---

## Production Considerations

1. **Privacy Policy:** Update your privacy policy to mention location data collection
2. **User Consent:** Clearly explain why you need location data
3. **Fallback:** Allow manual address entry if location fails
4. **Validation:** Validate latitude/longitude ranges on backend (-90 to 90, -180 to 180)
5. **Security:** Don't expose exact coordinates to other users unless necessary
6. **Performance:** Consider caching location to avoid repeated requests

---

## Next Steps

1. Update backend models and routes as shown above
2. Run database migration
3. Test backend endpoints with Postman/Thunder Client
4. Implement location logic in React Native app
5. Test on physical devices (iOS and Android)
6. Deploy updated backend
7. Release updated mobile app

---

## Questions?

For issues or questions, check:
- Expo Location docs: https://docs.expo.dev/versions/latest/sdk/location/
- React Native Geolocation: https://github.com/react-native-geolocation/react-native-geolocation
- Backend logs for debugging signup failures
