"""Tests for Phase 5: Memory, Ledger, and Intelligence."""

import pytest
from datetime import datetime, UTC

from caps.memory import SessionMemory, ConversationTurn, PaymentAttempt
from caps.ledger import AuditLedger, LedgerEntry, EventType
from caps.intelligence import (
    FraudIntelligence,
    MerchantReport,
    ReportType,
    MerchantBadge,
)


class TestSessionMemory:
    """Test Session Memory."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.memory = SessionMemory()
    
    def test_add_user_turn(self):
        """User turns should be recorded."""
        self.memory.add_user_turn(
            "Pay canteen@vit 50 rupees",
            intent_type="PAYMENT",
            amount=50.0,
            merchant_vpa="canteen@vit",
        )
        
        assert len(self.memory.conversation) == 1
        assert self.memory.conversation[0].content == "Pay canteen@vit 50 rupees"
    
    def test_record_payment_attempt(self):
        """Payment attempts should be tracked."""
        self.memory.record_payment_attempt(
            transaction_id="txn_123",
            merchant_vpa="canteen@vit",
            amount=50.0,
            decision="APPROVE",
            success=True,
            raw_input="Pay canteen 50",
        )
        
        assert len(self.memory.payment_attempts) == 1
        assert self.memory.get_last_merchant() == "canteen@vit"
        assert self.memory.get_last_amount() == 50.0
    
    def test_resolve_merchant_reference(self):
        """'That merchant' should resolve to last merchant."""
        self.memory.record_payment_attempt(
            transaction_id="txn_123",
            merchant_vpa="shop@upi",
            amount=100.0,
            decision="APPROVE",
            success=True,
            raw_input="Pay shop 100",
        )
        
        resolved = self.memory.resolve_reference("Pay that merchant again")
        
        assert resolved.get("merchant_vpa") == "shop@upi"
    
    def test_resolve_amount_reference(self):
        """'Same amount' should resolve to last amount."""
        self.memory.record_payment_attempt(
            transaction_id="txn_123",
            merchant_vpa="shop@upi",
            amount=75.0,
            decision="APPROVE",
            success=True,
            raw_input="Pay shop 75",
        )
        
        resolved = self.memory.resolve_reference("Pay canteen same amount")
        
        assert resolved.get("amount") == 75.0
    
    def test_resolve_repeat_payment(self):
        """'Again' should resolve both merchant and amount."""
        self.memory.record_payment_attempt(
            transaction_id="txn_123",
            merchant_vpa="grocery@upi",
            amount=200.0,
            decision="APPROVE",
            success=True,
            raw_input="Pay grocery 200",
        )
        
        resolved = self.memory.resolve_reference("Do that again")
        
        assert resolved.get("merchant_vpa") == "grocery@upi"
        assert resolved.get("amount") == 200.0
    
    def test_session_context(self):
        """Session context should aggregate stats."""
        self.memory.record_payment_attempt(
            transaction_id="txn_1",
            merchant_vpa="a@upi",
            amount=50.0,
            decision="APPROVE",
            success=True,
            raw_input="pay a 50",
        )
        self.memory.record_payment_attempt(
            transaction_id="txn_2",
            merchant_vpa="b@upi",
            amount=100.0,
            decision="APPROVE",
            success=True,
            raw_input="pay b 100",
        )
        
        context = self.memory.get_session_context()
        
        assert context.session_payment_count == 2
        assert context.session_total_spent == 150.0
        assert context.last_merchant == "b@upi"


class TestAuditLedger:
    """Test Audit Ledger with hash-chaining."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.ledger = AuditLedger()  # In-memory DB
    
    def test_append_entry(self):
        """Entries should be appended to ledger."""
        entry = self.ledger.append(
            event_type=EventType.INTENT_RECEIVED,
            payload={"raw_input": "Pay canteen 50"},
            user_id="user_test",
        )
        
        assert entry.event_type == EventType.INTENT_RECEIVED
        assert entry.previous_hash == "genesis"
        assert entry.hash is not None
    
    def test_hash_chain(self):
        """Each entry should link to previous via hash."""
        entry1 = self.ledger.append(
            event_type=EventType.INTENT_RECEIVED,
            payload={"test": 1},
        )
        entry2 = self.ledger.append(
            event_type=EventType.INTENT_VALIDATED,
            payload={"test": 2},
        )
        
        assert entry2.previous_hash == entry1.hash
    
    def test_chain_validation_passes(self):
        """Valid chain should pass validation."""
        self.ledger.append(EventType.INTENT_RECEIVED, {"data": 1})
        self.ledger.append(EventType.INTENT_VALIDATED, {"data": 2})
        self.ledger.append(EventType.POLICY_EVALUATED, {"data": 3})
        
        result = self.ledger.validate_chain()
        
        assert result.is_valid is True
        assert result.total_entries == 3
    
    def test_get_entries_by_transaction(self):
        """Entries should be queryable by transaction ID."""
        self.ledger.append(
            EventType.EXECUTION_STARTED,
            {"amount": 50},
            transaction_id="txn_123",
        )
        self.ledger.append(
            EventType.EXECUTION_COMPLETED,
            {"success": True},
            transaction_id="txn_123",
        )
        self.ledger.append(
            EventType.EXECUTION_STARTED,
            {"amount": 100},
            transaction_id="txn_456",
        )
        
        entries = self.ledger.get_entries_by_transaction("txn_123")
        
        assert len(entries) == 2
        assert all(e.transaction_id == "txn_123" for e in entries)


class TestFraudIntelligence:
    """Test Crowdsourced Fraud Intelligence."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.intel = FraudIntelligence()  # In-memory DB
    
    def test_report_merchant(self):
        """Reports should be stored."""
        report = self.intel.report_merchant(
            merchant_vpa="scam@upi",
            reporter_id="user_1",
            report_type=ReportType.SCAM,
            reason="Asked for OTP",
        )
        
        assert report.merchant_vpa == "scam@upi"
        assert report.report_type == ReportType.SCAM
    
    def test_unknown_badge_for_new_merchant(self):
        """New merchants should have UNKNOWN badge."""
        score = self.intel.get_merchant_score("new@merchant")
        
        assert score.badge == MerchantBadge.UNKNOWN
        assert score.total_reports == 0
    
    def test_scam_rate_calculation(self):
        """Scam rate should be calculated from reports."""
        # Add 10 reports: 3 scam, 7 legitimate
        for i in range(3):
            self.intel.report_merchant("test@upi", f"user_{i}", ReportType.SCAM)
        for i in range(3, 10):
            self.intel.report_merchant("test@upi", f"user_{i}", ReportType.LEGITIMATE)
        
        score = self.intel.get_merchant_score("test@upi")
        
        assert score.total_reports == 10
        assert score.scam_reports == 3
        assert score.scam_rate == pytest.approx(0.3, rel=0.01)
    
    def test_likely_scam_badge(self):
        """Merchants with >20% scam rate should get LIKELY_SCAM."""
        # 5 scam out of 10 = 50% scam rate
        for i in range(5):
            self.intel.report_merchant("bad@upi", f"user_{i}", ReportType.SCAM)
        for i in range(5, 10):
            self.intel.report_merchant("bad@upi", f"user_{i}", ReportType.LEGITIMATE)
        
        score = self.intel.get_merchant_score("bad@upi")
        
        assert score.badge == MerchantBadge.LIKELY_SCAM
    
    def test_likely_safe_badge(self):
        """Merchants with 20+ reports and <5% scam should get LIKELY_SAFE."""
        # 1 scam out of 25 = 4% scam rate
        self.intel.report_merchant("good@upi", "user_0", ReportType.SCAM)
        for i in range(1, 25):
            self.intel.report_merchant("good@upi", f"user_{i}", ReportType.LEGITIMATE)
        
        score = self.intel.get_merchant_score("good@upi")
        
        assert score.badge == MerchantBadge.LIKELY_SAFE
    
    def test_admin_verify_scam(self):
        """Admin can mark merchant as confirmed scam."""
        self.intel.report_merchant("fraud@upi", "user_1", ReportType.SCAM)
        self.intel.verify_merchant_as_scam("fraud@upi", "admin_1")
        
        score = self.intel.get_merchant_score("fraud@upi")
        
        assert score.badge == MerchantBadge.CONFIRMED_SCAM
