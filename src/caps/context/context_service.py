"""
FastAPI Context Service

Provides REST API endpoints for retrieving ground truth context data.
This service runs independently and is called AFTER intent validation.

SECURITY: This service holds sensitive data that NEVER goes to the LLM.
"""

from datetime import datetime, timedelta
from typing import Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from caps.context.models import UserContext, MerchantContext, TransactionRecord
from caps.context.mock_data import MOCK_USERS, MOCK_MERCHANTS, get_default_user, get_default_merchant


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

# In-memory storage (would be database in production)
transaction_history: Dict[str, list[TransactionRecord]] = {}


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "CAPS Context Service",
        "status": "running",
        "version": "0.1.0",
    }


@app.get("/context/user/{user_id}", response_model=UserContext)
async def get_user_context(user_id: str):
    """
    Get user context including balance, velocity, and device info.
    
    This endpoint is called AFTER intent validation to fetch ground truth.
    """
    # Check if user exists in mock data
    if user_id in MOCK_USERS:
        user_context = MOCK_USERS[user_id].model_copy(deep=True)
    else:
        # Return default user context for unknown users
        user_context = get_default_user().model_copy(deep=True)
        user_context.user_id = user_id
    
    # Update transaction velocity from recent history
    if user_id in transaction_history:
        recent_txns = [
            txn for txn in transaction_history[user_id]
            if txn.timestamp > datetime.utcnow() - timedelta(minutes=5)
        ]
        user_context.transactions_last_5min = len(recent_txns)
        
        today_txns = [
            txn for txn in transaction_history[user_id]
            if txn.timestamp.date() == datetime.utcnow().date()
        ]
        user_context.transactions_today = len(today_txns)
        user_context.daily_spend_today = sum(txn.amount for txn in today_txns)
        
        if today_txns:
            user_context.last_transaction_time = max(txn.timestamp for txn in today_txns)
    
    return user_context


@app.get("/context/merchant/{merchant_vpa}", response_model=MerchantContext)
async def get_merchant_context(merchant_vpa: str):
    """
    Get merchant context including reputation and risk metrics.
    
    Used by Policy Engine to assess merchant trustworthiness.
    """
    # Check if merchant exists in mock data
    if merchant_vpa in MOCK_MERCHANTS:
        return MOCK_MERCHANTS[merchant_vpa]
    else:
        # Return default merchant context for unknown merchants
        return get_default_merchant(merchant_vpa)


@app.post("/context/transaction")
async def record_transaction(transaction: TransactionRecord):
    """
    Record a transaction for velocity tracking.
    
    This is called after successful payment execution to update history.
    """
    user_id = transaction.user_id
    
    # Initialize user's transaction history if needed
    if user_id not in transaction_history:
        transaction_history[user_id] = []
    
    # Add transaction to history
    transaction_history[user_id].append(transaction)
    
    # Keep only last 24 hours of transactions (memory management)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    transaction_history[user_id] = [
        txn for txn in transaction_history[user_id]
        if txn.timestamp > cutoff
    ]
    
    return {
        "status": "recorded",
        "transaction_id": transaction.transaction_id,
        "user_id": user_id,
    }


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


if __name__ == "__main__":
    import uvicorn
    from caps.context.config import config
    
    uvicorn.run(
        "caps.context.context_service:app",
        host=config.host,
        port=config.port,
        reload=True,
    )
