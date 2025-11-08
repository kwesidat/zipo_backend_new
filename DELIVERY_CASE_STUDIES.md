# ZipoHub Delivery System - Case Studies & User Stories

## 📚 Table of Contents
1. [Case 1: Product Order with Courier Delivery](#case-1-product-order-with-courier-delivery)
2. [Case 2: ZipoExpress Standalone Delivery](#case-2-zipoexpress-standalone-delivery)
3. [Edge Cases & Special Scenarios](#edge-cases--special-scenarios)
4. [Real-World Examples](#real-world-examples)

---

## 🛍️ Case 1: Product Order with Courier Delivery

### Scenario 1.1: Customer Buys Phone, Requests Courier Delivery

**Actors:**
- **Kwame** (Customer in Accra)
- **Afia** (Seller in Kumasi)
- **Kofi** (Courier in Kumasi)

**Story:**

1. **Kwame browses products on ZipoHub**
   - Opens ZipoHub mobile app
   - Searches for "iPhone 13"
   - Finds Afia's listing: iPhone 13, GHS 3,500

2. **Kwame clicks "Buy Now"**
   ```
   Product: iPhone 13
   Price: GHS 3,500
   Seller: Afia (Kumasi)
   ```

3. **Kwame fills shipping form and enables courier delivery**
   ```javascript
   Shipping Address:
   - Name: Kwame Mensah
   - Phone: 0244123456
   - Address: 23 Oxford Street, Osu
   - City: Accra
   - Country: Ghana

   Delivery Options:
   ✓ Enable Courier Delivery
   - Priority: EXPRESS (wants it fast)
   - Notes: "Please call 30 minutes before delivery"
   ```

4. **Kwame completes payment via Paystack**
   - Total: GHS 3,500
   - Payment successful

5. **Backend automatically creates:**

   **Order:**
   ```
   Order ID: abc-123
   Status: CONFIRMED
   Payment Status: COMPLETED
   ```

   **Delivery Record:**
   ```
   Delivery ID: delivery-456
   Order ID: abc-123

   Pickup Address:
   - Address: Afia's Shop, Kejetia Market
   - City: Kumasi
   - Contact: Afia - 0201234567

   Delivery Address:
   - Address: 23 Oxford Street, Osu
   - City: Accra
   - Contact: Kwame - 0244123456

   Status: PENDING
   Priority: EXPRESS
   Delivery Fee: GHS 45.00 (calculated)
   Courier Fee: GHS 31.50 (70%)
   Platform Fee: GHS 13.50 (30%)
   ```

6. **Afia (Seller) receives notification**
   ```
   🎉 New Order Received!
   Order #abc-123

   Product: iPhone 13
   Quantity: 1
   Amount: GHS 3,500

   Courier Delivery: YES
   A courier will pick up from your location.

   Please prepare the item for pickup.
   ```

7. **Kofi (Courier) sees available delivery**
   - Opens courier app
   - Goes to "Available Deliveries"
   - Sees:
   ```
   📦 Delivery #delivery-456

   Pickup: Kejetia Market, Kumasi
   Contact: Afia - 0201234567

   Deliver to: Oxford Street, Accra
   Contact: Kwame - 0244123456

   Priority: EXPRESS
   You earn: GHS 31.50
   Distance: ~250km

   Notes: "Please call 30 minutes before delivery"

   [Accept Delivery]
   ```

8. **Kofi accepts delivery**
   - Clicks "Accept Delivery"
   - Provides estimated pickup time: "Today, 3:00 PM"
   - Provides estimated delivery time: "Tomorrow, 10:00 AM"
   - Status → ACCEPTED

9. **Kofi picks up from Afia**
   - Arrives at Afia's shop
   - Collects iPhone 13
   - Updates status → PICKED_UP
   - App records actual pickup time: "Today, 3:15 PM"

10. **Kofi starts journey to Accra**
    - Updates status → IN_TRANSIT
    - Kwame can track delivery in real-time

11. **Kofi calls Kwame 30 minutes before arrival**
    - "Hello, I'm 30 minutes away with your iPhone"

12. **Kofi delivers to Kwame**
    - Kwame receives iPhone 13
    - Kofi requests signature
    - Takes proof of delivery photo
    - Updates status → DELIVERED
    - App records actual delivery time: "Tomorrow, 10:15 AM"

13. **System processes courier payment**
    - Creates earning record for Kofi
    - Amount: GHS 31.50
    - Status: PENDING (will be paid during weekly payout)

**API Calls Flow:**

```javascript
// Step 1: Kwame buys product
POST /api/buy-now
{
  "productId": "phone-123",
  "quantity": 1,
  "shippingAddress": {...},
  "enableCourierDelivery": true,
  "deliveryPriority": "EXPRESS",
  "deliveryNotes": "Please call 30 minutes before delivery"
}
→ Response: { authorization_url, order_id }

// Step 2: Payment successful, backend auto-creates delivery
// (No API call needed, happens in verify-payment webhook)

// Step 3: Kofi views available deliveries
GET /api/deliveries/available
→ Response: { deliveries: [...], total_count: 5 }

// Step 4: Kofi accepts delivery
POST /api/deliveries/accept
{
  "delivery_id": "delivery-456",
  "estimated_pickup_time": "2025-11-08T15:00:00Z",
  "estimated_delivery_time": "2025-11-09T10:00:00Z"
}

// Step 5: Kofi updates status - Picked up
PUT /api/deliveries/delivery-456/status
{
  "status": "PICKED_UP",
  "notes": "Item collected from seller"
}

// Step 6: Kofi updates status - In transit
PUT /api/deliveries/delivery-456/status
{
  "status": "IN_TRANSIT"
}

// Step 7: Kofi updates status - Delivered
PUT /api/deliveries/delivery-456/status
{
  "status": "DELIVERED",
  "proof_of_delivery_urls": ["https://storage.com/proof1.jpg"],
  "customer_signature": "https://storage.com/signature.jpg"
}
```

---

### Scenario 1.2: Customer Buys Multiple Items from Different Sellers

**Actors:**
- **Ama** (Customer in Takoradi)
- **Yaw** (Seller 1 - Electronics in Accra)
- **Kwesi** (Seller 2 - Fashion in Tema)
- **Abena** (Courier)

**Story:**

1. **Ama adds items to cart**
   - Laptop from Yaw (Accra) - GHS 2,000
   - Backpack from Kwesi (Tema) - GHS 150

2. **Ama checks out cart**
   - Enables courier delivery
   - Priority: STANDARD
   - Total: GHS 2,150

3. **Backend creates ONE delivery** (Current implementation)
   ```
   Pickup: Yaw's location (first seller)
   Deliver to: Ama in Takoradi

   Note: Multi-seller deliveries need courier to coordinate
   ```

4. **Future Enhancement:** Create separate deliveries for each seller
   ```
   Delivery 1:
   - Pickup from Yaw (Accra)
   - Deliver to Ama (Takoradi)

   Delivery 2:
   - Pickup from Kwesi (Tema)
   - Deliver to Ama (Takoradi)
   ```

---

## 🚚 Case 2: ZipoExpress Standalone Delivery

### Scenario 2.1: Student Sends Books Home

**Actors:**
- **Adjoa** (Student at University of Ghana, Legon)
- **Adjoa's Mom** (Lives in Kumasi)
- **Samuel** (Courier)

**Story:**

1. **Adjoa wants to send books to her mom**
   - Opens ZipoHub app
   - Goes to "ZipoExpress" section
   - Clicks "Schedule Delivery"

2. **Adjoa fills delivery form**
   ```javascript
   Pickup Information:
   - Contact Name: Adjoa Boateng
   - Contact Phone: 0551234567
   - Address: Commonwealth Hall, Room 204
   - City: Accra (Legon)
   - Country: Ghana
   - Additional Info: "At the main entrance"

   Delivery Information:
   - Contact Name: Mrs. Boateng
   - Contact Phone: 0201234567
   - Address: 45 Adum Road
   - City: Kumasi
   - Country: Ghana
   - Additional Info: "White gate with blue door"

   Delivery Details:
   - Priority: STANDARD
   - Item Description: "5 textbooks in a box"
   - Notes: "Handle with care, books are fragile"
   - Scheduled Date: Tomorrow, 10:00 AM
   ```

3. **Adjoa submits request**
   - System calculates delivery fee
   - Distance: ~250km
   - Fee: GHS 40.00
   - Courier earns: GHS 28.00

4. **System creates:**
   ```
   Order (delivery-only):
   - Order ID: order-789
   - User ID: Adjoa
   - Subtotal: 0 (no product purchase)
   - Delivery Fee: GHS 40.00
   - Total: GHS 40.00
   - Status: PENDING
   - Payment Status: PENDING

   Delivery:
   - Delivery ID: delivery-789
   - Order ID: order-789
   - Pickup: Commonwealth Hall, Legon
   - Delivery: 45 Adum Road, Kumasi
   - Status: PENDING
   ```

5. **Adjoa sees confirmation**
   ```
   ✅ Delivery Scheduled!

   Delivery ID: #delivery-789
   Fee: GHS 40.00

   Couriers can now see and accept your delivery request.
   You'll be notified when a courier accepts.
   ```

6. **Samuel (Courier) sees request**
   - Opens courier app
   - Sees new delivery
   ```
   📦 Standalone Delivery

   Pickup from: Adjoa Boateng
   Location: Commonwealth Hall, Legon
   Phone: 0551234567

   Deliver to: Mrs. Boateng
   Location: 45 Adum Road, Kumasi
   Phone: 0201234567

   Item: 5 textbooks in a box
   Notes: Handle with care, books are fragile

   You earn: GHS 28.00

   [Accept Delivery]
   ```

7. **Samuel accepts and completes delivery**
   - Tomorrow, 10:00 AM: Picks up from Adjoa
   - Updates: PICKED_UP
   - Drives to Kumasi
   - Updates: IN_TRANSIT
   - Delivers to Mrs. Boateng
   - Gets signature
   - Updates: DELIVERED

8. **Adjoa's mom calls to confirm**
   - "I received the books, thank you!"

**API Calls Flow:**

```javascript
// Step 1: Adjoa schedules delivery
POST /api/deliveries/schedule
{
  "pickup_address": {
    "address": "Commonwealth Hall, Room 204",
    "city": "Accra",
    "country": "Ghana",
    "additional_info": "At the main entrance"
  },
  "delivery_address": {
    "address": "45 Adum Road",
    "city": "Kumasi",
    "country": "Ghana",
    "additional_info": "White gate with blue door"
  },
  "pickup_contact_name": "Adjoa Boateng",
  "pickup_contact_phone": "0551234567",
  "delivery_contact_name": "Mrs. Boateng",
  "delivery_contact_phone": "0201234567",
  "priority": "STANDARD",
  "notes": "Handle with care, books are fragile",
  "item_description": "5 textbooks in a box"
}
→ Response: { id, delivery_fee: 40.00, status: "PENDING" }

// Step 2: Samuel views available deliveries
GET /api/deliveries/available
→ Response: { deliveries: [...] }

// Step 3: Samuel accepts
POST /api/deliveries/accept
{
  "delivery_id": "delivery-789"
}

// Step 4-6: Samuel updates status throughout journey
PUT /api/deliveries/delivery-789/status
{ "status": "PICKED_UP" }

PUT /api/deliveries/delivery-789/status
{ "status": "IN_TRANSIT" }

PUT /api/deliveries/delivery-789/status
{
  "status": "DELIVERED",
  "proof_of_delivery_urls": ["https://storage.com/proof.jpg"],
  "customer_signature": "https://storage.com/signature.jpg"
}
```

---

### Scenario 2.2: Business Documents Delivery (URGENT)

**Actors:**
- **Mr. Mensah** (Business owner in Accra)
- **Client** (In Tema)
- **Efua** (Courier)

**Story:**

1. **Mr. Mensah needs to deliver contract documents urgently**
   - Opens ZipoExpress
   - Priority: URGENT
   - Scheduled: ASAP

2. **Details:**
   ```
   Pickup: Mr. Mensah's office, Airport Residential Area
   Deliver to: Client's office, Tema Community 1

   Priority: URGENT (2x multiplier)
   Distance: ~30km

   Calculation:
   - Base: GHS 10
   - Distance: 30km × GHS 2 = GHS 60
   - Subtotal: GHS 70
   - URGENT multiplier: 2x
   - Total Fee: GHS 140.00
   - Courier earns: GHS 98.00
   ```

3. **Efua sees URGENT delivery**
   - High earning: GHS 98.00
   - Accepts immediately
   - Picks up in 15 minutes
   - Delivers in 45 minutes
   - Total time: 1 hour

---

### Scenario 2.3: Food Delivery from Restaurant

**Actors:**
- **Akosua** (Customer)
- **Tasty Bites Restaurant** (Restaurant in Osu)
- **Papa** (Courier on motorcycle)

**Story:**

1. **Akosua orders food** (outside ZipoHub food ordering)
   - Calls Tasty Bites restaurant
   - Orders jollof rice and chicken
   - Needs delivery

2. **Restaurant owner uses ZipoExpress**
   ```
   Pickup: Tasty Bites, Oxford Street, Osu
   Deliver to: Akosua's home, Labone

   Priority: EXPRESS (food needs to arrive hot)
   Item: Food delivery
   Notes: "Keep food upright, handle carefully"
   ```

3. **Papa (on motorcycle) accepts**
   - Fast delivery with motorcycle
   - Picks up hot food
   - Delivers in 20 minutes

---

## ⚠️ Edge Cases & Special Scenarios

### Edge Case 1: Courier Cancels After Acceptance

**Scenario:**
1. Courier accepts delivery
2. Has emergency, can't complete
3. Needs to cancel

**Current Limitation:**
- No cancel endpoint yet

**Recommended Solution:**
```javascript
POST /api/deliveries/{delivery_id}/cancel
{
  "reason": "Emergency, unable to complete delivery"
}

// Backend:
// - Sets status back to PENDING
// - Removes courier assignment
// - Delivery becomes available again
// - Notifies customer about delay
```

---

### Edge Case 2: Customer Not Available at Delivery

**Scenario:**
1. Courier arrives at delivery location
2. Customer not answering phone
3. Can't complete delivery

**Solution:**
```javascript
PUT /api/deliveries/{delivery_id}/status
{
  "status": "FAILED",
  "notes": "Customer not available after multiple attempts. Called 3 times."
}

// Backend:
// - Marks delivery as FAILED
// - Courier may return item to seller
// - Customer charged a reattempt fee
```

---

### Edge Case 3: Item Damaged During Transit

**Scenario:**
1. Courier picks up item
2. Accident during transit
3. Item damaged

**Solution:**
```javascript
PUT /api/deliveries/{delivery_id}/status
{
  "status": "FAILED",
  "notes": "Minor accident, item packaging damaged",
  "proof_of_delivery_urls": ["https://storage.com/damage-photo.jpg"]
}

// Process:
// 1. Customer contacted for decision
// 2. Insurance claim filed (if applicable)
// 3. Refund processed or replacement arranged
```

---

### Edge Case 4: Wrong Address Provided

**Scenario:**
1. Customer provides wrong delivery address
2. Courier can't find location

**Current Limitation:**
- No update address endpoint

**Recommended Solution:**
```javascript
// Customer updates delivery address
PUT /api/deliveries/{delivery_id}/address
{
  "delivery_address": {
    "address": "Corrected address",
    "city": "Accra",
    "country": "Ghana"
  }
}

// Only allowed if status is PENDING or ACCEPTED
```

---

### Edge Case 5: Multiple Couriers Try to Accept Same Delivery

**Scenario:**
1. Delivery is PENDING
2. Two couriers click "Accept" at same time

**Solution (Already Implemented):**
```python
# In accept_delivery endpoint:
# Database check ensures only one courier can accept
if delivery["status"] != "PENDING":
    raise HTTPException(
        status_code=400,
        detail="Delivery has already been assigned"
    )
```
- First courier succeeds
- Second courier gets error: "Delivery already assigned"

---

## 🌍 Real-World Examples

### Example 1: E-commerce Platform (Jumia/Tonaton Style)

**Use Case:**
- ZipoHub sellers list products
- Customers buy products
- Automated courier delivery

**Benefits:**
- Sellers don't need their own delivery
- Customers get tracked delivery
- Couriers earn from deliveries

**Monthly Volume:**
- 500 orders with courier delivery
- Average fee: GHS 35
- Total delivery revenue: GHS 17,500
- Courier earnings: GHS 12,250 (70%)
- Platform earnings: GHS 5,250 (30%)

---

### Example 2: Document Courier Service

**Use Case:**
- Businesses send documents
- Lawyers send contracts
- Banks send cards

**Benefits:**
- No need to buy products
- Pure delivery service
- Urgent priority for time-sensitive items

**Monthly Volume:**
- 200 standalone deliveries
- Average fee: GHS 50
- Total revenue: GHS 10,000
- Courier earnings: GHS 7,000
- Platform earnings: GHS 3,000

---

### Example 3: Student Care Packages

**Use Case:**
- Parents send items to students
- Students send items home
- Peer-to-peer item transfer

**Benefits:**
- Affordable standard delivery
- Safe tracked delivery
- Proof of delivery for peace of mind

---

### Example 4: Small Business Logistics

**Use Case:**
- Small bakery sends cakes to customers
- Seamstress delivers custom dresses
- Artisan sends handmade items

**Benefits:**
- No need for own delivery fleet
- Pay per delivery
- Professional delivery service

---

## 📊 Pricing Examples

### Standard Priority (1.0x multiplier)

| Distance | Base + Distance | Total | Courier | Platform |
|----------|----------------|-------|---------|----------|
| 10km | GHS 10 + GHS 20 | GHS 30 | GHS 21 | GHS 9 |
| 25km | GHS 10 + GHS 50 | GHS 60 | GHS 42 | GHS 18 |
| 50km | GHS 10 + GHS 100 | GHS 110 | GHS 77 | GHS 33 |
| 100km | GHS 10 + GHS 200 | GHS 210 | GHS 147 | GHS 63 |

### Express Priority (1.5x multiplier)

| Distance | (Base + Distance) × 1.5 | Total | Courier | Platform |
|----------|-------------------------|-------|---------|----------|
| 10km | (GHS 10 + GHS 20) × 1.5 | GHS 45 | GHS 31.50 | GHS 13.50 |
| 25km | (GHS 10 + GHS 50) × 1.5 | GHS 90 | GHS 63 | GHS 27 |
| 50km | (GHS 10 + GHS 100) × 1.5 | GHS 165 | GHS 115.50 | GHS 49.50 |

### Urgent Priority (2.0x multiplier)

| Distance | (Base + Distance) × 2.0 | Total | Courier | Platform |
|----------|-------------------------|-------|---------|----------|
| 10km | (GHS 10 + GHS 20) × 2.0 | GHS 60 | GHS 42 | GHS 18 |
| 25km | (GHS 10 + GHS 50) × 2.0 | GHS 120 | GHS 84 | GHS 36 |
| 50km | (GHS 10 + GHS 100) × 2.0 | GHS 220 | GHS 154 | GHS 66 |

---

## 🎯 Success Metrics

### For Customers:
- ✅ Delivery within estimated time
- ✅ Item arrives safely
- ✅ Easy tracking
- ✅ Professional service

### For Sellers:
- ✅ Orders automatically get courier delivery
- ✅ No logistics management needed
- ✅ Increased sales with delivery option
- ✅ Customer satisfaction

### For Couriers:
- ✅ Flexible earning opportunities
- ✅ Choose deliveries that suit them
- ✅ Clear earnings (70% of fee)
- ✅ Weekly payouts

### For Platform:
- ✅ Additional revenue stream (30% of fees)
- ✅ Increased platform value
- ✅ Better customer retention
- ✅ Competitive advantage

---

## 🚀 Future Enhancements

1. **Multi-stop deliveries**
   - One courier picks up from multiple sellers
   - Delivers to one customer

2. **Return deliveries**
   - Customer returns item to seller
   - Courier handles reverse logistics

3. **Scheduled recurring deliveries**
   - Weekly grocery delivery
   - Monthly care packages

4. **Delivery pools**
   - Multiple customers in same area
   - One courier delivers to all
   - Lower fees through optimization

5. **Real-time tracking**
   - GPS tracking of courier
   - Live map showing courier location
   - ETA updates

6. **Rating system**
   - Customers rate couriers
   - Couriers rate customers
   - Top-rated couriers get priority

7. **Insurance options**
   - Add insurance for valuable items
   - Coverage for damage/loss
   - Extra fee for peace of mind

---

## 📞 Support Scenarios

### Customer Support Case 1: "Where is my delivery?"

**Customer:** Kwame (ordered iPhone)
**Status:** IN_TRANSIT for 2 days

**Support Action:**
```javascript
// 1. Check delivery status
GET /api/deliveries/{delivery_id}

// 2. Contact courier
// 3. Provide customer with update
// 4. If delayed, offer compensation
```

---

### Customer Support Case 2: "I want to cancel delivery"

**Customer:** Adjoa (scheduled book delivery)
**Status:** PENDING (no courier assigned yet)

**Support Action:**
```javascript
// Currently not supported - needs implementation
// Recommended: Add cancel endpoint for PENDING status only

POST /api/deliveries/{delivery_id}/cancel
```

---

### Customer Support Case 3: "Courier lost the item"

**Serious Issue**

**Support Action:**
1. Mark delivery as FAILED
2. Investigate with courier
3. File incident report
4. Process refund for customer
5. Penalize courier if negligence found
6. Update courier rating

---

This comprehensive guide covers all delivery scenarios! 🚀
