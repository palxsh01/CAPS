"""
CAPS Main Entry Point

CLI demo for Phase 1-5: Complete Payment Pipeline with Memory & Intelligence

This demonstrates the end-to-end flow:
1. Accept natural language input
2. Session Memory resolves references ("that merchant", "same amount")
3. LLM interprets to JSON (untrusted)
4. Schema validator enforces strict typing (Trust Gate 1)
5. Context service provides ground truth
6. Fraud Intelligence provides merchant reputation
7. Policy engine makes deterministic decision (Trust Gate 2)
8. Decision router routes to execution path
9. Execution engine simulates UPI Lite payment
10. Audit Ledger logs all events immutably
"""

import logging
import os
import sys
from dotenv import load_dotenv

from caps.agent import IntentInterpreter
from caps.schema import SchemaValidator, IntentType
from caps.context import ContextClient
from caps.context.config import config as context_config
from caps.policy import PolicyEngine, PolicyDecision
from caps.execution import DecisionRouter, ExecutionEngine, ExecutionState
from caps.memory import SessionMemory
from caps.ledger import AuditLedger, EventType
from caps.intelligence import FraudIntelligence, ReportType, MerchantBadge
from caps.intelligence.models import get_badge_emoji
from caps.rag import TransactionRetriever


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
    print("  Phase 5 Demo - Memory, Intelligence & Auditing")
    print("=" * 60 + "\n")


def print_decision(result):
    """Print policy decision with color coding."""
    decision = result.decision
    
    if decision == PolicyDecision.APPROVE:
        symbol = "✅"
        color_start = "\033[92m"  # Green
    elif decision == PolicyDecision.DENY:
        symbol = "❌"
        color_start = "\033[91m"  # Red
    elif decision == PolicyDecision.COOLDOWN:
        symbol = "⏳"
        color_start = "\033[93m"  # Yellow
    else:  # ESCALATE
        symbol = "⚠️"
        color_start = "\033[93m"  # Yellow
    
    color_end = "\033[0m"
    
    print(f"\n{color_start}🔐 [Policy Decision] {symbol} {decision.value}{color_end}")
    print(f"    Reason: {result.reason}")
    print(f"    Risk Score: {result.risk_score:.2f}")
    
    if result.violations:
        print(f"\n    Violations ({len(result.violations)}):")
        for v in result.violations:
            print(f"      - [{v.severity.upper()}] {v.rule_name}: {v.message}")


def print_execution_result(result):
    """Print execution result with color coding."""
    if result.success:
        color_start = "\033[92m"  # Green
        symbol = "✅"
    else:
        color_start = "\033[91m"  # Red
        symbol = "❌"
    
    color_end = "\033[0m"
    
    print(f"\n{color_start}💸 [Execution Result] {symbol} {result.state.value}{color_end}")
    print(f"    {result.message}")
    
    if result.success:
        print(f"    Transaction ID: {result.transaction_id}")
        print(f"    UPI Reference: {result.reference_number}")
        print(f"    Execution Hash: {result.execution_hash}")
    else:
        if result.error_code:
            print(f"    Error: {result.error_code} - {result.error_message}")


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
        # interpreter = IntentInterpreter(api_key=api_key)
        # Updated for Ollama (local LLM)
        interpreter = IntentInterpreter()
        
        logger.info("Initializing Schema Validator...")
        validator = SchemaValidator()
        
        logger.info("Initializing Context Client...")
        context_client = ContextClient()
        
        # Initialize Audit Ledger early for injection
        logger.info("Initializing Audit Ledger...")
        audit_ledger = AuditLedger()
        
        logger.info("Initializing Policy Engine...")
        policy_engine = PolicyEngine(ledger=audit_ledger)
        
        logger.info("Initializing Decision Router...")
        router = DecisionRouter()
        
        logger.info("Initializing Execution Engine...")
        execution_engine = ExecutionEngine(
            failure_rate=0.05, 
            ledger=audit_ledger,
            context_service=context_client
        )
        
        # Phase 5: Memory, Intelligence, Auditing, Security
        logger.info("Initializing Session Memory...")
        session_memory = SessionMemory()
        
        logger.info("Initializing Fraud Intelligence...")
        fraud_intel = FraudIntelligence()

        logger.info("Initializing RAG Retriever...")
        rag_retriever = TransactionRetriever(api_key=api_key)
        
        logger.info("Initializing Consent Manager...")
        from caps.security.consent import ConsentManager
        consent_manager = ConsentManager()
        
        print("✅ System initialized successfully!")
        print(f"🌐 Context service: http://{context_config.host}:{context_config.port}")
        print(f"🔐 Policy Engine: {len(policy_engine.rules)} rules loaded")
        print(f"💸 Execution Engine: Ready")
        print(f"🧠 Session Memory: Active")
        print(f"📒 Audit Ledger: Ready (hash-chained)")
        print(f"🛡️ Fraud Intelligence: Active")
        print(f"🔍 RAG Retriever: Active")
        print(f"🔑 Consent Manager: Active")
        print("\n⚠️  Make sure context service is running:")
        print("    python3 scripts/run_context_service.py\n")
    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        sys.exit(1)

    # Interactive loop
    print("Enter payment requests (or 'quit' to exit):")
    print("  Commands: history, ledger, search <query>, report <merchant> scam|safe\n")
    
    while True:
        try:
            # Get user input
            user_input = input("💬 You: ").strip()
            
            if not user_input:
                continue
                
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n👋 Goodbye!")
                break
            
            if user_input.lower() == "history":
                # Show transaction history
                history = execution_engine.get_transaction_history(context_config.default_user_id)
                if history:
                    print("\n📜 Transaction History:")
                    for txn in history:
                        print(f"    {txn.transaction_id}: ₹{txn.amount} → {txn.merchant_vpa} [{txn.state.value}]")
                else:
                    print("\n📜 No transactions yet.")
                print("\n" + "-" * 60 + "\n")
                continue
            
            if user_input.lower() == "ledger":
                # Show audit ledger
                entries = audit_ledger.get_recent_entries(10)
                if entries:
                    print("\n📒 Audit Ledger (recent 10):")
                    for e in entries:
                        print(f"    [{e.event_type.value}] {e.timestamp.strftime('%H:%M:%S')} - hash: {e.hash[:8]}...")
                    validation = audit_ledger.validate_chain()
                    status = "✅ Valid" if validation.is_valid else "❌ TAMPERED"
                    print(f"\n    Chain Status: {status} ({validation.total_entries} entries)")
                else:
                    print("\n📒 Audit ledger is empty.")
                print("\n" + "-" * 60 + "\n")
                continue
            
            if user_input.lower().startswith("report "):
                # Report merchant
                parts = user_input.split()
                if len(parts) >= 3:
                    merchant = parts[1]
                    report_type = parts[2].lower()
                    if report_type == "scam":
                        fraud_intel.report_merchant(merchant, context_config.default_user_id, ReportType.SCAM)
                        print(f"\n🚨 Reported {merchant} as SCAM")
                    elif report_type in ["safe", "legitimate"]:
                        fraud_intel.report_merchant(merchant, context_config.default_user_id, ReportType.LEGITIMATE)
                        print(f"\n✅ Reported {merchant} as LEGITIMATE")
                    else:
                        print("\n❌ Usage: report <merchant@vpa> scam|safe")
                else:
                    print("\n❌ Usage: report <merchant@vpa> scam|safe")
                print("\n" + "-" * 60 + "\n")
                continue
            
            if user_input.lower().startswith("reputation "):
                # Check merchant reputation
                parts = user_input.split()
                if len(parts) >= 2:
                    merchant = parts[1]
                    score = fraud_intel.get_merchant_score(merchant)
                    emoji = get_badge_emoji(score.badge)
                    print(f"\n🛡️ Merchant Reputation: {merchant}")
                    print(f"    Badge: {emoji} {score.badge.value}")
                    print(f"    Total Reports: {score.total_reports}")
                    print(f"    Scam Rate: {score.scam_rate:.1%}")
                    print(f"    Community Score: {score.community_score:.2f}")
                else:
                    print("\n❌ Usage: reputation <merchant@vpa>")
                print("\n" + "-" * 60 + "\n")
                continue

            print()  # Blank line for readability
            
            # Log intent received
            audit_ledger.append(
                EventType.INTENT_RECEIVED,
                {"raw_input": user_input},
                user_id=context_config.default_user_id,
                session_id=session_memory.session_id,
            )

            # Step 0: Session Memory - Resolve references
            resolved = session_memory.resolve_reference(user_input)
            if resolved.get("merchant_vpa") or resolved.get("amount"):
                print("🧠 [Session Memory] Resolving references...")
                if resolved.get("merchant_vpa"):
                    print(f"    'that merchant' → {resolved['merchant_vpa']}")
                if resolved.get("amount"):
                    print(f"    'same amount' → ₹{resolved['amount']:.2f}")
                print()
            
            # Enhance input with resolved references
            enhanced_input = user_input
            if resolved.get("merchant_vpa") and "that merchant" in user_input.lower():
                enhanced_input = user_input.replace("that merchant", resolved["merchant_vpa"])
            if resolved.get("merchant_vpa") and "previous merchant" in user_input.lower():
                enhanced_input = user_input.replace("previous merchant", resolved["merchant_vpa"])

            # Step 1: LLM Interpretation (Untrusted)
            print("🤖 [LLM] Interpreting intent...")
            raw_intent = interpreter.interpret_sync(enhanced_input)
            
            # Apply resolved references if LLM missed them
            if resolved.get("merchant_vpa") and not raw_intent.get("merchant_vpa"):
                raw_intent["merchant_vpa"] = resolved["merchant_vpa"]
            if resolved.get("amount") and not raw_intent.get("amount"):
                raw_intent["amount"] = resolved["amount"]
            
            print(f"    Raw output: {raw_intent.get('intent_type')}")
            print(f"    Confidence: {raw_intent.get('confidence_score', 0):.2f}")
            
            # Store conversation turn
            session_memory.add_user_turn(
                user_input,
                intent_type=raw_intent.get("intent_type"),
                amount=raw_intent.get("amount"),
                merchant_vpa=raw_intent.get("merchant_vpa"),
            )
            
            # Step 2: Schema Validation (Trust Gate 1)
            print("\n🔒 [Trust Gate 1] Schema Validation...")
            validated_intent, error = validator.validate_safe(raw_intent)
            
            if error:
                print(f"    ❌ Validation failed!")
                print(f"    Error: {error.message}")
                audit_ledger.append(
                    EventType.INTENT_REJECTED,
                    {"error": error.message},
                    user_id=context_config.default_user_id,
                )
                print("\n" + "-" * 60 + "\n")
                continue
            
            print(f"    ✅ Schema validation passed!")
            audit_ledger.append(
                EventType.INTENT_VALIDATED,
                {"intent_type": validated_intent.intent_type.value},
                user_id=context_config.default_user_id,
            )

            # Handle Non-Payment Intents
            if validated_intent.intent_type == IntentType.BALANCE_INQUIRY:
                try:
                    user_context = context_client.get_user_context_sync(context_config.default_user_id)
                    print(f"\n💰 [Balance Inquiry]")
                    print(f"    Wallet Balance: ₹{user_context.wallet_balance:.2f}")
                    print(f"    Daily Spend: ₹{user_context.daily_spend_today:.2f} / ₹{2000.00}") # Hardcoded limit for display
                except Exception as e:
                    print(f"    ❌ Failed to fetch balance: {e}")
                print("\n" + "-" * 60 + "\n")
                continue

            if validated_intent.intent_type == IntentType.TRANSACTION_HISTORY:
                history = execution_engine.get_transaction_history(context_config.default_user_id)
                if history:
                    print("\n📜 Transaction History:")
                    for txn in history:
                        print(f"    {txn.transaction_id}: ₹{txn.amount} → {txn.merchant_vpa} [{txn.state.value}]")
                else:
                    print("\n📜 No transactions yet.")
                print("\n" + "-" * 60 + "\n")
                continue
            
            # Step 3: Context Fetching
            print("\n🌐 [Context Service] Fetching ground truth...")
            
            user_context = None
            merchant_context = None
            
            try:
                user_context = context_client.get_user_context_sync(context_config.default_user_id)
                print(f"    ✅ User context retrieved")
                
                if validated_intent.intent_type == IntentType.PAYMENT and validated_intent.merchant_vpa:
                    merchant_context = context_client.get_merchant_context_sync(validated_intent.merchant_vpa)
                    print(f"    ✅ Merchant context retrieved")
                    
                    # Check fraud intelligence
                    intel_score = fraud_intel.get_merchant_score(validated_intent.merchant_vpa)
                    if intel_score.total_reports > 0:
                        emoji = get_badge_emoji(intel_score.badge)
                        print(f"    🛡️ Fraud Intel: {emoji} {intel_score.badge.value} ({intel_score.total_reports} reports)")
                
            except Exception as e:
                print(f"    ⚠️  Context service unavailable: {e}")
            
            audit_ledger.append(
                EventType.CONTEXT_FETCHED,
                {"user_id": context_config.default_user_id, "merchant_vpa": validated_intent.merchant_vpa},
                user_id=context_config.default_user_id,
            )
            
            # Display validated intent
            print("\n📋 [Validated Intent]:")
            print(f"    Type: {validated_intent.intent_type.value}")
            
            if validated_intent.amount:
                print(f"    Amount: {validated_intent.currency.value} {validated_intent.amount:.2f}")
            
            if validated_intent.merchant_vpa:
                print(f"    Merchant: {validated_intent.merchant_vpa}")
            
            # Display context summary
            if user_context:
                print("\n👤 [User Context]:")
                print(f"    Balance: ₹{user_context.wallet_balance:.2f}")
                print(f"    Daily Spend: ₹{user_context.daily_spend_today:.2f}")
                print(f"    Velocity (5min): {user_context.transactions_last_5min}")
            
            if merchant_context:
                print("\n🏪 [Merchant Context]:")
                print(f"    Reputation: {merchant_context.reputation_score:.2f}")
                if merchant_context.fraud_reports > 0:
                    print(f"    ⚠️  Fraud Reports: {merchant_context.fraud_reports}")
            
            # Step 4: Policy Evaluation (Trust Gate 2)
            print("\n🔐 [Trust Gate 2] Policy Evaluation...")
            policy_result = policy_engine.evaluate(
                validated_intent,
                user_context,
                merchant_context,
            )
            
            audit_ledger.append(
                EventType.POLICY_EVALUATED,
                {
                    "decision": policy_result.decision.value,
                    "risk_score": policy_result.risk_score,
                    "violations": len(policy_result.violations),
                },
                user_id=context_config.default_user_id,
            )
            
            # Display decision
            print_decision(policy_result)
            
            # Step 5: Decision Routing
            print("\n🔀 [Decision Router] Routing decision...")
            transaction = router.route(
                validated_intent,
                policy_result,
                context_config.default_user_id,
            )
            print(f"    State: {transaction.state.value}")
            print(f"    Transaction ID: {transaction.transaction_id}")
            
            # Step 6: Execution (only for APPROVED)
            if transaction.state == ExecutionState.APPROVED:
                print("\n💸 [Execution Engine] Processing payment...")
                audit_ledger.append(
                    EventType.EXECUTION_STARTED,
                    {"transaction_id": transaction.transaction_id},
                    user_id=context_config.default_user_id,
                    transaction_id=transaction.transaction_id,
                )
                
                exec_result = execution_engine.execute(transaction)
                print_execution_result(exec_result)
                
                # Record in session memory
                session_memory.record_payment_attempt(
                    transaction_id=transaction.transaction_id,
                    merchant_vpa=validated_intent.merchant_vpa or "unknown",
                    amount=validated_intent.amount or 0,
                    decision=policy_result.decision.value,
                    success=exec_result.success,
                    raw_input=user_input,
                )

                # Refresh context to show updated balance
                if exec_result.success:
                    try:
                        updated_context = context_client.get_user_context_sync(context_config.default_user_id)
                        print(f"    💰 Updated Balance: ₹{updated_context.wallet_balance:.2f}")
                    except Exception:
                        pass
                
                # Log to audit ledger
                if exec_result.success:
                    audit_ledger.append(
                        EventType.EXECUTION_COMPLETED,
                        {
                            "reference_number": exec_result.reference_number,
                            "execution_hash": exec_result.execution_hash,
                        },
                        user_id=context_config.default_user_id,
                        transaction_id=transaction.transaction_id,
                    )
                else:
                    audit_ledger.append(
                        EventType.EXECUTION_FAILED,
                        {
                            "error_code": exec_result.error_code,
                            "error_message": exec_result.error_message,
                        },
                        user_id=context_config.default_user_id,
                        transaction_id=transaction.transaction_id,
                    )
            else:
                print(f"\n➡️  [Next Action]:")
                if transaction.state == ExecutionState.DENIED:
                    print("    Payment blocked. User must modify request.")
                elif transaction.state == ExecutionState.COOLDOWN:
                    print("    Rate limit active. Wait and retry.")
                elif transaction.state == ExecutionState.ESCALATED:
                    print("    Requires additional verification (OTP/biometric)")

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
