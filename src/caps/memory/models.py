"""Memory models for session and conversation tracking."""

from datetime import datetime, UTC
from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class TurnRole(str, Enum):
    """Role in conversation turn."""
    USER = "user"
    SYSTEM = "system"


class ConversationTurn(BaseModel):
    """A single turn in the conversation."""
    
    role: TurnRole = Field(description="Who sent this message")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # For user turns - extracted intent info
    intent_type: Optional[str] = Field(default=None)
    amount: Optional[float] = Field(default=None)
    merchant_vpa: Optional[str] = Field(default=None)
    
    # For system turns - decision info
    decision: Optional[str] = Field(default=None)
    transaction_id: Optional[str] = Field(default=None)


class PaymentAttempt(BaseModel):
    """Record of a payment attempt for session memory."""
    
    transaction_id: str = Field(description="Transaction ID")
    merchant_vpa: str = Field(description="Merchant VPA")
    merchant_name: Optional[str] = Field(default=None, description="Friendly name if available")
    amount: float = Field(description="Amount in INR")
    decision: str = Field(description="Policy decision")
    success: bool = Field(description="Whether payment was executed")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reference_number: Optional[str] = Field(default=None)
    
    # For context
    raw_input: str = Field(description="Original user input")


class SessionContext(BaseModel):
    """Context from session for LLM prompting."""
    
    last_merchant: Optional[str] = Field(default=None, description="Most recent merchant")
    last_amount: Optional[float] = Field(default=None, description="Most recent amount")
    last_transaction_id: Optional[str] = Field(default=None)
    recent_merchants: list[str] = Field(default_factory=list, description="Recent merchants")
    session_payment_count: int = Field(default=0)
    session_total_spent: float = Field(default=0.0)
