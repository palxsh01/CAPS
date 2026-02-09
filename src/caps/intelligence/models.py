"""Models for crowdsourced fraud intelligence."""

import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    """Types of merchant reports."""
    
    SCAM = "SCAM"                    # Confirmed scam
    SUSPICIOUS = "SUSPICIOUS"        # Suspicious behavior
    LEGITIMATE = "LEGITIMATE"        # Positive experience
    VERIFIED = "VERIFIED"            # Admin-verified safe


class MerchantBadge(str, Enum):
    """Badge assigned to merchants based on community reports."""
    
    VERIFIED_SAFE = "VERIFIED_SAFE"      # 🛡️ 100+ reports, <1% scam
    LIKELY_SAFE = "LIKELY_SAFE"          # ✅ 20+ reports, <5% scam
    UNKNOWN = "UNKNOWN"                   # ❓ Insufficient reports
    CAUTION = "CAUTION"                  # ⚠️ 5-20% scam rate
    LIKELY_SCAM = "LIKELY_SCAM"          # 🚨 >20% scam rate
    CONFIRMED_SCAM = "CONFIRMED_SCAM"    # ☠️ Admin-verified scam


class MerchantReport(BaseModel):
    """User report about a merchant."""
    
    report_id: str = Field(
        default_factory=lambda: f"report_{uuid.uuid4().hex[:12]}",
        description="Unique report ID"
    )
    merchant_vpa: str = Field(description="Merchant VPA being reported")
    reporter_id: str = Field(description="User who submitted report")
    report_type: ReportType = Field(description="Type of report")
    reason: Optional[str] = Field(default=None, description="Optional reason")
    
    # Link to transaction for verification
    transaction_id: Optional[str] = Field(default=None)
    transaction_hash: Optional[str] = Field(default=None)
    
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Admin fields
    verified: bool = Field(default=False, description="Admin verified")
    verified_by: Optional[str] = Field(default=None)


class MerchantScore(BaseModel):
    """Aggregated community score for a merchant."""
    
    merchant_vpa: str = Field(description="Merchant VPA")
    
    # Aggregate stats
    total_reports: int = Field(default=0)
    scam_reports: int = Field(default=0)
    suspicious_reports: int = Field(default=0)
    legitimate_reports: int = Field(default=0)
    verified_reports: int = Field(default=0)
    
    # Calculated score
    community_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="0.0 = definitely scam, 1.0 = definitely safe"
    )
    scam_rate: float = Field(default=0.0, description="Percentage of scam reports")
    
    # Badge
    badge: MerchantBadge = Field(default=MerchantBadge.UNKNOWN)
    
    # Metadata
    first_report: Optional[datetime] = Field(default=None)
    last_report: Optional[datetime] = Field(default=None)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))


def get_badge_emoji(badge: MerchantBadge) -> str:
    """Get emoji for badge display."""
    emojis = {
        MerchantBadge.VERIFIED_SAFE: "🛡️",
        MerchantBadge.LIKELY_SAFE: "✅",
        MerchantBadge.UNKNOWN: "❓",
        MerchantBadge.CAUTION: "⚠️",
        MerchantBadge.LIKELY_SCAM: "🚨",
        MerchantBadge.CONFIRMED_SCAM: "☠️",
    }
    return emojis.get(badge, "❓")
