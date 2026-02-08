"""
Context Data Models

Defines the structure of context data that the Policy Engine receives.

SECURITY: This data is NEVER sent to the LLM. It's fetched AFTER intent validation
and used only for policy evaluation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class UserContext(BaseModel):
    """
    User Context - Ground truth about the user's current state.
    
    This is fetched from the Context Service AFTER schema validation.
    Never exposed to the LLM.
    """
    
    user_id: str = Field(description="Unique user identifier")
    
    # Wallet & Spending
    wallet_balance: float = Field(
        ge=0,
        description="Current UPI Lite wallet balance (INR)",
    )
    daily_spend_today: float = Field(
        ge=0,
        description="Total amount spent today (INR)",
    )
    
    # Velocity Controls
    transactions_last_5min: int = Field(
        ge=0,
        description="Number of transactions in last 5 minutes",
    )
    transactions_today: int = Field(
        ge=0,
        description="Total transactions today",
    )
    
    # Device & Session
    device_fingerprint: str = Field(
        description="Device identifier hash",
    )
    is_known_device: bool = Field(
        description="Whether this device has been used before",
    )
    session_age_seconds: int = Field(
        ge=0,
        description="Time since session started (seconds)",
    )
    
    # Location
    location: Optional[str] = Field(
        default=None,
        description="User location (city/region)",
    )
    
    # Timestamps
    last_transaction_time: Optional[datetime] = Field(
        default=None,
        description="Timestamp of last transaction",
    )
    
    # Metadata
    account_age_days: int = Field(
        ge=0,
        description="Days since account creation",
    )


class MerchantContext(BaseModel):
    """
    Merchant Context - Reputation and risk data about the payee.
    
    Used by the Policy Engine to assess merchant risk.
    """
    
    merchant_vpa: str = Field(
        description="Merchant VPA (identifier@provider)",
    )
    
    # Reputation
    reputation_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Merchant reputation (0.0 = risky, 1.0 = trusted)",
    )
    is_whitelisted: bool = Field(
        description="Whether merchant is on whitelist",
    )
    
    # Transaction History
    total_transactions: int = Field(
        ge=0,
        description="Total transactions with this merchant",
    )
    successful_transactions: int = Field(
        ge=0,
        description="Successful transactions",
    )
    
    # Risk Metrics
    refund_rate: float = Field(
        ge=0.0,
        le=1.0,
        description="Refund/chargeback rate",
    )
    fraud_reports: int = Field(
        ge=0,
        description="Number of fraud reports",
    )
    
    # Metadata
    merchant_category: Optional[str] = Field(
        default=None,
        description="Merchant category code (MCC)",
    )
    registration_date: Optional[datetime] = Field(
        default=None,
        description="When merchant was registered",
    )


class TransactionRecord(BaseModel):
    """Record of a transaction for velocity tracking."""
    
    transaction_id: str
    user_id: str
    merchant_vpa: str
    amount: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: str = Field(default="pending")  # pending, success, failed
