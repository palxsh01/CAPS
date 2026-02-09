"""Vector Store - Simple in-memory vector store with cosine similarity."""

import logging
import numpy as np
from typing import Optional, List, Tuple
from datetime import datetime

from caps.rag.models import TransactionEmbedding, TransactionMatch


logger = logging.getLogger(__name__)


class VectorStore:
    """
    Simple in-memory vector store.
    
    Uses numpy for cosine similarity search.
    For production, consider ChromaDB or Pinecone.
    """
    
    def __init__(self):
        """Initialize empty vector store."""
        self.transactions: List[TransactionEmbedding] = []
        self.embeddings: Optional[np.ndarray] = None
        
        logger.info("Vector Store initialized (in-memory)")
    
    def add(self, transaction: TransactionEmbedding) -> None:
        """
        Add a transaction to the store.
        
        Args:
            transaction: Transaction with embedding
        """
        if transaction.embedding is None:
            raise ValueError("Transaction must have embedding")
        
        self.transactions.append(transaction)
        
        # Update embeddings matrix
        new_embedding = np.array(transaction.embedding).reshape(1, -1)
        if self.embeddings is None:
            self.embeddings = new_embedding
        else:
            self.embeddings = np.vstack([self.embeddings, new_embedding])
        
        logger.debug(f"Added transaction: {transaction.transaction_id}")
    
    def add_batch(self, transactions: List[TransactionEmbedding]) -> None:
        """Add multiple transactions."""
        for txn in transactions:
            if txn.embedding is not None:
                self.add(txn)
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        user_id: Optional[str] = None,
        min_date: Optional[datetime] = None,
        max_date: Optional[datetime] = None,
        merchant_filter: Optional[str] = None,
    ) -> List[TransactionMatch]:
        """
        Search for similar transactions.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results
            user_id: Filter by user
            min_date: Filter by minimum date
            max_date: Filter by maximum date
            merchant_filter: Filter by merchant VPA substring
            
        Returns:
            List of matching transactions with scores
        """
        if self.embeddings is None or len(self.transactions) == 0:
            return []
        
        query_vec = np.array(query_embedding).reshape(1, -1)
        
        # Compute cosine similarities
        similarities = self._cosine_similarity(query_vec, self.embeddings)[0]
        
        # Build candidate list with filters
        candidates: List[Tuple[int, float]] = []
        
        for idx, (txn, score) in enumerate(zip(self.transactions, similarities)):
            # Apply filters
            if user_id and txn.user_id != user_id:
                continue
            if min_date and txn.timestamp < min_date:
                continue
            if max_date and txn.timestamp > max_date:
                continue
            if merchant_filter and merchant_filter.lower() not in txn.merchant_vpa.lower():
                continue
            
            candidates.append((idx, float(score)))
        
        # Sort by similarity descending
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k
        results = []
        for idx, score in candidates[:top_k]:
            results.append(TransactionMatch(
                transaction=self.transactions[idx],
                similarity=score,
            ))
        
        return results
    
    def get_by_merchant(
        self,
        merchant_vpa: str,
        limit: int = 10,
    ) -> List[TransactionEmbedding]:
        """Get transactions by merchant VPA."""
        matches = []
        for txn in reversed(self.transactions):
            if merchant_vpa.lower() in txn.merchant_vpa.lower():
                matches.append(txn)
                if len(matches) >= limit:
                    break
        return matches
    
    def get_recent(
        self,
        user_id: str,
        limit: int = 10,
    ) -> List[TransactionEmbedding]:
        """Get recent transactions for a user."""
        matches = []
        for txn in reversed(self.transactions):
            if txn.user_id == user_id:
                matches.append(txn)
                if len(matches) >= limit:
                    break
        return matches
    
    def count(self) -> int:
        """Get number of stored transactions."""
        return len(self.transactions)
    
    def clear(self) -> None:
        """Clear the store."""
        self.transactions.clear()
        self.embeddings = None
        logger.info("Vector store cleared")
    
    def _cosine_similarity(
        self,
        a: np.ndarray,
        b: np.ndarray,
    ) -> np.ndarray:
        """Compute cosine similarity between vectors."""
        # Normalize vectors
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
        
        # Compute dot product
        return np.dot(a_norm, b_norm.T)
