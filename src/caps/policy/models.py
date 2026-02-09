"""Policy decision models."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class PolicyDecision(str, Enum):
    """Policy evaluation decision types."""
    
    APPROVE = "APPROVE"      # All checks pass, execute payment
    DENY = "DENY"            # Hard invariant failed, block payment
    COOLDOWN = "COOLDOWN"    # Velocity limit hit, wait required
    ESCALATE = "ESCALATE"    # Suspicious pattern, require verification


class RuleCategory(str, Enum):
    """Categories of policy rules."""
    
    HARD_INVARIANT = "HARD_INVARIANT"      # Layer 1: Must pass or DENY
    VELOCITY = "VELOCITY"                   # Layer 2: Rate limiting
    THREAT_DEFENSE = "THREAT_DEFENSE"       # Layer 3: Agentic attacks
    BEHAVIORAL = "BEHAVIORAL"               # Layer 4: Anomaly detection


class RuleViolation(BaseModel):
    """Details of a rule violation."""
    
    rule_name: str = Field(description="Name of the violated rule")
    category: RuleCategory = Field(description="Category of the rule")
    message: str = Field(description="Human-readable violation message")
    severity: str = Field(description="Severity: critical, high, medium, low")
    details: Optional[dict] = Field(default=None, description="Additional details")


class PolicyResult(BaseModel):
    """Complete result of policy evaluation."""
    
    decision: PolicyDecision = Field(description="Final policy decision")
    reason: str = Field(description="Human-readable explanation")
    risk_score: float = Field(ge=0.0, le=1.0, description="Risk score (0=safe, 1=risky)")
    violations: List[RuleViolation] = Field(default_factory=list, description="List of violations")
    passed_rules: List[str] = Field(default_factory=list, description="Rules that passed")
    
    # Timing
    evaluation_time_ms: float = Field(default=0.0, description="Time to evaluate (ms)")
    
    @property
    def is_approved(self) -> bool:
        """Check if payment is approved."""
        return self.decision == PolicyDecision.APPROVE
    
    @property
    def is_denied(self) -> bool:
        """Check if payment is denied."""
        return self.decision == PolicyDecision.DENY
    
    @property
    def requires_action(self) -> bool:
        """Check if action is required (cooldown or escalation)."""
        return self.decision in [PolicyDecision.COOLDOWN, PolicyDecision.ESCALATE]
