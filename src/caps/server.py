"""
CAPS API Server - Phase 7
Exposes the CAPS payment processing logic via REST API for frontend integration.
"""

import logging
from datetime import datetime, timedelta, UTC
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables (API keys)
load_dotenv()

from caps.agent import IntentInterpreter
from caps.schema import PaymentIntent, SchemaValidator, IntentType
from caps.context.context_service import ContextService
from caps.policy import PolicyEngine
from caps.execution import DecisionRouter, ExecutionEngine
from caps.memory import SessionMemory
from caps.ledger import AuditLedger
from caps.intelligence import FraudIntelligence
from caps.intelligence.models import ReportType, MerchantBadge, MerchantRiskState, get_badge_emoji

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(title="CAPS API", version="0.7.0")

# CORS middleware
origins = [
    "http://localhost:5173",  # Vite dev server
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Data Models
class CommandRequest(BaseModel):
    text: str
    user_id: str = "user_default"


class CommandResponse(BaseModel):
    status: str
    message: str
    intent: Optional[Dict[str, Any]] = None
    policy_decision: Optional[str] = None
    execution_result: Optional[Dict[str, Any]] = None
    risk_info: Optional[Dict[str, Any]] = None
    context_used: Optional[Dict[str, Any]] = None
    user_state: Optional[Dict[str, Any]] = None
    fraud_intel: Optional[Dict[str, Any]] = None


class ReportRequest(BaseModel):
    merchant_vpa: str
    report_type: str = Field(description="SCAM, SUSPICIOUS, or LEGITIMATE")
    reason: Optional[str] = None
    user_id: str = "user_default"


# Initialize CAPS Components (Singletons)
class CAPSContainer:
    def __init__(self):
        self.ledger = AuditLedger()
        self.memory = SessionMemory()
        self.fraud_intelligence = FraudIntelligence()
        self.context_service = ContextService(fraud_intelligence=self.fraud_intelligence)  # Share FI instance
        self.validator = SchemaValidator()
        
        self.policy_engine = PolicyEngine()
        self.execution_engine = ExecutionEngine(ledger=self.ledger, context_service=self.context_service)
        self.router = DecisionRouter()
        
        self.interpreter = IntentInterpreter()
        
        logger.info("CAPS Components Initialized")


caps = CAPSContainer()


# ── Seed Demo Fraud Intelligence Data ──────────────────────────────────
def seed_fraud_data():
    """Populate FraudIntelligence with realistic demo merchants."""
    fi = caps.fraud_intelligence
    demo_merchants = [
        # Confirmed scammers
        ("fakeshop99@upi", "SCAM", "Fake electronics store, never delivers products"),
        ("fakeshop99@upi", "SCAM", "Charged me but no delivery"),
        ("fakeshop99@upi", "SCAM", "Fraudulent seller"),
        ("lotterywin@upi", "SCAM", "Lottery scam - asked for advance fee"),
        ("lotterywin@upi", "SCAM", "Fake lottery prize claim"),
        ("lotterywin@upi", "SUSPICIOUS", "Received unsolicited payment request"),
        ("quickloan247@upi", "SCAM", "Fake loan app - stole personal data"),
        ("quickloan247@upi", "SCAM", "Charged processing fee, no loan disbursed"),
        # Cautionary merchants
        ("discountbazaar@upi", "SUSPICIOUS", "Product quality is very poor"),
        ("discountbazaar@upi", "LEGITIMATE", "Received order but took 2 weeks"),
        ("discountbazaar@upi", "SCAM", "Wrong item delivered, no refund"),
        ("cryptotrader@upi", "SUSPICIOUS", "Promises guaranteed returns"),
        ("cryptotrader@upi", "SCAM", "Lost money on fake crypto scheme"),
        ("cryptotrader@upi", "LEGITIMATE", "Small trade went fine"),
        # Safe merchants
        ("amazon@upi", "LEGITIMATE", "Fast delivery, genuine products"),
        ("amazon@upi", "LEGITIMATE", "Great service"),
        ("amazon@upi", "VERIFIED", "Verified by admin"),
        ("swiggy@upi", "LEGITIMATE", "Food delivery on time"),
        ("swiggy@upi", "LEGITIMATE", "Good service"),
        ("flipkart@upi", "LEGITIMATE", "Genuine products, easy returns"),
        ("flipkart@upi", "LEGITIMATE", "Trusted platform"),
        ("flipkart@upi", "LEGITIMATE", "Always reliable"),
        ("zomato@upi", "LEGITIMATE", "Great food delivery"),
        ("zomato@upi", "LEGITIMATE", "On-time every time"),
    ]
    for vpa, rtype, reason in demo_merchants:
        fi.report_merchant(
            merchant_vpa=vpa,
            reporter_id=f"user_{hash(vpa + reason) % 1000:03d}",
            report_type=ReportType(rtype),
            reason=reason,
        )
    # Mark confirmed scammers via admin
    fi.verify_merchant_as_scam("fakeshop99@upi", "admin")
    fi.verify_merchant_as_scam("lotterywin@upi", "admin")
    fi.verify_merchant_as_scam("quickloan247@upi", "admin")
    fi.verify_merchant_as_scam("discountbazaar@upi", "admin")
    # Mark safe merchants
    fi.verify_merchant_as_safe("amazon@upi", "admin")
    fi.verify_merchant_as_safe("flipkart@upi", "admin")
    logger.info("Fraud Intelligence seeded with demo data")

seed_fraud_data()


# Routes
@app.get("/")
async def root():
    return {"status": "online", "system": "CAPS"}


@app.get("/context/{user_id}")
async def get_context(user_id: str):
    """Debug endpoint to see user context"""
    ctx = caps.context_service.get_user_context(user_id)
    return ctx.model_dump() if ctx else {"error": "User not found"}


@app.get("/user-state/{user_id}")
async def get_user_state_endpoint(user_id: str):
    """Get current user state (balance, spend, transactions) for frontend display."""
    u_ctx = caps.context_service.get_user_context(user_id)
    if not u_ctx:
        from caps.context.mock_data import get_default_user
        u_ctx = get_default_user()
        u_ctx.user_id = user_id
    
    recent_txns = caps.execution_engine.get_transaction_history(user_id)
    return {
        "balance": u_ctx.wallet_balance,
        "daily_spend": u_ctx.daily_spend_today,
        "daily_limit": 2000.0,
        "trust_score": u_ctx.trust_score,
        "recent_transactions": [
            {
                "merchant": t.merchant_vpa,
                "amount": t.amount,
                "status": t.state.value,
                "timestamp": t.created_at.isoformat() if t.created_at else None
            } for t in recent_txns[:10]
        ]
    }


# Helper to get current user state
def get_user_state(uid: str):
    u_ctx = caps.context_service.get_user_context(uid)
    if not u_ctx:
        from caps.context.mock_data import get_default_user
        u_ctx = get_default_user()
    
    # Get recent transactions
    recent_txns = caps.execution_engine.get_transaction_history(uid)
    return {
        "balance": u_ctx.wallet_balance,
        "daily_spend": u_ctx.daily_spend_today,
        "daily_limit": 2000.0, # Hardcoded for now, ideal matches rule
        "trust_score": u_ctx.trust_score,
        "recent_transactions": [
            {
                "merchant": t.merchant_vpa,
                "amount": t.amount,
                "status": t.state.value,
                "timestamp": t.created_at.isoformat() if t.created_at else None
            } for t in recent_txns[:10] # Return top 10 for better history
        ]
    }


@app.post("/process-command", response_model=CommandResponse)
async def process_command(req: CommandRequest):
    """
    Process a natural language command through the CAPS pipeline.
    """
    logger.info(f"Received command: {req.text} from {req.user_id}")
    
    # 0. Session Memory - Resolve references
    resolved = caps.memory.resolve_reference(req.text)
    enhanced_text = req.text
    
    # Simple replacement logic to help LLM
    if resolved.get("merchant_vpa"):
        # If we have a resolved merchant, append it to the text to ensure LLM sees it
        # regardless of specific phrasing
        enhanced_text = f"{req.text} (merchant: {resolved['merchant_vpa']})"
        
    if resolved.get("amount"):
        enhanced_text = f"{enhanced_text} (amount: {resolved['amount']})"
        
    logger.info(f"Enhanced input: {enhanced_text}")

    # 1. Intent Interpretation
    try:
        intent_data = await caps.interpreter.interpret(enhanced_text)
        
        # Check for Fail-Closed Error
        if intent_data.get("error"):
            logger.warning(f"Intent Interpreter unavailable: {intent_data['error']}")
            return CommandResponse(
                status="error",
                message="Service temporarily unavailable (Rate Limit). Please try again in a moment.",
                intent=intent_data,
                user_state=get_user_state(req.user_id)
            )

        # Merge resolved memory if LLM missed it
        if resolved.get("merchant_vpa") and not intent_data.get("merchant_vpa"):
            intent_data["merchant_vpa"] = resolved["merchant_vpa"]
            logger.info(f"Injected memory merchant: {resolved['merchant_vpa']}")
            
        if resolved.get("amount") and not intent_data.get("amount"):
            intent_data["amount"] = resolved["amount"]
            logger.info(f"Injected memory amount: {resolved['amount']}")

    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        # Return graceful error instead of 500
        return CommandResponse(
            status="error", 
            message=f"System Error: {str(e)}",
            user_state=get_user_state(req.user_id)
        )

    # 2. Schema Validation (Trust Gate 1)
    validated_intent, error = caps.validator.validate_safe(intent_data)
    
    if error:
        logger.warning(f"Schema validation failed: {error.message}")
        # Record bad turn
        caps.memory.add_user_turn(req.text, intent_type="UNKNOWN")
        return CommandResponse(
            status="error", 
            message=f"I couldn't understand that clearly. {error.message}",
            intent=intent_data,
            user_state=get_user_state(req.user_id),
            context_used=resolved if resolved else None
        )

    intent = validated_intent # Use the Pydantic model from now on

    # Record user turn in memory
    caps.memory.add_user_turn(
        req.text,
        intent_type=intent.intent_type.value if hasattr(intent.intent_type, 'value') else intent.intent_type,
        amount=intent.amount,
        merchant_vpa=intent.merchant_vpa
    )

    # HANDLE NON-PAYMENT INTENTS
    if intent.intent_type == IntentType.BALANCE_INQUIRY:
        user_ctx = caps.context_service.get_user_context(req.user_id)
        if not user_ctx:
            # Create default context if missing
            from caps.context.mock_data import get_default_user
            user_ctx = get_default_user()
            
        return CommandResponse(
            status="processed",
            message="Balance Inquiry",
            intent=intent.model_dump(),
            policy_decision="APPROVE",
            execution_result={
                "balance": user_ctx.wallet_balance,
                "daily_spend": user_ctx.daily_spend_today,
                "currency": "INR"
            },
            user_state=get_user_state(req.user_id),
            context_used=resolved if resolved else None
        )

    if intent.intent_type == IntentType.TRANSACTION_HISTORY:
        history = caps.execution_engine.get_transaction_history(req.user_id)
        history_data = [
            {
                "transaction_id": txn.transaction_id,
                "amount": txn.amount,
                "merchant_vpa": txn.merchant_vpa,
                "state": txn.state.value,
                "timestamp": txn.created_at.isoformat() if txn.created_at else None
            }
            for txn in history
        ]
        return CommandResponse(
            status="processed",
            message="Transaction History",
            intent=intent.model_dump(),
            policy_decision="APPROVE",
            execution_result={
                "history": history_data
            },
            user_state=get_user_state(req.user_id),
            context_used=resolved if resolved else None
        )

    # 3. Context Retrieval (Direct sync call)
    user_ctx = caps.context_service.get_user_context(req.user_id)
    if not user_ctx:
        # Create default context if missing
        from caps.context.mock_data import get_default_user
        user_ctx = get_default_user()
        user_ctx.user_id = req.user_id

    # We need to fetch merchant context if it's a payment
    merchant_ctx = None
    merchant_intel = None
    fraud_intel_dict = None
    if intent.merchant_vpa:
        merchant_ctx = caps.context_service.get_merchant_context(intent.merchant_vpa)
        
        # 3.5 Fraud Intelligence Check
        merchant_intel = caps.fraud_intelligence.get_merchant_score(intent.merchant_vpa)
        fraud_intel_dict = {
            "merchant_vpa": merchant_intel.merchant_vpa,
            "badge": merchant_intel.badge.value,
            "badge_emoji": get_badge_emoji(merchant_intel.badge),
            "community_score": merchant_intel.community_score,
            "scam_rate": round(merchant_intel.scam_rate * 100, 1),
            "total_reports": merchant_intel.total_reports,
            "scam_reports": merchant_intel.scam_reports,
            "risk_state": merchant_intel.risk_state.value,
        }
        
        # HARD BLOCK: Deny payment to scam/blocked merchants
        blocked_badges = {MerchantBadge.CONFIRMED_SCAM, MerchantBadge.LIKELY_SCAM}
        if merchant_intel.badge in blocked_badges or merchant_intel.risk_state == MerchantRiskState.BLOCKED:
            logger.warning(f"BLOCKED payment to {intent.merchant_vpa}: badge={merchant_intel.badge.value}, risk={merchant_intel.risk_state.value}")
            return CommandResponse(
                status="blocked",
                message=f"Payment BLOCKED: {intent.merchant_vpa} is flagged as {merchant_intel.badge.value} by the community. This merchant has a {fraud_intel_dict['scam_rate']}% scam rate across {merchant_intel.total_reports} reports.",
                intent=intent.model_dump(),
                policy_decision="DENY",
                fraud_intel=fraud_intel_dict,
                context_used=resolved if resolved else None,
                user_state=get_user_state(req.user_id)
            )
        
        # Build merchant context from fraud intelligence if context service has none
        # This ensures behavioral rules fire for merchants with scam reports
        if merchant_ctx is None and merchant_intel.total_reports > 0:
            from caps.context.models import MerchantContext
            risk_state_map = {
                "NEW": "NEW",
                "WATCHLIST": "WATCHLIST",
                "BLOCKED": "BLOCKED",
                "TRUSTED": "TRUSTED",
            }
            merchant_ctx = MerchantContext(
                merchant_vpa=intent.merchant_vpa,
                reputation_score=max(0.0, min(1.0, merchant_intel.community_score / 100.0)),
                is_whitelisted=False,
                total_transactions=0,
                successful_transactions=0,
                refund_rate=0.0,
                fraud_reports=merchant_intel.scam_reports,
                risk_state=risk_state_map.get(merchant_intel.risk_state.value, "NEW"),
            )
            logger.info(f"Built merchant context from fraud intel for {intent.merchant_vpa}: "
                       f"reputation={merchant_ctx.reputation_score:.2f}, "
                       f"fraud_reports={merchant_ctx.fraud_reports}, "
                       f"risk_state={merchant_ctx.risk_state}")

    # 4. Policy Evaluation
    policy_result = caps.policy_engine.evaluate(intent, user_ctx, merchant_ctx)
    
    # 5. Execution Routing
    execution_result_dict = None
    cmd_status = "processed"
    
    if policy_result.decision.value == "APPROVE":
        logger.info("Policy APPROVED. Executing transaction...")
        
        # Route: Create Transaction Record
        record = caps.router.route(intent, policy_result, req.user_id)
        
        # Execute
        exec_result = caps.execution_engine.execute(record)
        execution_result_dict = exec_result.__dict__
        
        if exec_result.success:
            cmd_status = "executed"
        else:
            cmd_status = "failed"
            
        # Record Payment Attempt in Memory
        caps.memory.record_payment_attempt(
            transaction_id=record.transaction_id,
            merchant_vpa=intent.merchant_vpa or "unknown",
            amount=intent.amount or 0.0,
            decision=policy_result.decision.value,
            success=exec_result.success,
            raw_input=req.text,
            reference_number=exec_result.reference_number
        )
            
    elif policy_result.decision.value == "DENY":
        cmd_status = "denied"
        # Just route to create denied record for logging
        caps.router.route(intent, policy_result, req.user_id)
        
        # Record Failed Payment Attempt in Memory
        caps.memory.record_payment_attempt(
            transaction_id="txn_denied", # Placeholder
            merchant_vpa=intent.merchant_vpa or "unknown",
            amount=intent.amount or 0.0,
            decision=policy_result.decision.value,
            success=False,
            raw_input=req.text
        )


    return CommandResponse(
        status=cmd_status,
        message=f"Processed: {intent.intent_type}",
        intent=intent.model_dump(),
        policy_decision=policy_result.decision.value,
        execution_result=execution_result_dict,
        risk_info={
            "score": policy_result.risk_score,
            "violations": [v.message for v in policy_result.violations],
            "passed_rules": policy_result.passed_rules,
            "reason": policy_result.reason
        },
        fraud_intel=fraud_intel_dict,
        context_used=resolved if resolved else None,
        user_state=get_user_state(req.user_id)
    )


# ── User-Approved Execution ───────────────────────────────────────────
class ApproveRequest(BaseModel):
    user_id: str
    merchant_vpa: str
    amount: float
    raw_input: str = ""

@app.post("/execute-approved", response_model=CommandResponse)
async def execute_approved(req: ApproveRequest):
    """Execute a payment that was escalated and approved by the user."""
    logger.info(f"User-approved execution: ₹{req.amount} → {req.merchant_vpa} from {req.user_id}")
    
    # Build intent directly (skip LLM — user already confirmed)
    intent = PaymentIntent(
        intent_type=IntentType.PAYMENT,
        merchant_vpa=req.merchant_vpa,
        amount=req.amount,
        raw_input=req.raw_input,
        confidence_score=1.0,  # User confirmed = full confidence
    )
    
    # Create an APPROVE policy result (user is the policy here)
    from caps.policy.models import PolicyResult, PolicyDecision
    policy_result = PolicyResult(
        decision=PolicyDecision.APPROVE,
        reason="User-approved after escalation",
        violations=[],
        passed_rules=["user_approval"],
        risk_score=0.0,
    )
    
    # Route and Execute
    record = caps.router.route(intent, policy_result, req.user_id)
    exec_result = caps.execution_engine.execute(record)
    
    cmd_status = "executed" if exec_result.success else "failed"
    
    # Record in session memory
    caps.memory.record_payment_attempt(
        transaction_id=record.transaction_id,
        merchant_vpa=req.merchant_vpa,
        amount=req.amount,
        decision="APPROVE",
        success=exec_result.success,
        raw_input=req.raw_input,
        reference_number=exec_result.reference_number
    )
    
    return CommandResponse(
        status=cmd_status,
        message=f"User-approved payment {'executed' if exec_result.success else 'failed'}",
        intent=intent.model_dump(),
        policy_decision="APPROVE",
        execution_result=exec_result.__dict__,
        user_state=get_user_state(req.user_id)
    )


# ── Fraud Intelligence Endpoints ───────────────────────────────────────
@app.get("/fraud/scammers")
async def get_scammers(limit: int = 20):
    """Get top scam-rated merchants with badges."""
    scammers = caps.fraud_intelligence.get_scam_merchants(limit=limit)
    # Also include cautionary merchants for a fuller picture
    conn = caps.fraud_intelligence._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM scores ORDER BY scam_rate DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    caps.fraud_intelligence._close_connection(conn)
    all_merchants = [caps.fraud_intelligence._row_to_score(row) for row in rows]
    
    return [
        {
            "merchant_vpa": m.merchant_vpa,
            "community_score": round(m.community_score, 2),
            "scam_rate": round(m.scam_rate * 100, 1),
            "badge": m.badge.value,
            "badge_emoji": get_badge_emoji(m.badge),
            "risk_state": m.risk_state.value,
            "total_reports": m.total_reports,
            "scam_reports": m.scam_reports,
            "legitimate_reports": m.legitimate_reports,
            "last_updated": m.last_updated.isoformat() if m.last_updated else None,
        }
        for m in all_merchants
    ]


@app.get("/fraud/merchant/{vpa}")
async def get_merchant_fraud_info(vpa: str):
    """Get detailed fraud score and recent reports for a merchant."""
    score = caps.fraud_intelligence.get_merchant_score(vpa)
    reports = caps.fraud_intelligence.get_reports_for_merchant(vpa, limit=10)
    
    return {
        "score": {
            "merchant_vpa": score.merchant_vpa,
            "community_score": round(score.community_score, 2),
            "scam_rate": round(score.scam_rate * 100, 1),
            "badge": score.badge.value,
            "badge_emoji": get_badge_emoji(score.badge),
            "risk_state": score.risk_state.value,
            "total_reports": score.total_reports,
            "scam_reports": score.scam_reports,
            "suspicious_reports": score.suspicious_reports,
            "legitimate_reports": score.legitimate_reports,
        },
        "reports": [
            {
                "report_id": r.report_id,
                "report_type": r.report_type.value,
                "reason": r.reason,
                "reporter_id": r.reporter_id,
                "timestamp": r.timestamp.isoformat() if r.timestamp else None,
                "verified": r.verified,
            }
            for r in reports
        ]
    }


@app.post("/fraud/report")
async def submit_fraud_report(req: ReportRequest):
    """Submit a crowdsourced fraud report about a merchant."""
    try:
        report_type = ReportType(req.report_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid report type: {req.report_type}. Use SCAM, SUSPICIOUS, or LEGITIMATE."
        )
    
    report = caps.fraud_intelligence.report_merchant(
        merchant_vpa=req.merchant_vpa,
        reporter_id=req.user_id,
        report_type=report_type,
        reason=req.reason,
    )
    
    # Get updated score after report
    updated_score = caps.fraud_intelligence.get_merchant_score(req.merchant_vpa)
    
    return {
        "status": "reported",
        "report_id": report.report_id,
        "updated_badge": updated_score.badge.value,
        "updated_badge_emoji": get_badge_emoji(updated_score.badge),
        "updated_score": round(updated_score.community_score, 2),
    }


@app.get("/fraud/stats")
async def get_fraud_stats():
    """Get summary fraud intelligence statistics."""
    conn = caps.fraud_intelligence._get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM reports")
    total_reports = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT merchant_vpa) FROM scores")
    total_merchants = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM scores WHERE badge IN ('LIKELY_SCAM', 'CONFIRMED_SCAM')")
    flagged_merchants = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM scores WHERE badge IN ('VERIFIED_SAFE', 'LIKELY_SAFE')")
    safe_merchants = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM reports WHERE report_type = 'SCAM'")
    scam_reports = cursor.fetchone()[0]
    
    caps.fraud_intelligence._close_connection(conn)
    
    return {
        "total_reports": total_reports,
        "total_merchants": total_merchants,
        "flagged_merchants": flagged_merchants,
        "safe_merchants": safe_merchants,
        "scam_reports": scam_reports,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
