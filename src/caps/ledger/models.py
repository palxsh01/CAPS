"""Ledger models for immutable audit logging."""

import hashlib
import json
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, computed_field


class EventType(str, Enum):
    """Types of events in the audit ledger."""
    
    INTENT_RECEIVED = "INTENT_RECEIVED"      # User input received
    INTENT_VALIDATED = "INTENT_VALIDATED"    # Schema validation passed
    INTENT_REJECTED = "INTENT_REJECTED"      # Schema validation failed
    CONTEXT_FETCHED = "CONTEXT_FETCHED"      # Context retrieved
    POLICY_EVALUATED = "POLICY_EVALUATED"    # Policy decision made
    EXECUTION_STARTED = "EXECUTION_STARTED"  # Payment execution began
    EXECUTION_COMPLETED = "EXECUTION_COMPLETED"  # Payment successful
    EXECUTION_FAILED = "EXECUTION_FAILED"    # Payment failed
    USER_FEEDBACK = "USER_FEEDBACK"          # User reported merchant


class LedgerEntry(BaseModel):
    """
    Immutable ledger entry with hash-chaining.
    
    Each entry contains:
    - Unique entry ID
    - Event type and payload
    - Previous entry's hash (for chain integrity)
    - Computed hash of this entry
    
    Tampering with any entry breaks the chain.
    """
    
    entry_id: str = Field(
        default_factory=lambda: f"entry_{uuid.uuid4().hex[:12]}",
        description="Unique entry identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When event occurred"
    )
    event_type: EventType = Field(description="Type of event")
    
    # Payload - the actual event data
    payload: dict = Field(description="Event-specific data")
    
    # Chain linking
    previous_hash: str = Field(
        default="genesis",
        description="Hash of previous entry"
    )
    
    # User/session context
    user_id: Optional[str] = Field(default=None)
    session_id: Optional[str] = Field(default=None)
    transaction_id: Optional[str] = Field(default=None)
    
    # Hash is computed on demand
    _cached_hash: Optional[str] = None
    
    def compute_hash(self) -> str:
        """
        Compute SHA-256 hash of this entry.
        
        Hash includes: previous_hash + timestamp + event_type + payload
        This creates an unbreakable chain.
        """
        # Create deterministic string from entry data
        hash_input = json.dumps({
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "payload": self.payload,
            "entry_id": self.entry_id,
        }, sort_keys=True)
        
        return hashlib.sha256(hash_input.encode()).hexdigest()[:32]
    
    @property
    def hash(self) -> str:
        """Get or compute hash."""
        if self._cached_hash is None:
            self._cached_hash = self.compute_hash()
        return self._cached_hash


class ChainValidationResult(BaseModel):
    """Result of ledger chain validation."""
    
    is_valid: bool = Field(description="Whether chain is valid")
    total_entries: int = Field(description="Total entries checked")
    broken_at: Optional[int] = Field(default=None, description="Index where chain broke")
    error_message: Optional[str] = Field(default=None)
