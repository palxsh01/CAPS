"""Execution models for transaction processing."""

import hashlib
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ExecutionState(str, Enum):
    """State machine states for transaction execution."""
    
    PENDING = "PENDING"              # Awaiting policy decision
    APPROVED = "APPROVED"            # Policy approved, ready to execute
    EXECUTING = "EXECUTING"          # Currently processing
    COMPLETED = "COMPLETED"          # Successfully executed
    FAILED = "FAILED"                # Execution failed
    DENIED = "DENIED"                # Policy denied
    COOLDOWN = "COOLDOWN"            # Rate limited, waiting
    ESCALATED = "ESCALATED"          # Requires additional verification
    CANCELLED = "CANCELLED"          # User cancelled


class TransactionRecord(BaseModel):
    """Immutable record of a transaction attempt."""
    
    transaction_id: str = Field(
        default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}",
        description="Unique transaction identifier"
    )
    intent_id: str = Field(description="Reference to original intent")
    user_id: str = Field(description="User who initiated transaction")
    merchant_vpa: str = Field(description="Merchant VPA")
    amount: float = Field(ge=0, description="Transaction amount in INR")
    
    # State tracking
    state: ExecutionState = Field(default=ExecutionState.PENDING)
    state_history: list[tuple[str, str]] = Field(
        default_factory=list,
        description="History of (state, timestamp) transitions"
    )
    
    # Hashing for integrity
    intent_hash: str = Field(description="Hash of original intent")
    approval_hash: Optional[str] = Field(default=None, description="Hash of policy approval")
    execution_hash: Optional[str] = Field(default=None, description="Hash of execution result")
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    executed_at: Optional[datetime] = Field(default=None)
    
    # Result
    error_message: Optional[str] = Field(default=None)
    
    def transition_to(self, new_state: ExecutionState) -> None:
        """Transition to a new state and record history."""
        self.state_history.append((self.state.value, datetime.now(UTC).isoformat()))
        self.state = new_state
    
    def compute_execution_hash(self) -> str:
        """Compute hash of execution for verification."""
        payload = f"{self.transaction_id}:{self.intent_hash}:{self.amount}:{self.merchant_vpa}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class ExecutionResult(BaseModel):
    """Result of transaction execution."""
    
    success: bool = Field(description="Whether execution succeeded")
    transaction_id: str = Field(description="Transaction ID")
    state: ExecutionState = Field(description="Final state")
    message: str = Field(description="Human-readable result message")
    
    # For successful executions
    reference_number: Optional[str] = Field(default=None, description="UPI reference number")
    executed_at: Optional[datetime] = Field(default=None)
    
    # For failed executions
    error_code: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    
    # Verification
    execution_hash: Optional[str] = Field(default=None)


class IdempotencyKey(BaseModel):
    """Key for idempotency checking."""
    
    key: str = Field(description="Unique idempotency key")
    transaction_id: str = Field(description="Associated transaction ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(description="When key expires")
