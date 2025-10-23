#!/usr/bin/env python3

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api"

# Test user credentials (you'll need to replace with actual test user)
TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"


def get_auth_token():
    """Get authentication token for test user"""
    login_data = {"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD}

    try:
        response = requests.post(f"{API_BASE}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Error during login: {str(e)}")
        return None


def test_get_user_invoices(token):
    """Test getting user invoices with pagination"""
    print("\n" + "=" * 50)
    print("🧪 Testing GET /api/user/invoices")
    print("=" * 50)

    headers = {"Authorization": f"Bearer {token}"}

    # Test basic request
    try:
        response = requests.get(f"{API_BASE}/user/invoices", headers=headers)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully retrieved user invoices")
            print(f"📊 Total invoices: {data.get('total_count', 0)}")
            print(f"📄 Current page: {data.get('page', 1)}")
            print(f"📝 Page size: {data.get('page_size', 20)}")
            print(f"📚 Total pages: {data.get('total_pages', 1)}")
            print(f"➡️ Has next: {data.get('has_next', False)}")
            print(f"⬅️ Has previous: {data.get('has_previous', False)}")

            invoices = data.get("invoices", [])
            if invoices:
                print(f"\n📋 First invoice details:")
                first_invoice = invoices[0]
                print(f"   🆔 ID: {first_invoice.get('id')}")
                print(f"   📄 Invoice Number: {first_invoice.get('invoiceNumber')}")
                print(
                    f"   💰 Total: {first_invoice.get('total')} {first_invoice.get('currency')}"
                )
                print(f"   📊 Status: {first_invoice.get('status')}")
                print(f"   📦 Product: {first_invoice.get('productName', 'N/A')}")
                print(f"   📅 Created: {first_invoice.get('createdAt')}")
                return first_invoice.get("id")  # Return first invoice ID for next test
            else:
                print("📭 No invoices found")
                return None
        else:
            print(f"❌ Failed to get invoices: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Error testing user invoices: {str(e)}")
        return None


def test_get_user_invoices_with_pagination(token):
    """Test getting user invoices with custom pagination"""
    print("\n" + "=" * 50)
    print("🧪 Testing GET /api/user/invoices with pagination")
    print("=" * 50)

    headers = {"Authorization": f"Bearer {token}"}
    params = {"page": 1, "page_size": 5}

    try:
        response = requests.get(
            f"{API_BASE}/user/invoices", headers=headers, params=params
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully retrieved paginated invoices")
            print(f"📊 Requested page size: 5, Got: {len(data.get('invoices', []))}")
        else:
            print(f"❌ Failed to get paginated invoices: {response.text}")

    except Exception as e:
        print(f"❌ Error testing paginated invoices: {str(e)}")


def test_get_user_invoices_with_status_filter(token):
    """Test getting user invoices with status filter"""
    print("\n" + "=" * 50)
    print("🧪 Testing GET /api/user/invoices with status filter")
    print("=" * 50)

    headers = {"Authorization": f"Bearer {token}"}
    params = {"status": "PAID"}

    try:
        response = requests.get(
            f"{API_BASE}/user/invoices", headers=headers, params=params
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully retrieved filtered invoices")
            print(f"📊 PAID invoices: {data.get('total_count', 0)}")

            invoices = data.get("invoices", [])
            for invoice in invoices:
                if invoice.get("status") != "PAID":
                    print(f"⚠️ Warning: Found non-PAID invoice: {invoice.get('status')}")
        else:
            print(f"❌ Failed to get filtered invoices: {response.text}")

    except Exception as e:
        print(f"❌ Error testing filtered invoices: {str(e)}")


def test_get_specific_user_invoice(token, invoice_id):
    """Test getting a specific user invoice by ID"""
    print("\n" + "=" * 50)
    print(f"🧪 Testing GET /api/user/invoices/{invoice_id}")
    print("=" * 50)

    if not invoice_id:
        print("⚠️ No invoice ID available, skipping specific invoice test")
        return

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{API_BASE}/user/invoices/{invoice_id}", headers=headers
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print("✅ Successfully retrieved specific invoice")
            print(f"📄 Invoice Number: {data.get('invoiceNumber')}")
            print(f"💰 Total: {data.get('total')} {data.get('currency')}")
            print(f"📊 Status: {data.get('status')}")
            print(f"👤 Customer: {data.get('customerName', 'N/A')}")
            print(f"📧 Email: {data.get('customerEmail')}")
            print(f"📦 Product: {data.get('productName', 'N/A')}")
            print(f"🔢 Quantity: {data.get('quantity', 'N/A')}")
            print(f"💵 Unit Price: {data.get('unitPrice', 'N/A')}")
            print(f"📅 Created: {data.get('createdAt')}")
            print(f"💳 Paid At: {data.get('paidAt', 'N/A')}")
        elif response.status_code == 404:
            print("❌ Invoice not found")
        elif response.status_code == 403:
            print("❌ Access denied - invoice doesn't belong to current user")
        else:
            print(f"❌ Failed to get specific invoice: {response.text}")

    except Exception as e:
        print(f"❌ Error testing specific invoice: {str(e)}")


def test_invalid_invoice_access(token):
    """Test accessing an invalid invoice ID"""
    print("\n" + "=" * 50)
    print("🧪 Testing GET /api/user/invoices with invalid ID")
    print("=" * 50)

    headers = {"Authorization": f"Bearer {token}"}
    fake_invoice_id = "00000000-0000-0000-0000-000000000000"

    try:
        response = requests.get(
            f"{API_BASE}/user/invoices/{fake_invoice_id}", headers=headers
        )
        print(f"Status Code: {response.status_code}")

        if response.status_code == 404:
            print("✅ Correctly returned 404 for invalid invoice ID")
        else:
            print(f"⚠️ Unexpected response for invalid ID: {response.text}")

    except Exception as e:
        print(f"❌ Error testing invalid invoice access: {str(e)}")


def test_unauthorized_access():
    """Test accessing invoices without authentication"""
    print("\n" + "=" * 50)
    print("🧪 Testing unauthorized access")
    print("=" * 50)

    try:
        response = requests.get(f"{API_BASE}/user/invoices")
        print(f"Status Code: {response.status_code}")

        if response.status_code == 401 or response.status_code == 403:
            print("✅ Correctly rejected unauthorized access")
        else:
            print(f"⚠️ Unexpected response for unauthorized access: {response.text}")

    except Exception as e:
        print(f"❌ Error testing unauthorized access: {str(e)}")


def main():
    """Main test function"""
    print("🚀 Starting User Invoice API Tests")
    print("=" * 60)

    # Test without authentication first
    test_unauthorized_access()

    # Get authentication token
    print("\n🔐 Getting authentication token...")
    token = get_auth_token()

    if not token:
        print("❌ Could not get authentication token. Please check:")
        print("   1. Server is running on http://localhost:8000")
        print("   2. Test user credentials are correct")
        print("   3. Test user exists in the database")
        return

    print("✅ Authentication token obtained")

    # Run all tests
    invoice_id = test_get_user_invoices(token)
    test_get_user_invoices_with_pagination(token)
    test_get_user_invoices_with_status_filter(token)
    test_get_specific_user_invoice(token, invoice_id)
    test_invalid_invoice_access(token)

    print("\n" + "=" * 60)
    print("🏁 User Invoice API Tests Completed")
    print("=" * 60)
    print("\nNote: If no invoices were found, this could mean:")
    print("1. The test user hasn't made any purchases yet")
    print("2. No invoices have been generated for completed purchases")
    print("3. The test user email doesn't match any invoice customer emails")
    print("\nTo create test data:")
    print("1. Make a purchase with the test user account")
    print("2. Complete the payment verification process")
    print("3. Check that invoices are being created properly")


if __name__ == "__main__":
    main()
