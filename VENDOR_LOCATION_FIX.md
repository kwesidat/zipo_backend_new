# Vendor Location Missing - Delivery Fee Always 40 GHS

## Problem
Delivery fee is always showing 40 GHS regardless of distance because vendor location (latitude/longitude) is not available.

## Root Cause
The backend API is not returning `latitude` and `longitude` fields in the seller/user object when fetching product details.

## Diagnosis Steps

### 1. Check Console Logs
When you go to checkout, check the console for these logs:
```
📦 Product fetched: { productId, seller, seller_latitude, seller_longitude }
📦 Delivery Items: [...]
📍 Customer Location: { latitude, longitude }
💰 Delivery Fee Calculation: { totalFee, breakdown, ... }
```

### 2. Expected vs Actual

**Expected:**
```javascript
seller: {
  user_id: "...",
  name: "Vendor Name",
  latitude: 5.603717,    // ✓ Should exist
  longitude: -0.186964,  // ✓ Should exist
}
```

**Actual (Problem):**
```javascript
seller: {
  user_id: "...",
  name: "Vendor Name",
  // ❌ latitude: missing
  // ❌ longitude: missing
}
```

## Backend Fix Required

The backend API endpoint `/api/products/{id}` with `include_seller_info=true` needs to include latitude/longitude in the seller object.

### Backend Code to Check

**File:** Backend product API handler

**Current (Problem):**
```python
seller_info = {
    "user_id": seller.id,
    "name": seller.name,
    "email": seller.email,
    "phone_number": seller.phone_number,
    "business_name": seller.business_name,
    # Missing: latitude, longitude
}
```

**Fixed (Solution):**
```python
seller_info = {
    "user_id": seller.id,
    "name": seller.name,
    "email": seller.email,
    "phone_number": seller.phone_number,
    "business_name": seller.business_name,
    "latitude": seller.latitude,      # ✓ Add this
    "longitude": seller.longitude,    # ✓ Add this
    "address": seller.address,        # Optional
    "city": seller.city,              # Optional
    "country": seller.country,        # Optional
}
```

## Temporary Workaround

Until the backend is fixed, the app will:
1. Show a warning: "Some vendor locations unavailable"
2. Use estimated distance of 2km (default fee: 40 GHS)
3. Calculation: 2 km × 20 GHS/km × priority multiplier

### Fee Calculation with Default Distance

| Priority | Calculation | Fee |
|----------|------------|-----|
| STANDARD | 2 × 20 × 1.0 | GHS 40 |
| EXPRESS | 2 × 20 × 1.5 | GHS 60 |
| URGENT | 2 × 20 × 2.0 | GHS 80 |

## Frontend Updates Made

### 1. Updated Type Definitions
- `Seller` interface now includes `latitude`, `longitude`
- `User` interface now includes location fields

### 2. Added Debug Logging
- Logs product details when fetched
- Logs delivery items with vendor locations
- Logs customer location
- Logs final fee calculation

### 3. Added Warning UI
- Shows when vendor location is unavailable
- Informs user that estimated distance is used

### 4. Fallback Logic
Already implemented in `app/utils/distance.ts:157-170`:
```typescript
if (firstItem.vendor_latitude && firstItem.vendor_longitude) {
  // Calculate actual distance
  const distance = calculateDistance(...)
  const fee = calculateDeliveryFee(distance, false, priority)
} else {
  // Use default distance when vendor location missing
  const defaultDistance = 2
  const defaultFee = calculateDeliveryFee(defaultDistance, false, priority)
}
```

## Testing After Backend Fix

1. **Add vendor location in database:**
   ```sql
   UPDATE users
   SET latitude = 5.603717, longitude = -0.186964
   WHERE role = 'seller' AND id = 'vendor_id';
   ```

2. **Test checkout:**
   - Add product to cart
   - Go to checkout
   - Select delivery location far from vendor (e.g., 10km away)
   - Expected fee: 10 × 20 × 1.0 = GHS 200 (STANDARD)

3. **Verify console logs show:**
   ```
   seller_latitude: 5.603717
   seller_longitude: -0.186964
   distance: 10.00 km
   deliveryFee: 200.00
   ```

## Next Steps

### For Backend Team:
1. Update product API to include seller latitude/longitude
2. Ensure all sellers have location data in database
3. Test API response includes location fields

### For Frontend Testing:
1. Check console logs to confirm vendor location is received
2. Test with different distances
3. Verify warning disappears when location available
4. Confirm accurate fee calculation

## Contact Points

If seller location is still missing after backend fix:
- Check database: Does seller have latitude/longitude set?
- Check API response: Is location included in seller object?
- Check product fetch: Is `include_seller_info=true` parameter working?
