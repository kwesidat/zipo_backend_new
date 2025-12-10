# Courier Status Updates and Notifications

## Overview

This document explains how courier delivery status updates work and how notifications are sent to all parties involved when a courier updates the status of an order with `useCourierService = true`.

## Problem Statement

Previously, when a courier updated the delivery status (e.g., PICKED_UP, IN_TRANSIT, DELIVERED), the changes were only reflected in the `Delivery` table but not in the associated `Order` table. This caused:

1. **Order status not reflecting courier updates** - Orders with `useCourierService = true` didn't show the current delivery status
2. **No notifications to involved parties** - Customers and sellers weren't informed about delivery progress

## Solution

### 1. Order Status Synchronization

When a courier updates delivery status via the `/delivery/{delivery_id}/status` endpoint, the system now:

- Updates the `Delivery` table with the new status
- **Automatically updates the Order's `courierServiceStatus`** to match the delivery status
- Maintains consistency between delivery and order records

#### Status Mapping

| Delivery Status | Order courierServiceStatus |
|----------------|---------------------------|
| ACCEPTED       | ACCEPTED                  |
| PICKED_UP      | PICKED_UP                 |
| IN_TRANSIT     | IN_TRANSIT                |
| DELIVERED      | DELIVERED                 |
| CANCELLED      | CANCELLED                 |
| FAILED         | FAILED                    |

### 2. Multi-Party Notifications

The system now sends real-time notifications to all parties involved in the delivery:

#### Notification Recipients

1. **Customer** (scheduled_by_user)
   - The user who created/scheduled the delivery
   - Receives customer-focused updates about their order

2. **Sellers** (if applicable)
   - All sellers whose products are in the order
   - Receive seller-focused updates about order delivery progress
   - System automatically identifies unique sellers from OrderItems

#### Notification Details by Status

##### PICKED_UP
- **Type**: INFO
- **Customer Notification**:
  - Title: "Order Picked Up"
  - Body: "Your order has been picked up by the courier and is on its way!"
- **Seller Notification**:
  - Title: "Order Picked Up"
  - Body: "Courier has picked up the order and delivery is in progress."

##### IN_TRANSIT
- **Type**: INFO
- **Customer Notification**:
  - Title: "Order In Transit"
  - Body: "Your order is currently in transit and will arrive soon."
- **Seller Notification**:
  - Title: "Order In Transit"
  - Body: "The order is in transit to the customer."

##### DELIVERED
- **Type**: SUCCESS
- **Customer Notification**:
  - Title: "Order Delivered Successfully!"
  - Body: "Your order has been delivered. Thank you for choosing our service!"
- **Seller Notification**:
  - Title: "Order Delivered Successfully"
  - Body: "The order has been successfully delivered to the customer."

##### CANCELLED
- **Type**: ERROR
- **Customer Notification**:
  - Title: "Delivery Cancelled"
  - Body: "Your delivery has been cancelled. [Courier notes or 'Please contact support for more details.']"
- **Seller Notification**:
  - Title: "Delivery Cancelled"
  - Body: "The delivery has been cancelled by the courier. [Courier notes]"

##### FAILED
- **Type**: ERROR
- **Customer Notification**:
  - Title: "Delivery Failed"
  - Body: "Delivery attempt failed. [Courier notes or 'Our team will contact you shortly.']"
- **Seller Notification**:
  - Title: "Delivery Failed"
  - Body: "Delivery attempt failed. [Courier notes or 'Customer will be contacted.']"

## Implementation Details

### Endpoint: `PUT /delivery/{delivery_id}/status`

**Request Body** (`UpdateDeliveryStatusRequest`):
```json
{
  "status": "PICKED_UP",
  "notes": "Optional courier notes",
  "location": "Optional current location",
  "proof_of_delivery_urls": ["url1", "url2"],
  "customer_signature": "signature_url"
}
```

**Process Flow**:

1. **Authentication & Authorization**
   - Verify user is a COURIER
   - Verify courier is assigned to this delivery

2. **Update Delivery Record**
   - Update delivery status
   - Add courier notes if provided
   - Record actual pickup/delivery times
   - Add proof of delivery if provided

3. **Sync Order Status** ✨ NEW
   - Get associated order_id from delivery
   - Update Order.courierServiceStatus to match delivery status
   - Update Order.updatedAt timestamp

4. **Create Status History**
   - Log status change in DeliveryStatusHistory table
   - Include notes and location

5. **Send Notifications** ✨ NEW
   - Create notification for customer
   - Query OrderItems to find all sellers
   - Create notifications for each unique seller
   - Set 7-day expiration on all notifications

6. **Update Courier Stats** (if DELIVERED)
   - Increment completed_deliveries count
   - Create CourierEarning record

### Code Location

File: `/app/routes/delivery.py`
Function: `update_delivery_status` (line ~888)

### Notification Schema

```json
{
  "id": "uuid",
  "userId": "recipient_user_id",
  "title": "Notification title",
  "notificationType": "INFO|SUCCESS|ERROR",
  "body": "Notification message body",
  "dismissed": false,
  "createdAt": "ISO timestamp",
  "expiresAt": "ISO timestamp (7 days from creation)"
}
```

## Benefits

### For Customers
- Real-time updates on delivery progress
- Know exactly when order is picked up, in transit, or delivered
- Immediate notification of any issues (cancellation, failure)

### For Sellers
- Track delivery progress for their products
- Know when items have been successfully delivered
- Get notified of delivery issues that may require action

### For Couriers
- Updates automatically sync across system
- No manual status synchronization needed
- Clear communication with all parties

### For System
- Data consistency between Delivery and Order tables
- Complete audit trail via notifications
- Better transparency and trust

## Error Handling

- Notification failures are logged but don't block status updates
- If notification creation fails, error is logged with warning level
- Status update proceeds successfully even if notifications fail
- Ensures delivery operations aren't disrupted by notification issues

## Logging

The system logs:
- ✅ Successful Order courierServiceStatus updates
- ⚠️ Failed Order courierServiceStatus updates (warning)
- ✅ Customer notification sent
- ✅ Seller notifications sent (with count)
- ⚠️ Failed notification creation (error level)
- ✅ Overall delivery status update completion

## Future Enhancements

Potential improvements:
- Push notifications (FCM/APNS) in addition to in-app notifications
- SMS notifications for critical status changes
- Email notifications for delivery completion
- Customizable notification preferences per user
- Notification batching for multiple status updates
- Real-time websocket updates for live tracking
