# Courier Authentication - React Native Implementation Guide

This guide will help you implement the courier authentication system in your React Native project using **unified authentication**.

## 🎯 Key Concept: Unified Authentication

**All users (Customers, Sellers, and Couriers) use the same authentication endpoints** (`/api/auth/*`). The only courier-specific endpoint is signup (`/api/courier/signup`), which creates a courier profile. After signup, couriers use the regular auth endpoints for login, password reset, etc.

---

## Table of Contents
1. [API Endpoints Overview](#api-endpoints-overview)
2. [Setup & Installation](#setup--installation)
3. [Authentication Flow](#authentication-flow)
4. [Implementation Steps](#implementation-steps)
5. [Code Examples](#code-examples)
6. [User Type Detection](#user-type-detection)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## API Endpoints Overview

### Courier-Specific Endpoint

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/courier/signup` | POST | Register a new courier (creates courier profile) | No |

### Shared Authentication Endpoints (All User Types)

These endpoints work for **all users** including couriers:

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/auth/login` | POST | Login (customers, sellers, couriers) | No |
| `/api/auth/refresh` | POST | Refresh access token | No |
| `/api/auth/status` | GET | Validate current token | Yes |
| `/api/auth/logout` | POST | Logout user | Yes |
| `/api/auth/password-reset/request` | POST | Request password reset OTP | No |
| `/api/auth/password-reset/verify-otp` | POST | Verify OTP code | No |
| `/api/auth/password-reset/complete` | POST | Complete password reset | No |

---

## Setup & Installation

### 1. Install Required Packages

```bash
npm install axios react-native-async-storage/async-storage
# or
yarn add axios @react-native-async-storage/async-storage
```

### 2. Create API Configuration

Create a file: `src/services/api.js`

```javascript
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://your-api-domain.com/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use(
  async (config) => {
    const token = await AsyncStorage.getItem('access_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor to handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = await AsyncStorage.getItem('refresh_token');
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token, refresh_token } = response.data;

        await AsyncStorage.setItem('access_token', access_token);
        await AsyncStorage.setItem('refresh_token', refresh_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        // Refresh failed, logout user
        await AsyncStorage.multiRemove([
          'access_token',
          'refresh_token',
          'user',
        ]);
        // Navigate to login screen
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default api;
```

---

## Authentication Flow

```
┌─────────────────┐
│ Courier Sign Up │──────────┐
│ /courier/signup │          │
└─────────────────┘          │
                             ▼
                      ┌──────────────┐
                      │Verify Email  │
                      └──────┬───────┘
                             │
                             ▼
                      ┌──────────────┐
                      │Regular Login │──────┐
                      │ /auth/login  │      │
                      └──────────────┘      │
                                            ▼
┌─────────────────┐                 ┌──────────────┐
│ Customer/Seller │────────────────▶│ Store Tokens │
│    Sign Up      │                 └──────┬───────┘
│  /auth/signup   │                        │
└─────────────────┘                        ▼
                                    ┌──────────────┐
                                    │Check user_type│
                                    └──────┬───────┘
                                           │
                     ┌─────────────────────┼─────────────────┐
                     ▼                     ▼                 ▼
              ┌─────────────┐      ┌─────────────┐  ┌─────────────┐
              │ Customer UI │      │ Courier UI  │  │ Seller UI   │
              └─────────────┘      └─────────────┘  └─────────────┘
```

---

## Implementation Steps

### Step 1: Create Unified Authentication Service

Create a file: `src/services/authService.js`

```javascript
import api from './api';
import AsyncStorage from '@react-native-async-storage/async-storage';

class AuthService {
  /**
   * Sign up a new courier (courier-specific)
   * @param {Object} data - Courier signup data
   * @returns {Promise}
   */
  async signupCourier(data) {
    try {
      const response = await api.post('/courier/signup', {
        email: data.email,
        password: data.password,
        name: data.name,
        phone_number: data.phone_number,
        country: data.country,
        city: data.city,
        address: data.address,
        vehicle_type: data.vehicle_type, // BICYCLE, MOTORCYCLE, CAR, VAN, TRUCK
        vehicle_number: data.vehicle_number,
        license_number: data.license_number,
      });

      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Sign up a regular user (customer/seller)
   * @param {Object} data - User signup data
   * @returns {Promise}
   */
  async signup(data) {
    try {
      const response = await api.post('/auth/signup', {
        email: data.email,
        password: data.password,
        name: data.name,
        phone_number: data.phone_number,
        country: data.country,
        city: data.city,
        address: data.address,
        business_name: data.business_name,
        business_description: data.business_description,
        role: data.role || 'CUSTOMER', // CUSTOMER or SELLER
      });

      const { user, access_token, refresh_token } = response.data;

      // Store tokens and user data
      await this.storeAuthData(access_token, refresh_token, user);

      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Login user (works for all user types)
   * @param {string} email
   * @param {string} password
   * @returns {Promise}
   */
  async login(email, password) {
    try {
      const response = await api.post('/auth/login', {
        email,
        password,
      });

      const { user, access_token, refresh_token } = response.data;

      // Store tokens and user data
      await this.storeAuthData(access_token, refresh_token, user);

      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Logout user
   * @returns {Promise}
   */
  async logout() {
    try {
      await api.post('/auth/logout');
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      // Clear local storage
      await AsyncStorage.multiRemove([
        'access_token',
        'refresh_token',
        'user',
      ]);
    }
  }

  /**
   * Refresh access token
   * @returns {Promise}
   */
  async refreshToken() {
    try {
      const refreshToken = await AsyncStorage.getItem('refresh_token');

      if (!refreshToken) {
        throw new Error('No refresh token available');
      }

      const response = await api.post('/auth/refresh', {
        refresh_token: refreshToken,
      });

      const { access_token, refresh_token: new_refresh_token } = response.data;

      await AsyncStorage.setItem('access_token', access_token);
      await AsyncStorage.setItem('refresh_token', new_refresh_token);

      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Validate current token
   * @returns {Promise}
   */
  async validateToken() {
    try {
      const response = await api.get('/auth/status');
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Request password reset OTP
   * @param {string} email
   * @returns {Promise}
   */
  async requestPasswordReset(email) {
    try {
      const response = await api.post('/auth/password-reset/request', {
        email,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Verify OTP code
   * @param {string} email
   * @param {string} token
   * @returns {Promise}
   */
  async verifyOTP(email, token) {
    try {
      const response = await api.post('/auth/password-reset/verify-otp', {
        email,
        token,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Complete password reset
   * @param {string} email
   * @param {string} token
   * @param {string} newPassword
   * @returns {Promise}
   */
  async completePasswordReset(email, token, newPassword) {
    try {
      const response = await api.post('/auth/password-reset/complete', {
        email,
        token,
        new_password: newPassword,
      });
      return response.data;
    } catch (error) {
      throw this.handleError(error);
    }
  }

  /**
   * Get current user data
   * @returns {Promise}
   */
  async getCurrentUser() {
    try {
      const userJson = await AsyncStorage.getItem('user');
      return userJson ? JSON.parse(userJson) : null;
    } catch (error) {
      console.error('Error getting current user:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated
   * @returns {Promise<boolean>}
   */
  async isAuthenticated() {
    try {
      const token = await AsyncStorage.getItem('access_token');
      return !!token;
    } catch (error) {
      return false;
    }
  }

  /**
   * Get user type (CUSTOMER, SELLER, COURIER)
   * @returns {Promise<string|null>}
   */
  async getUserType() {
    try {
      const user = await this.getCurrentUser();
      return user?.user_type || user?.role || null;
    } catch (error) {
      return null;
    }
  }

  /**
   * Store authentication data
   * @private
   */
  async storeAuthData(accessToken, refreshToken, user) {
    await AsyncStorage.multiSet([
      ['access_token', accessToken],
      ['refresh_token', refreshToken],
      ['user', JSON.stringify(user)],
    ]);
  }

  /**
   * Handle API errors
   * @private
   */
  handleError(error) {
    if (error.response) {
      // Server responded with error
      const message = error.response.data?.detail || error.response.data?.message || 'An error occurred';
      return new Error(message);
    } else if (error.request) {
      // Request made but no response
      return new Error('Network error. Please check your connection.');
    } else {
      // Something else happened
      return new Error(error.message || 'An unexpected error occurred');
    }
  }
}

export default new AuthService();
```

---

## Code Examples

### Example 1: Courier Sign Up Screen

```javascript
import React, { useState } from 'react';
import { View, TextInput, Button, Alert, ScrollView, Picker } from 'react-native';
import authService from '../services/authService';

const CourierSignUpScreen = ({ navigation }) => {
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    phone_number: '',
    country: '',
    city: '',
    address: '',
    vehicle_type: 'MOTORCYCLE',
    vehicle_number: '',
    license_number: '',
  });
  const [loading, setLoading] = useState(false);

  const handleSignUp = async () => {
    setLoading(true);
    try {
      const result = await authService.signupCourier(formData);
      Alert.alert(
        'Success',
        result.message || 'Account created successfully! Please verify your email.',
        [
          {
            text: 'OK',
            onPress: () => navigation.navigate('Login')
          }
        ]
      );
    } catch (error) {
      Alert.alert('Error', error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={{ padding: 20 }}>
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
      <TextInput
        placeholder="Full Name"
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
      />
      <TextInput
        placeholder="Phone Number"
        value={formData.phone_number}
        onChangeText={(text) => setFormData({ ...formData, phone_number: text })}
        keyboardType="phone-pad"
      />

      <Picker
        selectedValue={formData.vehicle_type}
        onValueChange={(value) => setFormData({ ...formData, vehicle_type: value })}
      >
        <Picker.Item label="Bicycle" value="BICYCLE" />
        <Picker.Item label="Motorcycle" value="MOTORCYCLE" />
        <Picker.Item label="Car" value="CAR" />
        <Picker.Item label="Van" value="VAN" />
        <Picker.Item label="Truck" value="TRUCK" />
      </Picker>

      <TextInput
        placeholder="Vehicle Number"
        value={formData.vehicle_number}
        onChangeText={(text) => setFormData({ ...formData, vehicle_number: text })}
      />
      <TextInput
        placeholder="License Number"
        value={formData.license_number}
        onChangeText={(text) => setFormData({ ...formData, license_number: text })}
      />

      <Button
        title={loading ? 'Signing Up...' : 'Sign Up as Courier'}
        onPress={handleSignUp}
        disabled={loading}
      />
    </ScrollView>
  );
};

export default CourierSignUpScreen;
```

### Example 2: Unified Login Screen

```javascript
import React, { useState } from 'react';
import { View, TextInput, Button, Alert, StyleSheet } from 'react-native';
import authService from '../services/authService';

const LoginScreen = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email || !password) {
      Alert.alert('Error', 'Please enter email and password');
      return;
    }

    setLoading(true);
    try {
      const result = await authService.login(email, password);

      // Check user type and navigate accordingly
      const userType = result.user.user_type || result.user.role;

      switch (userType) {
        case 'COURIER':
          navigation.replace('CourierHome');
          break;
        case 'SELLER':
          navigation.replace('SellerHome');
          break;
        case 'CUSTOMER':
        default:
          navigation.replace('CustomerHome');
          break;
      }
    } catch (error) {
      Alert.alert('Login Failed', error.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <TextInput
        style={styles.input}
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        keyboardType="email-address"
        autoCapitalize="none"
      />
      <TextInput
        style={styles.input}
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
      />
      <Button
        title={loading ? 'Logging in...' : 'Login'}
        onPress={handleLogin}
        disabled={loading}
      />
      <Button
        title="Forgot Password?"
        onPress={() => navigation.navigate('ForgotPassword')}
      />
      <Button
        title="Sign Up as Customer/Seller"
        onPress={() => navigation.navigate('SignUp')}
      />
      <Button
        title="Sign Up as Courier"
        onPress={() => navigation.navigate('CourierSignUp')}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    paddingHorizontal: 15,
    marginBottom: 15,
  },
});

export default LoginScreen;
```

### Example 3: Authentication Context with User Type Detection

Create a file: `src/context/AuthContext.js`

```javascript
import React, { createContext, useState, useEffect, useContext } from 'react';
import authService from '../services/authService';

const AuthContext = createContext();

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userType, setUserType] = useState(null);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const authenticated = await authService.isAuthenticated();
      setIsAuthenticated(authenticated);

      if (authenticated) {
        const userData = await authService.getCurrentUser();
        setUser(userData);
        setUserType(userData?.user_type || userData?.role);
      }
    } catch (error) {
      console.error('Auth check error:', error);
    } finally {
      setLoading(false);
    }
  };

  const login = async (email, password) => {
    const result = await authService.login(email, password);
    setUser(result.user);
    setUserType(result.user?.user_type || result.user?.role);
    setIsAuthenticated(true);
    return result;
  };

  const signupCourier = async (data) => {
    const result = await authService.signupCourier(data);
    // Note: Courier signup doesn't auto-login, user needs to verify email first
    return result;
  };

  const signup = async (data) => {
    const result = await authService.signup(data);
    setUser(result.user);
    setUserType(result.user?.user_type || result.user?.role);
    setIsAuthenticated(true);
    return result;
  };

  const logout = async () => {
    await authService.logout();
    setUser(null);
    setUserType(null);
    setIsAuthenticated(false);
  };

  const isCourier = () => userType === 'COURIER';
  const isSeller = () => userType === 'SELLER';
  const isCustomer = () => userType === 'CUSTOMER';

  return (
    <AuthContext.Provider
      value={{
        user,
        userType,
        isAuthenticated,
        loading,
        login,
        signup,
        signupCourier,
        logout,
        refreshUser: checkAuth,
        isCourier,
        isSeller,
        isCustomer,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
```

---

## User Type Detection

The API returns `user_type` field in the user object:

```javascript
{
  "user": {
    "user_id": "uuid",
    "name": "John Doe",
    "email": "john@example.com",
    "user_type": "COURIER",  // CUSTOMER, SELLER, or COURIER
    "courier_profile": {      // Only present if user_type is COURIER
      "courier_id": "uuid",
      "courier_code": "COU-ABC123",
      "vehicle_type": "MOTORCYCLE",
      "rating": 4.8,
      "is_verified": true
    }
  }
}
```

### Conditional Navigation Based on User Type

```javascript
const navigateBasedOnUserType = (user) => {
  const userType = user.user_type || user.role;

  switch (userType) {
    case 'COURIER':
      return navigation.replace('CourierDashboard');
    case 'SELLER':
      return navigation.replace('SellerDashboard');
    case 'CUSTOMER':
    default:
      return navigation.replace('Home');
  }
};
```

### Conditional UI Rendering

```javascript
const HomeScreen = () => {
  const { user, isCourier, isSeller, isCustomer } = useAuth();

  return (
    <View>
      {isCourier() && <CourierDashboard />}
      {isSeller() && <SellerDashboard />}
      {isCustomer() && <CustomerDashboard />}
    </View>
  );
};
```

---

## Error Handling

Same as before - unified across all user types.

---

## Best Practices

### 1. Single Sign-In Flow
- Use the same login screen for all user types
- Detect user type after successful login
- Route to appropriate dashboard based on `user_type`

### 2. User Type Checking
```javascript
// Always check user_type field
const userType = user.user_type || user.role;

// Use helper functions
if (authContext.isCourier()) {
  // Show courier-specific features
}
```

### 3. Courier Profile Access
```javascript
// Check if courier profile exists
if (user.user_type === 'COURIER' && user.courier_profile) {
  const courierCode = user.courier_profile.courier_code;
  const rating = user.courier_profile.rating;
  // Use courier data
}
```

---

## API Response Examples

### Courier Login Response
```json
{
  "user": {
    "user_id": "uuid",
    "name": "John Doe",
    "email": "courier@example.com",
    "phone_number": "+1234567890",
    "user_type": "COURIER",
    "verified": true,
    "role": "COURIER",
    "courier_profile": {
      "courier_id": "uuid",
      "courier_code": "COU-ABC123",
      "vehicle_type": "MOTORCYCLE",
      "vehicle_number": "GH-1234-20",
      "license_number": "DL-12345",
      "rating": 4.8,
      "total_deliveries": 150,
      "completed_deliveries": 148,
      "is_available": true,
      "is_verified": true
    }
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

### Customer/Seller Login Response
```json
{
  "user": {
    "user_id": "uuid",
    "name": "Jane Smith",
    "email": "customer@example.com",
    "user_type": "CUSTOMER",
    "verified": true,
    "role": "CUSTOMER",
    "courier_profile": null
  },
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

## Summary

✅ **Courier Signup**: Use `/api/courier/signup`
✅ **All Login**: Use `/api/auth/login` (works for all user types)
✅ **Password Reset**: Use `/api/auth/password-reset/*` (works for all user types)
✅ **Token Refresh**: Use `/api/auth/refresh` (works for all user types)
✅ **User Type**: Check `user.user_type` field to determine user role
✅ **Courier Profile**: Available as `user.courier_profile` when `user_type === 'COURIER'`

---

## License
Private - ZipoHub Internal Use Only
