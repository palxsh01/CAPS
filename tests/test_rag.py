"""Tests for RAG module."""

import pytest
import numpy as np
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock, patch

from caps.rag.models import TransactionEmbedding, RAGQuery, RAGResult
from caps.rag.vector_store import VectorStore


class TestVectorStore:
    """Test Vector Store."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.store = VectorStore()
    
    def test_add_transaction(self):
        """Transactions should be added with embeddings."""
        txn = TransactionEmbedding(
            transaction_id="txn_001",
            merchant_vpa="canteen@vit",
            amount=50.0,
            description="Payment to canteen",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
        )
        
        self.store.add(txn)
        
        assert self.store.count() == 1
    
    def test_search_by_similarity(self):
        """Search should return similar transactions."""
        # Add transactions with different embeddings
        txn1 = TransactionEmbedding(
            transaction_id="txn_001",
            merchant_vpa="canteen@vit",
            amount=50.0,
            description="Canteen payment",
            embedding=[1.0, 0.0, 0.0],
        )
        txn2 = TransactionEmbedding(
            transaction_id="txn_002",
            merchant_vpa="shop@upi",
            amount=100.0,
            description="Shop payment",
            embedding=[0.0, 1.0, 0.0],
        )
        txn3 = TransactionEmbedding(
            transaction_id="txn_003",
            merchant_vpa="canteen@vit",
            amount=75.0,
            description="Another canteen payment",
            embedding=[0.9, 0.1, 0.0],  # Similar to txn1
        )
        
        self.store.add(txn1)
        self.store.add(txn2)
        self.store.add(txn3)
        
        # Search with embedding similar to txn1
        results = self.store.search(
            query_embedding=[1.0, 0.0, 0.0],
            top_k=2,
        )
        
        assert len(results) == 2
        # First result should be txn1 (exact match)
        assert results[0].transaction.transaction_id == "txn_001"
        # Second should be txn3 (similar)
        assert results[1].transaction.transaction_id == "txn_003"
    
    def test_search_with_merchant_filter(self):
        """Search should filter by merchant."""
        txn1 = TransactionEmbedding(
            transaction_id="txn_001",
            merchant_vpa="canteen@vit",
            amount=50.0,
            description="Canteen",
            embedding=[1.0, 0.0, 0.0],
        )
        txn2 = TransactionEmbedding(
            transaction_id="txn_002",
            merchant_vpa="shop@upi",
            amount=100.0,
            description="Shop",
            embedding=[0.9, 0.1, 0.0],
        )
        
        self.store.add(txn1)
        self.store.add(txn2)
        
        results = self.store.search(
            query_embedding=[1.0, 0.0, 0.0],
            top_k=5,
            merchant_filter="canteen",
        )
        
        assert len(results) == 1
        assert results[0].transaction.merchant_vpa == "canteen@vit"
    
    def test_get_by_merchant(self):
        """Should get transactions by merchant VPA."""
        txn1 = TransactionEmbedding(
            transaction_id="txn_001",
            merchant_vpa="canteen@vit",
            amount=50.0,
            description="",
            embedding=[1.0, 0.0, 0.0],
        )
        txn2 = TransactionEmbedding(
            transaction_id="txn_002",
            merchant_vpa="canteen@vit",
            amount=75.0,
            description="",
            embedding=[0.0, 1.0, 0.0],
        )
        
        self.store.add(txn1)
        self.store.add(txn2)
        
        results = self.store.get_by_merchant("canteen")
        
        assert len(results) == 2


class TestTransactionEmbedding:
    """Test Transaction Embedding model."""
    
    def test_to_text(self):
        """Should convert to text for embedding."""
        txn = TransactionEmbedding(
            transaction_id="txn_001",
            merchant_vpa="canteen@vit",
            merchant_name="VIT Canteen",
            amount=50.0,
            description="Payment",
            timestamp=datetime(2026, 2, 9, 10, 30, tzinfo=UTC),
        )
        
        text = txn.to_text()
        
        assert "₹50" in text
        assert "VIT Canteen" in text
        assert "2026-02-09" in text
