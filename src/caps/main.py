"""
CAPS Main Entry Point

Simple CLI demo for Phase 1-2: Foundation & Context Engineering

This demonstrates the end-to-end flow:
1. Accept natural language input
2. LLM interprets to JSON (untrusted)
3. Schema validator enforces strict typing (Trust Gate 1)
4. Context service provides ground truth (NEW in Phase 2)
5. Output validated intent + context
"""

import logging
import os
import sys
from dotenv import load_dotenv

from caps.agent import IntentInterpreter
from caps.schema import SchemaValidator, ValidationError, IntentType
from caps.context import ContextClient
from caps.context.config import config as context_config


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def print_banner():
    """Print CAPS banner."""
    print("\n" + "=" * 60)
    print("  CAPS: Context-Aware Agentic Payment System")
    print("  Phase 2 Demo - Intent Interpreter + Context Service")
    print("=" * 60 + "\n")


def main():
    """Main CLI application."""
    # Load environment variables
    load_dotenv()

    # Check for API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ Error: GOOGLE_API_KEY not found in environment")
        print("Please create a .env file with your API key:")
        print("  cp .env.example .env")
        print("  # Edit .env and add your API key")
        sys.exit(1)

    print_banner()

    # Initialize components
    try:
        logger.info("Initializing Intent Interpreter...")
        interpreter = IntentInterpreter(api_key=api_key)
        
        logger.info("Initializing Schema Validator...")
        validator = SchemaValidator()
        
        logger.info("Initializing Context Client...")
        context_client = ContextClient()
        
        print("✅ System initialized successfully!")
        print(f"🌐 Context service: http://{context_config.host}:{context_config.port}")
        print("\n⚠️  Make sure context service is running:")
        print("    python3 scripts/run_context_service.py\n")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

    # Interactive loop
    print("Enter payment requests (or 'quit' to exit):\n")
    
    while True:
        try:
            # Get user input
            user_input = input("💬 You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break

            print()  # Blank line for readability

            # Step 1: LLM Interpretation (Untrusted)
            print("🤖 [LLM] Interpreting intent...")
            raw_intent = interpreter.interpret_sync(user_input)
            
            print(f"    Raw output: {raw_intent.get('intent_type')}")
            print(f"    Confidence: {raw_intent.get('confidence_score', 0):.2f}")
            
            # Step 2: Schema Validation (Trust Gate 1)
            print("\n🔒 [Validator] Checking schema...")
            validated_intent, error = validator.validate_safe(raw_intent)
            
            if error:
                print(f"    ❌ Validation failed!")
                print(f"    Error: {error.message}")
                if error.errors:
                    for err in error.errors:
                        print(f"      - {err.get('field')}: {err.get('msg')}")
                print("\n" + "-" * 60 + "\n")
                continue
            
            print(f"    ✅ Schema validation passed!")
            
            # Step 3: Context Fetching (NEW - Phase 2)
            print("\n🌐 [Context Service] Fetching ground truth...")
            
            try:
                # Fetch user context
                user_context = context_client.get_user_context_sync(context_config.default_user_id)
                print(f"    ✅ User context retrieved")
                
                # Fetch merchant context if it's a payment
                merchant_context = None
                if validated_intent.intent_type == IntentType.PAYMENT and validated_intent.merchant_vpa:
                    merchant_context = context_client.get_merchant_context_sync(validated_intent.merchant_vpa)
                    print(f"    ✅ Merchant context retrieved")
                
            except Exception as e:
                print(f"    ⚠️  Context service unavailable: {e}")
                print(f"    Continuing without context...")
                user_context = None
                merchant_context = None
            
            # Display validated intent
            print("\n📋 [Result] Validated Payment Intent:")
            print(f"    Intent ID: {validated_intent.intent_id}")
            print(f"    Type: {validated_intent.intent_type.value}")
            
            if validated_intent.amount:
                print(f"    Amount: {validated_intent.currency.value} {validated_intent.amount:.2f}")
            
            if validated_intent.merchant_vpa:
                print(f"    Merchant: {validated_intent.merchant_vpa}")
            
            print(f"    Confidence: {validated_intent.confidence_score:.2f}")
            
            # Display user context (NEW)
            if user_context:
                print("\n👤 [User Context]:")
                print(f"    Wallet Balance: ₹{user_context.wallet_balance:.2f}")
                print(f"    Daily Spend: ₹{user_context.daily_spend_today:.2f} / ₹2000")
                print(f"    Transactions (5 min): {user_context.transactions_last_5min} / 10")
                print(f"    Device: {'Known' if user_context.is_known_device else 'New (⚠️ )'}")
                print(f"    Location: {user_context.location}")
            
            # Display merchant context (NEW)
            if merchant_context:
                print("\n🏪 [Merchant Context]:")
                print(f"    Reputation: {merchant_context.reputation_score:.2f} / 1.0")
                print(f"    Whitelisted: {'✅' if merchant_context.is_whitelisted else '❌'}")
                print(f"    Transactions: {merchant_context.total_transactions}")
                print(f"    Refund Rate: {merchant_context.refund_rate:.1%}")
                
                if merchant_context.fraud_reports > 0:
                    print(f"    ⚠️  Fraud Reports: {merchant_context.fraud_reports}")
            
            # Show what would happen next
            if validated_intent.confidence_score < 0.5:
                print("\n⚠️  Low confidence - would require user confirmation")
            elif validated_intent.intent_type == IntentType.PAYMENT:
                print("\n➡️  Next: Would pass (Intent + Context) to Policy Engine")
                
                # Show policy hints based on context
                if user_context:
                    if validated_intent.amount and validated_intent.amount > user_context.wallet_balance:
                        print("    ❌ Likely DENY: Insufficient balance")
                    elif validated_intent.amount and validated_intent.amount > 500:
                        print("    ❌ Likely DENY: Exceeds UPI Lite limit (₹500)")
                    elif user_context.transactions_last_5min >= 10:
                        print("    ⚠️  Likely COOLDOWN: Velocity limit reached")
                    elif merchant_context and merchant_context.reputation_score < 0.3:
                        print("    ⚠️  Likely ESCALATE: Low merchant reputation")
                    else:
                        print("    ✅ Likely APPROVE: All checks would pass")
            else:
                print(f"\n➡️  Next: Would handle {validated_intent.intent_type.value}")

            print("\n" + "-" * 60 + "\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            logger.exception("Unexpected error in main loop")
            print()


if __name__ == "__main__":
    main()
