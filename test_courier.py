#!/usr/bin/env python3
"""Test courier user login and available deliveries"""
import requests
import json
import sys

BASE_URL = "http://localhost:8080"

def test_courier_login():
    """Test courier user login"""
    print("=" * 60)
    print("Testing Courier Login")
    print("=" * 60)

    login_data = {
        "email": "rhntssk@gmail.com",
        "password": "123456789Aa@"
    }

    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=login_data,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Login failed: {response.json()}")
            return None

    except Exception as e:
        print(f"❌ Error during login: {str(e)}")
        return None


def test_available_deliveries(auth_token):
    """Test getting available deliveries for courier"""
    print("\n" + "=" * 60)
    print("Testing Available Deliveries")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/deliveries/available",
            headers=headers,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Found {data.get('total_count', 0)} available deliveries")
            return data
        else:
            print(f"❌ Failed to fetch deliveries: {response.json()}")
            return None

    except Exception as e:
        print(f"❌ Error fetching deliveries: {str(e)}")
        return None


def test_my_deliveries(auth_token):
    """Test getting courier's accepted deliveries"""
    print("\n" + "=" * 60)
    print("Testing Courier's My Deliveries")
    print("=" * 60)

    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        response = requests.get(
            f"{BASE_URL}/api/deliveries/courier/my-deliveries",
            headers=headers,
            timeout=10
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")

        if response.status_code == 200:
            data = response.json()
            print(f"\n✅ Found {data.get('total_count', 0)} assigned deliveries")
            return data
        else:
            print(f"❌ Failed to fetch my deliveries: {response.json()}")
            return None

    except Exception as e:
        print(f"❌ Error fetching my deliveries: {str(e)}")
        return None


def main():
    """Main test function"""
    print("\n🚚 Testing Courier User Functionality")
    print("Email: rhntssk@gmail.com")
    print("Password: 123456789Aa@")
    print()

    # Test login
    login_response = test_courier_login()

    if not login_response:
        print("\n❌ Cannot proceed without successful login")
        sys.exit(1)

    # Extract access token
    access_token = login_response.get("access_token")
    user_info = login_response.get("user", {})

    print(f"\n✅ Logged in as: {user_info.get('name')} ({user_info.get('email')})")
    print(f"User Type: {user_info.get('user_type')}")
    print(f"User ID: {user_info.get('user_id')}")

    if not access_token:
        print("\n❌ No access token received")
        sys.exit(1)

    # Test available deliveries
    test_available_deliveries(access_token)

    # Test my deliveries
    test_my_deliveries(access_token)

    print("\n" + "=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
