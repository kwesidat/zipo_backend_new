# React Native Subscription Plans Implementation Guide

## Overview
This guide shows how to integrate the ZipoHub subscription plans API into your React Native application.

## Prerequisites
- React Native project setup
- Axios or Fetch API for HTTP requests
- AsyncStorage for token management (if using authentication)

## API Base URL
```javascript
const API_BASE_URL = "http://your-api-domain.com/api";
// For local development on Android emulator
// const API_BASE_URL = "http://10.0.2.2:8000/api";
// For iOS simulator
// const API_BASE_URL = "http://localhost:8000/api";
```

## Installation

Install required packages:
```bash
npm install axios @react-native-async-storage/async-storage
# or
yarn add axios @react-native-async-storage/async-storage
```

## API Service Setup

Create `services/subscriptionService.js`:

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://your-api-domain.com/api';

class SubscriptionService {
  constructor() {
    this.api = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json',
      },
    });
  }

  /**
   * Get all subscription plans with optional filters
   * @param {Object} filters - Optional filters (tier, region, interval, isActive)
   * @returns {Promise} - Array of subscription plans
   */
  async getAllPlans(filters = {}) {
    try {
      const params = new URLSearchParams();

      if (filters.tier) params.append('tier', filters.tier);
      if (filters.region) params.append('region', filters.region);
      if (filters.interval) params.append('interval', filters.interval);
      if (filters.isActive !== undefined) params.append('isActive', filters.isActive);

      const response = await this.api.get(`/subscription-plans?${params.toString()}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to fetch subscription plans',
      };
    }
  }

  /**
   * Get a specific subscription plan by ID
   * @param {string} planId - The subscription plan ID
   * @returns {Promise} - Subscription plan details
   */
  async getPlanById(planId) {
    try {
      const response = await this.api.get(`/subscription-plans/${planId}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to fetch subscription plan',
      };
    }
  }

  /**
   * Get subscription plans by tier
   * @param {string} tier - Subscription tier (LEVEL1, LEVEL2, LEVEL3)
   * @param {string} region - Optional region filter
   * @returns {Promise} - Array of subscription plans
   */
  async getPlansByTier(tier, region = null) {
    try {
      const params = region ? `?region=${region}` : '';
      const response = await this.api.get(`/subscription-plans/tier/${tier}${params}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to fetch subscription plans',
      };
    }
  }

  /**
   * Get subscription plans by region
   * @param {string} region - Region (GHANA, INTERNATIONAL)
   * @returns {Promise} - Array of subscription plans
   */
  async getPlansByRegion(region) {
    try {
      const response = await this.api.get(`/subscription-plans/region/${region}`);
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Failed to fetch subscription plans',
      };
    }
  }
}

export default new SubscriptionService();
```

## React Native Components

### 1. Subscription Plans List Screen

Create `screens/SubscriptionPlansScreen.js`:

```javascript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import subscriptionService from '../services/subscriptionService';

const SubscriptionPlansScreen = ({ navigation }) => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedRegion, setSelectedRegion] = useState('GHANA');

  useEffect(() => {
    fetchPlans();
  }, [selectedRegion]);

  const fetchPlans = async () => {
    setLoading(true);
    const result = await subscriptionService.getPlansByRegion(selectedRegion);

    if (result.success) {
      setPlans(result.data);
    } else {
      alert('Error: ' + result.error);
    }

    setLoading(false);
  };

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchPlans();
    setRefreshing(false);
  };

  const renderPlanCard = ({ item }) => (
    <TouchableOpacity
      style={styles.planCard}
      onPress={() => navigation.navigate('PlanDetails', { planId: item.id })}
    >
      <View style={styles.planHeader}>
        <Text style={styles.planName}>{item.name}</Text>
        <Text style={styles.planTier}>{item.tier}</Text>
      </View>

      <Text style={styles.planDescription}>{item.description}</Text>

      <View style={styles.priceContainer}>
        <Text style={styles.price}>
          {item.currency} {item.price}
        </Text>
        <Text style={styles.interval}>/{item.interval}</Text>
      </View>

      {item.features && (
        <View style={styles.featuresContainer}>
          <Text style={styles.featuresTitle}>Features:</Text>
          {Object.entries(item.features).map(([key, value]) => (
            <Text key={key} style={styles.featureItem}>
              • {key}: {value}
            </Text>
          ))}
        </View>
      )}

      <View style={styles.planFooter}>
        {item.maxProducts && (
          <Text style={styles.planDetail}>
            Max Products: {item.maxProducts}
          </Text>
        )}
        {item.maxPhotosPerProduct && (
          <Text style={styles.planDetail}>
            Max Photos: {item.maxPhotosPerProduct}
          </Text>
        )}
      </View>

      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => handleSelectPlan(item)}
      >
        <Text style={styles.selectButtonText}>Select Plan</Text>
      </TouchableOpacity>
    </TouchableOpacity>
  );

  const handleSelectPlan = (plan) => {
    // Navigate to payment or subscription confirmation
    navigation.navigate('SubscriptionCheckout', { plan });
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Subscription Plans</Text>

        <View style={styles.regionToggle}>
          <TouchableOpacity
            style={[
              styles.regionButton,
              selectedRegion === 'GHANA' && styles.regionButtonActive,
            ]}
            onPress={() => setSelectedRegion('GHANA')}
          >
            <Text
              style={[
                styles.regionButtonText,
                selectedRegion === 'GHANA' && styles.regionButtonTextActive,
              ]}
            >
              Ghana
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.regionButton,
              selectedRegion === 'INTERNATIONAL' && styles.regionButtonActive,
            ]}
            onPress={() => setSelectedRegion('INTERNATIONAL')}
          >
            <Text
              style={[
                styles.regionButtonText,
                selectedRegion === 'INTERNATIONAL' && styles.regionButtonTextActive,
              ]}
            >
              International
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      <FlatList
        data={plans}
        renderItem={renderPlanCard}
        keyExtractor={(item) => item.id}
        contentContainerStyle={styles.listContainer}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No subscription plans available</Text>
          </View>
        }
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    backgroundColor: '#fff',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  headerTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 16,
  },
  regionToggle: {
    flexDirection: 'row',
    gap: 8,
  },
  regionButton: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    backgroundColor: '#f0f0f0',
    alignItems: 'center',
  },
  regionButtonActive: {
    backgroundColor: '#007AFF',
  },
  regionButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#333',
  },
  regionButtonTextActive: {
    color: '#fff',
  },
  listContainer: {
    padding: 16,
  },
  planCard: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    marginBottom: 16,
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
    marginBottom: 8,
  },
  planName: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#333',
  },
  planTier: {
    fontSize: 12,
    fontWeight: '600',
    color: '#007AFF',
    backgroundColor: '#E3F2FD',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
  },
  planDescription: {
    fontSize: 14,
    color: '#666',
    marginBottom: 12,
  },
  priceContainer: {
    flexDirection: 'row',
    alignItems: 'baseline',
    marginBottom: 16,
  },
  price: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
  },
  interval: {
    fontSize: 16,
    color: '#666',
    marginLeft: 4,
  },
  featuresContainer: {
    marginBottom: 12,
  },
  featuresTitle: {
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 4,
    color: '#333',
  },
  featureItem: {
    fontSize: 12,
    color: '#666',
    marginLeft: 8,
    marginBottom: 2,
  },
  planFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 16,
  },
  planDetail: {
    fontSize: 12,
    color: '#666',
  },
  selectButton: {
    backgroundColor: '#007AFF',
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  selectButtonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  emptyContainer: {
    padding: 32,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
  },
});

export default SubscriptionPlansScreen;
```

### 2. Using React Hooks

Create a custom hook `hooks/useSubscriptionPlans.js`:

```javascript
import { useState, useEffect } from 'react';
import subscriptionService from '../services/subscriptionService';

export const useSubscriptionPlans = (filters = {}) => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchPlans();
  }, [filters]);

  const fetchPlans = async () => {
    setLoading(true);
    setError(null);

    const result = await subscriptionService.getAllPlans(filters);

    if (result.success) {
      setPlans(result.data);
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  const refetch = () => {
    fetchPlans();
  };

  return { plans, loading, error, refetch };
};

export const useSubscriptionPlan = (planId) => {
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (planId) {
      fetchPlan();
    }
  }, [planId]);

  const fetchPlan = async () => {
    setLoading(true);
    setError(null);

    const result = await subscriptionService.getPlanById(planId);

    if (result.success) {
      setPlan(result.data);
    } else {
      setError(result.error);
    }

    setLoading(false);
  };

  return { plan, loading, error, refetch: fetchPlan };
};
```

### 3. Usage Example with Hooks

```javascript
import React from 'react';
import { View, Text, FlatList, ActivityIndicator } from 'react-native';
import { useSubscriptionPlans } from '../hooks/useSubscriptionPlans';

const SimplePlansScreen = () => {
  const { plans, loading, error, refetch } = useSubscriptionPlans({
    region: 'GHANA',
    isActive: true,
  });

  if (loading) {
    return <ActivityIndicator size="large" />;
  }

  if (error) {
    return <Text>Error: {error}</Text>;
  }

  return (
    <FlatList
      data={plans}
      renderItem={({ item }) => (
        <View>
          <Text>{item.name}</Text>
          <Text>{item.currency} {item.price}</Text>
        </View>
      )}
      keyExtractor={(item) => item.id}
      onRefresh={refetch}
      refreshing={loading}
    />
  );
};
```

## API Endpoints Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/subscription-plans` | GET | Get all subscription plans |
| `/api/subscription-plans?tier=LEVEL1` | GET | Filter by tier |
| `/api/subscription-plans?region=GHANA` | GET | Filter by region |
| `/api/subscription-plans?interval=MONTHLY` | GET | Filter by interval |
| `/api/subscription-plans/{planId}` | GET | Get plan by ID |
| `/api/subscription-plans/tier/{tier}` | GET | Get plans by tier |
| `/api/subscription-plans/region/{region}` | GET | Get plans by region |

## Query Parameters

- `tier`: LEVEL1, LEVEL2, LEVEL3
- `region`: GHANA, INTERNATIONAL
- `interval`: DAILY, WEEKLY, MONTHLY, QUARTERLY, BIANNUALLY, ANNUALLY
- `isActive`: true, false

## Response Format

```json
{
  "id": "uuid",
  "name": "Basic Plan",
  "description": "Perfect for small businesses",
  "tier": "LEVEL1",
  "price": 29.99,
  "currency": "GHS",
  "interval": "MONTHLY",
  "region": "GHANA",
  "features": {
    "productListings": "Unlimited",
    "support": "24/7 Email"
  },
  "maxProducts": 100,
  "maxPhotosPerProduct": 5,
  "commissionRate": 0.05,
  "isActive": true,
  "createdAt": "2025-01-01T00:00:00Z",
  "updatedAt": "2025-01-01T00:00:00Z"
}
```

## Error Handling

```javascript
try {
  const result = await subscriptionService.getAllPlans();

  if (result.success) {
    console.log('Plans:', result.data);
  } else {
    console.error('Error:', result.error);
  }
} catch (error) {
  console.error('Unexpected error:', error);
}
```

## Notes

1. **Prisma Client Generation**: Before running your backend, execute:
   ```bash
   prisma db push
   prisma generate
   ```

2. **Database Setup**: Ensure your PostgreSQL database is configured and the SubscriptionPlan table is created.

3. **Authentication**: The subscription plans endpoints are publicly accessible (no auth required). If you want to restrict access, remove `/api/subscription-plans` from the `excluded_paths` in `app/main.py`.

4. **Testing**: Use the FastAPI docs at `http://localhost:8000/docs` to test the endpoints.

5. **Production**: Update the API base URL to your production domain before deploying.