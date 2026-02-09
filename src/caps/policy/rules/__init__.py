"""Base class for policy rules."""

from abc import ABC, abstractmethod
from typing import Optional, Tuple

from caps.schema import PaymentIntent
from caps.context import UserContext, MerchantContext
from caps.policy.models import RuleCategory, RuleViolation


class Rule(ABC):
    """Abstract base class for policy rules."""
    
    def __init__(
        self,
        name: str,
        category: RuleCategory,
        description: str,
        severity: str = "medium",
    ):
        """
        Initialize a policy rule.
        
        Args:
            name: Unique rule identifier
            category: Rule category (determines decision on fail)
            description: Human-readable description
            severity: Severity level (critical, high, medium, low)
        """
        self.name = name
        self.category = category
        self.description = description
        self.severity = severity
    
    @abstractmethod
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional["UserContext"] = None,
        merchant_context: Optional["MerchantContext"] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        """
        Evaluate the rule against intent and context.
        
        Args:
            intent: Validated payment intent
            user_context: User context data (optional)
            merchant_context: Merchant context data (optional)
            
        Returns:
            Tuple of (passed: bool, violation: RuleViolation or None)
        """
        pass
    
    def create_violation(self, message: str, details: Optional[dict] = None) -> RuleViolation:
        """Create a violation for this rule."""
        return RuleViolation(
            rule_name=self.name,
            category=self.category,
            message=message,
            severity=self.severity,
            details=details,
        )
