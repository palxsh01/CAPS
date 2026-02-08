"""Tests for Context Service."""

import pytest
from fastapi.testclient import TestClient

from caps.context.context_service import app
from caps.context.models import UserContext, MerchantContext


# Test client
client = TestClient(app)


class TestContextServiceEndpoints:
    """Test Context Service REST endpoints."""

    def test_health_check(self):
        """Test root health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "CAPS Context Service"
        assert data["status"] == "running"

    def test_get_user_context_known_user(self):
        """Test fetching context for known user."""
        response = client.get("/context/user/user_normal")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "user_normal"
        assert data["wallet_balance"] == 1500.0
        assert data["is_known_device"] is True

    def test_get_user_context_unknown_user(self):
        """Test fetching context for unknown user (returns default)."""
        response = client.get("/context/user/unknown_user_123")
        assert response.status_code == 200
        
        data = response.json()
        assert data["user_id"] == "unknown_user_123"
        assert "wallet_balance" in data
        assert "device_fingerprint" in data

    def test_get_merchant_context_known_merchant(self):
        """Test fetching context for known merchant."""
        response = client.get("/context/merchant/canteen@vit")
        assert response.status_code == 200
        
        data = response.json()
        assert data["merchant_vpa"] == "canteen@vit"
        assert data["reputation_score"] == 0.95
        assert data["is_whitelisted"] is True

    def test_get_merchant_context_unknown_merchant(self):
        """Test fetching context for unknown merchant (returns default)."""
        response = client.get("/context/merchant/unknown@merchant")
        assert response.status_code == 200
        
        data = response.json()
        assert data["merchant_vpa"] == "unknown@merchant"
        assert data["reputation_score"] == 0.50
        assert data["is_whitelisted"] is False

    def test_record_transaction(self):
        """Test recording a transaction."""
        transaction_data = {
            "transaction_id": "txn_test_123",
            "user_id": "user_test",
            "merchant_vpa": "shop@upi",
            "amount": 100.0,
            "status": "success",
        }
        
        response = client.post("/context/transaction", json=transaction_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "recorded"
        assert data["transaction_id"] == "txn_test_123"

    def test_get_stats(self):
        """Test stats endpoint."""
        response = client.get("/context/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "users_tracked" in data
        assert "total_transactions" in data
        assert "mock_users_available" in data
        assert data["mock_users_available"] == 5  # We have 5 mock users


class TestMockData:
    """Test mock data integrity."""

    def test_user_profiles_complete(self):
        """Test that all user profiles are complete."""
        user_ids = ["user_normal", "user_low_balance", "user_high_velocity", "user_new_device"]
        
        for user_id in user_ids:
            response = client.get(f"/context/user/{user_id}")
            assert response.status_code == 200
            
            user_context = UserContext(**response.json())
            assert user_context.user_id == user_id
            assert user_context.wallet_balance >= 0
            assert 0.0 <= user_context.reputation_score <= 1.0 if hasattr(user_context, 'reputation_score') else True

    def test_merchant_profiles_complete(self):
        """Test that all merchant profiles are complete."""
        merchant_vpas = ["canteen@vit", "shop@upi", "scam@merchant"]
        
        for vpa in merchant_vpas:
            response = client.get(f"/context/merchant/{vpa}")
            assert response.status_code == 200
            
            merchant_context = MerchantContext(**response.json())
            assert merchant_context.merchant_vpa == vpa
            assert 0.0 <= merchant_context.reputation_score <= 1.0
            assert 0.0 <= merchant_context.refund_rate <= 1.0
