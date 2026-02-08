"""
Test Context API

Manual testing script for context service endpoints.
"""

import httpx
from caps.context.config import config


def main():
    """Test context service APIs."""
    base_url = f"http://{config.host}:{config.port}"
    
    print("=" * 60)
    print("  CAPS Context Service - API Test")
    print("=" * 60)
    print(f"\nTesting service at: {base_url}\n")
    
    try:
        # Test health check
        print("1. Testing health check...")
        with httpx.Client() as client:
            response = client.get(f"{base_url}/")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.json()}\n")
        
        # Test user context
        print("2. Testing user context retrieval...")
        user_ids = ["user_normal", "user_low_balance", "user_high_velocity", "user_new_device"]
        
        with httpx.Client() as client:
            for user_id in user_ids:
                response = client.get(f"{base_url}/context/user/{user_id}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ {user_id}:")
                    print(f"      Balance: ₹{data['wallet_balance']:.2f}")
                    print(f"      Daily spend: ₹{data['daily_spend_today']:.2f}")
                    print(f"      Transactions (5min): {data['transactions_last_5min']}")
                    print(f"      Known device: {data['is_known_device']}")
                else:
                    print(f"   ❌ {user_id}: Error {response.status_code}")
                print()
        
        # Test merchant context
        print("3. Testing merchant context retrieval...")
        merchant_vpas = ["canteen@vit", "shop@upi", "newstore@upi", "scam@merchant"]
        
        with httpx.Client() as client:
            for vpa in merchant_vpas:
                response = client.get(f"{base_url}/context/merchant/{vpa}")
                if response.status_code == 200:
                    data = response.json()
                    print(f"   ✅ {vpa}:")
                    print(f"      Reputation: {data['reputation_score']:.2f}")
                    print(f"      Whitelisted: {data['is_whitelisted']}")
                    print(f"      Refund rate: {data['refund_rate']:.2%}")

                else:
                    print(f"   ❌ {vpa}: Error {response.status_code}")
                print()
        
        # Test stats endpoint
        print("4. Testing stats endpoint...")
        with httpx.Client() as client:
            response = client.get(f"{base_url}/context/stats")
            if response.status_code == 200:
                stats = response.json()
                print(f"   ✅ Service Statistics:")
                print(f"      Users tracked: {stats['users_tracked']}")
                print(f"      Total transactions: {stats['total_transactions']}")
                print(f"      Mock users: {stats['mock_users_available']}")
                print(f"      Mock merchants: {stats['mock_merchants_available']}")
            else:
                print(f"   ❌ Error {response.status_code}")
        
        print("\n" + "=" * 60)
        print("✅ All tests completed successfully!")
        print("=" * 60)
        
    except httpx.ConnectError:
        print("\n❌ Error: Could not connect to context service")
        print(f"   Make sure the service is running: python scripts/run_context_service.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
