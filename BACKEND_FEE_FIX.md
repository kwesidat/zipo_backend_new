# Backend Delivery Fee Calculation Fix Guide

## Problem
The delivery fee is showing as a hardcoded **30 GHS** instead of the calculated amount based on distance and priority.

## Expected Behavior
- Fee should be calculated based on:
  - **Distance** (in kilometers) between pickup and delivery locations
  - **Priority Level**: STANDARD (1x), EXPRESS (1.5x), URGENT (2x)
  - **Base Rate**: GHS 15.00 per kilometer

### Formula:
```
delivery_fee = distance_km × 15.00 × priority_multiplier
```

**Examples:**
- 5 km, STANDARD: 5 × 15 × 1.0 = **GHS 75.00**
- 5 km, EXPRESS: 5 × 15 × 1.5 = **GHS 112.50**
- 5 km, URGENT: 5 × 15 × 2.0 = **GHS 150.00**

---

## Backend Endpoints to Fix

### 1. POST `/deliveries/`
**Purpose:** Create a delivery and calculate fee

**Request Body:**
```json
{
  "pickup_address": {
    "address": "123 Main St",
    "city": "Accra",
    "country": "Ghana",
    "latitude": 5.6037,
    "longitude": -0.1870
  },
  "delivery_address": {
    "address": "456 Oak Ave",
    "city": "Accra",
    "country": "Ghana",
    "latitude": 5.6500,
    "longitude": -0.2000
  },
  "pickup_contact_name": "John Doe",
  "pickup_contact_phone": "+233123456789",
  "delivery_contact_name": "Jane Smith",
  "delivery_contact_phone": "+233987654321",
  "priority": "STANDARD",
  "notes": "Handle with care",
  "item_description": "Electronics"
}
```

**Expected Response:**
```json
{
  "id": "delivery-uuid-here",
  "pickup_address": { ... },
  "delivery_address": { ... },
  "pickup_contact_name": "John Doe",
  "pickup_contact_phone": "+233123456789",
  "delivery_contact_name": "Jane Smith",
  "delivery_contact_phone": "+233987654321",
  "priority": "STANDARD",
  "delivery_fee": "75.00",  // ← MUST BE CALCULATED, NOT HARDCODED
  "status": "PENDING",
  "created_at": "2025-01-15T10:30:00Z",
  ...
}
```

**Backend Fix Needed:**
```python
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance between two points in kilometers using Haversine formula
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))

    # Radius of earth in kilometers
    r = 6371

    return c * r

def calculate_delivery_fee(
    pickup_lat: float,
    pickup_lon: float,
    delivery_lat: float,
    delivery_lon: float,
    priority: str
) -> Decimal:
    """
    Calculate delivery fee based on distance and priority
    """
    # Calculate distance
    distance_km = calculate_distance(
        pickup_lat,
        pickup_lon,
        delivery_lat,
        delivery_lon
    )

    # Base rate per kilometer
    base_rate_per_km = Decimal('15.00')

    # Priority multipliers
    priority_multipliers = {
        'STANDARD': Decimal('1.0'),
        'EXPRESS': Decimal('1.5'),
        'URGENT': Decimal('2.0')
    }

    # Get multiplier (default to STANDARD if not found)
    multiplier = priority_multipliers.get(priority, Decimal('1.0'))

    # Calculate fee
    delivery_fee = Decimal(str(distance_km)) * base_rate_per_km * multiplier

    # Round to 2 decimal places
    return delivery_fee.quantize(Decimal('0.01'))

# In your delivery creation endpoint:
@router.post("/deliveries/")
async def create_delivery(delivery_data: DeliveryCreate, db: Session = Depends(get_db)):
    # Extract coordinates
    pickup_lat = delivery_data.pickup_address.latitude
    pickup_lon = delivery_data.pickup_address.longitude
    delivery_lat = delivery_data.delivery_address.latitude
    delivery_lon = delivery_data.delivery_address.longitude
    priority = delivery_data.priority

    # Calculate fee
    calculated_fee = calculate_delivery_fee(
        pickup_lat,
        pickup_lon,
        delivery_lat,
        delivery_lon,
        priority
    )

    # Create delivery object
    delivery = Delivery(
        **delivery_data.dict(),
        delivery_fee=calculated_fee,  # ← Use calculated fee, NOT hardcoded 30
        status="PENDING"
    )

    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    return delivery
```

---

### 2. POST `/deliveries/{delivery_id}/initialize-payment`
**Purpose:** Initialize Paystack payment for a delivery

**Expected Response:**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "access-code-here",
  "reference": "payment-ref-here",
  "delivery_fee": "75.00"  // ← Should match the delivery's calculated fee
}
```

**Backend Fix Needed:**
```python
@router.post("/deliveries/{delivery_id}/initialize-payment")
async def initialize_payment(
    delivery_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Get the delivery
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()

    if not delivery:
        raise HTTPException(status_code=404, detail="Delivery not found")

    # Get the CALCULATED fee from the delivery (NOT hardcoded 30)
    amount_to_charge = float(delivery.delivery_fee)  # ← Use delivery's fee

    # Convert to kobo/pesewas (Paystack uses smallest currency unit)
    amount_in_pesewas = int(amount_to_charge * 100)

    # Initialize Paystack payment
    paystack_response = initialize_paystack_payment(
        email=current_user.email,
        amount=amount_in_pesewas,  # ← Correct calculated amount
        delivery_id=delivery_id
    )

    return {
        "authorization_url": paystack_response["authorization_url"],
        "access_code": paystack_response["access_code"],
        "reference": paystack_response["reference"],
        "delivery_fee": delivery.delivery_fee  # ← Return the actual fee
    }
```

---

### 3. POST `/deliveries/delivery/initialize-payment`
**Purpose:** Create delivery AND initialize payment in one step

**Request Body:** (Same as POST `/deliveries/`)

**Expected Response:**
```json
{
  "authorization_url": "https://checkout.paystack.com/...",
  "access_code": "access-code-here",
  "reference": "payment-ref-here",
  "delivery_fee": "75.00",  // ← MUST BE CALCULATED
  "delivery_id": "delivery-uuid-here"
}
```

**Backend Fix Needed:**
```python
@router.post("/deliveries/delivery/initialize-payment")
async def create_and_initialize_payment(
    delivery_data: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Calculate fee FIRST
    calculated_fee = calculate_delivery_fee(
        delivery_data.pickup_address.latitude,
        delivery_data.pickup_address.longitude,
        delivery_data.delivery_address.latitude,
        delivery_data.delivery_address.longitude,
        delivery_data.priority
    )

    # Create delivery with calculated fee
    delivery = Delivery(
        **delivery_data.dict(),
        delivery_fee=calculated_fee,  # ← NOT 30!
        customer_id=current_user.id,
        status="PENDING"
    )

    db.add(delivery)
    db.commit()
    db.refresh(delivery)

    # Initialize payment with CALCULATED amount
    amount_in_pesewas = int(float(calculated_fee) * 100)

    paystack_response = initialize_paystack_payment(
        email=current_user.email,
        amount=amount_in_pesewas,  # ← Correct amount
        delivery_id=str(delivery.id)
    )

    return {
        "authorization_url": paystack_response["authorization_url"],
        "access_code": paystack_response["access_code"],
        "reference": paystack_response["reference"],
        "delivery_fee": str(calculated_fee),  # ← Return calculated fee
        "delivery_id": str(delivery.id)
    }
```

---

## Common Issues to Check

### Issue 1: Hardcoded Value in Model
**Check your Delivery model:**
```python
# ❌ WRONG - Don't do this:
class Delivery(Base):
    delivery_fee = Column(Numeric(10, 2), default=30.00)  # Hardcoded!

# ✅ CORRECT - No default, calculate on creation:
class Delivery(Base):
    delivery_fee = Column(Numeric(10, 2), nullable=False)
```

### Issue 2: Missing Latitude/Longitude Validation
```python
# Make sure coordinates are provided and valid
if not all([
    delivery_data.pickup_address.latitude,
    delivery_data.pickup_address.longitude,
    delivery_data.delivery_address.latitude,
    delivery_data.delivery_address.longitude
]):
    raise HTTPException(
        status_code=400,
        detail="Pickup and delivery coordinates are required"
    )
```

### Issue 3: Wrong Currency Conversion for Paystack
```python
# Paystack expects amount in pesewas (GHS 1 = 100 pesewas)
# Fee: GHS 75.00 → 7500 pesewas

# ✅ CORRECT:
amount_in_pesewas = int(float(delivery_fee) * 100)

# ❌ WRONG:
amount_in_pesewas = 3000  # Always 30 GHS
```

---

## Testing the Fix

### Step 1: Test Delivery Creation
```bash
curl -X POST "http://your-backend/deliveries/" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pickup_address": {
      "address": "123 Main St",
      "city": "Accra",
      "country": "Ghana",
      "latitude": 5.6037,
      "longitude": -0.1870
    },
    "delivery_address": {
      "address": "456 Oak Ave",
      "city": "Accra",
      "country": "Ghana",
      "latitude": 5.6500,
      "longitude": -0.2000
    },
    "pickup_contact_name": "John Doe",
    "pickup_contact_phone": "+233123456789",
    "delivery_contact_name": "Jane Smith",
    "delivery_contact_phone": "+233987654321",
    "priority": "STANDARD",
    "item_description": "Test Item"
  }'
```

**Expected:** `delivery_fee` should be around **75-80 GHS**, NOT 30!

### Step 2: Test Payment Initialization
```bash
curl -X POST "http://your-backend/deliveries/{delivery_id}/initialize-payment" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:**
- `delivery_fee` should match the delivery's calculated fee
- Paystack `amount` should be `delivery_fee × 100` pesewas

### Step 3: Check Paystack Dashboard
After payment initialization:
1. Go to Paystack Dashboard
2. Check the transaction amount
3. **Should match calculated fee**, not 30 GHS!

---

## Quick Checklist for Backend Developer

- [ ] Distance calculation function uses Haversine formula
- [ ] Fee calculation includes distance × 15 × priority_multiplier
- [ ] Priority multipliers: STANDARD=1.0, EXPRESS=1.5, URGENT=2.0
- [ ] Delivery model doesn't have hardcoded default fee
- [ ] POST `/deliveries/` calculates and stores fee
- [ ] POST `/deliveries/{id}/initialize-payment` uses delivery's fee
- [ ] POST `/deliveries/delivery/initialize-payment` calculates fee
- [ ] Paystack amount = delivery_fee × 100 (convert to pesewas)
- [ ] All responses include correct `delivery_fee` field
- [ ] Latitude/longitude validation is in place

---

## Frontend Debugging (Already Implemented)

The frontend now logs all fee-related data:
- Check console logs for: `"Calculated Fee:"`, `"Final fee to charge:"`
- These logs will show what the backend is returning
- If logs show 30 consistently, the backend needs fixing

---

## Contact
If you need help implementing this fix, provide:
1. Your backend framework (FastAPI/Django/Flask/etc.)
2. Console logs from the frontend showing the fee issue
3. A sample response from your `/deliveries/` endpoint

**The issue is 100% in the backend - the frontend is now correctly using the API responses!**
