"""Decision Router - Routes policy decisions to appropriate handlers."""

import logging
from typing import Optional, Callable, Dict

from caps.schema import PaymentIntent
from caps.policy import PolicyDecision, PolicyResult
from caps.execution.models import ExecutionState, TransactionRecord


logger = logging.getLogger(__name__)


class DecisionRouter:
    """
    Routes policy decisions to appropriate execution paths.
    
    State Machine:
    
    PENDING → [Policy Check] → APPROVED → [Execute] → COMPLETED
                            ↘ DENIED (terminal)
                            ↘ COOLDOWN (wait, retry)
                            ↘ ESCALATED (verify, retry)
    """
    
    def __init__(self):
        """Initialize the decision router."""
        self.handlers: Dict[PolicyDecision, Callable] = {
            PolicyDecision.APPROVE: self._handle_approve,
            PolicyDecision.DENY: self._handle_deny,
            PolicyDecision.COOLDOWN: self._handle_cooldown,
            PolicyDecision.ESCALATE: self._handle_escalate,
        }
        logger.info("Decision Router initialized")
    
    def route(
        self,
        intent: PaymentIntent,
        policy_result: PolicyResult,
        user_id: str,
    ) -> TransactionRecord:
        """
        Route a policy decision to create a transaction record.
        
        Args:
            intent: Validated payment intent
            policy_result: Result from policy engine
            user_id: User who initiated the request
            
        Returns:
            TransactionRecord with appropriate state
        """
        # Create transaction record
        record = TransactionRecord(
            intent_id=str(intent.intent_id),
            user_id=user_id,
            merchant_vpa=intent.merchant_vpa or "unknown",
            amount=intent.amount or 0.0,
            intent_hash=self._compute_intent_hash(intent),
        )
        
        # Route to appropriate handler
        handler = self.handlers.get(policy_result.decision)
        if handler:
            handler(record, policy_result)
        else:
            logger.error(f"Unknown decision type: {policy_result.decision}")
            record.transition_to(ExecutionState.DENIED)
            record.error_message = "Unknown decision type"
        
        logger.info(
            f"Routed decision {policy_result.decision.value} → "
            f"State: {record.state.value}"
        )
        
        return record
    
    def _handle_approve(
        self,
        record: TransactionRecord,
        policy_result: PolicyResult,
    ) -> None:
        """Handle APPROVE decision - mark ready for execution."""
        record.transition_to(ExecutionState.APPROVED)
        record.approval_hash = self._compute_approval_hash(policy_result)
    
    def _handle_deny(
        self,
        record: TransactionRecord,
        policy_result: PolicyResult,
    ) -> None:
        """Handle DENY decision - terminal state."""
        record.transition_to(ExecutionState.DENIED)
        record.error_message = policy_result.reason
    
    def _handle_cooldown(
        self,
        record: TransactionRecord,
        policy_result: PolicyResult,
    ) -> None:
        """Handle COOLDOWN decision - rate limited."""
        record.transition_to(ExecutionState.COOLDOWN)
        record.error_message = policy_result.reason
    
    def _handle_escalate(
        self,
        record: TransactionRecord,
        policy_result: PolicyResult,
    ) -> None:
        """Handle ESCALATE decision - requires verification."""
        record.transition_to(ExecutionState.ESCALATED)
        record.error_message = policy_result.reason
    
    def _compute_intent_hash(self, intent: PaymentIntent) -> str:
        """Compute hash of intent for verification."""
        import hashlib
        payload = f"{intent.intent_id}:{intent.amount}:{intent.merchant_vpa}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
    
    def _compute_approval_hash(self, policy_result: PolicyResult) -> str:
        """Compute hash of policy approval."""
        import hashlib
        payload = f"{policy_result.decision.value}:{policy_result.risk_score}"
        return hashlib.sha256(payload.encode()).hexdigest()[:16]
