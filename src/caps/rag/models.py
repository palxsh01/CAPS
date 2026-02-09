"""Models for RAG system."""

import uuid
from datetime import datetime, UTC
from typing import Optional, List
from pydantic import BaseModel, Field


class TransactionEmbedding(BaseModel):
    """Transaction with its embedding vector."""
    
    transaction_id: str = Field(description="Unique transaction ID")
    merchant_vpa: str = Field(description="Merchant VPA")
    merchant_name: Optional[str] = Field(default=None)
    amount: float = Field(description="Transaction amount")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Natural language description for embedding
    description: str = Field(description="Human-readable description")
    
    # Embedding vector (will be populated by embedding service)
    embedding: Optional[List[float]] = Field(default=None)
    
    # Metadata
    user_id: str = Field(default="user_test")
    success: bool = Field(default=True)
    category: Optional[str] = Field(default=None)
    
    def to_text(self) -> str:
        """Convert transaction to text for embedding."""
        time_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        merchant = self.merchant_name or self.merchant_vpa
        return f"Payment of ₹{self.amount:.0f} to {merchant} on {time_str}"


class RAGQuery(BaseModel):
    """Query for RAG retrieval."""
    
    query_text: str = Field(description="Natural language query")
    user_id: str = Field(default="user_test")
    
    # Filters
    min_date: Optional[datetime] = Field(default=None)
    max_date: Optional[datetime] = Field(default=None)
    merchant_filter: Optional[str] = Field(default=None)
    
    # Settings
    top_k: int = Field(default=5, description="Number of results")


class RAGResult(BaseModel):
    """Result from RAG retrieval."""
    
    query: str = Field(description="Original query")
    matches: List["TransactionMatch"] = Field(default_factory=list)
    
    # Derived context
    suggested_merchant: Optional[str] = Field(default=None)
    suggested_amount: Optional[float] = Field(default=None)
    context_summary: Optional[str] = Field(default=None)


class TransactionMatch(BaseModel):
    """A matching transaction with similarity score."""
    
    transaction: TransactionEmbedding
    similarity: float = Field(ge=0, le=1)
    
    class Config:
        arbitrary_types_allowed = True
