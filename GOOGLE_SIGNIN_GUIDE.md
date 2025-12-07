# Google Sign-In Integration Guide for React Native

This guide provides step-by-step instructions for implementing Google Sign-In in your React Native app with the ZipoHub backend.

## Overview

The Google Sign-In flow allows users to authenticate using their Google account. For new users, they will be directed to a role selection screen to complete their profile.

## Backend Setup

### 1. Supabase Configuration

First, enable Google authentication in your Supabase project:

1. Go to your Supabase Dashboard
2. Navigate to **Authentication** → **Providers**
3. Enable **Google** provider
4. Add your Google OAuth credentials:
   - **Client ID** (from Google Cloud Console)
   - **Client Secret** (from Google Cloud Console)
5. Add authorized redirect URIs:
   - `https://your-project.supabase.co/auth/v1/callback`
   - For mobile: Your app's deep link scheme (e.g., `com.yourapp://`)

### 2. Google Cloud Console Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable **Google+ API**
4. Create OAuth 2.0 credentials:
   - **Android**: Add your app's SHA-1 fingerprint
   - **iOS**: Add your iOS bundle ID
5. Download the `google-services.json` (Android) and `GoogleService-Info.plist` (iOS)

## React Native Setup

### 1. Install Dependencies

```bash
npm install @react-native-google-signin/google-signin
# or
yarn add @react-native-google-signin/google-signin
```

### 2. Configure Google Sign-In

#### Android Configuration

1. Place `google-services.json` in `android/app/`
2. Add to `android/build.gradle`:

```gradle
buildscript {
    dependencies {
        classpath 'com.google.gms:google-services:4.3.15'
    }
}
```

3. Add to `android/app/build.gradle`:

```gradle
apply plugin: 'com.google.gms.google-services'

dependencies {
    implementation 'com.google.android.gms:play-services-auth:20.7.0'
}
```

#### iOS Configuration

1. Place `GoogleService-Info.plist` in `ios/YourApp/`
2. Add to `ios/Podfile`:

```ruby
pod 'GoogleSignIn'
```

3. Run `cd ios && pod install`
4. Add URL scheme to `ios/YourApp/Info.plist`:

```xml
<key>CFBundleURLTypes</key>
<array>
    <dict>
        <key>CFBundleURLSchemes</key>
        <array>
            <string>com.googleusercontent.apps.YOUR_CLIENT_ID</string>
        </array>
    </dict>
</array>
```

### 3. Initialize Google Sign-In

Create a `GoogleSignIn.js` utility file:

```javascript
import { GoogleSignin } from '@react-native-google-signin/google-signin';

export const configureGoogleSignIn = () => {
  GoogleSignin.configure({
    webClientId: 'YOUR_WEB_CLIENT_ID.apps.googleusercontent.com', // From Google Cloud Console
    offlineAccess: true,
    forceCodeForRefreshToken: true,
  });
};
```

Call this in your `App.js` or `index.js`:

```javascript
import { configureGoogleSignIn } from './utils/GoogleSignIn';

// In your app initialization
useEffect(() => {
  configureGoogleSignIn();
}, []);
```

## Implementation

### 1. Google Sign-In Button Component

```javascript
import React, { useState } from 'react';
import { View, TouchableOpacity, Text, ActivityIndicator, StyleSheet } from 'react-native';
import { GoogleSignin } from '@react-native-google-signin/google-signin';
import axios from 'axios';

const API_BASE_URL = 'https://your-api-url.com/api';

const GoogleSignInButton = ({ onSuccess, onError }) => {
  const [loading, setLoading] = useState(false);

  const handleGoogleSignIn = async () => {
    try {
      setLoading(true);

      // 1. Check if Google Play Services are available
      await GoogleSignin.hasPlayServices();

      // 2. Sign in with Google
      const userInfo = await GoogleSignin.signIn();

      // 3. Get the ID token
      const { idToken } = userInfo;

      // 4. Send ID token to your backend
      const response = await axios.post(`${API_BASE_URL}/auth/google/signin`, {
        id_token: idToken,
        device_info: 'react-native-mobile'
      });

      const {
        user,
        session,
        supabase_tokens,
        is_new_user,
        needs_profile_completion
      } = response.data;

      // 5. Store tokens securely
      await storeTokens(supabase_tokens);

      // 6. Handle navigation based on user status
      if (is_new_user || needs_profile_completion) {
        // Navigate to role selection screen
        onSuccess({ user, navigateTo: 'RoleSelection' });
      } else {
        // Navigate to home screen
        onSuccess({ user, navigateTo: 'Home' });
      }

    } catch (error) {
      console.error('Google Sign-In Error:', error);

      if (error.code === 'SIGN_IN_CANCELLED') {
        onError('Sign-in cancelled');
      } else if (error.code === 'IN_PROGRESS') {
        onError('Sign-in already in progress');
      } else if (error.code === 'PLAY_SERVICES_NOT_AVAILABLE') {
        onError('Play Services not available');
      } else {
        onError(error.message || 'Sign-in failed');
      }
    } finally {
      setLoading(false);
    }
  };

  const storeTokens = async (tokens) => {
    // Use secure storage (e.g., react-native-keychain)
    // Example with AsyncStorage (not recommended for production):
    // await AsyncStorage.setItem('access_token', tokens.access_token);
    // await AsyncStorage.setItem('refresh_token', tokens.refresh_token);
  };

  return (
    <TouchableOpacity
      style={styles.button}
      onPress={handleGoogleSignIn}
      disabled={loading}
    >
      {loading ? (
        <ActivityIndicator color="#fff" />
      ) : (
        <Text style={styles.buttonText}>Sign in with Google</Text>
      )}
    </TouchableOpacity>
  );
};

const styles = StyleSheet.create({
  button: {
    backgroundColor: '#4285F4',
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 48,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default GoogleSignInButton;
```

### 2. Role Selection Screen

Create a screen for new users to select their role and complete their profile:

```javascript
import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, ScrollView } from 'react-native';
import axios from 'axios';

const API_BASE_URL = 'https://your-api-url.com/api';

const RoleSelectionScreen = ({ route, navigation }) => {
  const { user } = route.params;
  const [selectedRole, setSelectedRole] = useState('client');
  const [userType, setUserType] = useState('CUSTOMER');
  const [formData, setFormData] = useState({
    phone_number: '',
    country: '',
    city: '',
    address: '',
    business_name: '',
    business_description: '',
  });
  const [loading, setLoading] = useState(false);

  const roles = [
    { value: 'client', label: 'Customer', userType: 'CUSTOMER' },
    { value: 'seller', label: 'Seller', userType: 'SELLER' },
  ];

  const handleRoleSelect = (role, type) => {
    setSelectedRole(role);
    setUserType(type);
  };

  const handleSubmit = async () => {
    try {
      setLoading(true);

      // Get stored access token
      const accessToken = await getAccessToken(); // Implement this function

      // Update user profile
      const updateData = {
        phone_number: formData.phone_number,
        country: formData.country,
        city: formData.city,
        address: formData.address,
        role: selectedRole,
        user_type: userType,
      };

      // Add seller-specific fields if applicable
      if (selectedRole === 'seller') {
        updateData.business_name = formData.business_name;
        updateData.business_description = formData.business_description;
      }

      const response = await axios.put(
        `${API_BASE_URL}/user/profile`,
        updateData,
        {
          headers: {
            'Authorization': `Bearer ${accessToken}`
          }
        }
      );

      // Navigate to home screen
      navigation.reset({
        index: 0,
        routes: [{ name: 'Home' }],
      });

    } catch (error) {
      console.error('Profile update error:', error);
      alert('Failed to update profile. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Complete Your Profile</Text>
      <Text style={styles.subtitle}>Welcome, {user.name}!</Text>

      <View style={styles.section}>
        <Text style={styles.label}>Select Your Role</Text>
        <View style={styles.roleContainer}>
          {roles.map((role) => (
            <TouchableOpacity
              key={role.value}
              style={[
                styles.roleButton,
                selectedRole === role.value && styles.roleButtonActive
              ]}
              onPress={() => handleRoleSelect(role.value, role.userType)}
            >
              <Text style={[
                styles.roleButtonText,
                selectedRole === role.value && styles.roleButtonTextActive
              ]}>
                {role.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Phone Number *</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your phone number"
          value={formData.phone_number}
          onChangeText={(text) => setFormData({ ...formData, phone_number: text })}
          keyboardType="phone-pad"
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Country *</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your country"
          value={formData.country}
          onChangeText={(text) => setFormData({ ...formData, country: text })}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>City *</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your city"
          value={formData.city}
          onChangeText={(text) => setFormData({ ...formData, city: text })}
        />
      </View>

      <View style={styles.section}>
        <Text style={styles.label}>Address</Text>
        <TextInput
          style={styles.input}
          placeholder="Enter your address"
          value={formData.address}
          onChangeText={(text) => setFormData({ ...formData, address: text })}
          multiline
        />
      </View>

      {selectedRole === 'seller' && (
        <>
          <View style={styles.section}>
            <Text style={styles.label}>Business Name *</Text>
            <TextInput
              style={styles.input}
              placeholder="Enter your business name"
              value={formData.business_name}
              onChangeText={(text) => setFormData({ ...formData, business_name: text })}
            />
          </View>

          <View style={styles.section}>
            <Text style={styles.label}>Business Description</Text>
            <TextInput
              style={styles.input}
              placeholder="Describe your business"
              value={formData.business_description}
              onChangeText={(text) => setFormData({ ...formData, business_description: text })}
              multiline
              numberOfLines={4}
            />
          </View>
        </>
      )}

      <TouchableOpacity
        style={styles.submitButton}
        onPress={handleSubmit}
        disabled={loading || !formData.phone_number || !formData.country || !formData.city}
      >
        <Text style={styles.submitButtonText}>
          {loading ? 'Saving...' : 'Complete Profile'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
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
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    marginBottom: 24,
  },
  section: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  roleContainer: {
    flexDirection: 'row',
    gap: 12,
  },
  roleButton: {
    flex: 1,
    padding: 16,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: '#ddd',
    alignItems: 'center',
  },
  roleButtonActive: {
    borderColor: '#4285F4',
    backgroundColor: '#E8F0FE',
  },
  roleButtonText: {
    fontSize: 16,
    color: '#666',
  },
  roleButtonTextActive: {
    color: '#4285F4',
    fontWeight: '600',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
  },
  submitButton: {
    backgroundColor: '#4285F4',
    padding: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 20,
    marginBottom: 40,
  },
  submitButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});

export default RoleSelectionScreen;
```

### 3. Navigation Setup

Add the screens to your navigation:

```javascript
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import LoginScreen from './screens/LoginScreen';
import RoleSelectionScreen from './screens/RoleSelectionScreen';
import HomeScreen from './screens/HomeScreen';

const Stack = createNativeStackNavigator();

function App() {
  return (
    <NavigationContainer>
      <Stack.Navigator>
        <Stack.Screen name="Login" component={LoginScreen} />
        <Stack.Screen
          name="RoleSelection"
          component={RoleSelectionScreen}
          options={{ title: 'Complete Profile' }}
        />
        <Stack.Screen name="Home" component={HomeScreen} />
      </Stack.Navigator>
    </NavigationContainer>
  );
}
```

## API Endpoints

### Google Sign-In

**Endpoint:** `POST /api/auth/google/signin`

**Request:**
```json
{
  "id_token": "google_id_token_here",
  "device_info": "react-native-mobile"
}
```

**Response:**
```json
{
  "user": {
    "user_id": "uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "verified": true,
    "role": "client",
    "phone_number": null,
    "country": null,
    "city": null,
    "address": null,
    "business_name": null,
    "business_description": null,
    "user_type": null
  },
  "session": {
    "token": "jwt_token",
    "expires_at": "2024-12-06T12:00:00Z"
  },
  "supabase_tokens": {
    "access_token": "supabase_access_token",
    "refresh_token": "supabase_refresh_token"
  },
  "is_new_user": true,
  "needs_profile_completion": true
}
```

## Flow Diagram

```
User clicks "Sign in with Google"
        ↓
Google Sign-In SDK opens
        ↓
User selects Google account
        ↓
App receives ID token
        ↓
Send ID token to backend
        ↓
Backend verifies with Supabase
        ↓
    Is new user?
    ├─ Yes → Navigate to Role Selection Screen
    │         ↓
    │    User selects role & fills details
    │         ↓
    │    Update profile via API
    │         ↓
    └─ No  → Navigate to Home Screen
```

## Security Best Practices

1. **Secure Token Storage**: Use `react-native-keychain` or `expo-secure-store` instead of AsyncStorage
2. **Token Refresh**: Implement automatic token refresh before expiration
3. **Error Handling**: Handle all Google Sign-In error codes properly
4. **Deep Linking**: Configure deep links for email verification and password reset

## Testing

### Test Google Sign-In Flow

1. Use a real Google account (test accounts may have restrictions)
2. Test both new user and existing user flows
3. Test role selection and profile completion
4. Verify tokens are stored securely
5. Test sign-out and re-sign-in

## Troubleshooting

### Common Issues

1. **"Developer Error" on Android**
   - Verify SHA-1 fingerprint in Google Console
   - Ensure `google-services.json` is in correct location

2. **"Sign in with Google temporarily disabled"**
   - Check Google OAuth credentials
   - Verify Supabase Google provider configuration

3. **Backend returns 401**
   - Verify ID token is being sent correctly
   - Check Supabase Google provider is enabled

4. **Profile not updating**
   - Ensure access token is included in Authorization header
   - Verify user_id matches authenticated user

## Additional Resources

- [Google Sign-In for React Native](https://github.com/react-native-google-signin/google-signin)
- [Supabase Auth Documentation](https://supabase.com/docs/guides/auth)
- [Google Cloud Console](https://console.cloud.google.com/)
