"""
CAPS API Server - Phase 7
Exposes the CAPS payment processing logic via REST API for frontend integration.
"""

import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables (API keys)
load_dotenv()

from caps.agent import IntentInterpreter
from caps.schema import PaymentIntent, SchemaValidator
from caps.context.context_service import ContextService
from caps.policy import PolicyEngine
from caps.execution import DecisionRouter, ExecutionEngine
from caps.memory import SessionMemory
from caps.ledger import AuditLedger
from caps.intelligence import FraudIntelligence

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI App
app = FastAPI(title="CAPS API", version="0.7.0")

# CORS middleware
origins = [
    "http://localhost:5173",  # Vite dev server
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


# Initialize CAPS Components (Singletons)
class CAPSContainer:
    def __init__(self):
        self.ledger = AuditLedger()
        self.memory = SessionMemory()
        self.context_service = ContextService()  # Direct service call (Monolith)
        self.fraud_intelligence = FraudIntelligence()
        self.validator = SchemaValidator()
        
        self.policy_engine = PolicyEngine()
        self.execution_engine = ExecutionEngine(ledger=self.ledger, context_service=self.context_service)
        self.router = DecisionRouter()
        
        self.interpreter = IntentInterpreter()
        
        logger.info("CAPS Components Initialized")


caps = CAPSContainer()


# Routes
@app.get("/")
async def root():
    return {"status": "online", "system": "CAPS"}


@app.get("/context/{user_id}")
async def get_context(user_id: str):
    """Debug endpoint to see user context"""
    ctx = caps.context_service.get_user_context(user_id)
    return ctx.model_dump() if ctx else {"error": "User not found"}


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
                intent=intent_data
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
        return CommandResponse(status="error", message=f"System Error: {str(e)}")

    # 2. Schema Validation (Trust Gate 1)
    validated_intent, error = caps.validator.validate_safe(intent_data)
    
    if error:
        logger.warning(f"Schema validation failed: {error.message}")
        # Record bad turn
        caps.memory.add_user_turn(req.text, intent_type="UNKNOWN")
        return CommandResponse(
            status="error", 
            message=f"I couldn't understand that clearly. {error.message}",
            intent=intent_data
        )

    intent = validated_intent # Use the Pydantic model from now on

    # Record user turn in memory
    caps.memory.add_user_turn(
        req.text,
        intent_type=intent.intent_type.value if hasattr(intent.intent_type, 'value') else intent.intent_type,
        amount=intent.amount,
        merchant_vpa=intent.merchant_vpa
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
    if intent.merchant_vpa:
        merchant_ctx = caps.context_service.get_merchant_context(intent.merchant_vpa)

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
            "violations": [v.message for v in policy_result.violations]
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
