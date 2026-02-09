"""Tests for Execution Engine and Decision Router."""

import pytest
from datetime import datetime, UTC

from caps.schema import PaymentIntent, IntentType, Currency
from caps.policy import PolicyDecision, PolicyResult
from caps.execution import (
    ExecutionState,
    ExecutionResult,
    TransactionRecord,
    DecisionRouter,
    ExecutionEngine,
)


class TestDecisionRouter:
    """Test Decision Router state transitions."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.router = DecisionRouter()
        self.intent = PaymentIntent(
            intent_type=IntentType.PAYMENT,
            amount=100.0,
            currency=Currency.INR,
            merchant_vpa="shop@upi",
            confidence_score=0.95,
            raw_input="Pay shop@upi 100 rupees",
        )
    
    def test_route_approve(self):
        """APPROVE decision should transition to APPROVED state."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        
        assert record.state == ExecutionState.APPROVED
        assert record.approval_hash is not None
        assert record.error_message is None
    
    def test_route_deny(self):
        """DENY decision should transition to DENIED state."""
        policy_result = PolicyResult(
            decision=PolicyDecision.DENY,
            reason="Amount exceeds limit",
            risk_score=0.5,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        
        assert record.state == ExecutionState.DENIED
        assert record.error_message == "Amount exceeds limit"
    
    def test_route_cooldown(self):
        """COOLDOWN decision should transition to COOLDOWN state."""
        policy_result = PolicyResult(
            decision=PolicyDecision.COOLDOWN,
            reason="Rate limit exceeded",
            risk_score=0.3,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        
        assert record.state == ExecutionState.COOLDOWN
        assert record.error_message == "Rate limit exceeded"
    
    def test_route_escalate(self):
        """ESCALATE decision should transition to ESCALATED state."""
        policy_result = PolicyResult(
            decision=PolicyDecision.ESCALATE,
            reason="Suspicious activity",
            risk_score=0.7,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        
        assert record.state == ExecutionState.ESCALATED
        assert record.error_message == "Suspicious activity"
    
    def test_state_history_tracked(self):
        """State transitions should be recorded in history."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        
        # Should have transition from PENDING to APPROVED
        assert len(record.state_history) == 1
        assert record.state_history[0][0] == "PENDING"


class TestExecutionEngine:
    """Test Execution Engine."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.engine = ExecutionEngine(failure_rate=0.0)  # No random failures
        self.router = DecisionRouter()
        self.intent = PaymentIntent(
            intent_type=IntentType.PAYMENT,
            amount=100.0,
            currency=Currency.INR,
            merchant_vpa="shop@upi",
            confidence_score=0.95,
            raw_input="Pay shop@upi 100 rupees",
        )
    
    def test_execute_approved_transaction(self):
        """Approved transactions should execute successfully."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        result = self.engine.execute(record)
        
        assert result.success is True
        assert result.state == ExecutionState.COMPLETED
        assert result.reference_number is not None
        assert result.execution_hash is not None
    
    def test_reject_non_approved_transaction(self):
        """Non-approved transactions should fail."""
        record = TransactionRecord(
            intent_id="test_intent",
            user_id="user_test",
            merchant_vpa="shop@upi",
            amount=100.0,
            intent_hash="abc123",
            state=ExecutionState.DENIED,  # Not approved
        )
        
        result = self.engine.execute(record)
        
        assert result.success is False
        assert result.error_code == "INVALID_STATE"
    
    def test_idempotency_prevents_duplicate(self):
        """Duplicate transactions should be rejected."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        # First execution
        record1 = self.router.route(self.intent, policy_result, "user_test")
        result1 = self.engine.execute(record1)
        assert result1.success is True
        
        # Second execution with same details (different record object)
        record2 = self.router.route(self.intent, policy_result, "user_test")
        result2 = self.engine.execute(record2)
        
        assert result2.success is False
        assert result2.error_code == "DUPLICATE"
    
    def test_transaction_logged(self):
        """Executed transactions should be logged."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        record = self.router.route(self.intent, policy_result, "user_test")
        result = self.engine.execute(record)
        
        # Should be in transaction log
        logged = self.engine.get_transaction(result.transaction_id)
        assert logged is not None
        assert logged.state == ExecutionState.COMPLETED
    
    def test_transaction_history(self):
        """Transaction history should be retrievable by user."""
        policy_result = PolicyResult(
            decision=PolicyDecision.APPROVE,
            reason="All checks passed",
            risk_score=0.0,
        )
        
        # Execute a transaction
        record = self.router.route(self.intent, policy_result, "user_test")
        self.engine.execute(record)
        
        # Get history
        history = self.engine.get_transaction_history("user_test")
        assert len(history) == 1
        assert history[0].user_id == "user_test"


class TestTransactionRecord:
    """Test TransactionRecord model."""
    
    def test_state_transition(self):
        """State transitions should be tracked."""
        record = TransactionRecord(
            intent_id="test",
            user_id="user_test",
            merchant_vpa="shop@upi",
            amount=100.0,
            intent_hash="abc123",
        )
        
        assert record.state == ExecutionState.PENDING
        
        record.transition_to(ExecutionState.APPROVED)
        assert record.state == ExecutionState.APPROVED
        assert len(record.state_history) == 1
        
        record.transition_to(ExecutionState.COMPLETED)
        assert record.state == ExecutionState.COMPLETED
        assert len(record.state_history) == 2
    
    def test_compute_execution_hash(self):
        """Execution hash should be consistent."""
        record = TransactionRecord(
            intent_id="test",
            user_id="user_test",
            merchant_vpa="shop@upi",
            amount=100.0,
            intent_hash="abc123",
        )
        
        hash1 = record.compute_execution_hash()
        hash2 = record.compute_execution_hash()
        
        assert hash1 == hash2  # Deterministic
        assert len(hash1) == 16  # 16 hex chars
