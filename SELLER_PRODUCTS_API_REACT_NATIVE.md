# Seller Product Management API - React Native Integration Guide

Complete guide for sellers to manage their products in the ZipoHub marketplace using React Native.

## Base URL

```
https://your-api-domain.com/api
```

## Authentication

All seller endpoints require authentication. Include the JWT token in the Authorization header:

```javascript
Authorization: Bearer YOUR_JWT_TOKEN
```

---

## Product Fields Structure

The `fields` property allows you to add custom attributes specific to your product type.

**Structure:** JSON object with key-value pairs

**Example:**
```json
{
  "Storage": "64GB",
  "Color": "Midnight Black",
  "RAM": "8GB",
  "Screen Size": "6.5 inches",
  "Battery": "5000mAh",
  "Warranty": "1 Year"
}
```

**React Native Example:**
```javascript
const productFields = {
  "Storage": "128GB",
  "Color": "Silver",
  "RAM": "12GB",
  "Camera": "50MP Triple Camera",
  "Processor": "Snapdragon 8 Gen 2"
};
```

---

## API Endpoints

### 1. Create Product

**Endpoint:** `POST /products`

**Description:** Add a new product to your seller catalog.

**Request Body:**
```json
{
  "name": "iPhone 15 Pro Max",
  "price": 1299.99,
  "country": "Ghana",
  "categoryId": "uuid-of-category",
  "subCategoryId": "uuid-of-subcategory",
  "description": "Brand new iPhone 15 Pro Max with warranty",
  "condition": "NEW",
  "photos": [
    "https://example.com/photo1.jpg",
    "https://example.com/photo2.jpg"
  ],
  "fields": {
    "Storage": "256GB",
    "Color": "Natural Titanium",
    "RAM": "8GB"
  },
  "currency": "GHS",
  "quantity": 10,
  "allowPurchaseOnPlatform": true,
  "featured": false
}
```

**React Native Example:**
```javascript
import axios from 'axios';
import * as ImagePicker from 'expo-image-picker';

const createProduct = async (productData) => {
  try {
    const token = await getAuthToken();

    const response = await axios.post(
      'https://your-api-domain.com/api/products',
      {
        name: productData.name,
        price: parseFloat(productData.price),
        country: productData.country,
        categoryId: productData.categoryId,
        subCategoryId: productData.subCategoryId,
        description: productData.description,
        condition: productData.condition, // "NEW", "USED", "REFURBISHED"
        photos: productData.photos, // Array of URLs
        fields: productData.fields, // Custom attributes object
        currency: productData.currency || "GHS",
        quantity: parseInt(productData.quantity),
        allowPurchaseOnPlatform: productData.allowPurchaseOnPlatform || false,
        featured: false // Sellers typically can't set this on creation
      },
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    console.log('Product created:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error creating product:', error.response?.data || error.message);
    throw error;
  }
};

// Usage Example
const newProduct = {
  name: "Samsung Galaxy S24 Ultra",
  price: 1199.99,
  country: "Ghana",
  categoryId: "electronics-uuid",
  subCategoryId: "smartphones-uuid",
  description: "Latest flagship smartphone with S Pen",
  condition: "NEW",
  photos: [
    "https://cloudinary.com/photo1.jpg",
    "https://cloudinary.com/photo2.jpg"
  ],
  fields: {
    "Storage": "512GB",
    "Color": "Titanium Gray",
    "RAM": "12GB",
    "Camera": "200MP",
    "Display": "6.8 inch AMOLED"
  },
  quantity: 5,
  allowPurchaseOnPlatform: true
};

await createProduct(newProduct);
```

**Response (201 Created):**
```json
{
  "id": "product-uuid",
  "name": "iPhone 15 Pro Max",
  "price": 1299.99,
  "country": "Ghana",
  "categoryId": "category-uuid",
  "subCategoryId": "subcategory-uuid",
  "sellerId": "your-user-uuid",
  "description": "Brand new iPhone 15 Pro Max with warranty",
  "condition": "NEW",
  "photos": ["url1", "url2"],
  "fields": {
    "Storage": "256GB",
    "Color": "Natural Titanium",
    "RAM": "8GB"
  },
  "currency": "GHS",
  "quantity": 10,
  "allowPurchaseOnPlatform": true,
  "featured": false,
  "created_at": "2025-09-30T10:00:00Z",
  "updated_at": "2025-09-30T10:00:00Z"
}
```

---

### 2. Get My Products

**Endpoint:** `GET /products/my-products`

**Description:** Get all products created by the authenticated seller.

**Query Parameters:**
- `page` (integer, default: 1) - Page number
- `page_size` (integer, default: 20, max: 100) - Items per page
- `sort_by` (string) - Sort order: `created_at`, `price_asc`, `price_desc`, `name`, `featured`

**React Native Example:**
```javascript
const getMyProducts = async (page = 1, pageSize = 20, sortBy = 'created_at') => {
  try {
    const token = await getAuthToken();

    const response = await axios.get(
      'https://your-api-domain.com/api/products/my-products',
      {
        params: {
          page: page,
          page_size: pageSize,
          sort_by: sortBy
        },
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error fetching products:', error.response?.data || error.message);
    throw error;
  }
};

// Usage with FlatList
const SellerProductsScreen = () => {
  const [products, setProducts] = useState([]);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const data = await getMyProducts(page, 20, 'created_at');
      setProducts(data.products);
    } catch (error) {
      Alert.alert('Error', 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProducts();
  }, [page]);

  return (
    <FlatList
      data={products}
      keyExtractor={(item) => item.id}
      renderItem={({ item }) => <ProductCard product={item} />}
      refreshing={loading}
      onRefresh={loadProducts}
    />
  );
};
```

**Response (200 OK):**
```json
{
  "products": [
    {
      "id": "product-uuid",
      "name": "iPhone 15 Pro Max",
      "price": 1299.99,
      "currency": "GHS",
      "country": "Ghana",
      "condition": "NEW",
      "photos": ["url1", "url2"],
      "featured": false,
      "quantity": 10,
      "allowPurchaseOnPlatform": true,
      "created_at": "2025-09-30T10:00:00Z",
      "seller_name": null,
      "category_name": "Electronics",
      "subcategory_name": "Smartphones"
    }
  ],
  "total_count": 50,
  "page": 1,
  "page_size": 20,
  "total_pages": 3,
  "has_next": true,
  "has_previous": false
}
```

---

### 3. Update Product

**Endpoint:** `PUT /products/{product_id}`

**Description:** Update an existing product. All fields are optional.

**Request Body:** (All fields optional)
```json
{
  "name": "iPhone 15 Pro Max - Updated",
  "price": 1199.99,
  "description": "Price reduced!",
  "quantity": 8,
  "fields": {
    "Storage": "512GB",
    "Color": "Blue Titanium"
  }
}
```

**React Native Example:**
```javascript
const updateProduct = async (productId, updates) => {
  try {
    const token = await getAuthToken();

    const response = await axios.put(
      `https://your-api-domain.com/api/products/${productId}`,
      updates,
      {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error updating product:', error.response?.data || error.message);
    throw error;
  }
};

// Usage Examples

// Update price only
await updateProduct('product-uuid-123', {
  price: 999.99
});

// Update multiple fields
await updateProduct('product-uuid-123', {
  name: "iPhone 15 Pro Max - Limited Offer",
  price: 1099.99,
  quantity: 5,
  description: "Special discount for limited time!"
});

// Update custom fields
await updateProduct('product-uuid-123', {
  fields: {
    "Storage": "1TB",
    "Color": "Desert Titanium",
    "Warranty": "2 Years Extended"
  }
});

// Add new photos (replace entire array)
await updateProduct('product-uuid-123', {
  photos: [
    "https://cloudinary.com/new-photo1.jpg",
    "https://cloudinary.com/new-photo2.jpg",
    "https://cloudinary.com/new-photo3.jpg"
  ]
});
```

**Response (200 OK):** Returns the updated product object.

---

### 4. Toggle Featured Status

**Endpoint:** `PATCH /products/{product_id}/featured`

**Description:** Mark/unmark a product as featured. Featured products appear in the featured section.

**Query Parameters:**
- `featured` (boolean, required) - Set to `true` to feature, `false` to unfeature

**React Native Example:**
```javascript
const toggleProductFeatured = async (productId, isFeatured) => {
  try {
    const token = await getAuthToken();

    const response = await axios.patch(
      `https://your-api-domain.com/api/products/${productId}/featured`,
      null,
      {
        params: {
          featured: isFeatured
        },
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error toggling featured:', error.response?.data || error.message);
    throw error;
  }
};

// Usage in a component
const ProductCard = ({ product, onUpdate }) => {
  const [isFeatured, setIsFeatured] = useState(product.featured);
  const [loading, setLoading] = useState(false);

  const handleToggleFeatured = async () => {
    setLoading(true);
    try {
      const newStatus = !isFeatured;
      await toggleProductFeatured(product.id, newStatus);
      setIsFeatured(newStatus);
      Alert.alert('Success', `Product ${newStatus ? 'featured' : 'unfeatured'} successfully`);
      onUpdate && onUpdate();
    } catch (error) {
      Alert.alert('Error', 'Failed to update featured status');
    } finally {
      setLoading(false);
    }
  };

  return (
    <View>
      <Text>{product.name}</Text>
      <Switch
        value={isFeatured}
        onValueChange={handleToggleFeatured}
        disabled={loading}
      />
      <Text>{isFeatured ? 'Featured' : 'Not Featured'}</Text>
    </View>
  );
};
```

**Response (200 OK):** Returns the updated product object.

---

### 5. Toggle Online Payment

**Endpoint:** `PATCH /products/{product_id}/online-payment`

**Description:** Enable/disable online payment for a product. When enabled, customers can purchase directly on the platform.

**Query Parameters:**
- `allow_payment` (boolean, required) - Set to `true` to enable, `false` to disable

**React Native Example:**
```javascript
const toggleOnlinePayment = async (productId, allowPayment) => {
  try {
    const token = await getAuthToken();

    const response = await axios.patch(
      `https://your-api-domain.com/api/products/${productId}/online-payment`,
      null,
      {
        params: {
          allow_payment: allowPayment
        },
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error toggling payment:', error.response?.data || error.message);
    throw error;
  }
};

// Usage in a component
const PaymentToggle = ({ product }) => {
  const [allowPayment, setAllowPayment] = useState(product.allowPurchaseOnPlatform);

  const handleToggle = async () => {
    try {
      const newStatus = !allowPayment;
      await toggleOnlinePayment(product.id, newStatus);
      setAllowPayment(newStatus);
      Alert.alert(
        'Success',
        newStatus
          ? 'Online payment enabled. Customers can now purchase directly.'
          : 'Online payment disabled. Customers must contact you directly.'
      );
    } catch (error) {
      Alert.alert('Error', 'Failed to update payment settings');
    }
  };

  return (
    <View style={styles.toggleContainer}>
      <Text style={styles.label}>Accept Online Payments</Text>
      <Switch
        value={allowPayment}
        onValueChange={handleToggle}
        trackColor={{ false: "#767577", true: "#81b0ff" }}
        thumbColor={allowPayment ? "#f5dd4b" : "#f4f3f4"}
      />
      <Text style={styles.hint}>
        {allowPayment
          ? 'Customers can buy now with card/mobile money'
          : 'Customers must contact you for purchase'}
      </Text>
    </View>
  );
};
```

**Response (200 OK):** Returns the updated product object.

---

### 6. Delete Product

**Endpoint:** `DELETE /products/{product_id}`

**Description:** Permanently delete a product from your catalog.

**React Native Example:**
```javascript
const deleteProduct = async (productId) => {
  try {
    const token = await getAuthToken();

    await axios.delete(
      `https://your-api-domain.com/api/products/${productId}`,
      {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    console.log('Product deleted successfully');
  } catch (error) {
    console.error('Error deleting product:', error.response?.data || error.message);
    throw error;
  }
};

// Usage with confirmation
const handleDeleteProduct = (productId, productName) => {
  Alert.alert(
    'Delete Product',
    `Are you sure you want to delete "${productName}"? This action cannot be undone.`,
    [
      {
        text: 'Cancel',
        style: 'cancel'
      },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          try {
            await deleteProduct(productId);
            Alert.alert('Success', 'Product deleted successfully');
            // Refresh product list
            refreshProducts();
          } catch (error) {
            Alert.alert('Error', 'Failed to delete product');
          }
        }
      }
    ]
  );
};
```

**Response (204 No Content):** No response body.

---

### 7. Get Single Product Details

**Endpoint:** `GET /products/{product_id}`

**Description:** Get detailed information about a specific product.

**Query Parameters:**
- `include_seller_info` (boolean, default: true)
- `include_category_info` (boolean, default: true)

**React Native Example:**
```javascript
const getProductDetails = async (productId) => {
  try {
    const token = await getAuthToken();

    const response = await axios.get(
      `https://your-api-domain.com/api/products/${productId}`,
      {
        params: {
          include_seller_info: true,
          include_category_info: true
        },
        headers: {
          'Authorization': `Bearer ${token}`
        }
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error fetching product:', error.response?.data || error.message);
    throw error;
  }
};

// Usage
const ProductDetailsScreen = ({ route }) => {
  const { productId } = route.params;
  const [product, setProduct] = useState(null);

  useEffect(() => {
    const loadProduct = async () => {
      const data = await getProductDetails(productId);
      setProduct(data);
    };
    loadProduct();
  }, [productId]);

  return (
    <ScrollView>
      <Text>{product?.name}</Text>
      <Text>{product?.price} {product?.currency}</Text>
      <Text>{product?.description}</Text>

      {/* Display custom fields */}
      {product?.fields && Object.entries(product.fields).map(([key, value]) => (
        <View key={key}>
          <Text>{key}: {value}</Text>
        </View>
      ))}
    </ScrollView>
  );
};
```

**Response (200 OK):** Returns full product details including seller and category info.

---

## Complete Seller Product Manager Component

```javascript
import React, { useState, useEffect } from 'react';
import {
  View, Text, FlatList, TouchableOpacity,
  Alert, Switch, StyleSheet, Image
} from 'react-native';
import axios from 'axios';
import AsyncStorage from '@react-native-async-storage/async-storage';

const API_BASE_URL = 'https://your-api-domain.com/api';

const SellerProductManager = () => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);

  const getAuthToken = async () => {
    return await AsyncStorage.getItem('authToken');
  };

  const fetchProducts = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const response = await axios.get(
        `${API_BASE_URL}/products/my-products`,
        {
          params: { page, page_size: 20 },
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      setProducts(response.data.products);
    } catch (error) {
      Alert.alert('Error', 'Failed to load products');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleFeatured = async (productId, currentStatus) => {
    try {
      const token = await getAuthToken();
      await axios.patch(
        `${API_BASE_URL}/products/${productId}/featured`,
        null,
        {
          params: { featured: !currentStatus },
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      fetchProducts(); // Refresh list
      Alert.alert('Success', 'Featured status updated');
    } catch (error) {
      Alert.alert('Error', 'Failed to update featured status');
    }
  };

  const handleTogglePayment = async (productId, currentStatus) => {
    try {
      const token = await getAuthToken();
      await axios.patch(
        `${API_BASE_URL}/products/${productId}/online-payment`,
        null,
        {
          params: { allow_payment: !currentStatus },
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      fetchProducts(); // Refresh list
      Alert.alert('Success', 'Payment settings updated');
    } catch (error) {
      Alert.alert('Error', 'Failed to update payment settings');
    }
  };

  const handleDelete = (productId, productName) => {
    Alert.alert(
      'Delete Product',
      `Delete "${productName}"?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: async () => {
            try {
              const token = await getAuthToken();
              await axios.delete(
                `${API_BASE_URL}/products/${productId}`,
                { headers: { 'Authorization': `Bearer ${token}` } }
              );
              fetchProducts();
              Alert.alert('Success', 'Product deleted');
            } catch (error) {
              Alert.alert('Error', 'Failed to delete product');
            }
          }
        }
      ]
    );
  };

  useEffect(() => {
    fetchProducts();
  }, [page]);

  const renderProduct = ({ item }) => (
    <View style={styles.productCard}>
      <Image source={{ uri: item.photos[0] }} style={styles.image} />

      <View style={styles.productInfo}>
        <Text style={styles.productName}>{item.name}</Text>
        <Text style={styles.price}>{item.currency} {item.price}</Text>
        <Text>Stock: {item.quantity}</Text>

        {/* Custom Fields Display */}
        {item.fields && Object.entries(item.fields).map(([key, value]) => (
          <Text key={key} style={styles.field}>
            {key}: {value}
          </Text>
        ))}
      </View>

      <View style={styles.controls}>
        <View style={styles.toggleRow}>
          <Text>Featured</Text>
          <Switch
            value={item.featured}
            onValueChange={() => handleToggleFeatured(item.id, item.featured)}
          />
        </View>

        <View style={styles.toggleRow}>
          <Text>Online Payment</Text>
          <Switch
            value={item.allowPurchaseOnPlatform}
            onValueChange={() => handleTogglePayment(item.id, item.allowPurchaseOnPlatform)}
          />
        </View>

        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.editButton}
            onPress={() => navigation.navigate('EditProduct', { productId: item.id })}
          >
            <Text style={styles.buttonText}>Edit</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.deleteButton}
            onPress={() => handleDelete(item.id, item.name)}
          >
            <Text style={styles.buttonText}>Delete</Text>
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );

  return (
    <View style={styles.container}>
      <FlatList
        data={products}
        keyExtractor={(item) => item.id}
        renderItem={renderProduct}
        refreshing={loading}
        onRefresh={fetchProducts}
        ListEmptyComponent={
          <Text style={styles.emptyText}>No products yet. Add your first product!</Text>
        }
      />

      <TouchableOpacity
        style={styles.addButton}
        onPress={() => navigation.navigate('AddProduct')}
      >
        <Text style={styles.addButtonText}>+ Add Product</Text>
      </TouchableOpacity>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5'
  },
  productCard: {
    backgroundColor: 'white',
    margin: 10,
    borderRadius: 8,
    padding: 15,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3
  },
  image: {
    width: '100%',
    height: 200,
    borderRadius: 8,
    marginBottom: 10
  },
  productInfo: {
    marginBottom: 15
  },
  productName: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 5
  },
  price: {
    fontSize: 16,
    color: '#2ecc71',
    fontWeight: '600',
    marginBottom: 5
  },
  field: {
    fontSize: 12,
    color: '#666',
    marginTop: 2
  },
  controls: {
    borderTopWidth: 1,
    borderTopColor: '#eee',
    paddingTop: 15
  },
  toggleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10
  },
  actions: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 10
  },
  editButton: {
    flex: 1,
    backgroundColor: '#3498db',
    padding: 10,
    borderRadius: 5,
    marginRight: 5
  },
  deleteButton: {
    flex: 1,
    backgroundColor: '#e74c3c',
    padding: 10,
    borderRadius: 5,
    marginLeft: 5
  },
  buttonText: {
    color: 'white',
    textAlign: 'center',
    fontWeight: 'bold'
  },
  emptyText: {
    textAlign: 'center',
    marginTop: 50,
    fontSize: 16,
    color: '#999'
  },
  addButton: {
    position: 'absolute',
    bottom: 20,
    right: 20,
    backgroundColor: '#2ecc71',
    paddingHorizontal: 20,
    paddingVertical: 15,
    borderRadius: 30,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.3,
    shadowRadius: 4,
    elevation: 5
  },
  addButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: 'bold'
  }
});

export default SellerProductManager;
```

---

## Product Form Example (Add/Edit)

```javascript
import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  ScrollView, Alert, Switch, StyleSheet
} from 'react-native';
import axios from 'axios';

const ProductForm = ({ route, navigation }) => {
  const isEdit = route.params?.productId;

  const [formData, setFormData] = useState({
    name: '',
    price: '',
    country: 'Ghana',
    categoryId: '',
    subCategoryId: '',
    description: '',
    condition: 'NEW',
    photos: [],
    quantity: '',
    currency: 'GHS',
    allowPurchaseOnPlatform: false
  });

  // Custom fields (dynamic attributes)
  const [customFields, setCustomFields] = useState([
    { key: '', value: '' }
  ]);

  const addCustomField = () => {
    setCustomFields([...customFields, { key: '', value: '' }]);
  };

  const updateCustomField = (index, field, value) => {
    const updated = [...customFields];
    updated[index][field] = value;
    setCustomFields(updated);
  };

  const removeCustomField = (index) => {
    const updated = customFields.filter((_, i) => i !== index);
    setCustomFields(updated);
  };

  const handleSubmit = async () => {
    try {
      const token = await getAuthToken();

      // Convert custom fields array to object
      const fieldsObject = {};
      customFields.forEach(field => {
        if (field.key && field.value) {
          fieldsObject[field.key] = field.value;
        }
      });

      const payload = {
        ...formData,
        price: parseFloat(formData.price),
        quantity: parseInt(formData.quantity),
        fields: Object.keys(fieldsObject).length > 0 ? fieldsObject : null
      };

      if (isEdit) {
        await axios.put(
          `${API_BASE_URL}/products/${route.params.productId}`,
          payload,
          { headers: { 'Authorization': `Bearer ${token}` } }
        );
        Alert.alert('Success', 'Product updated');
      } else {
        await axios.post(
          `${API_BASE_URL}/products`,
          payload,
          { headers: { 'Authorization': `Bearer ${token}` } }
        );
        Alert.alert('Success', 'Product created');
      }

      navigation.goBack();
    } catch (error) {
      Alert.alert('Error', error.response?.data?.detail || 'Failed to save product');
    }
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.label}>Product Name</Text>
      <TextInput
        style={styles.input}
        value={formData.name}
        onChangeText={(text) => setFormData({ ...formData, name: text })}
        placeholder="e.g., iPhone 15 Pro Max"
      />

      <Text style={styles.label}>Price</Text>
      <TextInput
        style={styles.input}
        value={formData.price}
        onChangeText={(text) => setFormData({ ...formData, price: text })}
        placeholder="0.00"
        keyboardType="decimal-pad"
      />

      <Text style={styles.label}>Stock Quantity</Text>
      <TextInput
        style={styles.input}
        value={formData.quantity}
        onChangeText={(text) => setFormData({ ...formData, quantity: text })}
        placeholder="0"
        keyboardType="number-pad"
      />

      <Text style={styles.label}>Description</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={formData.description}
        onChangeText={(text) => setFormData({ ...formData, description: text })}
        placeholder="Describe your product..."
        multiline
        numberOfLines={4}
      />

      {/* Custom Fields Section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Product Attributes</Text>
        <Text style={styles.sectionSubtitle}>
          Add specific details (Storage, Color, RAM, etc.)
        </Text>

        {customFields.map((field, index) => (
          <View key={index} style={styles.fieldRow}>
            <TextInput
              style={[styles.input, styles.fieldInput]}
              value={field.key}
              onChangeText={(text) => updateCustomField(index, 'key', text)}
              placeholder="Attribute (e.g., Storage)"
            />
            <TextInput
              style={[styles.input, styles.fieldInput]}
              value={field.value}
              onChangeText={(text) => updateCustomField(index, 'value', text)}
              placeholder="Value (e.g., 64GB)"
            />
            <TouchableOpacity
              style={styles.removeButton}
              onPress={() => removeCustomField(index)}
            >
              <Text style={styles.removeButtonText}>✕</Text>
            </TouchableOpacity>
          </View>
        ))}

        <TouchableOpacity style={styles.addFieldButton} onPress={addCustomField}>
          <Text style={styles.addFieldButtonText}>+ Add Attribute</Text>
        </TouchableOpacity>
      </View>

      {/* Allow Online Payment Toggle */}
      <View style={styles.toggleContainer}>
        <Text style={styles.label}>Accept Online Payments</Text>
        <Switch
          value={formData.allowPurchaseOnPlatform}
          onValueChange={(value) =>
            setFormData({ ...formData, allowPurchaseOnPlatform: value })
          }
        />
      </View>

      <TouchableOpacity style={styles.submitButton} onPress={handleSubmit}>
        <Text style={styles.submitButtonText}>
          {isEdit ? 'Update Product' : 'Create Product'}
        </Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: 'white'
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginTop: 15,
    marginBottom: 5
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16
  },
  textArea: {
    height: 100,
    textAlignVertical: 'top'
  },
  section: {
    marginTop: 25,
    padding: 15,
    backgroundColor: '#f9f9f9',
    borderRadius: 8
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 5
  },
  sectionSubtitle: {
    fontSize: 12,
    color: '#666',
    marginBottom: 15
  },
  fieldRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 10
  },
  fieldInput: {
    flex: 1,
    marginRight: 10
  },
  removeButton: {
    width: 30,
    height: 30,
    backgroundColor: '#e74c3c',
    borderRadius: 15,
    justifyContent: 'center',
    alignItems: 'center'
  },
  removeButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold'
  },
  addFieldButton: {
    marginTop: 10,
    padding: 10,
    backgroundColor: '#3498db',
    borderRadius: 5,
    alignItems: 'center'
  },
  addFieldButtonText: {
    color: 'white',
    fontWeight: '600'
  },
  toggleContainer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 20,
    padding: 15,
    backgroundColor: '#f0f0f0',
    borderRadius: 8
  },
  submitButton: {
    marginTop: 30,
    marginBottom: 40,
    backgroundColor: '#2ecc71',
    padding: 15,
    borderRadius: 8,
    alignItems: 'center'
  },
  submitButtonText: {
    color: 'white',
    fontSize: 18,
    fontWeight: 'bold'
  }
});

export default ProductForm;
```

---

## Error Handling

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | Bad Request | Invalid category/subcategory or validation error |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Trying to edit/delete another seller's product |
| 404 | Not Found | Product not found |
| 500 | Internal Server Error | Server error |

---

## Best Practices

1. **Images**: Upload images to a CDN (Cloudinary, AWS S3) before creating the product
2. **Validation**: Validate all inputs on the client side before submitting
3. **Fields**: Use consistent naming for custom fields (e.g., always "Storage", not "storage" or "STORAGE")
4. **Pricing**: Always use 2 decimal places for prices
5. **Stock Management**: Update quantity when items are sold
6. **Online Payment**: Only enable if you're ready to fulfill orders immediately

---

## Required Dependencies

```bash
npm install axios
npm install @react-native-async-storage/async-storage
npm install expo-image-picker  # For photo uploads
```

---

## Support

For issues or questions:
- API Documentation: `https://your-api-domain.com/docs`
- Email: seller-support@zipohub.com