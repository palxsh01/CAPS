
import pytest
from datetime import datetime, UTC
from caps.ledger.ledger import AuditLedger
from caps.ledger.models import EventType
from caps.policy.engine import PolicyEngine
from caps.execution.engine import ExecutionEngine, TransactionRecord, ExecutionState
from caps.schema import PaymentIntent, IntentType

def test_structured_logging_integration():
    # 1. Setup Ledger
    ledger = AuditLedger(":memory:")
    # Use get_recent_entries
    entries = ledger.get_recent_entries(100) 
    assert len(entries) == 0
    
    # 2. Setup Engines with Ledger
    policy_engine = PolicyEngine(ledger=ledger)
    execution_engine = ExecutionEngine(ledger=ledger, failure_rate=0.0) # Ensure success
    
    # 3. Simulate Policy Check
    intent = PaymentIntent(
        intent_type=IntentType.PAYMENT,
        amount=100.0,
        currency="INR",
        merchant_vpa="test@upi",
        confidence_score=1.0,
        raw_input="pay test 100"
    )
    
    # Mock User Context
    from caps.context import UserContext
    user_context = UserContext(
        user_id="user_1",
        account_balance=5000.0,
        wallet_balance=5000.0,
        daily_spend=0.0,
        daily_spend_today=0.0,
        risk_score=0.0,
        transactions_last_5min=0,
        transactions_today=0,
        device_fingerprint="device_123",
        is_known_device=True,
        session_age_seconds=60,
        account_age_days=365
    )
    
    # Evaluate policy with context
    result = policy_engine.evaluate(intent, user_context=user_context)
    
    # Verify Policy Log
    history = ledger.get_recent_entries(20)[::-1] # Reverse to get chronological order
    assert len(history) == 1
    assert history[0].event_type == EventType.POLICY_EVALUATED
    assert history[0].payload["decision"] == "APPROVE"
    assert history[0].hash is not None
    
    # 4. Simulate Execution
    record = TransactionRecord(
        intent_id="test_intent",
        user_id="user_1",
        merchant_vpa="test@upi",
        amount=100.0,
        intent_hash="hash"
    )
    record.state = ExecutionState.APPROVED
    record.approval_hash = "mock_hash"
    
    # Execute
    execution_engine.execute(record)
    
    # Verify Execution Logs
    history = ledger.get_recent_entries(20)[::-1] # Reverse because recent returns DESC
    # Should have: DECISION, EXECUTION_STARTED, EXECUTION_COMPLETED
    assert len(history) == 3
    
    assert history[1].event_type == EventType.EXECUTION_STARTED
    assert history[2].event_type == EventType.EXECUTION_COMPLETED
    
    # Check chaining
    assert history[1].previous_hash == history[0].hash
    assert history[2].previous_hash == history[1].hash
    
    # Validate chain
    validation = ledger.validate_chain()
    assert validation.is_valid
    assert validation.total_entries == 3
    
    print("Structured logging verification passed!")

if __name__ == "__main__":
    test_structured_logging_integration()
