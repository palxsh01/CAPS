"""Layer 3: Agentic Threat Defense Rules.

These rules detect attempts to manipulate the LLM agent
through prompt injection, intent splitting, or other attacks.
"""

import re
from typing import Optional, Tuple, List

from caps.schema import PaymentIntent, IntentType
from caps.context import UserContext, MerchantContext
from caps.policy.models import RuleCategory, RuleViolation
from caps.policy.rules import Rule


# Minimum confidence threshold for payment execution
MIN_CONFIDENCE_THRESHOLD = 0.7

# Suspicious keywords that may indicate prompt injection
SUSPICIOUS_KEYWORDS: List[str] = [
    "ignore previous",
    "disregard",
    "override",
    "system prompt",
    "you are now",
    "pretend",
    "act as",
    "bypass",
    "skip validation",
    "admin mode",
    "debug mode",
    "unlimited",
    "no limit",
    "maximum amount",
    "all my money",
    "entire balance",
    "everything",
]


class ConfidenceThresholdRule(Rule):
    """Require minimum LLM confidence for payment execution."""
    
    def __init__(self):
        super().__init__(
            name="confidence_threshold",
            category=RuleCategory.THREAT_DEFENSE,
            description=f"LLM confidence must be at least {MIN_CONFIDENCE_THRESHOLD}",
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
        
        if intent.confidence_score < MIN_CONFIDENCE_THRESHOLD:
            return False, self.create_violation(
                f"LLM confidence ({intent.confidence_score:.2f}) below threshold "
                f"({MIN_CONFIDENCE_THRESHOLD}). Requires user confirmation.",
                details={
                    "confidence": intent.confidence_score,
                    "threshold": MIN_CONFIDENCE_THRESHOLD,
                    "raw_input": intent.raw_input,
                }
            )
        
        return True, None


class PromptInjectionRule(Rule):
    """Detect potential prompt injection attempts in user input."""
    
    def __init__(self):
        super().__init__(
            name="prompt_injection",
            category=RuleCategory.THREAT_DEFENSE,
            description="Detect prompt injection keywords in input",
            severity="critical",
        )
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> Tuple[bool, Optional[RuleViolation]]:
        if not intent.raw_input:
            return True, None
        
        input_lower = intent.raw_input.lower()
        
        detected_keywords = []
        for keyword in SUSPICIOUS_KEYWORDS:
            if keyword in input_lower:
                detected_keywords.append(keyword)
        
        if detected_keywords:
            return False, self.create_violation(
                f"Potential prompt injection detected. "
                f"Suspicious keywords: {', '.join(detected_keywords)}",
                details={
                    "detected_keywords": detected_keywords,
                    "raw_input": intent.raw_input,
                }
            )
        
        return True, None


class IntentSplittingRule(Rule):
    """Detect attempts to split a large transaction into smaller ones."""
    
    def __init__(self):
        super().__init__(
            name="intent_splitting",
            category=RuleCategory.THREAT_DEFENSE,
            description="Detect transaction splitting patterns",
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
        
        if not intent.raw_input:
            return True, None
        
        # Detect patterns like "pay 100 five times" or "repeat 10 times"
        split_patterns = [
            r'\b(\d+)\s*times?\b',
            r'\brepeat\b',
            r'\beach\b.*\btimes?\b',
            r'\bsplit\b',
            r'\bdivide\b',
            r'\bseparate\b.*\bpayments?\b',
        ]
        
        input_lower = intent.raw_input.lower()
        
        for pattern in split_patterns:
            if re.search(pattern, input_lower):
                return False, self.create_violation(
                    "Potential intent splitting detected. "
                    "Multiple transaction requests should be made separately.",
                    details={
                        "pattern_matched": pattern,
                        "raw_input": intent.raw_input,
                    }
                )
        
        return True, None


# Export all Layer 3 rules
THREAT_DEFENSE_RULES = [
    ConfidenceThresholdRule(),
    PromptInjectionRule(),
    IntentSplittingRule(),
]
