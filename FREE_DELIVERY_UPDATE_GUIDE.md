# Free Delivery Feature Update Guide - Product Management

## Overview
This guide covers how to implement the **free_delivery** field in your React Native app for product creation and editing, following the backend schema update.

---

## Backend Changes (Already Done ✓)

### Schema Update
```prisma
model products {
  // ... other fields
  free_delivery           Boolean             @default(true)
  // ... rest of fields
}
```

### API Models Updated
- `ProductBase`: Added `free_delivery: bool = Field(default=True)`
- `ProductUpdate`: Added `free_delivery: Optional[bool] = None`
- `ProductListItem`: Added `free_delivery: bool = True`
- All product endpoints now return and accept `free_delivery` field

---

## API Endpoints Updated

### Product Creation Endpoints

#### 1. POST `/products` (JSON)
```json
{
  "name": "iPhone 14 Pro",
  "price": 1200.00,
  "country": "Ghana",
  "categoryId": "uuid-here",
  "subCategoryId": "uuid-here",
  "description": "Latest iPhone model",
  "condition": "NEW",
  "photos": ["url1", "url2"],
  "currency": "GHS",
  "quantity": 10,
  "allowPurchaseOnPlatform": true,
  "featured": false,
  "free_delivery": true,        // NEW FIELD
  "fields": {
    "Storage": "256GB",
    "Color": "Space Black"
  }
}
```

#### 2. POST `/products/create-with-images` (Multipart Form Data)
```
name: "iPhone 14 Pro"
price: 1200.00
country: "Ghana"
categoryId: "uuid-here"
subCategoryId: "uuid-here"
description: "Latest iPhone model"
condition: "NEW"
currency: "GHS"
quantity: 10
allowPurchaseOnPlatform: true
featured: false
free_delivery: true                // NEW FIELD
fields: '{"Storage": "256GB"}'
images: [file1, file2]
```

### Product Update Endpoint

#### PUT `/products/{product_id}`
```json
{
  "name": "iPhone 14 Pro (Updated)",
  "price": 1150.00,
  "free_delivery": false,      // Can update this field
  "quantity": 8
}
```

### Product Response Format
All product endpoints now return:
```json
{
  "id": "uuid",
  "name": "Product Name",
  "price": 1200.00,
  "free_delivery": true,       // NEW FIELD IN RESPONSE
  "quantity": 10,
  // ... other fields
}
```

---

## React Native Implementation

### 1. Update TypeScript Interfaces (if using TypeScript)

**types/product.ts:**
```typescript
export interface Product {
  id: string;
  name: string;
  price: number;
  country: string;
  categoryId: string;
  subCategoryId: string;
  sellerId: string;
  description?: string;
  condition?: 'NEW' | 'USED' | 'REFURBISHED';
  photos: string[];
  fields?: Record<string, any>;
  currency: 'GHS' | 'USD';
  quantity: number;
  allowPurchaseOnPlatform: boolean;
  featured: boolean;
  free_delivery: boolean;        // ADD THIS
  created_at?: string;
  updated_at?: string;
}

export interface ProductCreateRequest {
  name: string;
  price: number;
  country: string;
  categoryId: string;
  subCategoryId: string;
  description?: string;
  condition?: 'NEW' | 'USED' | 'REFURBISHED';
  photos: string[];
  fields?: Record<string, any>;
  currency: 'GHS' | 'USD';
  quantity: number;
  allowPurchaseOnPlatform: boolean;
  featured: boolean;
  free_delivery: boolean;        // ADD THIS
}

export interface ProductUpdateRequest {
  name?: string;
  price?: number;
  country?: string;
  categoryId?: string;
  subCategoryId?: string;
  description?: string;
  condition?: 'NEW' | 'USED' | 'REFURBISHED';
  photos?: string[];
  fields?: Record<string, any>;
  currency?: 'GHS' | 'USD';
  quantity?: number;
  allowPurchaseOnPlatform?: boolean;
  featured?: boolean;
  free_delivery?: boolean;       // ADD THIS
}
```

### 2. Update Product Creation Screen

**screens/CreateProductScreen.js:**

```javascript
import React, { useState } from 'react';
import {
  View,
  Text,
  TextInput,
  Button,
  Switch,
  StyleSheet,
  ScrollView,
  Alert
} from 'react-native';
import axios from 'axios';

const CreateProductScreen = ({ navigation }) => {
  const [formData, setFormData] = useState({
    name: '',
    price: '',
    country: '',
    categoryId: '',
    subCategoryId: '',
    description: '',
    condition: 'NEW',
    currency: 'GHS',
    quantity: 0,
    allowPurchaseOnPlatform: false,
    featured: false,
    free_delivery: true,              // ADD THIS - Default to true
    photos: [],
    fields: {},
  });

  const [loading, setLoading] = useState(false);

  const handleCreateProduct = async () => {
    if (!formData.name || !formData.price) {
      Alert.alert('Error', 'Please fill in all required fields');
      return;
    }

    setLoading(true);

    try {
      const token = await getAuthToken(); // Your auth token retrieval method

      const productData = {
        name: formData.name,
        price: parseFloat(formData.price),
        country: formData.country,
        categoryId: formData.categoryId,
        subCategoryId: formData.subCategoryId,
        description: formData.description,
        condition: formData.condition,
        currency: formData.currency,
        quantity: parseInt(formData.quantity),
        allowPurchaseOnPlatform: formData.allowPurchaseOnPlatform,
        featured: formData.featured,
        free_delivery: formData.free_delivery,    // INCLUDE THIS
        photos: formData.photos,
        fields: formData.fields,
      };

      const response = await axios.post(
        'YOUR_API_URL/products',
        productData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.data) {
        Alert.alert('Success', 'Product created successfully!');
        navigation.goBack();
      }
    } catch (error) {
      console.error('Create product error:', error);
      Alert.alert(
        'Error',
        error.response?.data?.detail || 'Failed to create product'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Create New Product</Text>

      <TextInput
        style={styles.input}
        placeholder="Product Name *"
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
      />

      <TextInput
        style={styles.input}
        placeholder="Price *"
        value={formData.price}
        onChangeText={(text) => setFormData({ ...formData, price: text })}
        keyboardType="decimal-pad"
      />

      <TextInput
        style={styles.input}
        placeholder="Country"
        value={formData.country}
        onChangeText={(text) => setFormData({ ...formData, country: text })}
      />

      <TextInput
        style={styles.input}
        placeholder="Description"
        value={formData.description}
        onChangeText={(text) => setFormData({ ...formData, description: text })}
        multiline
        numberOfLines={4}
      />

      <TextInput
        style={styles.input}
        placeholder="Quantity"
        value={String(formData.quantity)}
        onChangeText={(text) => setFormData({ ...formData, quantity: text })}
        keyboardType="number-pad"
      />

      {/* Free Delivery Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Free Delivery</Text>
        <Switch
          value={formData.free_delivery}
          onValueChange={(value) =>
            setFormData({ ...formData, free_delivery: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.free_delivery ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      {/* Allow Online Purchase Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Allow Online Purchase</Text>
        <Switch
          value={formData.allowPurchaseOnPlatform}
          onValueChange={(value) =>
            setFormData({ ...formData, allowPurchaseOnPlatform: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.allowPurchaseOnPlatform ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      {/* Featured Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Featured Product</Text>
        <Switch
          value={formData.featured}
          onValueChange={(value) =>
            setFormData({ ...formData, featured: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.featured ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      <Button
        title={loading ? 'Creating...' : 'Create Product'}
        onPress={handleCreateProduct}
        disabled={loading}
      />
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
    marginBottom: 20,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 12,
    marginBottom: 15,
    borderRadius: 8,
    fontSize: 16,
  },
  switchContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
    marginBottom: 15,
  },
  switchLabel: {
    fontSize: 16,
    color: '#333',
  },
});

export default CreateProductScreen;
```

### 3. Update Product Edit Screen

**screens/EditProductScreen.js:**

```javascript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  Button,
  Switch,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert
} from 'react-native';
import axios from 'axios';

const EditProductScreen = ({ route, navigation }) => {
  const { productId } = route.params;
  const [formData, setFormData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchProduct();
  }, []);

  const fetchProduct = async () => {
    try {
      const token = await getAuthToken();
      const response = await axios.get(
        `YOUR_API_URL/products/${productId}`,
        {
          headers: { 'Authorization': `Bearer ${token}` },
        }
      );

      if (response.data) {
        setFormData({
          name: response.data.name,
          price: String(response.data.price),
          country: response.data.country,
          description: response.data.description || '',
          quantity: response.data.quantity,
          allowPurchaseOnPlatform: response.data.allowPurchaseOnPlatform,
          featured: response.data.featured,
          free_delivery: response.data.free_delivery,    // LOAD THIS FIELD
        });
      }
    } catch (error) {
      console.error('Fetch product error:', error);
      Alert.alert('Error', 'Failed to load product details');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateProduct = async () => {
    setSaving(true);

    try {
      const token = await getAuthToken();

      const updateData = {
        name: formData.name,
        price: parseFloat(formData.price),
        country: formData.country,
        description: formData.description,
        quantity: parseInt(formData.quantity),
        allowPurchaseOnPlatform: formData.allowPurchaseOnPlatform,
        featured: formData.featured,
        free_delivery: formData.free_delivery,          // INCLUDE THIS
      };

      const response = await axios.put(
        `YOUR_API_URL/products/${productId}`,
        updateData,
        {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.data) {
        Alert.alert('Success', 'Product updated successfully!');
        navigation.goBack();
      }
    } catch (error) {
      console.error('Update product error:', error);
      Alert.alert(
        'Error',
        error.response?.data?.detail || 'Failed to update product'
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  if (!formData) {
    return (
      <View style={styles.centerContainer}>
        <Text>Failed to load product</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Edit Product</Text>

      <TextInput
        style={styles.input}
        placeholder="Product Name *"
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
      />

      <TextInput
        style={styles.input}
        placeholder="Price *"
        value={formData.price}
        onChangeText={(text) => setFormData({ ...formData, price: text })}
        keyboardType="decimal-pad"
      />

      <TextInput
        style={styles.input}
        placeholder="Country"
        value={formData.country}
        onChangeText={(text) => setFormData({ ...formData, country: text })}
      />

      <TextInput
        style={styles.input}
        placeholder="Description"
        value={formData.description}
        onChangeText={(text) => setFormData({ ...formData, description: text })}
        multiline
        numberOfLines={4}
      />

      <TextInput
        style={styles.input}
        placeholder="Quantity"
        value={String(formData.quantity)}
        onChangeText={(text) => setFormData({ ...formData, quantity: text })}
        keyboardType="number-pad"
      />

      {/* Free Delivery Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Free Delivery</Text>
        <Switch
          value={formData.free_delivery}
          onValueChange={(value) =>
            setFormData({ ...formData, free_delivery: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.free_delivery ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      {/* Allow Online Purchase Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Allow Online Purchase</Text>
        <Switch
          value={formData.allowPurchaseOnPlatform}
          onValueChange={(value) =>
            setFormData({ ...formData, allowPurchaseOnPlatform: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.allowPurchaseOnPlatform ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      {/* Featured Toggle */}
      <View style={styles.switchContainer}>
        <Text style={styles.switchLabel}>Featured Product</Text>
        <Switch
          value={formData.featured}
          onValueChange={(value) =>
            setFormData({ ...formData, featured: value })
          }
          trackColor={{ false: '#767577', true: '#81b0ff' }}
          thumbColor={formData.featured ? '#007AFF' : '#f4f3f4'}
        />
      </View>

      <Button
        title={saving ? 'Saving...' : 'Update Product'}
        onPress={handleUpdateProduct}
        disabled={saving}
      />
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#fff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 20,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    padding: 12,
    marginBottom: 15,
    borderRadius: 8,
    fontSize: 16,
  },
  switchContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
    marginBottom: 15,
  },
  switchLabel: {
    fontSize: 16,
    color: '#333',
  },
});

export default EditProductScreen;
```

### 4. Update Product List/Card Component

**components/ProductCard.js:**

```javascript
import React from 'react';
import { View, Text, Image, TouchableOpacity, StyleSheet } from 'react-native';

const ProductCard = ({ product, onPress }) => {
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

        {/* Free Delivery Badge */}
        {product.free_delivery && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>🚚 Free Delivery</Text>
          </View>
        )}

        <Text style={styles.quantity}>
          Stock: {product.quantity}
        </Text>
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
  badge: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 4,
    alignSelf: 'flex-start',
    marginBottom: 4,
  },
  badgeText: {
    fontSize: 12,
    color: '#2E7D32',
    fontWeight: '600',
  },
  quantity: {
    fontSize: 12,
    color: '#666',
  },
});

export default ProductCard;
```

### 5. Display Free Delivery in Product Details

**screens/ProductDetailScreen.js:**

```javascript
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Image,
  ScrollView,
  StyleSheet,
  ActivityIndicator
} from 'react-native';
import axios from 'axios';

const ProductDetailScreen = ({ route }) => {
  const { productId } = route.params;
  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchProduct();
  }, []);

  const fetchProduct = async () => {
    try {
      const response = await axios.get(`YOUR_API_URL/products/${productId}`);
      setProduct(response.data);
    } catch (error) {
      console.error('Fetch product error:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color="#007AFF" />
      </View>
    );
  }

  if (!product) {
    return (
      <View style={styles.centerContainer}>
        <Text>Product not found</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <Image
        source={{ uri: product.photos[0] || 'https://via.placeholder.com/400' }}
        style={styles.mainImage}
      />

      <View style={styles.contentContainer}>
        <Text style={styles.name}>{product.name}</Text>

        <Text style={styles.price}>
          {product.currency} {product.price.toFixed(2)}
        </Text>

        {/* Badges */}
        <View style={styles.badgesContainer}>
          {product.free_delivery && (
            <View style={styles.deliveryBadge}>
              <Text style={styles.deliveryBadgeText}>🚚 Free Delivery</Text>
            </View>
          )}

          {product.featured && (
            <View style={styles.featuredBadge}>
              <Text style={styles.featuredBadgeText}>⭐ Featured</Text>
            </View>
          )}
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Condition:</Text>
          <Text style={styles.infoValue}>{product.condition}</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Stock:</Text>
          <Text style={styles.infoValue}>{product.quantity}</Text>
        </View>

        <View style={styles.infoRow}>
          <Text style={styles.infoLabel}>Country:</Text>
          <Text style={styles.infoValue}>{product.country}</Text>
        </View>

        <Text style={styles.sectionTitle}>Description</Text>
        <Text style={styles.description}>{product.description}</Text>

        {product.seller && (
          <View style={styles.sellerContainer}>
            <Text style={styles.sectionTitle}>Seller Information</Text>
            <Text style={styles.sellerName}>
              {product.seller.business_name || product.seller.name}
            </Text>
            <Text style={styles.sellerEmail}>{product.seller.email}</Text>
          </View>
        )}
      </View>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#fff',
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  mainImage: {
    width: '100%',
    height: 300,
    resizeMode: 'cover',
  },
  contentContainer: {
    padding: 20,
  },
  name: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 12,
  },
  price: {
    fontSize: 28,
    fontWeight: 'bold',
    color: '#007AFF',
    marginBottom: 16,
  },
  badgesContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginBottom: 20,
  },
  deliveryBadge: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    marginRight: 8,
    marginBottom: 8,
  },
  deliveryBadgeText: {
    fontSize: 14,
    color: '#2E7D32',
    fontWeight: '600',
  },
  featuredBadge: {
    backgroundColor: '#FFF3E0',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    marginRight: 8,
    marginBottom: 8,
  },
  featuredBadgeText: {
    fontSize: 14,
    color: '#E65100',
    fontWeight: '600',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: '#eee',
  },
  infoLabel: {
    fontSize: 16,
    color: '#666',
  },
  infoValue: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    marginTop: 24,
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    color: '#555',
    lineHeight: 24,
  },
  sellerContainer: {
    marginTop: 24,
    padding: 16,
    backgroundColor: '#f9f9f9',
    borderRadius: 8,
  },
  sellerName: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 4,
  },
  sellerEmail: {
    fontSize: 14,
    color: '#666',
  },
});

export default ProductDetailScreen;
```

---

## Testing Checklist

### Backend Testing
- [x] Product model includes `free_delivery` field
- [x] Create product endpoint accepts `free_delivery`
- [x] Update product endpoint accepts `free_delivery`
- [x] All product list endpoints return `free_delivery`
- [x] Product detail endpoint returns `free_delivery`

### Frontend Testing
- [ ] Create product form includes free delivery toggle
- [ ] Free delivery defaults to `true` on create
- [ ] Edit product form loads existing free delivery value
- [ ] Can update free delivery status
- [ ] Product list displays free delivery badge
- [ ] Product detail shows free delivery status
- [ ] API requests include free_delivery field
- [ ] API responses parse free_delivery field correctly

---

## API Request/Response Examples

### Create Product Request
```bash
POST /products
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "name": "Samsung Galaxy S23",
  "price": 899.99,
  "country": "Ghana",
  "categoryId": "cat-uuid",
  "subCategoryId": "subcat-uuid",
  "description": "Latest Samsung flagship",
  "condition": "NEW",
  "photos": ["url1", "url2"],
  "currency": "GHS",
  "quantity": 15,
  "allowPurchaseOnPlatform": true,
  "featured": false,
  "free_delivery": true,
  "fields": {"Storage": "128GB", "Color": "Phantom Black"}
}
```

### Create Product Response
```json
{
  "id": "prod-uuid",
  "name": "Samsung Galaxy S23",
  "price": 899.99,
  "country": "Ghana",
  "categoryId": "cat-uuid",
  "subCategoryId": "subcat-uuid",
  "sellerId": "seller-uuid",
  "description": "Latest Samsung flagship",
  "condition": "NEW",
  "photos": ["url1", "url2"],
  "fields": {"Storage": "128GB", "Color": "Phantom Black"},
  "currency": "GHS",
  "quantity": 15,
  "allowPurchaseOnPlatform": true,
  "featured": false,
  "free_delivery": true,
  "created_at": "2025-12-05T10:00:00Z",
  "updated_at": "2025-12-05T10:00:00Z"
}
```

### Update Product Request
```bash
PUT /products/{product_id}
Authorization: Bearer YOUR_TOKEN
Content-Type: application/json

{
  "price": 849.99,
  "quantity": 10,
  "free_delivery": false
}
```

### Get Products Response
```json
{
  "products": [
    {
      "id": "prod-uuid",
      "name": "Samsung Galaxy S23",
      "price": 899.99,
      "currency": "GHS",
      "country": "Ghana",
      "condition": "NEW",
      "photos": ["url1"],
      "featured": false,
      "quantity": 15,
      "allowPurchaseOnPlatform": true,
      "free_delivery": true,
      "created_at": "2025-12-05T10:00:00Z",
      "seller_name": "Tech Store Ghana",
      "category_name": "Electronics",
      "subcategory_name": "Smartphones"
    }
  ],
  "total_count": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1,
  "has_next": false,
  "has_previous": false
}
```

---

## Common Issues & Solutions

### Issue: free_delivery not saving
**Solution:** Check that the field is included in the request body and not filtered out.

### Issue: Switch not displaying correct state
**Solution:** Ensure you're using boolean values, not strings ("true"/"false").

### Issue: Badge not showing on product cards
**Solution:** Verify the API response includes `free_delivery` field and it's properly parsed.

### Issue: Default value not working
**Solution:** In the backend, the default is `true`. Ensure your form initializes with this value.

---

## Production Considerations

1. **Migration:** Run Prisma migration to add the field to existing products
2. **Existing Data:** All existing products will default to `free_delivery = true`
3. **UI/UX:** Make the free delivery badge prominent for better user experience
4. **Filters:** Consider adding a filter to show only products with free delivery
5. **Analytics:** Track which products perform better with/without free delivery

---

## Next Steps

1. Test product creation with free_delivery field
2. Test product editing with free_delivery field
3. Verify product lists display the badge correctly
4. Update product filters if needed (add free delivery filter)
5. Update any product management dashboards
6. Consider adding bulk update functionality for sellers

---

## Questions?

For issues or questions, check:
- Backend API logs for debugging
- React Native debugger for API request/response inspection
- Verify authentication tokens are valid
