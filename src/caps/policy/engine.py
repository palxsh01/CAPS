"""Policy Engine - Core Decision Making Logic.

The Policy Engine evaluates intents against context using deterministic rules.
This is Trust Gate 2 - the LLM cannot bypass these rules.
"""

import logging
import time
from typing import Optional, List

from caps.schema import PaymentIntent, IntentType
from caps.context import UserContext, MerchantContext
from caps.policy.models import PolicyDecision, PolicyResult, RuleViolation, RuleCategory
from caps.ledger.models import EventType
from caps.policy.rules import Rule
from caps.policy.rules.hard_invariants import HARD_INVARIANT_RULES
from caps.policy.rules.velocity import VELOCITY_RULES
from caps.policy.rules.threat_defense import THREAT_DEFENSE_RULES
from caps.policy.rules.behavioral import BEHAVIORAL_RULES


logger = logging.getLogger(__name__)


class PolicyEngine:
    """
    Deterministic Policy Engine for payment decisions.
    
    Evaluates intents through 4 layers of rules:
    - Layer 1: Hard Invariants (DENY on fail)
    - Layer 2: Velocity Controls (COOLDOWN on fail)
    - Layer 3: Agentic Threat Defense (ESCALATE on fail)
    - Layer 4: Behavioral Analysis (ESCALATE on fail)
    
    SECURITY: This engine runs deterministic Python code.
    The LLM cannot influence or bypass these rules.
    """
    
    def __init__(self, ledger=None):
        """Initialize the policy engine with all rule layers."""
        self.rules: List[Rule] = []
        self.ledger = ledger
        
        # Add rules in order (Layer 1 first)
        self.rules.extend(HARD_INVARIANT_RULES)
        self.rules.extend(VELOCITY_RULES)
        self.rules.extend(THREAT_DEFENSE_RULES)
        self.rules.extend(BEHAVIORAL_RULES)
        
        logger.info(f"Policy Engine initialized with {len(self.rules)} rules")
    
    def evaluate(
        self,
        intent: PaymentIntent,
        user_context: Optional[UserContext] = None,
        merchant_context: Optional[MerchantContext] = None,
    ) -> PolicyResult:
        """
        Evaluate an intent against all policy rules.
        
        Args:
            intent: Validated payment intent
            user_context: User context from context service
            merchant_context: Merchant context from context service
            
        Returns:
            PolicyResult with decision and details
        """
        start_time = time.time()
        
        violations: List[RuleViolation] = []
        passed_rules: List[str] = []
        
        # Non-payment intents get approved by default
        if intent.intent_type != IntentType.PAYMENT:
            return PolicyResult(
                decision=PolicyDecision.APPROVE,
                reason=f"{intent.intent_type.value} intent - no payment policy required",
                risk_score=0.0,
                passed_rules=["non_payment_intent"],
                evaluation_time_ms=(time.time() - start_time) * 1000,
            )
        
        # Evaluate all rules
        for rule in self.rules:
            passed, violation = rule.evaluate(intent, user_context, merchant_context)
            
            if passed:
                passed_rules.append(rule.name)
            else:
                violations.append(violation)
                logger.warning(f"Rule '{rule.name}' failed: {violation.message}")
        
        # Determine decision based on violations
        decision, reason = self._determine_decision(violations)
        risk_score = self._calculate_risk_score(violations, passed_rules)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        result = PolicyResult(
            decision=decision,
            reason=reason,
            risk_score=risk_score,
            violations=violations,
            passed_rules=passed_rules,
            evaluation_time_ms=elapsed_ms,
        )
        
        # Log to Audit Ledger if available
        if self.ledger:
            self.ledger.log_event(
                event_type=EventType.POLICY_EVALUATED,
                payload={
                    "intent": intent.model_dump(mode='json'),
                    "decision": decision.value,
                    "reason": reason,
                    "risk_score": risk_score,
                    "violations": [v.model_dump(mode='json') for v in violations],
                    "evaluation_time_ms": elapsed_ms,
                }
            )
        
        logger.info(f"Policy evaluation complete: {decision.value} (risk: {risk_score:.2f})")
        return result
    
    def _determine_decision(
        self,
        violations: List[RuleViolation],
    ) -> tuple[PolicyDecision, str]:
        """Determine the final decision based on violations."""
        if not violations:
            return PolicyDecision.APPROVE, "All policy checks passed"
        
        # Check for hard invariant violations (Layer 1) - instant DENY
        hard_violations = [v for v in violations if v.category == RuleCategory.HARD_INVARIANT]
        if hard_violations:
            return (
                PolicyDecision.DENY,
                f"Hard limit violated: {hard_violations[0].message}"
            )
        
        # Check for velocity violations (Layer 2) - COOLDOWN
        velocity_violations = [v for v in violations if v.category == RuleCategory.VELOCITY]
        if velocity_violations:
            return (
                PolicyDecision.COOLDOWN,
                f"Rate limit exceeded: {velocity_violations[0].message}"
            )
        
        # Check for threat/behavioral violations (Layer 3-4) - ESCALATE
        threat_violations = [v for v in violations if v.category in [
            RuleCategory.THREAT_DEFENSE,
            RuleCategory.BEHAVIORAL,
        ]]
        if threat_violations:
            return (
                PolicyDecision.ESCALATE,
                f"Suspicious activity: {threat_violations[0].message}"
            )
        
        # Fallback - shouldn't happen
        return PolicyDecision.DENY, "Unknown violation type"
    
    def _calculate_risk_score(
        self,
        violations: List[RuleViolation],
        passed_rules: List[str],
    ) -> float:
        """Calculate a risk score from 0.0 (safe) to 1.0 (risky)."""
        if not violations:
            return 0.0
        
        # Weight based on severity
        severity_weights = {
            "critical": 1.0,
            "high": 0.7,
            "medium": 0.4,
            "low": 0.2,
        }
        
        total_risk = sum(
            severity_weights.get(v.severity, 0.5)
            for v in violations
        )
        
        # Normalize to 0-1 range
        return min(1.0, total_risk / max(1, len(self.rules) * 0.3))
