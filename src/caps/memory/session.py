"""Session Memory - Stores conversation history within a session."""

import logging
import uuid
from datetime import datetime, UTC
from typing import Optional, List

from caps.memory.models import (
    ConversationTurn,
    PaymentAttempt,
    SessionContext,
    TurnRole,
)


logger = logging.getLogger(__name__)


class SessionMemory:
    """
    Session Memory for conversation continuity.
    
    Enables:
    - "Pay that merchant again" - references previous merchant
    - "Same amount" - references previous amount
    - "My last payment" - retrieves last transaction
    - Conversation context for LLM
    
    Note: This is in-memory and resets when the session ends.
    For persistent history, use the Audit Ledger.
    """
    
    def __init__(self, max_turns: int = 20, max_payments: int = 10):
        """
        Initialize session memory.
        
        Args:
            max_turns: Maximum conversation turns to keep
            max_payments: Maximum payment attempts to track
        """
        self.session_id = f"session_{uuid.uuid4().hex[:12]}"
        self.max_turns = max_turns
        self.max_payments = max_payments
        
        self.conversation: List[ConversationTurn] = []
        self.payment_attempts: List[PaymentAttempt] = []
        self.session_start = datetime.now(UTC)
        
        logger.info(f"Session Memory initialized: {self.session_id}")
    
    def add_user_turn(
        self,
        content: str,
        intent_type: Optional[str] = None,
        amount: Optional[float] = None,
        merchant_vpa: Optional[str] = None,
    ) -> None:
        """Record a user message."""
        turn = ConversationTurn(
            role=TurnRole.USER,
            content=content,
            intent_type=intent_type,
            amount=amount,
            merchant_vpa=merchant_vpa,
        )
        self._add_turn(turn)
    
    def add_system_turn(
        self,
        content: str,
        decision: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> None:
        """Record a system response."""
        turn = ConversationTurn(
            role=TurnRole.SYSTEM,
            content=content,
            decision=decision,
            transaction_id=transaction_id,
        )
        self._add_turn(turn)
    
    def record_payment_attempt(
        self,
        transaction_id: str,
        merchant_vpa: str,
        amount: float,
        decision: str,
        success: bool,
        raw_input: str,
        reference_number: Optional[str] = None,
        merchant_name: Optional[str] = None,
    ) -> None:
        """Record a payment attempt."""
        attempt = PaymentAttempt(
            transaction_id=transaction_id,
            merchant_vpa=merchant_vpa,
            merchant_name=merchant_name,
            amount=amount,
            decision=decision,
            success=success,
            raw_input=raw_input,
            reference_number=reference_number,
        )
        
        self.payment_attempts.append(attempt)
        
        # Keep only recent attempts
        if len(self.payment_attempts) > self.max_payments:
            self.payment_attempts = self.payment_attempts[-self.max_payments:]
        
        logger.debug(f"Recorded payment attempt: {transaction_id}")
    
    def get_last_payment(self) -> Optional[PaymentAttempt]:
        """Get the most recent payment attempt."""
        if self.payment_attempts:
            return self.payment_attempts[-1]
        return None
    
    def get_last_successful_payment(self) -> Optional[PaymentAttempt]:
        """Get the most recent successful payment."""
        for attempt in reversed(self.payment_attempts):
            if attempt.success:
                return attempt
        return None
    
    def get_last_merchant(self) -> Optional[str]:
        """Get the most recent merchant VPA."""
        if self.payment_attempts:
            return self.payment_attempts[-1].merchant_vpa
        return None
    
    def get_last_amount(self) -> Optional[float]:
        """Get the most recent payment amount."""
        if self.payment_attempts:
            return self.payment_attempts[-1].amount
        return None
    
    def get_recent_merchants(self, limit: int = 5) -> List[str]:
        """Get list of recently used merchant VPAs."""
        merchants = []
        seen = set()
        for attempt in reversed(self.payment_attempts):
            if attempt.merchant_vpa not in seen:
                merchants.append(attempt.merchant_vpa)
                seen.add(attempt.merchant_vpa)
            if len(merchants) >= limit:
                break
        return merchants
    
    def get_session_context(self) -> SessionContext:
        """Get session context for LLM prompting."""
        last_payment = self.get_last_payment()
        
        total_spent = sum(
            p.amount for p in self.payment_attempts if p.success
        )
        
        return SessionContext(
            last_merchant=self.get_last_merchant(),
            last_amount=self.get_last_amount(),
            last_transaction_id=last_payment.transaction_id if last_payment else None,
            recent_merchants=self.get_recent_merchants(),
            session_payment_count=len(self.payment_attempts),
            session_total_spent=total_spent,
        )
    
    def get_conversation_context(self, last_n: int = 5) -> str:
        """
        Get recent conversation as text for LLM context.
        
        Returns formatted conversation history.
        """
        recent = self.conversation[-last_n:] if self.conversation else []
        
        lines = []
        for turn in recent:
            role = "User" if turn.role == TurnRole.USER else "System"
            lines.append(f"{role}: {turn.content}")
            
            if turn.merchant_vpa:
                lines.append(f"  → Merchant: {turn.merchant_vpa}")
            if turn.amount:
                lines.append(f"  → Amount: ₹{turn.amount}")
            if turn.decision:
                lines.append(f"  → Decision: {turn.decision}")
        
        return "\n".join(lines)
    
    def resolve_reference(self, user_input: str) -> dict:
        """
        Resolve pronoun references in user input.
        
        Detects patterns like:
        - "that merchant" / "same merchant" → last merchant
        - "same amount" → last amount
        - "again" / "repeat" → last payment
        
        Returns dict with resolved values.
        """
        input_lower = user_input.lower()
        resolved = {}
        
        # Check for merchant references
        merchant_refs = [
            "that merchant", "same merchant", "them again", "the same", 
            "pay him", "pay her", "pay them",
            "previous user", "previous person", "last user", "last person"
        ]
        if any(ref in input_lower for ref in merchant_refs):
            last_merchant = self.get_last_merchant()
            if last_merchant:
                resolved["merchant_vpa"] = last_merchant
                logger.info(f"Resolved merchant reference: {last_merchant}")
        
        # Check for amount references
        amount_refs = ["same amount", "same price"]
        if any(ref in input_lower for ref in amount_refs):
            last_amount = self.get_last_amount()
            if last_amount:
                resolved["amount"] = last_amount
                logger.info(f"Resolved amount reference: {last_amount}")
        
        # Check for "again" / "repeat" patterns
        repeat_refs = ["again", "repeat", "once more", "one more time"]
        if any(ref in input_lower for ref in repeat_refs):
            last_payment = self.get_last_successful_payment()
            if last_payment:
                resolved["merchant_vpa"] = last_payment.merchant_vpa
                resolved["amount"] = last_payment.amount
                logger.info(f"Resolved repeat: {last_payment.merchant_vpa} ₹{last_payment.amount}")
        
        return resolved
    
    def _add_turn(self, turn: ConversationTurn) -> None:
        """Add a turn and maintain max size."""
        self.conversation.append(turn)
        
        if len(self.conversation) > self.max_turns:
            self.conversation = self.conversation[-self.max_turns:]
    
    def clear(self) -> None:
        """Clear session memory."""
        self.conversation.clear()
        self.payment_attempts.clear()
        self.session_start = datetime.now(UTC)
        logger.info("Session memory cleared")
