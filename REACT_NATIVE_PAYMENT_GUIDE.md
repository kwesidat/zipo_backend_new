# React Native Paystack Subscription Payment Guide

Complete guide for implementing subscription payments in React Native with Paystack and webhook integration.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Payment Flow Diagram](#payment-flow-diagram)
4. [Backend Setup](#backend-setup)
5. [React Native Implementation](#react-native-implementation)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│  React Native App  →  Backend API  →  Paystack  →  Webhook  │
└─────────────────────────────────────────────────────────────┘

1. User selects plan in your app
2. App calls your backend /api/subscribe
3. Backend initializes payment with Paystack
4. App opens Paystack checkout (WebView or browser)
5. User pays with card
6. Paystack AUTOMATICALLY calls your webhook
7. Webhook creates subscription & pays commission
8. App verifies payment and shows success
```

### Key Concept: Webhook vs Verification

| Endpoint | Called By | Purpose | When It Runs |
|----------|-----------|---------|--------------|
| **Webhook** (`/api/webhooks/paystack`) | Paystack (automatic) | Creates subscription, pays commission | Always, even if user closes app |
| **Verify** (`/api/subscription/verify`) | Your app (manual) | Confirms payment for user UI | Only when user returns to app |

**Important:** The webhook does the real work. Verification just confirms status for the user.

---

## Installation

### 1. Install Required Packages

```bash
npm install react-native-paystack-webview
# or
yarn add react-native-paystack-webview

# For iOS
cd ios && pod install && cd ..
```

### 2. Add Permissions

**Android:** `android/app/src/main/AndroidManifest.xml`
```xml
<uses-permission android:name="android.permission.INTERNET" />
```

**iOS:** Already included in react-native-paystack-webview

---

## Payment Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     COMPLETE PAYMENT FLOW                       │
└─────────────────────────────────────────────────────────────────┘

STEP 1: Initialize Payment
─────────────────────────────────────────────────────
[React Native App]
  User clicks "Subscribe to Plan"
        ↓
  POST /api/subscribe
  {
    subscriptionPlanId: "plan_uuid",
    referralCode: "AGENT123"  // Optional
  }
        ↓
[Your Backend - app/routes/payments.py]
  1. Validate user is authenticated
  2. Get plan details from database
  3. Calculate amount in kobo (GHS 100 = 10000 kobo)
  4. Prepare metadata:
     {
       userId: "user_uuid",
       subscriptionId: "plan_uuid",
       transactionType: "subscription",
       referralCode: "AGENT123"  // If provided
     }
  5. Call Paystack API to initialize payment
        ↓
  Response:
  {
    authorization_url: "https://checkout.paystack.com/xyz",
    access_code: "abc123",
    reference: "ref_xxx"
  }
        ↓
[React Native App]
  Receives authorization_url and reference


STEP 2: User Pays
─────────────────────────────────────────────────────
[React Native App]
  Opens Paystack WebView with authorization_url
        ↓
[Paystack Payment Page]
  User enters card details:
  - Card number
  - Expiry date
  - CVV
  - PIN (if required)
  - OTP (if required)
        ↓
  Paystack processes payment
        ↓
  Payment successful ✅


STEP 3: Webhook Processing (AUTOMATIC - Paystack calls this)
─────────────────────────────────────────────────────
[Paystack Server]
  Immediately sends HTTP POST to:
  https://your-domain.com/api/webhooks/paystack

  Headers:
  {
    "x-paystack-signature": "hmac_sha512_signature",
    "content-type": "application/json"
  }

  Body:
  {
    "event": "charge.success",
    "data": {
      "id": 123456,
      "reference": "ref_xxx",
      "amount": 10000,  // in kobo
      "currency": "GHS",
      "status": "success",
      "metadata": {
        "userId": "user_uuid",
        "subscriptionId": "plan_uuid",
        "transactionType": "subscription",
        "referralCode": "AGENT123"
      }
    }
  }
        ↓
[Your Backend - app/routes/webhooks.py]
  1. ✅ Verify signature (security)
  2. ✅ Extract metadata
  3. ✅ Check for duplicate subscription (5-min window)
  4. ✅ Create/renew subscription in database
  5. ✅ Process agent commission (10%)
  6. ✅ Process referral commission (if applicable)
  7. ✅ Update agent balances
  8. ✅ Create activity logs
  9. ✅ Send success response to Paystack
        ↓
  Database now has:
  - New UserSubscription record
  - CommissionTransaction records
  - AgentActivity logs
  - Updated agent balances


STEP 4: User Returns to App
─────────────────────────────────────────────────────
[Paystack WebView]
  Closes and returns to React Native app
        ↓
[React Native App]
  onSuccess callback triggered
  Receives: { transactionRef: "ref_xxx" }
        ↓
  POST /api/subscription/verify?reference=ref_xxx
        ↓
[Your Backend - app/routes/payments.py]
  1. Verify with Paystack API
  2. Check subscription exists (created by webhook)
  3. Return subscription details
        ↓
  Response:
  {
    "status": "success",
    "subscription": {
      "id": "sub_uuid",
      "plan": { "name": "Level 1" },
      "expiresAt": "2025-11-04T12:00:00Z"
    }
  }
        ↓
[React Native App]
  Shows success message
  Navigates to home screen
  Updates UI to show active subscription


STEP 5: Verify Subscription Active
─────────────────────────────────────────────────────
[React Native App]
  On app launch or navigation:
  GET /api/subscription/status
        ↓
[Your Backend]
  Response:
  {
    "has_subscription": true,
    "can_create_product": true,
    "max_products": 5,
    "current_products": 2,
    "expires_at": "2025-11-04T12:00:00Z",
    "plan": { "name": "Level 1" }
  }
        ↓
[React Native App]
  Updates UI based on subscription status
```

---

## Backend Setup

### 1. Verify Environment Variables

```bash
# .env file
PAYSTACK_SECRET_KEY=sk_test_your_secret_key
PAYSTACK_API_KEY=sk_test_your_secret_key
```

### 2. Configure Paystack Webhook

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Navigate to **Settings → Webhooks**
3. Add webhook URL:
   ```
   Production: https://api.your-domain.com/api/webhooks/paystack
   Development: https://your-ngrok-url.ngrok.io/api/webhooks/paystack
   ```

### 3. Get Your Paystack Public Key

1. Go to [Paystack Dashboard](https://dashboard.paystack.com)
2. Navigate to **Settings → API Keys & Webhooks**
3. Copy **Public Key** (starts with `pk_test_` or `pk_live_`)

---

## React Native Implementation

### Step 1: Create API Service

```typescript
// services/api.ts
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_URL = 'https://your-backend-url.com/api';

// Get auth token from storage
const getAuthToken = async () => {
  return await AsyncStorage.getItem('auth_token');
};

// Subscribe to plan
export const subscribeToPlain = async (
  subscriptionPlanId: string,
  referralCode?: string
) => {
  const token = await getAuthToken();

  const response = await axios.post(
    `${API_URL}/subscribe`,
    {
      subscriptionPlanId,
      referralCode, // Optional: pass if user has referral code
    },
    {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    }
  );

  return response.data;
};

// Verify payment
export const verifySubscriptionPayment = async (reference: string) => {
  const token = await getAuthToken();

  const response = await axios.post(
    `${API_URL}/subscription/verify?reference=${reference}`,
    {},
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  return response.data;
};

// Get subscription status
export const getSubscriptionStatus = async () => {
  const token = await getAuthToken();

  const response = await axios.get(`${API_URL}/subscription/status`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  return response.data;
};

// Get available plans
export const getSubscriptionPlans = async () => {
  const response = await axios.get(`${API_URL}/subscription-plans`);
  return response.data;
};
```

### Step 2: Create Payment Hook

```typescript
// hooks/usePaystackPayment.ts
import { useState } from 'react';
import { Alert } from 'react-native';
import { subscribeToPlain, verifySubscriptionPayment } from '../services/api';

interface PaymentData {
  authorization_url: string;
  access_code: string;
  reference: string;
}

export const usePaystackPayment = () => {
  const [loading, setLoading] = useState(false);
  const [paymentData, setPaymentData] = useState<PaymentData | null>(null);

  const initializePayment = async (
    subscriptionPlanId: string,
    referralCode?: string
  ) => {
    try {
      setLoading(true);

      // Step 1: Initialize payment with your backend
      const response = await subscribeToPlain(subscriptionPlanId, referralCode);

      console.log('Payment initialized:', response);

      setPaymentData(response.data);
      return response.data;

    } catch (error: any) {
      console.error('Payment initialization error:', error);

      Alert.alert(
        'Payment Error',
        error.response?.data?.detail || 'Failed to initialize payment'
      );

      throw error;
    } finally {
      setLoading(false);
    }
  };

  const verifyPayment = async (reference: string) => {
    try {
      setLoading(true);

      // Step 2: Verify payment after user completes payment
      const response = await verifySubscriptionPayment(reference);

      console.log('Payment verified:', response);

      return response;

    } catch (error: any) {
      console.error('Payment verification error:', error);

      Alert.alert(
        'Verification Error',
        error.response?.data?.detail || 'Failed to verify payment'
      );

      throw error;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    paymentData,
    initializePayment,
    verifyPayment,
  };
};
```

### Step 3: Create Subscription Screen

```typescript
// screens/SubscriptionScreen.tsx
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { Paystack } from 'react-native-paystack-webview';
import { usePaystackPayment } from '../hooks/usePaystackPayment';
import { getSubscriptionPlans } from '../services/api';

const PAYSTACK_PUBLIC_KEY = 'pk_test_your_public_key_here'; // From Paystack dashboard

interface Plan {
  id: string;
  name: string;
  description: string;
  price: number;
  currency: string;
  interval: string;
  tier: string;
}

export const SubscriptionScreen = ({ navigation, route }) => {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<Plan | null>(null);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [showPaystack, setShowPaystack] = useState(false);

  const { loading, paymentData, initializePayment, verifyPayment } = usePaystackPayment();

  // Optional: Get referral code from route params or AsyncStorage
  const referralCode = route.params?.referralCode;

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      const data = await getSubscriptionPlans();
      setPlans(data);
    } catch (error) {
      Alert.alert('Error', 'Failed to load subscription plans');
    } finally {
      setLoadingPlans(false);
    }
  };

  const handleSelectPlan = async (plan: Plan) => {
    setSelectedPlan(plan);

    try {
      // Initialize payment with your backend
      const paymentInfo = await initializePayment(plan.id, referralCode);

      // Show Paystack WebView
      setShowPaystack(true);

    } catch (error) {
      // Error already handled in hook
    }
  };

  const handlePaymentSuccess = async (response: any) => {
    console.log('Payment successful:', response);

    setShowPaystack(false);

    try {
      // Verify payment with your backend
      const verification = await verifyPayment(response.transactionRef.reference);

      // Show success message
      Alert.alert(
        'Subscription Activated! 🎉',
        `You are now subscribed to ${selectedPlan?.name}`,
        [
          {
            text: 'OK',
            onPress: () => {
              // Navigate to home or dashboard
              navigation.navigate('Home');
            },
          },
        ]
      );

    } catch (error) {
      // Verification failed, but payment might still be processed by webhook
      Alert.alert(
        'Payment Processing',
        'Your payment is being processed. Please check your subscription status in a moment.',
        [
          {
            text: 'OK',
            onPress: () => navigation.navigate('Home'),
          },
        ]
      );
    }
  };

  const handlePaymentCancel = () => {
    console.log('Payment cancelled');
    setShowPaystack(false);

    Alert.alert(
      'Payment Cancelled',
      'You cancelled the payment process.'
    );
  };

  if (loadingPlans) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#0066cc" />
        <Text style={styles.loadingText}>Loading subscription plans...</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Choose Your Plan</Text>

      {plans.map((plan) => (
        <TouchableOpacity
          key={plan.id}
          style={styles.planCard}
          onPress={() => handleSelectPlan(plan)}
          disabled={loading}
        >
          <View style={styles.planHeader}>
            <Text style={styles.planName}>{plan.name}</Text>
            <Text style={styles.planTier}>{plan.tier}</Text>
          </View>

          <Text style={styles.planDescription}>{plan.description}</Text>

          <View style={styles.planFooter}>
            <Text style={styles.planPrice}>
              {plan.currency} {(plan.price / 100).toFixed(2)}
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
          paystackKey={PAYSTACK_PUBLIC_KEY}
          amount={selectedPlan!.price / 100} // Convert kobo to main currency
          billingEmail="user@example.com" // Get from user data
          billingName="User Name" // Get from user data
          currency={selectedPlan!.currency}
          channels={['card', 'bank', 'ussd', 'qr', 'mobile_money']}
          refNumber={paymentData.reference}
          onCancel={handlePaymentCancel}
          onSuccess={handlePaymentSuccess}
          autoStart={true}
        />
      )}
    </View>
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
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
    color: '#333',
  },
  planCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 20,
    marginBottom: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  planHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  planName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  planTier: {
    fontSize: 12,
    color: '#0066cc',
    backgroundColor: '#e6f2ff',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  planDescription: {
    fontSize: 14,
    color: '#666',
    marginBottom: 15,
  },
  planFooter: {
    flexDirection: 'row',
    alignItems: 'baseline',
  },
  planPrice: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#0066cc',
  },
  planInterval: {
    fontSize: 14,
    color: '#999',
    marginLeft: 5,
  },
  planLoader: {
    marginTop: 10,
  },
});
```

### Step 4: Check Subscription Status

```typescript
// screens/HomeScreen.tsx or App.tsx
import React, { useEffect, useState } from 'react';
import { View, Text, StyleSheet, TouchableOpacity } from 'react-native';
import { getSubscriptionStatus } from '../services/api';

export const HomeScreen = ({ navigation }) => {
  const [subscriptionStatus, setSubscriptionStatus] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkSubscription();
  }, []);

  const checkSubscription = async () => {
    try {
      const status = await getSubscriptionStatus();
      setSubscriptionStatus(status);
    } catch (error) {
      console.error('Error checking subscription:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <View style={styles.container}><Text>Loading...</Text></View>;
  }

  return (
    <View style={styles.container}>
      {subscriptionStatus?.has_subscription ? (
        <View style={styles.activeSubscription}>
          <Text style={styles.statusText}>✅ Active Subscription</Text>
          <Text style={styles.planName}>{subscriptionStatus.plan?.name}</Text>
          <Text style={styles.expiryText}>
            Expires: {new Date(subscriptionStatus.expires_at).toLocaleDateString()}
          </Text>
          <Text style={styles.productsText}>
            Products: {subscriptionStatus.current_products} / {subscriptionStatus.max_products || '∞'}
          </Text>
        </View>
      ) : (
        <View style={styles.noSubscription}>
          <Text style={styles.statusText}>❌ No Active Subscription</Text>
          <Text style={styles.message}>Subscribe to start selling</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => navigation.navigate('Subscription')}
          >
            <Text style={styles.buttonText}>View Plans</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    justifyContent: 'center',
  },
  activeSubscription: {
    backgroundColor: '#e6f9e6',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
  },
  noSubscription: {
    backgroundColor: '#ffe6e6',
    padding: 20,
    borderRadius: 12,
    alignItems: 'center',
  },
  statusText: {
    fontSize: 20,
    fontWeight: 'bold',
    marginBottom: 10,
  },
  planName: {
    fontSize: 18,
    marginBottom: 5,
  },
  expiryText: {
    fontSize: 14,
    color: '#666',
  },
  productsText: {
    fontSize: 14,
    color: '#666',
    marginTop: 5,
  },
  message: {
    fontSize: 16,
    marginBottom: 20,
  },
  button: {
    backgroundColor: '#0066cc',
    paddingHorizontal: 30,
    paddingVertical: 12,
    borderRadius: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: 'bold',
  },
});
```

---

## Testing

### Test with Paystack Test Cards

Use these test cards on Paystack payment page:

| Card Number | Expiry | CVV | PIN | OTP | Result |
|-------------|--------|-----|-----|-----|--------|
| 4084084084084081 | Any future date | 408 | 0000 | 123456 | Success |
| 5060990580000217499 | Any future date | 606 | 1234 | 123456 | Success |
| 4084084084084081 | Any future date | 408 | 0000 | 000000 | Failed |

### Testing Flow

1. **Start your backend**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

2. **Start ngrok** (for local testing)
   ```bash
   ngrok http 8000
   # Update Paystack webhook with ngrok URL
   ```

3. **Update API_URL in React Native**
   ```typescript
   const API_URL = 'https://your-ngrok-url.ngrok.io/api';
   ```

4. **Run React Native app**
   ```bash
   npx react-native run-android
   # or
   npx react-native run-ios
   ```

5. **Test payment flow**
   - Select a plan
   - Use test card: 4084084084084081
   - Complete payment
   - Check backend logs for webhook processing

### Verify Webhook Received

Check your backend logs for:
```
🔄 Webhook received at: 2025-10-04T12:00:00
✅ Signature verified
📨 Processing event: charge.success
💰 Payment amount: 10000 kobo (GHS 100.00)
✅ Subscription created
💰 Commission processed: GHS 10.00
⚡ Webhook acknowledged in 250ms
```

---

## Troubleshooting

### Issue: Payment succeeds but subscription not created

**Cause:** Webhook not configured or failing

**Solution:**
1. Check Paystack dashboard → Settings → Webhooks
2. Verify webhook URL is correct
3. Check backend logs for webhook errors
4. Test webhook endpoint: `GET /api/webhooks/paystack/health`

### Issue: "Invalid signature" error in webhook

**Cause:** Wrong Paystack secret key

**Solution:**
```bash
# Verify in .env
PAYSTACK_SECRET_KEY=sk_test_your_actual_key
PAYSTACK_API_KEY=sk_test_your_actual_key
```

### Issue: Paystack WebView not opening

**Cause:** Missing public key or wrong format

**Solution:**
```typescript
// Make sure you're using PUBLIC key (pk_test_...)
const PAYSTACK_PUBLIC_KEY = 'pk_test_xxxxx'; // NOT sk_test_
```

### Issue: User pays but verify endpoint fails

**This is OK!** The webhook already created the subscription. The verify endpoint is optional.

**Solution:**
```typescript
// Handle gracefully
catch (error) {
  Alert.alert(
    'Payment Processing',
    'Your payment is being processed. Check subscription status shortly.',
    [{ text: 'OK', onPress: () => navigation.navigate('Home') }]
  );
}
```

### Issue: Referral commission not working

**Cause:** Referral code not passed in metadata

**Solution:**
```typescript
// Make sure to pass referralCode
await initializePayment(plan.id, referralCode);

// Check backend receives it
metadata = {
  userId: user_id,
  subscriptionId: plan_id,
  referralCode: referral_code  // ✅ Must be included
}
```

### Issue: Double subscription created

**Cause:** User paying twice quickly

**Solution:** Backend already handles this with 5-minute duplicate check. No action needed.

---

## Best Practices

### 1. Handle Network Errors

```typescript
const initializePayment = async (planId: string) => {
  try {
    // ... payment logic
  } catch (error: any) {
    if (error.response?.status === 401) {
      Alert.alert('Session Expired', 'Please login again');
      navigation.navigate('Login');
    } else if (error.message === 'Network Error') {
      Alert.alert('Network Error', 'Please check your internet connection');
    } else {
      Alert.alert('Error', 'Something went wrong. Please try again');
    }
  }
};
```

### 2. Show Loading States

```typescript
{loading ? (
  <ActivityIndicator size="large" color="#0066cc" />
) : (
  <TouchableOpacity onPress={handleSelectPlan}>
    <Text>Subscribe</Text>
  </TouchableOpacity>
)}
```

### 3. Refresh Subscription Status

```typescript
useEffect(() => {
  // Refresh when screen comes into focus
  const unsubscribe = navigation.addListener('focus', () => {
    checkSubscription();
  });

  return unsubscribe;
}, [navigation]);
```

### 4. Store Referral Code

```typescript
// When user clicks referral link
import AsyncStorage from '@react-native-async-storage/async-storage';

const handleReferralLink = async (code: string) => {
  await AsyncStorage.setItem('referral_code', code);
};

// Use it during subscription
const referralCode = await AsyncStorage.getItem('referral_code');
await initializePayment(planId, referralCode);
```

### 5. Clear Referral After Use

```typescript
const handlePaymentSuccess = async (response) => {
  // ... verify payment

  // Clear referral code after successful payment
  await AsyncStorage.removeItem('referral_code');

  // ... navigate
};
```

---

## Complete Example Project Structure

```
your-app/
├── src/
│   ├── screens/
│   │   ├── SubscriptionScreen.tsx  ✅ Plan selection & payment
│   │   ├── HomeScreen.tsx           ✅ Subscription status display
│   │   └── PaymentSuccessScreen.tsx ✅ Success confirmation
│   ├── services/
│   │   └── api.ts                   ✅ API calls
│   ├── hooks/
│   │   └── usePaystackPayment.ts    ✅ Payment logic
│   ├── types/
│   │   └── subscription.ts          ✅ TypeScript types
│   └── navigation/
│       └── AppNavigator.tsx         ✅ Navigation setup
└── package.json
```

---

## Summary Checklist

### Backend Setup
- [ ] Add `PAYSTACK_SECRET_KEY` to `.env`
- [ ] Configure webhook URL in Paystack dashboard
- [ ] Run SQL function `increment_agent_balances.sql`
- [ ] Test webhook health: `GET /api/webhooks/paystack/health`

### React Native Setup
- [ ] Install `react-native-paystack-webview`
- [ ] Get Paystack public key from dashboard
- [ ] Create API service with auth headers
- [ ] Implement payment hook
- [ ] Create subscription screen
- [ ] Add subscription status check

### Testing
- [ ] Test with Paystack test cards
- [ ] Verify webhook receives events
- [ ] Check subscription created in database
- [ ] Verify commission processed
- [ ] Test referral code flow

---

## Support & Resources

- **Paystack Docs:** https://paystack.com/docs
- **Test Cards:** https://paystack.com/docs/payments/test-payments
- **Webhook Events:** https://paystack.com/docs/payments/webhooks
- **React Native Paystack:** https://github.com/just1and0/react-native-paystack-webview

---

**Last Updated:** October 4, 2025
**Version:** 1.0.0
