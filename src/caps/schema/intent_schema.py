"""
Payment Intent Schema Definition

This module defines the authoritative JSON schema for payment intents using Pydantic.
All payment requests must conform to this schema (Trust Gate 1).
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class IntentType(str, Enum):
    """Supported intent types."""

    PAYMENT = "PAYMENT"
    BALANCE_INQUIRY = "BALANCE_INQUIRY"
    TRANSACTION_HISTORY = "TRANSACTION_HISTORY"


class Currency(str, Enum):
    """Supported currencies."""

    INR = "INR"


class PaymentIntent(BaseModel):
    """
    Payment Intent Schema
    
    This is the core data structure that bridges the LLM reasoning layer
    and the deterministic control plane. Every field is strictly typed and validated.
    """

    # Unique identifier for this intent
    intent_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this payment intent",
    )

    # Intent classification
    intent_type: IntentType = Field(
        description="Type of intent (PAYMENT, BALANCE_INQUIRY, etc.)",
    )

    # Payment details (required for PAYMENT intent_type)
    amount: Optional[float] = Field(
        default=None,
        gt=0,
        description="Transaction amount (must be positive)",
    )

    currency: Currency = Field(
        default=Currency.INR,
        description="Currency code",
    )

    merchant_vpa: Optional[str] = Field(
        default=None,
        description="Merchant's VPA (Virtual Payment Address)",
    )

    # LLM confidence score
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM confidence in intent interpretation (0.0-1.0)",
    )

    # Metadata
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Intent creation timestamp",
    )

    raw_input: Optional[str] = Field(
        default=None,
        description="Original user input (for audit)",
    )

    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional context (extensible)",
    )

    @field_validator("merchant_vpa")
    @classmethod
    def validate_vpa_format(cls, v: Optional[str]) -> Optional[str]:
        """Validate VPA format: identifier@provider"""
        if v is None:
            return v

        if "@" not in v:
            raise ValueError("VPA must contain '@' separator")

        parts = v.split("@")
        if len(parts) != 2:
            raise ValueError("VPA must have format: identifier@provider")

        identifier, provider = parts
        if not identifier or not provider:
            raise ValueError("VPA identifier and provider cannot be empty")

        return v

    @field_validator("amount")
    @classmethod
    def validate_payment_amount(cls, v: Optional[float], info) -> Optional[float]:
        """Ensure amount is provided for PAYMENT intent types."""
        # This validation happens after field assignment
        # We need to check intent_type from values being validated
        if v is None:
            return v
        
        if v <= 0:
            raise ValueError("Payment amount must be positive")

        return v

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "intent_type": "PAYMENT",
                    "amount": 50.0,
                    "currency": "INR",
                    "merchant_vpa": "canteen@vit",
                    "confidence_score": 0.95,
                    "raw_input": "Pay canteen 50 rupees",
                }
            ]
        }
    }
