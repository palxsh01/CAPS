"""Transaction Retriever - RAG for historical transaction context."""

import logging
import os
from datetime import datetime, timedelta, UTC
from typing import Optional, List

from google import genai
from google.genai import types

from caps.rag.models import (
    TransactionEmbedding,
    RAGQuery,
    RAGResult,
    TransactionMatch,
)
from caps.rag.vector_store import VectorStore


logger = logging.getLogger(__name__)


# Temporal patterns for query understanding
TEMPORAL_PATTERNS = {
    "yesterday": timedelta(days=1),
    "last week": timedelta(days=7),
    "last month": timedelta(days=30),
    "today": timedelta(days=0),
    "this week": timedelta(days=7),
    "recently": timedelta(days=3),
}


class TransactionRetriever:
    """
    RAG system for transaction history.
    
    Uses Gemini embeddings to:
    - Store transaction history as vectors
    - Retrieve relevant transactions for queries
    - Enable "pay same as yesterday" queries
    - Detect fraud patterns via historical analysis
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        embedding_model: str = "text-embedding-004",
    ):
        """
        Initialize the retriever.
        
        Args:
            api_key: Google API key
            embedding_model: Model for embeddings
        """
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        self.embedding_model = embedding_model
        
        # Initialize Gemini client
        self.client = genai.Client(api_key=self.api_key)
        
        # Initialize vector store
        self.store = VectorStore()
        
        logger.info(f"Transaction Retriever initialized (model: {embedding_model})")
    
    def add_transaction(
        self,
        transaction_id: str,
        merchant_vpa: str,
        amount: float,
        user_id: str = "user_test",
        merchant_name: Optional[str] = None,
        success: bool = True,
        timestamp: Optional[datetime] = None,
        category: Optional[str] = None,
    ) -> TransactionEmbedding:
        """
        Add a transaction to the retrieval system.
        
        Generates embedding and stores in vector store.
        """
        txn = TransactionEmbedding(
            transaction_id=transaction_id,
            merchant_vpa=merchant_vpa,
            merchant_name=merchant_name,
            amount=amount,
            user_id=user_id,
            success=success,
            timestamp=timestamp or datetime.now(UTC),
            category=category,
            description=f"Payment of ₹{amount:.0f} to {merchant_name or merchant_vpa}",
        )
        
        # Generate embedding
        try:
            embedding = self._generate_embedding(txn.to_text())
            txn.embedding = embedding
            
            # Add to store
            self.store.add(txn)
            
            logger.debug(f"Added transaction to RAG: {transaction_id}")
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            # Store without embedding for non-semantic retrieval
        
        return txn
    
    def query(
        self,
        query_text: str,
        user_id: str = "user_test",
        top_k: int = 5,
    ) -> RAGResult:
        """
        Query transaction history.
        
        Supports:
        - "What did I pay yesterday?"
        - "Pay same merchant as last week"
        - "Show my canteen payments"
        """
        # Parse temporal context
        min_date, max_date = self._parse_temporal(query_text)
        
        # Generate query embedding
        try:
            query_embedding = self._generate_embedding(query_text)
        except Exception as e:
            logger.warning(f"Failed to generate query embedding: {e}")
            return RAGResult(query=query_text, matches=[])
        
        # Search vector store
        matches = self.store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            user_id=user_id,
            min_date=min_date,
            max_date=max_date,
        )
        
        # Build result
        result = RAGResult(
            query=query_text,
            matches=matches,
        )
        
        # Extract suggestions from top match
        if matches:
            top_match = matches[0].transaction
            result.suggested_merchant = top_match.merchant_vpa
            result.suggested_amount = top_match.amount
            result.context_summary = self._build_summary(matches)
        
        return result
    
    def get_merchant_history(
        self,
        merchant_vpa: str,
        limit: int = 10,
    ) -> List[TransactionEmbedding]:
        """Get transaction history for a merchant."""
        return self.store.get_by_merchant(merchant_vpa, limit)
    
    def detect_anomaly(
        self,
        amount: float,
        merchant_vpa: str,
        user_id: str = "user_test",
    ) -> dict:
        """
        Detect if transaction is anomalous based on history.
        
        Returns:
            Dict with is_anomaly, reason, typical_amount
        """
        # Get historical transactions for this merchant
        history = self.store.get_by_merchant(merchant_vpa, limit=20)
        user_history = [t for t in history if t.user_id == user_id]
        
        if not user_history:
            return {
                "is_anomaly": False,
                "reason": "No history for comparison",
                "typical_amount": None,
            }
        
        # Calculate typical amount
        amounts = [t.amount for t in user_history]
        avg_amount = sum(amounts) / len(amounts)
        max_amount = max(amounts)
        
        # Check if current amount is anomalous
        if amount > max_amount * 2:
            return {
                "is_anomaly": True,
                "reason": f"Amount ₹{amount:.0f} is 2x+ higher than historical max ₹{max_amount:.0f}",
                "typical_amount": avg_amount,
            }
        
        if amount > avg_amount * 3:
            return {
                "is_anomaly": True,
                "reason": f"Amount ₹{amount:.0f} is 3x+ higher than average ₹{avg_amount:.0f}",
                "typical_amount": avg_amount,
            }
        
        return {
            "is_anomaly": False,
            "reason": "Within normal range",
            "typical_amount": avg_amount,
        }
    
    def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Gemini."""
        response = self.client.models.embed_content(
            model=self.embedding_model,
            contents=text,
        )
        return list(response.embeddings[0].values)
    
    def _parse_temporal(self, query: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """Parse temporal references from query."""
        query_lower = query.lower()
        now = datetime.now(UTC)
        
        for pattern, delta in TEMPORAL_PATTERNS.items():
            if pattern in query_lower:
                if pattern in ["yesterday", "today"]:
                    # Single day
                    target_date = now - delta
                    min_date = target_date.replace(hour=0, minute=0, second=0)
                    max_date = target_date.replace(hour=23, minute=59, second=59)
                    return min_date, max_date
                else:
                    # Range
                    min_date = now - delta
                    return min_date, now
        
        return None, None
    
    def _build_summary(self, matches: List[TransactionMatch]) -> str:
        """Build context summary from matches."""
        if not matches:
            return "No matching transactions found."
        
        lines = []
        for i, match in enumerate(matches[:3], 1):
            txn = match.transaction
            time_str = txn.timestamp.strftime("%b %d")
            lines.append(f"{i}. ₹{txn.amount:.0f} to {txn.merchant_vpa} ({time_str})")
        
        return "\n".join(lines)
