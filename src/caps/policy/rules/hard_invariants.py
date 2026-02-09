"""Layer 1: Hard Invariant Rules.

These rules MUST pass or the payment is instantly DENIED.
No exceptions, no overrides - these are the hard limits.
"""

from typing import Optional, Tuple

from caps.schema import PaymentIntent, IntentType
from caps.context import UserContext, MerchantContext
from caps.policy.models import RuleCategory, RuleViolation
from caps.policy.rules import Rule


# UPI Lite hard limits
UPI_LITE_MAX_AMOUNT = 500.0  # ₹500 per transaction
UPI_LITE_DAILY_LIMIT = 2000.0  # ₹2000 per day


class AmountLimitRule(Rule):
    """Enforce UPI Lite transaction amount limit (₹500)."""
    
    def __init__(self):
        super().__init__(
            name="amount_limit",
            category=RuleCategory.HARD_INVARIANT,
            description=f"Transaction amount must not exceed ₹{UPI_LITE_MAX_AMOUNT}",
            severity="critical",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        # Only check for payment intents
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
        
        # No amount = can't evaluate, pass for now
        if intent.amount is None:
            return True, None
        
        if intent.amount > UPI_LITE_MAX_AMOUNT:
            return False, self.create_violation(
                f"Amount ₹{intent.amount:.2f} exceeds UPI Lite limit of ₹{UPI_LITE_MAX_AMOUNT}",
                details={
                    "requested_amount": intent.amount,
                    "max_allowed": UPI_LITE_MAX_AMOUNT,
                }
            )
        
        return True, None


class DailySpendLimitRule(Rule):
    """Enforce daily spending limit (₹2000)."""
    
    def __init__(self):
        super().__init__(
            name="daily_spend_limit",
            category=RuleCategory.HARD_INVARIANT,
            description=f"Daily spend must not exceed ₹{UPI_LITE_DAILY_LIMIT}",
            severity="critical",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
        
        if intent.amount is None:
            return True, None
        
        if user_context is None:
            # No context = can't verify, fail safe
            return False, self.create_violation(
                "Cannot verify daily spend without user context",
                details={"reason": "missing_context"}
            )
        
        projected_daily = user_context.daily_spend_today + intent.amount
        
        if projected_daily > UPI_LITE_DAILY_LIMIT:
            remaining = max(0, UPI_LITE_DAILY_LIMIT - user_context.daily_spend_today)
            return False, self.create_violation(
                f"Transaction would exceed daily limit. "
                f"Spent today: ₹{user_context.daily_spend_today:.2f}, "
                f"Remaining: ₹{remaining:.2f}",
                details={
                    "daily_spent": user_context.daily_spend_today,
                    "requested_amount": intent.amount,
                    "projected_total": projected_daily,
                    "daily_limit": UPI_LITE_DAILY_LIMIT,
                    "remaining": remaining,
                }
            )
        
        return True, None


class BalanceCheckRule(Rule):
    """Ensure sufficient wallet balance."""
    
    def __init__(self):
        super().__init__(
            name="balance_check",
            category=RuleCategory.HARD_INVARIANT,
            description="User must have sufficient wallet balance",
            severity="critical",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
        
        if intent.amount is None:
            return True, None
        
        if user_context is None:
            return False, self.create_violation(
                "Cannot verify balance without user context",
                details={"reason": "missing_context"}
            )
        
        if intent.amount > user_context.wallet_balance:
            return False, self.create_violation(
                f"Insufficient balance. "
                f"Required: ₹{intent.amount:.2f}, "
                f"Available: ₹{user_context.wallet_balance:.2f}",
                details={
                    "required": intent.amount,
                    "available": user_context.wallet_balance,
                    "shortfall": intent.amount - user_context.wallet_balance,
                }
            )
        
        return True, None


class MerchantCheckRule(Rule):
    """Ensure merchant VPA is valid."""
    
    def __init__(self):
        super().__init__(
            name="merchant_check",
            category=RuleCategory.HARD_INVARIANT,
            description="Merchant VPA must be valid and known",
            severity="critical",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if intent.intent_type != IntentType.PAYMENT:
            return True, None
            
        if not intent.merchant_vpa or intent.merchant_vpa.lower() == "unknown":
            return False, self.create_violation(
                "Payment requires a valid merchant VPA",
                details={"merchant_vpa": intent.merchant_vpa}
            )
            
        return True, None


# Export all Layer 1 rules
HARD_INVARIANT_RULES = [
    MerchantCheckRule(),
    AmountLimitRule(),
    DailySpendLimitRule(),
    BalanceCheckRule(),
]
