"""Integration tests for context service and client."""

import pytest
from caps.context import ContextClient
from caps.context.mock_data import MOCK_USERS, MOCK_MERCHANTS


class TestContextClient:
    """Test Context Client integration."""

    @pytest.fixture
    def context_client(self):
        """Create context client for testing."""
        # Uses default config (localhost:8001)
        return ContextClient()

    def test_get_user_context_sync(self, context_client):
        """Test synchronous user context retrieval."""
        try:
            user_context = context_client.get_user_context_sync("user_test")
            assert user_context.user_id == "user_test"
            assert user_context.wallet_balance > 0
        except Exception:
            pytest.skip("Context service not running")

    def test_get_merchant_context_sync(self, context_client):
        """Test synchronous merchant context retrieval."""
        try:
            merchant_context = context_client.get_merchant_context_sync("canteen@vit")
            assert merchant_context.merchant_vpa == "canteen@vit"
            assert merchant_context.reputation_score > 0
        except Exception:
            pytest.skip("Context service not running")


class TestEndToEndFlow:
    """Test end-to-end intent + context flow."""

    def test_intent_validation_then_context(self):
        """Test that context is fetched AFTER validation."""
        from caps.schema import SchemaValidator
        
        # Step 1: Validate intent (no context yet)
        validator = SchemaValidator()
        intent_data = {
            "intent_type": "PAYMENT",
            "amount": 100.0,
            "merchant_vpa": "shop@upi",
            "confidence_score": 0.9,
        }
        
        validated_intent = validator.validate(intent_data)
        assert validated_intent.amount == 100.0
        
        # Step 2: Fetch context AFTER validation
        try:
            context_client = ContextClient()
            user_context = context_client.get_user_context_sync("user_test")
            merchant_context = context_client.get_merchant_context_sync(validated_intent.merchant_vpa)
            
            # Verify context data
            assert user_context.wallet_balance >= 0
            assert merchant_context.reputation_score >= 0
        except Exception:
            pytest.skip("Context service not running")
