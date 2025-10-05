# React Native + Next.js Subscription Payment Guide

Complete guide for implementing Paystack subscriptions in React Native mobile app using your existing Next.js backend.

---

## 📋 Overview

Your Next.js backend is already deployed at `https://www.zipohubonline.com` with working Paystack webhooks. This guide shows how to connect your React Native app to it.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React Native App → Next.js API → Paystack → Webhook        │
└─────────────────────────────────────────────────────────────┘

1. Mobile app calls Next.js API
2. Next.js initializes payment with Paystack
3. App opens Paystack checkout (WebView)
4. User pays
5. Paystack calls your webhook (automatic)
6. Webhook creates subscription in database
7. App verifies payment
```

---

## 🔧 Installation

### 1. Install Required Packages

```bash
npm install react-native-paystack-webview axios @react-native-async-storage/async-storage
# or
yarn add react-native-paystack-webview axios @react-native-async-storage/async-storage

# For iOS
cd ios && pod install && cd ..
```

### 2. Get Paystack Public Key

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Settings → API Keys & Webhooks
3. Copy **Public Key** (`pk_test_...`)

---

## 📱 React Native Implementation

### Step 1: Create API Configuration

```typescript
// src/config/api.ts
export const API_CONFIG = {
  BASE_URL: 'https://www.zipohubonline.com/api',
  PAYSTACK_PUBLIC_KEY: 'pk_test_d7ff80abce295bf7e23135cb4854b5b702c8550e', // Your key
};
```

### Step 2: Create API Service

```typescript
// src/services/subscription.service.ts
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { API_CONFIG } from '../config/api';

// Types
interface SubscriptionPlan {
  id: string;
  name: string;
  description: string;
  amount: number;
  currency: string;
  interval: string;
  region: string;
  planCode: string;
  subscriptionTier: string;
}

interface InitializePaymentResponse {
  data: {
    authorization_url: string;
    access_code: string;
    reference: string;
  };
}

interface SubscriptionStatusResponse {
  hasSubscription: boolean;
  subscription?: {
    id: string;
    expiresAt: string;
    plan: SubscriptionPlan;
  };
}

// Get auth token
const getAuthToken = async () => {
  return await AsyncStorage.getItem('auth_token');
};

// Get subscription plans
export const getSubscriptionPlans = async (): Promise<SubscriptionPlan[]> => {
  try {
    const response = await axios.get(
      `${API_CONFIG.BASE_URL}/subscription-plans`,
      {
        params: { region: 'GHANA' }
      }
    );
    return response.data;
  } catch (error: any) {
    console.error('Error fetching plans:', error.response?.data || error.message);
    throw new Error(error.response?.data?.error || 'Failed to fetch subscription plans');
  }
};

// Initialize subscription payment
export const initializeSubscription = async (
  subscriptionId: string,
  referralCode?: string
): Promise<InitializePaymentResponse> => {
  try {
    const token = await getAuthToken();

    if (!token) {
      throw new Error('Not authenticated');
    }

    const response = await axios.post(
      `${API_CONFIG.BASE_URL}/subscribe`,
      {
        subscriptionId,
        // Note: Next.js backend gets referral from cookies
        // For mobile, we'll handle it differently (see below)
      },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      }
    );

    return response.data;
  } catch (error: any) {
    console.error('Error initializing subscription:', error.response?.data || error.message);
    throw new Error(error.response?.data?.error || 'Failed to initialize payment');
  }
};

// Check subscription status
export const getSubscriptionStatus = async (): Promise<SubscriptionStatusResponse> => {
  try {
    const token = await getAuthToken();

    if (!token) {
      throw new Error('Not authenticated');
    }

    const response = await axios.get(
      `${API_CONFIG.BASE_URL}/subscription/status`,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );

    return response.data;
  } catch (error: any) {
    console.error('Error fetching subscription status:', error.response?.data || error.message);
    throw new Error(error.response?.data?.error || 'Failed to fetch subscription status');
  }
};

// Verify payment (optional - webhook handles the actual subscription creation)
export const verifyPayment = async (reference: string) => {
  try {
    const token = await getAuthToken();

    if (!token) {
      throw new Error('Not authenticated');
    }

    const response = await axios.get(
      `${API_CONFIG.BASE_URL}/verify-payment`,
      {
        params: { reference },
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }
    );

    return response.data;
  } catch (error: any) {
    console.error('Error verifying payment:', error.response?.data || error.message);
    // Don't throw - webhook already processed the payment
    return null;
  }
};
```

### Step 3: Create Payment Hook

```typescript
// src/hooks/useSubscription.ts
import { useState, useCallback } from 'react';
import { Alert } from 'react-native';
import {
  getSubscriptionPlans,
  initializeSubscription,
  getSubscriptionStatus,
  verifyPayment,
} from '../services/subscription.service';

interface PaymentData {
  authorization_url: string;
  access_code: string;
  reference: string;
}

export const useSubscription = () => {
  const [loading, setLoading] = useState(false);
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [subscriptionStatus, setSubscriptionStatus] = useState<any>(null);

  // Fetch available plans
  const fetchPlans = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getSubscriptionPlans();
      setPlans(data);
      return data;
    } catch (error: any) {
      Alert.alert('Error', error.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  // Initialize payment
  const startPayment = useCallback(async (
    subscriptionId: string,
    referralCode?: string
  ) => {
    try {
      setLoading(true);
      const data = await initializeSubscription(subscriptionId, referralCode);
      setPaymentData(data.data);
      return data.data;
    } catch (error: any) {
      Alert.alert('Payment Error', error.message);
      throw error;
    } finally {
      setLoading(false);
    }
  }, []);

  // Check subscription status
  const checkStatus = useCallback(async () => {
    try {
      setLoading(true);
      const status = await getSubscriptionStatus();
      setSubscriptionStatus(status);
      return status;
    } catch (error: any) {
      Alert.alert('Error', error.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // Verify payment after completion
  const verify = useCallback(async (reference: string) => {
    try {
      setLoading(true);
      const result = await verifyPayment(reference);
      return result;
    } catch (error: any) {
      // Don't show error - webhook already processed
      console.log('Verification error (non-critical):', error.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return {
    loading,
    paymentData,
    plans,
    subscriptionStatus,
    fetchPlans,
    startPayment,
    checkStatus,
    verify,
  };
};
```

### Step 4: Create Subscription Screen

```typescript
// src/screens/SubscriptionScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
  ScrollView,
} from 'react-native';
import { Paystack } from 'react-native-paystack-webview';
import { useSubscription } from '../hooks/useSubscription';
import { API_CONFIG } from '../config/api';
import AsyncStorage from '@react-native-async-storage/async-storage';

export const SubscriptionScreen = ({ navigation, route }) => {
  const [selectedPlan, setSelectedPlan] = useState<any>(null);
  const [showPaystack, setShowPaystack] = useState(false);
  const [userEmail, setUserEmail] = useState('');
  const [userName, setUserName] = useState('');

  const {
    loading,
    paymentData,
    plans,
    fetchPlans,
    startPayment,
    verify,
    checkStatus,
  } = useSubscription();

  // Get referral code from route params or AsyncStorage
  const referralCode = route.params?.referralCode;

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    // Fetch plans
    await fetchPlans();

    // Get user info from storage
    const email = await AsyncStorage.getItem('user_email');
    const name = await AsyncStorage.getItem('user_name');
    setUserEmail(email || 'user@example.com');
    setUserName(name || 'User');
  };

  const handleSelectPlan = async (plan: any) => {
    setSelectedPlan(plan);

    try {
      // Initialize payment
      await startPayment(plan.id, referralCode);

      // Show Paystack WebView
      setShowPaystack(true);
    } catch (error) {
      // Error already handled in hook
      console.error('Payment initialization failed:', error);
    }
  };

  const handlePaymentSuccess = async (response: any) => {
    console.log('✅ Payment successful:', response);
    setShowPaystack(false);

    // Optional: Verify payment (webhook already processed it)
    try {
      await verify(response.transactionRef.reference);
    } catch (error) {
      // Ignore verification errors
    }

    // Refresh subscription status
    await checkStatus();

    // Show success
    Alert.alert(
      'Subscription Activated! 🎉',
      `You are now subscribed to ${selectedPlan?.name}`,
      [
        {
          text: 'OK',
          onPress: () => navigation.navigate('Home'),
        },
      ]
    );
  };

  const handlePaymentCancel = () => {
    console.log('❌ Payment cancelled');
    setShowPaystack(false);
    Alert.alert('Payment Cancelled', 'You cancelled the payment process.');
  };

  if (loading && plans.length === 0) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#0066cc" />
        <Text style={styles.loadingText}>Loading subscription plans...</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Choose Your Plan</Text>
      <Text style={styles.subtitle}>Select a subscription tier to start selling</Text>

      {plans.map((plan) => (
        <TouchableOpacity
          key={plan.id}
          style={[
            styles.planCard,
            selectedPlan?.id === plan.id && styles.planCardSelected,
          ]}
          onPress={() => handleSelectPlan(plan)}
          disabled={loading}
        >
          <View style={styles.planHeader}>
            <Text style={styles.planName}>{plan.name}</Text>
            <View style={styles.tierBadge}>
              <Text style={styles.tierText}>{plan.subscriptionTier}</Text>
            </View>
          </View>

          <Text style={styles.planDescription}>{plan.description}</Text>

          <View style={styles.planFooter}>
            <Text style={styles.planPrice}>
              {plan.currency} {(plan.amount / 100).toFixed(2)}
            </Text>
            <Text style={styles.planInterval}>/ {plan.interval.toLowerCase()}</Text>
          </View>

          {loading && selectedPlan?.id === plan.id && (
            <ActivityIndicator style={styles.planLoader} color="#0066cc" />
          )}
        </TouchableOpacity>
      ))}

      {/* Paystack WebView */}
      {showPaystack && paymentData && (
        <Paystack
          paystackKey={API_CONFIG.PAYSTACK_PUBLIC_KEY}
          amount={selectedPlan.amount / 100} // Convert kobo to cedis
          billingEmail={userEmail}
          billingName={userName}
          currency={selectedPlan.currency}
          channels={['card', 'bank', 'ussd', 'mobile_money']}
          refNumber={paymentData.reference}
          onCancel={handlePaymentCancel}
          onSuccess={handlePaymentSuccess}
          autoStart={true}
        />
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 8,
    color: '#333',
  },
  subtitle: {
    fontSize: 16,
    color: '#666',
    marginBottom: 24,
  },
  planCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
    borderWidth: 2,
    borderColor: 'transparent',
  },
  planCardSelected: {
    borderColor: '#0066cc',
    backgroundColor: '#f0f7ff',
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  planName: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#333',
  },
  tierBadge: {
    backgroundColor: '#0066cc',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
  },
  tierText: {
    fontSize: 12,
    color: '#fff',
    fontWeight: '600',
  },
  planDescription: {
    fontSize: 14,
    color: '#666',
    marginBottom: 16,
    lineHeight: 20,
  },
  planFooter: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  planPrice: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#0066cc',
  },
  planInterval: {
    fontSize: 16,
    color: '#999',
    marginLeft: 6,
  },
  planLoader: {
    marginTop: 12,
  },
});
```

### Step 5: Create Home Screen with Subscription Status

```typescript
// src/screens/HomeScreen.tsx
import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  ScrollView,
} from 'react-native';
import { useSubscription } from '../hooks/useSubscription';

export const HomeScreen = ({ navigation }) => {
  const [refreshing, setRefreshing] = useState(false);
  const { loading, subscriptionStatus, checkStatus } = useSubscription();

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    await checkStatus();
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await loadStatus();
    setRefreshing(false);
  };

  if (loading && !subscriptionStatus) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#0066cc" />
      </View>
    );
  }

  const hasSubscription = subscriptionStatus?.hasSubscription;
  const subscription = subscriptionStatus?.subscription;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.title}>My Subscription</Text>

      {hasSubscription && subscription ? (
        <View style={styles.activeCard}>
          <View style={styles.statusBadge}>
            <Text style={styles.statusText}>✅ Active</Text>
          </View>

          <Text style={styles.planName}>{subscription.plan?.name}</Text>
          <Text style={styles.planTier}>{subscription.plan?.subscriptionTier}</Text>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Expires:</Text>
            <Text style={styles.infoValue}>
              {new Date(subscription.expiresAt).toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Interval:</Text>
            <Text style={styles.infoValue}>
              {subscription.plan?.interval}
            </Text>
          </View>

          <View style={styles.infoRow}>
            <Text style={styles.infoLabel}>Price:</Text>
            <Text style={styles.infoValue}>
              {subscription.plan?.currency} {(subscription.plan?.amount / 100).toFixed(2)}
            </Text>
          </View>

          <TouchableOpacity
            style={styles.manageButton}
            onPress={() => navigation.navigate('Subscription')}
          >
            <Text style={styles.manageButtonText}>Manage Subscription</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.inactiveCard}>
          <Text style={styles.noSubIcon}>📋</Text>
          <Text style={styles.noSubTitle}>No Active Subscription</Text>
          <Text style={styles.noSubMessage}>
            Subscribe to a plan to start selling your products
          </Text>

          <TouchableOpacity
            style={styles.subscribeButton}
            onPress={() => navigation.navigate('Subscription')}
          >
            <Text style={styles.subscribeButtonText}>View Plans</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 28,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#333',
  },
  activeCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
    borderLeftWidth: 4,
    borderLeftColor: '#4CAF50',
  },
  statusBadge: {
    backgroundColor: '#E8F5E9',
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    marginBottom: 16,
  },
  statusText: {
    color: '#4CAF50',
    fontWeight: '600',
    fontSize: 14,
  },
  planName: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 4,
  },
  planTier: {
    fontSize: 14,
    color: '#0066cc',
    marginBottom: 20,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#f0f0f0',
  },
  infoLabel: {
    fontSize: 14,
    color: '#666',
  },
  infoValue: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  manageButton: {
    backgroundColor: '#0066cc',
    paddingVertical: 14,
    borderRadius: 8,
    marginTop: 20,
    alignItems: 'center',
  },
  manageButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  inactiveCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 32,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  noSubIcon: {
    fontSize: 64,
    marginBottom: 16,
  },
  noSubTitle: {
    fontSize: 22,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 8,
  },
  noSubMessage: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  subscribeButton: {
    backgroundColor: '#0066cc',
    paddingHorizontal: 32,
    paddingVertical: 14,
    borderRadius: 8,
  },
  subscribeButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
});
```

---

## 🔐 Authentication Setup

Your Next.js backend expects a JWT token. Make sure to save it after login:

```typescript
// src/screens/LoginScreen.tsx
import AsyncStorage from '@react-native-async-storage/async-storage';

const handleLogin = async (email: string, password: string) => {
  try {
    const response = await axios.post(
      'https://www.zipohubonline.com/api/auth/login',
      { email, password }
    );

    // Save auth data
    await AsyncStorage.setItem('auth_token', response.data.token);
    await AsyncStorage.setItem('user_email', response.data.user.email);
    await AsyncStorage.setItem('user_name', response.data.user.name);

    // Navigate to home
    navigation.navigate('Home');
  } catch (error) {
    Alert.alert('Login Failed', error.message);
  }
};
```

---

## 🧪 Testing

### Test with Paystack Test Cards

| Card Number | Expiry | CVV | PIN | OTP | Result |
|-------------|--------|-----|-----|-----|--------|
| 4084084084084081 | Any future | 408 | 0000 | 123456 | Success |
| 5060990580000217499 | Any future | 606 | 1234 | 123456 | Success |

### Testing Flow

1. **Login to your app**
2. **Navigate to Subscription screen**
3. **Select a plan**
4. **Use test card details**
5. **Complete payment**
6. **Check Home screen for active subscription**

### Verify Webhook Processed

Check your Next.js webhook logs or database:
- `UserSubscriptions` table should have new record
- Subscription should show on Home screen

---

## 🎯 Referral Code Support

To pass referral codes from mobile app, you need to modify your Next.js `/subscribe` endpoint:

### Option 1: Pass in Request Body (Recommended)

**Update Next.js endpoint:**

```typescript
// app/api/subscribe/route.ts
const reqBody: {
  subscriptionId: string;
  referralCode?: string; // Add this
} = await request.json();

// Use referral code from body instead of cookies
const referralCode = reqBody.referralCode || request.cookies.get("referral_code")?.value;
```

**Mobile app:**

```typescript
await initializeSubscription(plan.id, 'AGENT123');
```

### Option 2: Use Headers

**Update Next.js endpoint:**

```typescript
const referralCode = request.headers.get('X-Referral-Code') ||
                     request.cookies.get("referral_code")?.value;
```

**Mobile app:**

```typescript
headers: {
  'Authorization': `Bearer ${token}`,
  'X-Referral-Code': referralCode,
}
```

---

## 🐛 Troubleshooting

### Issue: "Unauthorized" error

**Solution:** Check auth token is saved and valid

```typescript
const token = await AsyncStorage.getItem('auth_token');
console.log('Token:', token); // Should not be null
```

### Issue: Paystack WebView not opening

**Solution:** Check public key is correct

```typescript
// Should start with pk_test_ or pk_live_
PAYSTACK_PUBLIC_KEY: 'pk_test_d7ff80abce295bf7e23135cb4854b5b702c8550e'
```

### Issue: Payment succeeds but subscription not created

**Cause:** Webhook not receiving events

**Solution:**
1. Check Paystack Dashboard → Settings → Webhooks
2. Verify URL: `https://www.zipohubonline.com/api/payments/paystack/webhook`
3. Check webhook logs in Paystack dashboard

### Issue: CORS errors

**Cause:** Mobile apps don't have CORS issues, but if testing in web browser:

**Solution:** Your Next.js backend should already have CORS configured. If not, add:

```typescript
// next.config.js
async headers() {
  return [
    {
      source: '/api/:path*',
      headers: [
        { key: 'Access-Control-Allow-Origin', value: '*' },
        { key: 'Access-Control-Allow-Methods', value: 'GET,POST,PUT,DELETE,OPTIONS' },
        { key: 'Access-Control-Allow-Headers', value: 'Authorization, Content-Type' },
      ],
    },
  ];
}
```

---

## 📋 Summary Checklist

### Next.js Backend
- [x] Webhook already configured at `/api/payments/paystack/webhook`
- [x] `/subscribe` endpoint exists
- [ ] (Optional) Update to accept referralCode in request body

### React Native App
- [ ] Install `react-native-paystack-webview`
- [ ] Install `axios` and `@react-native-async-storage/async-storage`
- [ ] Add Paystack public key to config
- [ ] Create subscription service
- [ ] Create subscription hook
- [ ] Create Subscription screen
- [ ] Create Home screen with status
- [ ] Test with Paystack test cards

### Testing
- [ ] User can view plans
- [ ] User can select plan and pay
- [ ] Payment WebView opens correctly
- [ ] Subscription created after payment
- [ ] Home screen shows active subscription
- [ ] Subscription expires at correct time

---

## 🎉 You're Done!

Your mobile app now uses the same backend and webhooks as your website. No duplicate code, no separate webhook configuration needed!

**Questions? Check:**
- Paystack Dashboard for webhook logs
- Your Next.js deployment logs on Vercel
- React Native debugger console

---

**Last Updated:** October 4, 2025
**Backend:** https://www.zipohubonline.com
**Webhook:** https://www.zipohubonline.com/api/payments/paystack/webhook
