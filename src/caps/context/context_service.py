"""
FastAPI Context Service

Provides REST API endpoints for retrieving ground truth context data.
This service runs independently and is called AFTER intent validation.

SECURITY: This service holds sensitive data that NEVER goes to the LLM.
"""

from datetime import datetime, timedelta, UTC
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from caps.context.models import UserContext, MerchantContext, TransactionRecord
from caps.context.mock_data import MOCK_USERS, MOCK_MERCHANTS, get_default_user, get_default_merchant
from caps.intelligence.aggregator import FraudIntelligence


app = FastAPI(
    title="CAPS Context Service",
    description="Ground truth data service for CAPS Payment System",
    version="0.1.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global storage (shared between API and Class)
transaction_history: Dict[str, list[TransactionRecord]] = {}

class ContextService:
    """Service to provide context for policy evaluation and state management."""
    
    def __init__(self, fraud_intelligence: FraudIntelligence | None = None):
        """Initialize context service with optional shared FraudIntelligence."""
        from caps.context.mock_data import MOCK_USERS, MOCK_MERCHANTS, get_default_user, get_default_merchant
        self.users = MOCK_USERS
        self.merchants = MOCK_MERCHANTS
        self.default_user = get_default_user
        self.default_merchant = get_default_merchant
        self.fi = fraud_intelligence or FraudIntelligence()
        
    def get_user_context(self, user_id: str) -> Optional[UserContext]:
        """Get context for a user with dynamic velocity/balance."""
        # Get base user
        if user_id in self.users:
            user_context = self.users[user_id] # Reference to mutable object
        else:
            user_context = self.default_user().model_copy(deep=True)
            user_context.user_id = user_id
            # Determine if we should persist this new user? For now, transient.
        
        # Calculate velocity from history
        if user_id in transaction_history:
            history = transaction_history[user_id]
            
            # Last 5 mins
            recent_txns = [
                txn for txn in history
                if txn.timestamp > datetime.now(UTC) - timedelta(minutes=5)
            ]
            user_context.transactions_last_5min = len(recent_txns)
            
            # Today
            today_txns = [
                txn for txn in history
                if txn.timestamp.date() == datetime.now(UTC).date()
            ]
            user_context.transactions_today = len(today_txns)
            user_context.daily_spend_today = sum(txn.amount for txn in today_txns)
            
            if today_txns:
                user_context.last_transaction_time = max(txn.timestamp for txn in today_txns)
        
        return user_context
    
    def get_merchant_context(self, merchant_vpa: str) -> MerchantContext:
        """Get context for a merchant."""
        # 1. Get base context (mock/DB)
        base = self.merchants.get(merchant_vpa)
        if not base:
            base = self.default_merchant(merchant_vpa)
            
        # 2. Enrich with Real-time Intelligence
        # Override mock defaults with live fraud intelligence data
        if hasattr(base, 'risk_state'):
            score = self.fi.get_merchant_score(merchant_vpa)
            base.risk_state = score.risk_state.value
            
            # Enrich fraud reports and reputation from fraud intelligence
            if score.total_reports > 0:
                base.fraud_reports = score.scam_reports
                # community_score is 0-100, reputation is 0-1
                # Use community_score directly as a 0-1 ratio
                base.reputation_score = max(0.0, min(1.0, score.community_score / 100.0))
            
        return base

    def record_transaction(self, user_id: str, transaction: TransactionRecord) -> Dict[str, Any]:
        """Record a transaction and update state."""
        # Initialize user's transaction history if needed
        if user_id not in transaction_history:
            transaction_history[user_id] = []
        
        # Add transaction to history
        transaction_history[user_id].append(transaction)
        
        # Keep only last 24 hours of transactions (memory management)
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        transaction_history[user_id] = [
            txn for txn in transaction_history[user_id]
            if txn.timestamp > cutoff
        ]
        
        # Update Fraud Intelligence stats
        if transaction.is_refund:
            self.fi.update_transaction_stats(
                merchant_vpa=transaction.merchant_vpa,
                is_refund=True
            )
        elif transaction.status == "success":
            self.fi.update_transaction_stats(
                merchant_vpa=transaction.merchant_vpa,
                success=True
            )
            
        # Update User Balance (Mock)
        # Note: logic moved from previous iteration
        if user_id in self.users:
            user = self.users[user_id]
            old_balance = user.wallet_balance
            
            if transaction.status == "success" and not transaction.is_refund:
                 # 1. Update Balance
                 user.wallet_balance -= transaction.amount
                 print(f"DEBUG: Updated balance for {user_id}: {old_balance} -> {user.wallet_balance}")
                 
                 # 2. Dynamic Trust Memory
                 # Add to known contacts if not present
                 if transaction.merchant_vpa not in user.known_contacts:
                     user.known_contacts.append(transaction.merchant_vpa)
                     print(f"DEBUG: Added {transaction.merchant_vpa} to known_contacts")
                     
                 # Increase trust score (capped at 1.0)
                 # Small increment for successful transaction
                 old_trust = user.trust_score
                 user.trust_score = min(1.0, user.trust_score + 0.01)
                 if user.trust_score > old_trust:
                     print(f"DEBUG: Increased trust score: {old_trust} -> {user.trust_score}")
                     
            elif transaction.status == "success" and transaction.is_refund:
                 user.wallet_balance += transaction.amount
                 print(f"DEBUG: Refunded balance for {user_id}: {old_balance} -> {user.wallet_balance}")
        else:
            print(f"DEBUG: User {user_id} not found in MOCK_USERS during update")
        
        return {
            "status": "recorded",
            "transaction_id": transaction.transaction_id,
            "user_id": user_id,
        }


@app.get("/context/user/{user_id}", response_model=UserContext)
async def get_user_context_endpoint(user_id: str):
    """
    Get user context including balance and velocity limits.
    
    Used by Policy Engine to enforce spending limits.
    """
    if context_service is None:
        raise HTTPException(status_code=500, detail="ContextService not initialized")
    return context_service.get_user_context(user_id)


@app.get("/context/merchant/{merchant_vpa}", response_model=MerchantContext)
async def get_merchant_context(merchant_vpa: str):
    """
    Get merchant context including reputation and risk metrics.
    
    Used by Policy Engine to assess merchant trustworthiness.
    """
    if context_service is None:
        raise HTTPException(status_code=500, detail="ContextService not initialized")
    return context_service.get_merchant_context(merchant_vpa)


@app.post("/context/transaction")
async def record_transaction_endpoint(transaction: TransactionRecord):
    """
    Record a transaction for velocity tracking.
    
    This is called after successful payment execution to update history.
    """
    print(f"DEBUG: Received transaction record for {transaction.user_id}: {transaction.transaction_id}")
    return context_service.record_transaction(transaction.user_id, transaction)


@app.get("/context/stats")
async def get_stats():
    """Get service statistics (for debugging)."""
    total_users_tracked = len(transaction_history)
    total_transactions = sum(len(txns) for txns in transaction_history.values())
    
    return {
        "users_tracked": total_users_tracked,
        "total_transactions": total_transactions,
        "mock_users_available": len(MOCK_USERS),
        "mock_merchants_available": len(MOCK_MERCHANTS),
    }



# Global instance
context_service = ContextService()


if __name__ == "__main__":
    import uvicorn
    from caps.context.config import config
    
    uvicorn.run(
        "caps.context.context_service:app",
        host=config.host,
        port=config.port,
        reload=True,
    )
