import asyncio
import logging
import httpx
from caps.server import caps, process_command, CommandRequest
from caps.context.models import UserContext, MerchantContext
from caps.policy import PolicyDecision
from caps.schema import PaymentIntent, IntentType

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SystemVerifier")

CONTEXT_SERVICE_URL = "http://127.0.0.1:8001"

async def verify_context_service():
    """Verify Context Service is reachable and serving data."""
    logger.info("🔍 Verifying Context Service...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        # Test User Context
        try:
            resp = await client.get(f"{CONTEXT_SERVICE_URL}/context/user/user_test")
            resp.raise_for_status()
            user = resp.json()
            if user['user_id'] == 'user_test':
                 logger.info("✅ Context Service: User 'user_test' found.")
            else:
                 logger.error(f"❌ Context Service: User ID mismatch. Got {user.get('user_id')}")
                 return False
        except Exception as e:
            logger.error(f"❌ Context Service: Failed to get user. {e}")
            return False

        # Test Merchant Context
        try:
             resp = await client.get(f"{CONTEXT_SERVICE_URL}/context/merchant/canteen@vit")
             resp.raise_for_status()
             logger.info("✅ Context Service: Merchant 'canteen@vit' found.")
        except Exception as e:
             logger.error(f"❌ Context Service: Failed to get merchant. {e}")
             return False
             
    return True

async def verify_intent_interpreter():
    """Verify Local LLM (Ollama) is working."""
    logger.info("🔍 Verifying Intent Interpreter (Ollama)...")
    try:
        req = CommandRequest(text="pay Arihant 50", user_id="user_test")
        intent_data = await caps.interpreter.interpret(req.text)
        
        if intent_data.get("intent_type") == "PAYMENT" and intent_data.get("amount") == 50:
             logger.info("✅ Intent Interpreter: Correctly parsed 'pay Arihant 50'.")
             return True
        elif intent_data.get("error"):
             logger.error(f"❌ Intent Interpreter: Failed closed with error: {intent_data['error']}")
             return False
        else:
             logger.error(f"❌ Intent Interpreter: Incorrect parsing: {intent_data}")
             return False
    except Exception as e:
        logger.error(f"❌ Intent Interpreter: Exception: {e}")
        return False

async def verify_policy_engine(user_id="user_test"):
    """Verify Policy Engine using real context data."""
    logger.info("🔍 Verifying Policy Engine...")
    
    # 1. Fetch real context first
    async with httpx.AsyncClient() as client:
        u_resp = await client.get(f"{CONTEXT_SERVICE_URL}/context/user/{user_id}")
        user_data = u_resp.json()
        user_ctx = UserContext(**user_data)
        
        m_resp = await client.get(f"{CONTEXT_SERVICE_URL}/context/merchant/canteen@vit")
        merchant_data = m_resp.json()
        merchant_ctx = MerchantContext(**merchant_data)
        
    # Test 1: Safe Transaction (Should Approve)
    logger.info("   Testing Safe Transaction (50 INR)...")
    intent_safe = PaymentIntent(
        intent_type=IntentType.PAYMENT, 
        amount=50.0, 
        merchant_vpa="canteen@vit", 
        confidence_score=1.0, 
        raw_input="test safe"
    )
    
    decision = caps.policy_engine.evaluate(
        intent=intent_safe,
        user_context=user_ctx,
        merchant_context=merchant_ctx,
    )
    
    if decision.decision == PolicyDecision.APPROVE:
        logger.info("✅ Policy Engine: Approved safe transaction.")
    else:
        logger.error(f"❌ Policy Engine: Denied safe transaction. Reason: {decision.reason}")
        return False

    # Test 2: Unsafe Transaction (High Value > Limit)
    logger.info("   Testing High Value Transaction (5000 INR)...")
    intent_risky = PaymentIntent(
        intent_type=IntentType.PAYMENT, 
        amount=5000.0, 
        merchant_vpa="canteen@vit", 
        confidence_score=1.0, 
        raw_input="test risk"
    )
    
    decision_high = caps.policy_engine.evaluate(
        intent=intent_risky,
        user_context=user_ctx,
        merchant_context=merchant_ctx,
    )
    
    if decision_high.decision == PolicyDecision.DENY:
        logger.info("✅ Policy Engine: Denied high value transaction (Balance/Limit Check).")
    else:
        logger.error(f"❌ Policy Engine: Incorrectly approved high value transactions! {decision_high.decision}")
        return False

    return True

async def main():
    print("="*60)
    print("🚀 CAPS System Integrity v1.0")
    print("="*60)
    
    # 1. Verify Context
    if not await verify_context_service():
        print("\n❌ ABORTING: Context Service is down or broken.")
        return
        
    # 2. Verify Intent
    if not await verify_intent_interpreter():
        print("\n❌ ABORTING: Intent Interpreter is failing.")
        return

    # 3. Verify Policy
    if not await verify_policy_engine():
        print("\n❌ ABORTING: Policy Engine logic is flawed.")
        return
        
    print("\n" + "="*60)
    print("✅✅✅ SYSTEM INTEGRITY VERIFIED successfully!")
    print("All components are wired and functioning correctly.")
    print("You may now run the main demo.")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(main())
