"""Unit tests for schema validation (Trust Gate 1)."""

import pytest
from caps.schema import PaymentIntent, IntentType, Currency, SchemaValidator, ValidationError


class TestPaymentIntentSchema:
    """Test PaymentIntent model validation."""

    def test_valid_payment_intent(self):
        """Test that a valid payment intent parses successfully."""
        data = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "currency": "INR",
            "merchant_vpa": "canteen@vit",
            "confidence_score": 0.95,
        }
        
        intent = PaymentIntent(**data)
        
        assert intent.intent_type == IntentType.PAYMENT
        assert intent.amount == 50.0
        assert intent.currency == Currency.INR
        assert intent.merchant_vpa == "canteen@vit"
        assert intent.confidence_score == 0.95
        assert intent.intent_id is not None  # Auto-generated

    def test_invalid_negative_amount(self):
        """Test that negative amounts are rejected."""
        data = {
            "intent_type": "PAYMENT",
            "amount": -100.0,
            "merchant_vpa": "store@merchant",
            "confidence_score": 0.9,
        }
        
        with pytest.raises(Exception):  # Pydantic ValidationError
            PaymentIntent(**data)

    def test_invalid_zero_amount(self):
        """Test that zero amounts are rejected."""
        data = {
            "intent_type": "PAYMENT",
            "amount": 0.0,
            "merchant_vpa": "store@merchant",
            "confidence_score": 0.9,
        }
        
        with pytest.raises(Exception):
            PaymentIntent(**data)

    def test_invalid_vpa_format_no_at(self):
        """Test that VPA without @ is rejected."""
        data = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "merchant_vpa": "invalidvpa",
            "confidence_score": 0.9,
        }
        
        with pytest.raises(Exception):
            PaymentIntent(**data)

    def test_invalid_vpa_format_multiple_at(self):
        """Test that VPA with multiple @ is rejected."""
        data = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "merchant_vpa": "invalid@multiple@vpa",
            "confidence_score": 0.9,
        }
        
        with pytest.raises(Exception):
            PaymentIntent(**data)

    def test_confidence_score_boundaries(self):
        """Test confidence score boundary validation."""
        # Valid: 0.0
        data_min = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "merchant_vpa": "test@vpa",
            "confidence_score": 0.0,
        }
        intent_min = PaymentIntent(**data_min)
        assert intent_min.confidence_score == 0.0

        # Valid: 1.0
        data_max = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "merchant_vpa": "test@vpa",
            "confidence_score": 1.0,
        }
        intent_max = PaymentIntent(**data_max)
        assert intent_max.confidence_score == 1.0

        # Invalid: > 1.0
        data_over = {
            "intent_type": "PAYMENT",
            "amount": 50.0,
            "merchant_vpa": "test@vpa",
            "confidence_score": 1.5,
        }
        with pytest.raises(Exception):
            PaymentIntent(**data_over)

    def test_balance_inquiry_intent(self):
        """Test balance inquiry intent (no amount required)."""
        data = {
            "intent_type": "BALANCE_INQUIRY",
            "confidence_score": 0.99,
        }
        
        intent = PaymentIntent(**data)
        assert intent.intent_type == IntentType.BALANCE_INQUIRY
        assert intent.amount is None


class TestSchemaValidator:
    """Test SchemaValidator (Trust Gate 1)."""

    def test_validate_valid_dict(self):
        """Test validation of valid dictionary."""
        validator = SchemaValidator()
        
        data = {
            "intent_type": "PAYMENT",
            "amount": 100.0,
            "merchant_vpa": "shop@upi",
            "confidence_score": 0.85,
        }
        
        intent = validator.validate(data)
        assert intent.amount == 100.0
        assert intent.merchant_vpa == "shop@upi"

    def test_validate_valid_json_string(self):
        """Test validation of valid JSON string."""
        validator = SchemaValidator()
        
        json_str = '{"intent_type": "PAYMENT", "amount": 75.5, "merchant_vpa": "cafe@bank", "confidence_score": 0.92}'
        
        intent = validator.validate(json_str)
        assert intent.amount == 75.5
        assert intent.merchant_vpa == "cafe@bank"

    def test_validate_invalid_json(self):
        """Test that invalid JSON raises PARSE_ERROR."""
        validator = SchemaValidator()
        
        invalid_json = '{invalid json}'
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(invalid_json)
        
        assert "PARSE_ERROR" in exc_info.value.message

    def test_validate_schema_violation(self):
        """Test that schema violations raise VALIDATION_ERROR."""
        validator = SchemaValidator()
        
        data = {
            "intent_type": "PAYMENT",
            "amount": -50.0,  # Invalid: negative
            "merchant_vpa": "test@vpa",
            "confidence_score": 0.9,
        }
        
        with pytest.raises(ValidationError) as exc_info:
            validator.validate(data)
        
        assert "VALIDATION_ERROR" in exc_info.value.message
        assert len(exc_info.value.errors) > 0

    def test_validate_safe_success(self):
        """Test safe validation with valid data."""
        validator = SchemaValidator()
        
        data = {
            "intent_type": "PAYMENT",
            "amount": 200.0,
            "merchant_vpa": "merchant@provider",
            "confidence_score": 0.88,
        }
        
        intent, error = validator.validate_safe(data)
        
        assert intent is not None
        assert error is None
        assert intent.amount == 200.0

    def test_validate_safe_failure(self):
        """Test safe validation with invalid data."""
        validator = SchemaValidator()
        
        data = {
            "intent_type": "PAYMENT",
            "amount": 0.0,  # Invalid
            "merchant_vpa": "test@vpa",
            "confidence_score": 0.9,
        }
        
        intent, error = validator.validate_safe(data)
        
        assert intent is None
        assert error is not None
        assert isinstance(error, ValidationError)
