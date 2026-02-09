"""Layer 2: Velocity Control Rules.

These rules detect rapid transaction patterns that may indicate
automated attacks or wallet draining attempts.
"""

from typing import Optional, Tuple

from caps.schema import PaymentIntent, IntentType
from caps.context import UserContext, MerchantContext
from caps.policy.models import RuleCategory, RuleViolation
from caps.policy.rules import Rule


# Velocity limits
MAX_TRANSACTIONS_5MIN = 10  # Max transactions in 5 minute window
IDENTICAL_AMOUNT_THRESHOLD = 3  # Flag if same amount appears 3+ times rapidly


class TransactionVelocityRule(Rule):
    """Limit transaction rate to prevent rapid-fire attacks."""
    
    def __init__(self):
        super().__init__(
            name="transaction_velocity",
            category=RuleCategory.VELOCITY,
            description=f"Max {MAX_TRANSACTIONS_5MIN} transactions per 5 minutes",
            severity="high",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
        
        if user_context is None:
            # No context = can't check velocity, pass with warning
            return True, None
        
        if user_context.transactions_last_5min >= MAX_TRANSACTIONS_5MIN:
            return False, self.create_violation(
                f"Transaction velocity limit reached. "
                f"{user_context.transactions_last_5min} transactions in last 5 minutes "
                f"(limit: {MAX_TRANSACTIONS_5MIN})",
                details={
                    "current_count": user_context.transactions_last_5min,
                    "limit": MAX_TRANSACTIONS_5MIN,
                    "cooldown_suggested": "5 minutes",
                }
            )
        
        return True, None


class MerchantSwitchingRule(Rule):
    """Detect rapid switching between different merchants."""
    
    def __init__(self):
        super().__init__(
            name="merchant_switching",
            category=RuleCategory.VELOCITY,
            description="Detect rapid merchant switching patterns",
            severity="medium",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
        
        if user_context is None:
            return True, None
        
        # High velocity with unknown merchant = suspicious
        if user_context.transactions_last_5min >= 5:
            if merchant_context and merchant_context.total_transactions == 0:
                return False, self.create_violation(
                    "High transaction velocity with new/unknown merchant",
                    details={
                        "transactions_5min": user_context.transactions_last_5min,
                        "merchant": intent.merchant_vpa,
                        "merchant_history": 0,
                    }
                )
        
        return True, None


# Export all Layer 2 rules
VELOCITY_RULES = [
    TransactionVelocityRule(),
    MerchantSwitchingRule(),
]
