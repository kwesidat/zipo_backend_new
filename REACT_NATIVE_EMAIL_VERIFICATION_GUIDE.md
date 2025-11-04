# React Native Email Verification Implementation Guide

## Overview
Your backend uses **Supabase's token_hash verification** system. After signup, users receive an email with a confirmation link that needs to be handled in your React Native app.

## Backend Endpoint

**Endpoint:** `GET /auth/confirm`

**Query Parameters:**
- `token_hash` (required): The token hash from the email
- `type` (required): Verification type (e.g., "signup")
- `email` (optional): User's email address

**Response (Success):**
```json
{
  "message": "Email verified successfully! You can now log in.",
  "verified": true,
  "user": {
    "user_id": "uuid",
    "email": "user@example.com",
    "email_confirmed_at": "2024-01-01T00:00:00Z"
  },
  "session": {
    "access_token": "eyJ...",
    "refresh_token": "eyJ..."
  }
}
```

---

## Implementation Options

### Option 1: Deep Linking (Recommended for Mobile Apps)

Deep links allow your app to open directly when users click the email link on their mobile device.

#### Step 1: Install Dependencies

```bash
npm install react-native-deep-linking
# or
yarn add react-native-deep-linking

# For Expo
npx expo install expo-linking
```

#### Step 2: Configure Deep Links

**For React Native (Non-Expo):**

**`android/app/src/main/AndroidManifest.xml`:**
```xml
<activity
  android:name=".MainActivity"
  android:launchMode="singleTask">

  <intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />

    <!-- Replace with your domain -->
    <data android:scheme="https" />
    <data android:host="www.zipohubonline.com" />
    <data android:pathPrefix="/auth/confirm" />
  </intent-filter>

  <!-- Custom scheme as fallback -->
  <intent-filter>
    <action android:name="android.intent.action.VIEW" />
    <category android:name="android.intent.category.DEFAULT" />
    <category android:name="android.intent.category.BROWSABLE" />
    <data android:scheme="zipohub" />
  </intent-filter>
</activity>
```

**`ios/YourApp/Info.plist`:**
```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleTypeRole</key>
    <string>Editor</string>
    <key>CFBundleURLName</key>
    <string>com.yourcompany.zipohub</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>zipohub</string>
    </array>
  </dict>
</array>

<!-- For Universal Links -->
<key>com.apple.developer.associated-domains</key>
<array>
  <string>applinks:www.zipohubonline.com</string>
</array>
```

**For Expo:**

**`app.json`:**
```json
{
  "expo": {
    "scheme": "zipohub",
    "android": {
      "intentFilters": [
        {
          "action": "VIEW",
          "autoVerify": true,
          "data": [
            {
              "scheme": "https",
              "host": "www.zipohubonline.com",
              "pathPrefix": "/auth/confirm"
            }
          ],
          "category": ["BROWSABLE", "DEFAULT"]
        }
      ]
    },
    "ios": {
      "associatedDomains": ["applinks:www.zipohubonline.com"]
    }
  }
}
```

#### Step 3: Handle Deep Links in Your App

**`App.js` or `App.tsx` (Non-Expo):**
```javascript
import React, { useEffect } from 'react';
import { Linking } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';

function App() {
  useEffect(() => {
    // Handle initial URL (when app is opened from closed state)
    Linking.getInitialURL().then((url) => {
      if (url) {
        handleDeepLink(url);
      }
    });

    // Handle URL when app is already open
    const subscription = Linking.addEventListener('url', (event) => {
      handleDeepLink(event.url);
    });

    return () => {
      subscription.remove();
    };
  }, []);

  const handleDeepLink = async (url) => {
    if (!url) return;

    // Parse the URL
    const { hostname, path, queryParams } = Linking.parse(url);

    // Check if it's an email confirmation link
    if (path === 'auth/confirm' || path === '/auth/confirm') {
      const { token_hash, type, email } = queryParams;

      if (token_hash && type) {
        await verifyEmail(token_hash, type, email);
      }
    }
  };

  const verifyEmail = async (tokenHash, type, email) => {
    try {
      const params = new URLSearchParams({
        token_hash: tokenHash,
        type: type,
      });

      if (email) {
        params.append('email', email);
      }

      const response = await fetch(
        `https://your-backend-api.com/auth/confirm?${params.toString()}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const data = await response.json();

      if (response.ok && data.verified) {
        // Store tokens
        await AsyncStorage.setItem('access_token', data.session.access_token);
        await AsyncStorage.setItem('refresh_token', data.session.refresh_token);

        // Navigate to main app or show success message
        Alert.alert(
          'Email Verified!',
          'Your email has been verified successfully.',
          [
            {
              text: 'Continue',
              onPress: () => {
                // Navigate to home or dashboard
                navigation.navigate('Home');
              },
            },
          ]
        );
      } else {
        Alert.alert('Verification Failed', data.detail || 'Please try again.');
      }
    } catch (error) {
      console.error('Email verification error:', error);
      Alert.alert(
        'Error',
        'Failed to verify email. Please try again or request a new verification link.'
      );
    }
  };

  return (
    <NavigationContainer>
      {/* Your navigation setup */}
    </NavigationContainer>
  );
}

export default App;
```

**For Expo:**
```javascript
import * as Linking from 'expo-linking';
import { useEffect } from 'react';

function App() {
  useEffect(() => {
    // Get initial URL
    Linking.getInitialURL().then((url) => {
      if (url) {
        handleDeepLink(url);
      }
    });

    // Listen for URL changes
    const subscription = Linking.addEventListener('url', (event) => {
      handleDeepLink(event.url);
    });

    return () => {
      subscription.remove();
    };
  }, []);

  const handleDeepLink = async (url) => {
    const { hostname, path, queryParams } = Linking.parse(url);

    if (path === 'auth/confirm' || path === '/auth/confirm') {
      const { token_hash, type, email } = queryParams;

      if (token_hash && type) {
        await verifyEmail(token_hash, type, email);
      }
    }
  };

  // Same verifyEmail function as above
  // ...
}
```

---

### Option 2: Manual Code Entry (Fallback)

If deep linking doesn't work or users open the email on a different device, provide a manual verification option.

#### Step 1: Create Verification Screen

```javascript
import React, { useState } from 'react';
import {
  View,
  TextInput,
  Button,
  Alert,
  ActivityIndicator,
  StyleSheet,
} from 'react-native';

function EmailVerificationScreen({ route, navigation }) {
  const [tokenHash, setTokenHash] = useState('');
  const [loading, setLoading] = useState(false);
  const email = route.params?.email || '';

  const handleVerification = async () => {
    if (!tokenHash) {
      Alert.alert('Error', 'Please enter the verification code');
      return;
    }

    setLoading(true);

    try {
      const params = new URLSearchParams({
        token_hash: tokenHash,
        type: 'signup',
      });

      if (email) {
        params.append('email', email);
      }

      const response = await fetch(
        `https://your-backend-api.com/auth/confirm?${params.toString()}`,
        {
          method: 'GET',
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );

      const data = await response.json();

      if (response.ok && data.verified) {
        await AsyncStorage.setItem('access_token', data.session.access_token);
        await AsyncStorage.setItem('refresh_token', data.session.refresh_token);

        Alert.alert('Success', 'Email verified successfully!', [
          {
            text: 'Continue',
            onPress: () => navigation.navigate('Home'),
          },
        ]);
      } else {
        Alert.alert('Error', data.detail || 'Verification failed');
      }
    } catch (error) {
      console.error('Verification error:', error);
      Alert.alert('Error', 'Failed to verify email. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResendEmail = async () => {
    if (!email) {
      Alert.alert('Error', 'Email address is required');
      return;
    }

    try {
      const response = await fetch(
        'https://your-backend-api.com/auth/resend-verification',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ email }),
        }
      );

      const data = await response.json();

      if (response.ok) {
        Alert.alert('Success', data.message);
      } else {
        Alert.alert('Error', data.detail || 'Failed to resend email');
      }
    } catch (error) {
      console.error('Resend error:', error);
      Alert.alert('Error', 'Failed to resend verification email');
    }
  };

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        placeholder="Enter verification code"
        value={tokenHash}
        onChangeText={setTokenHash}
        autoCapitalize="none"
      />

      {loading ? (
        <ActivityIndicator size="large" />
      ) : (
        <>
          <Button title="Verify Email" onPress={handleVerification} />
          <Button
            title="Resend Verification Email"
            onPress={handleResendEmail}
          />
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ccc',
    padding: 10,
    marginBottom: 20,
    borderRadius: 5,
  },
});

export default EmailVerificationScreen;
```

---

## Update Your Supabase Email Template

To ensure the deep link works correctly, update your Supabase email template:

```html
<h2>Confirm Your Signup</h2>

<p>Follow this link to confirm your account:</p>

<!-- Web Browser Button -->
<a href="https://www.zipohubonline.com/auth/confirm?token_hash={{ .TokenHash }}&type=signup&email={{ .Email }}"
   style="display: inline-block; padding: 12px 24px; background-color: #10B981; color: white; text-decoration: none; border-radius: 4px;">
  Confirm Your Account (Web)
</a>

<!-- Mobile App Deep Link -->
<a href="zipohub://auth/confirm?token_hash={{ .TokenHash }}&type=signup&email={{ .Email }}"
   style="display: inline-block; padding: 12px 24px; background-color: #3B82F6; color: white; text-decoration: none; border-radius: 4px; margin: 8px 0;">
  Open in Mobile App
</a>

<p style="font-size: 12px; color: #64748B; margin-top: 24px;">
  Or copy this code to verify manually: <strong>{{ .TokenHash }}</strong>
</p>
```

---

## Complete Signup Flow

**`SignupScreen.js`:**
```javascript
import React, { useState } from 'react';
import { View, TextInput, Button, Alert } from 'react-native';

function SignupScreen({ navigation }) {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    phone_number: '',
    country: '',
    city: '',
  });

  const handleSignup = async () => {
    try {
      const response = await fetch(
        'https://your-backend-api.com/auth/mobile/signup',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            ...formData,
            role: 'CUSTOMER', // or 'SELLER'
          }),
        }
      );

      const data = await response.json();

      if (response.ok) {
        Alert.alert(
          'Success',
          'Account created! Please check your email to verify your account.',
          [
            {
              text: 'OK',
              onPress: () => {
                // Navigate to verification screen
                navigation.navigate('EmailVerification', {
                  email: formData.email
                });
              },
            },
          ]
        );
      } else {
        Alert.alert('Error', data.detail || 'Signup failed');
      }
    } catch (error) {
      console.error('Signup error:', error);
      Alert.alert('Error', 'Failed to create account. Please try again.');
    }
  };

  return (
    <View style={{ padding: 20 }}>
      <TextInput
        placeholder="Name"
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
      />
      <TextInput
        placeholder="Email"
        value={formData.email}
        onChangeText={(text) => setFormData({ ...formData, email: text })}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        placeholder="Password"
        value={formData.password}
        onChangeText={(text) => setFormData({ ...formData, password: text })}
        secureTextEntry
      />
      <Button title="Sign Up" onPress={handleSignup} />
    </View>
  );
}

export default SignupScreen;
```

---

## Testing

### Test Deep Links on Android:
```bash
# Test with ADB
adb shell am start -W -a android.intent.action.VIEW \
  -d "https://www.zipohubonline.com/auth/confirm?token_hash=TEST_TOKEN&type=signup&email=test@example.com" \
  com.yourcompany.zipohub

# Or with custom scheme
adb shell am start -W -a android.intent.action.VIEW \
  -d "zipohub://auth/confirm?token_hash=TEST_TOKEN&type=signup" \
  com.yourcompany.zipohub
```

### Test Deep Links on iOS:
```bash
xcrun simctl openurl booted "zipohub://auth/confirm?token_hash=TEST_TOKEN&type=signup"
```

### Test with Expo:
```bash
npx uri-scheme open "zipohub://auth/confirm?token_hash=TEST_TOKEN&type=signup" --ios
npx uri-scheme open "zipohub://auth/confirm?token_hash=TEST_TOKEN&type=signup" --android
```

---

## Best Practices

1. **Always handle errors gracefully** - Show user-friendly messages
2. **Store tokens securely** - Use `@react-native-async-storage/async-storage` or `expo-secure-store`
3. **Handle edge cases**:
   - User clicks link multiple times
   - Token expired
   - User already verified
   - App not installed (web fallback)
4. **Add loading states** - Show spinners during API calls
5. **Test on both platforms** - iOS and Android handle deep links differently

---

## Summary

**Recommended Approach:** Use **Deep Linking** (Option 1) for the best user experience. Users tap the email link, your app opens automatically, and verification happens seamlessly.

**Key Files to Create:**
- `App.js/App.tsx` - Handle deep link routing
- `EmailVerificationScreen.js` - Manual verification fallback
- Configure `AndroidManifest.xml` and `Info.plist` (or `app.json` for Expo)

**API Endpoints Used:**
- `GET /auth/confirm` - Verify email with token_hash
- `POST /auth/resend-verification` - Resend verification email
