# Seller Orders Endpoint Documentation

## Overview

The seller orders endpoint allows sellers to view all orders that contain their products. This endpoint provides sellers with detailed information about customer orders, including only the items they sold and the revenue they earned from each order.

## Endpoint Details

**URL:** `/api/seller/orders`  
**Method:** `GET`  
**Authentication:** Required (Bearer token)  
**Response Model:** `SellerOrdersListResponse`

## Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `status` | string | No | None | Filter orders by status (PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED) |
| `payment_status` | string | No | None | Filter orders by payment status (PENDING, PAID, FAILED, REFUNDED) |
| `limit` | integer | No | 20 | Number of orders per page (1-100) |
| `offset` | integer | No | 0 | Number of orders to skip for pagination |

## Example Requests

### Basic Request
```http
GET /api/seller/orders
Authorization: Bearer your-jwt-token
```

### With Filters
```http
GET /api/seller/orders?status=CONFIRMED&payment_status=PAID&limit=10
Authorization: Bearer your-jwt-token
```

### With Pagination
```http
GET /api/seller/orders?limit=5&offset=10
Authorization: Bearer your-jwt-token
```

## Response Format

### Success Response (200 OK)

```json
{
  "orders": [
    {
      "id": "60566edc-24a9-486e-86f4-52b5c30678a8",
      "userId": "user-123",
      "customerName": "John Doe",
      "customerEmail": "john@example.com",
      "customerPhone": "+233123456789",
      "subtotal": 150.00,
      "discountAmount": 10.00,
      "tax": 5.00,
      "total": 145.00,
      "sellerRevenue": 100.00,
      "status": "CONFIRMED",
      "paymentStatus": "PAID",
      "currency": "GHS",
      "shippingAddress": {
        "fullName": "John Doe",
        "phone": "+233123456789",
        "email": "john@example.com",
        "address": "123 Main St",
        "city": "Accra",
        "region": "Greater Accra"
      },
      "trackingNumber": "TRK123456789",
      "paymentMethod": "card",
      "paymentGateway": "PAYSTACK",
      "createdAt": "2025-01-15T10:30:00Z",
      "updatedAt": "2025-01-15T11:00:00Z",
      "items": [
        {
          "id": "item-1",
          "productId": "product-123",
          "title": "Wireless Bluetooth Headphones",
          "image": "https://example.com/headphones.jpg",
          "quantity": 1,
          "price": 100.00,
          "subtotal": 100.00,
          "condition": "NEW",
          "location": "Accra"
        }
      ],
      "itemCount": 1
    }
  ],
  "total": 25,
  "page": 1,
  "limit": 20,
  "totalPages": 2
}
```

### Error Responses

#### 401 Unauthorized
```json
{
  "detail": "Authentication required"
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Failed to fetch seller orders"
}
```

## Data Models

### SellerOrdersListResponse
- `orders`: Array of SellerOrder objects
- `total`: Total number of orders for the seller
- `page`: Current page number
- `limit`: Orders per page
- `totalPages`: Total number of pages

### SellerOrder
- `id`: Order ID
- `userId`: Customer's user ID
- `customerName`: Customer's full name (from shipping address)
- `customerEmail`: Customer's email (from shipping address)
- `customerPhone`: Customer's phone (from shipping address)
- `subtotal`: Order subtotal (entire order)
- `discountAmount`: Total discount applied (entire order)
- `tax`: Tax amount (entire order)
- `total`: Total order amount (entire order)
- `sellerRevenue`: Revenue earned by this seller from this order
- `status`: Order status
- `paymentStatus`: Payment status
- `currency`: Order currency
- `shippingAddress`: Shipping address object
- `trackingNumber`: Shipping tracking number
- `paymentMethod`: Payment method used
- `paymentGateway`: Payment gateway used
- `createdAt`: Order creation date
- `updatedAt`: Order last update date
- `items`: Array of SellerOrderItem objects (only seller's items)
- `itemCount`: Number of items sold by this seller in this order

### SellerOrderItem
- `id`: Order item ID
- `productId`: Product ID
- `title`: Product title
- `image`: Product image URL
- `quantity`: Quantity ordered
- `price`: Price per unit
- `subtotal`: Total price for this item (price × quantity)
- `condition`: Product condition
- `location`: Product location

## Business Logic

### Order Filtering
- Only orders containing the seller's products are returned
- Orders are filtered by the authenticated seller's ID
- Filters are applied to the order-level properties (status, payment_status)

### Revenue Calculation
- `sellerRevenue` represents only the seller's portion of the total order
- Calculated by summing (price × quantity) for all seller's items in the order
- This may be different from the total order amount if the order contains items from multiple sellers

### Customer Information
- Customer details are extracted from the order's shipping address
- If shipping address is missing, customer fields will be null
- Customer information is order-specific, not user profile data

### Pagination
- Uses offset-based pagination
- Default limit is 20 orders per page
- Maximum limit is 100 orders per page
- `totalPages` is calculated as `ceil(total / limit)`

## Implementation Details

### Database Query
The endpoint queries the `OrderItem` table to find items sold by the seller, then joins with the `Order` table to get order details:

```sql
SELECT oi.*, o.* 
FROM OrderItem oi
JOIN Order o ON oi.orderId = o.id
WHERE oi.sellerId = ?
ORDER BY oi.createdAt DESC
```

### Order Grouping
- Order items are grouped by `orderId` to create complete order objects
- Each order contains only the items sold by the requesting seller
- Multiple items from the same seller in one order are combined

### Timezone Handling
- All datetime fields are converted to UTC timezone-aware format
- Uses the `parse_datetime_to_utc()` helper function for consistent parsing

## Error Handling

### Common Issues
1. **Authentication Failure**: Ensure valid JWT token is provided
2. **No Orders Found**: Returns empty array with total=0 (not an error)
3. **Invalid Filters**: Invalid status values are ignored
4. **Database Connection**: Returns 500 error if database is unavailable

### Debugging
- Check server logs for detailed error information
- Verify seller has products and customers have placed orders
- Ensure OrderItem records have correct sellerId values

## Usage Examples

### Frontend Integration (JavaScript)
```javascript
async function getSellerOrders(page = 1, status = null) {
  const params = new URLSearchParams({
    limit: '10',
    offset: (page - 1) * 10
  });
  
  if (status) {
    params.append('status', status);
  }
  
  const response = await fetch(`/api/seller/orders?${params}`, {
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });
  
  return response.json();
}
```

### Mobile App Integration (React Native)
```javascript
const fetchOrders = async (filters = {}) => {
  try {
    const queryString = Object.keys(filters)
      .map(key => `${key}=${filters[key]}`)
      .join('&');
      
    const response = await fetch(`${API_BASE}/seller/orders?${queryString}`, {
      headers: {
        'Authorization': `Bearer ${userToken}`,
      }
    });
    
    return await response.json();
  } catch (error) {
    console.error('Failed to fetch orders:', error);
  }
};
```

## Related Endpoints

- `GET /api/seller/dashboard` - Overall seller metrics and recent orders
- `GET /api/seller/customers` - Customer management for sellers
- `GET /api/orders` - Customer's own orders (different from seller orders)
- `GET /api/seller/top-products` - Best selling products for seller

## Testing

### Test with Active Seller
```bash
curl -X GET "http://localhost:8080/api/seller/orders?limit=5" \
  -H "Authorization: Bearer seller-jwt-token" \
  -H "Content-Type: application/json"
```

### Test with Filters
```bash
curl -X GET "http://localhost:8080/api/seller/orders?status=CONFIRMED&payment_status=PAID" \
  -H "Authorization: Bearer seller-jwt-token"
```

### Expected Results
- **Active sellers with orders**: Returns paginated list of orders with seller's items
- **New sellers**: Returns empty array with `total: 0`
- **Invalid authentication**: Returns 401 error
- **Server issues**: Returns 500 error with generic message

## Performance Considerations

### Optimization
- Query uses indexed fields (`sellerId`, `orderId`)
- Pagination limits memory usage for large datasets
- Customer information is extracted efficiently from shipping address

### Scalability
- Supports high-volume sellers with proper pagination
- Database queries are optimized for performance
- Consider caching for frequently accessed data

## Security

### Access Control
- Only authenticated sellers can access their own orders
- No cross-seller data leakage
- Customer personal information is limited to order context

### Data Privacy
- Customer details are only shown for orders containing seller's products
- No access to customer's other orders or profile information
- Shipping address information is order-specific

## Changelog

### Version 1.0.0 (2025-01-19)
- Initial implementation of seller orders endpoint
- Support for status and payment status filtering
- Pagination with configurable limits
- Customer information extraction from shipping address
- Seller revenue calculation
- Comprehensive error handling and logging