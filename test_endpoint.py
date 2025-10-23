#!/usr/bin/env python3
"""
Simple test script to verify the dashboard endpoint works after server restart
"""

import requests
import json
import sys
from datetime import datetime


def test_dashboard_endpoint():
    """Test the dashboard endpoint with and without authentication"""
    print("🧪 TESTING SELLER DASHBOARD ENDPOINT")
    print("=" * 50)

    base_url = "http://localhost:8080"
    endpoint = f"{base_url}/api/seller/dashboard"

    # Test 1: Check if endpoint is accessible (should require auth)
    print("1. Testing endpoint accessibility...")
    try:
        response = requests.get(endpoint, timeout=10)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 422:
            # This means the old broken function is still loaded
            print(
                "   ❌ ISSUE: 422 error suggests old function definition is still active"
            )
            print("   🔧 SOLUTION: Restart the FastAPI server to load the fixed code")
            print("   📝 Response:", response.json())
            return False

        elif response.status_code == 401 or response.status_code == 403:
            print("   ✅ GOOD: Endpoint requires authentication (as expected)")
            return True

        elif response.status_code == 500:
            print("   ❌ ISSUE: 500 error - there might still be a code problem")
            print(
                "   📝 Response:",
                response.text[:200] + "..."
                if len(response.text) > 200
                else response.text,
            )
            return False

        else:
            print(f"   ❓ UNEXPECTED: Status {response.status_code}")
            print(
                "   📝 Response:",
                response.text[:200] + "..."
                if len(response.text) > 200
                else response.text,
            )
            return False

    except requests.exceptions.ConnectionError:
        print("   ❌ ERROR: Cannot connect to server")
        print(
            "   🔧 SOLUTION: Make sure the server is running on http://localhost:8080"
        )
        return False

    except requests.exceptions.Timeout:
        print("   ❌ ERROR: Request timed out")
        return False

    except Exception as e:
        print(f"   ❌ UNEXPECTED ERROR: {e}")
        return False


def test_with_mock_auth():
    """Test with a mock authorization header"""
    print("\n2. Testing with mock authorization header...")

    endpoint = "http://localhost:8080/api/seller/dashboard"
    headers = {
        "Authorization": "Bearer mock-token-for-testing",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(endpoint, headers=headers, timeout=10)
        print(f"   Status Code: {response.status_code}")

        if response.status_code == 422:
            print("   ❌ ISSUE: Still getting 422 - server needs restart")
            return False

        elif response.status_code == 401 or response.status_code == 403:
            print("   ✅ GOOD: Mock token rejected (authentication working)")
            return True

        elif response.status_code == 500:
            print("   ❌ ISSUE: 500 error - check server logs")
            try:
                error_detail = response.json()
                print(
                    f"   📝 Error: {error_detail.get('detail', 'No detail provided')}"
                )
            except:
                print("   📝 Raw response:", response.text[:200])
            return False

        elif response.status_code == 200:
            print("   ✅ SUCCESS: Got 200 response (though with mock auth)")
            try:
                data = response.json()
                print(
                    f"   📊 Sample data: totalOrders={data.get('totalOrders', 'N/A')}, totalRevenue={data.get('totalSales', 'N/A')}"
                )
                return True
            except:
                print("   📝 Response not JSON:", response.text[:100])
                return True  # Still success if we got 200

        else:
            print(f"   ❓ UNEXPECTED: Status {response.status_code}")
            return False

    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False


def check_server_status():
    """Check if the server is running"""
    print("\n3. Checking server status...")

    try:
        response = requests.get("http://localhost:8080/docs", timeout=5)
        if response.status_code == 200:
            print("   ✅ Server is running (docs accessible)")
            return True
        else:
            print(f"   ❓ Server responding but docs returned {response.status_code}")
            return False
    except:
        print("   ❌ Server not responding")
        return False


def main():
    """Main test function"""
    print(f"🕐 Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Check server status first
    server_ok = check_server_status()
    if not server_ok:
        print("\n❌ RESULT: Server is not running or not accessible")
        print(
            "🔧 ACTION: Start the server with: uvicorn app.main:app --reload --port 8080"
        )
        return

    # Test endpoint
    endpoint_ok = test_dashboard_endpoint()
    auth_ok = test_with_mock_auth()

    print("\n" + "=" * 50)
    print("📋 TEST SUMMARY")
    print("=" * 50)

    if endpoint_ok and auth_ok:
        print("✅ SUCCESS: Dashboard endpoint is working correctly!")
        print("📝 Next steps:")
        print("   1. Test with real authentication token")
        print("   2. Verify dashboard data with active seller account")
        print("   3. Check that zeros appear for inactive sellers")

    elif not endpoint_ok and not auth_ok:
        print("❌ FAILURE: Endpoint has issues")
        if "422" in str(endpoint_ok):
            print("🔧 ACTION: Restart the FastAPI server to load fixed code")
        else:
            print("🔧 ACTION: Check server logs for errors")

    else:
        print("⚠️  PARTIAL: Some tests passed, some failed")
        print("🔧 ACTION: Review individual test results above")

    print(f"\n🕐 Test completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
