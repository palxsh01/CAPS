"""
CAPS Main Entry Point

Simple CLI demo for Phase 1: Foundation & Agent Setup

This demonstrates the end-to-end flow:
1. Accept natural language input
2. LLM interprets to JSON (untrusted)
3. Schema validator enforces strict typing (Trust Gate 1)
4. Output validated intent
"""

import logging
import os
import sys
from dotenv import load_dotenv

from caps.agent import IntentInterpreter
from caps.schema import SchemaValidator, ValidationError


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
    print("  Phase 1 Demo - Intent Interpreter")
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
        
        print("✅ System initialized successfully!\n")
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
            else:
                print(f"    ✅ Schema validation passed!")
                
                # Display validated intent
                print("\n📋 [Result] Validated Payment Intent:")
                print(f"    Intent ID: {validated_intent.intent_id}")
                print(f"    Type: {validated_intent.intent_type.value}")
                
                if validated_intent.amount:
                    print(f"    Amount: {validated_intent.currency.value} {validated_intent.amount:.2f}")
                
                if validated_intent.merchant_vpa:
                    print(f"    Merchant: {validated_intent.merchant_vpa}")
                
                print(f"    Confidence: {validated_intent.confidence_score:.2f}")
                
                # Show what would happen next
                if validated_intent.confidence_score < 0.5:
                    print("\n⚠️  Low confidence - would require user confirmation")
                elif validated_intent.intent_type.value == "PAYMENT":
                    print("\n➡️  Next: Would pass to Policy Engine for approval")
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
