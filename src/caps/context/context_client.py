"""
Context Client

HTTP client for fetching context from the Context Service.

SECURITY: This client is called AFTER schema validation.
It never passes context data to the LLM.
"""

import logging
from typing import Optional
import httpx

from caps.context.models import UserContext, MerchantContext, TransactionRecord
from caps.context.config import config


logger = logging.getLogger(__name__)


class ContextClient:
    """
    Client for Context Service
    
    Fetches ground truth data (balance, velocity, reputation) for policy evaluation.
    This data is NEVER sent to the LLM.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        """
        Initialize context client.
        
        Args:
            base_url: Base URL of context service (default: from config)
        """
        self.base_url = base_url or f"http://{config.host}:{config.port}"
        self.logger = logger
        
    async def get_user_context(self, user_id: str) -> UserContext:
        """
        Fetch user context from service.
        
        Args:
            user_id: User identifier
            
        Returns:
            UserContext with balance, velocity, device info
            
        Raises:
            Exception: If service is unavailable
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/context/user/{user_id}",
                    timeout=5.0,
                )
                response.raise_for_status()
                
                data = response.json()
                user_context = UserContext(**data)
                
                self.logger.info(f"Fetched context for user: {user_id}")
                return user_context
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch user context: {e}")
            raise Exception(f"Context service error: {e}")
    
    async def get_merchant_context(self, merchant_vpa: str) -> MerchantContext:
        """
        Fetch merchant context from service.
        
        Args:
            merchant_vpa: Merchant VPA address
            
        Returns:
            MerchantContext with reputation and risk metrics
            
        Raises:
            Exception: If service is unavailable
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/context/merchant/{merchant_vpa}",
                    timeout=5.0,
                )
                response.raise_for_status()
                
                data = response.json()
                merchant_context = MerchantContext(**data)
                
                self.logger.info(f"Fetched context for merchant: {merchant_vpa}")
                return merchant_context
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch merchant context: {e}")
            raise Exception(f"Context service error: {e}")
    
    async def record_transaction_async(self, transaction: TransactionRecord) -> dict:
        """
        Record a transaction for velocity tracking.
        
        Args:
            transaction: Transaction record
            
        Returns:
            Confirmation dict
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/context/transaction",
                    json=transaction.model_dump(mode='json'),
                    timeout=5.0,
                )
                response.raise_for_status()
                
                result = response.json()
                self.logger.info(f"Recorded transaction: {transaction.transaction_id}")
                return result
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to record transaction: {e}")
            raise Exception(f"Context service error: {e}")
    
    def get_user_context_sync(self, user_id: str) -> UserContext:
        """
        Synchronous version of get_user_context (for CLI).
        
        Args:
            user_id: User identifier
            
        Returns:
            UserContext
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/context/user/{user_id}",
                    timeout=5.0,
                )
                response.raise_for_status()
                
                data = response.json()
                user_context = UserContext(**data)
                
                self.logger.info(f"Fetched context for user: {user_id}")
                return user_context
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch user context: {e}")
            raise Exception(f"Context service error: {e}")
    
    def get_merchant_context_sync(self, merchant_vpa: str) -> MerchantContext:
        """
        Synchronous version of get_merchant_context (for CLI).
        
        Args:
            merchant_vpa: Merchant VPA
            
        Returns:
            MerchantContext
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/context/merchant/{merchant_vpa}",
                    timeout=5.0,
                )
                response.raise_for_status()
                
                data = response.json()
                merchant_context = MerchantContext(**data)
                
                self.logger.info(f"Fetched context for merchant: {merchant_vpa}")
                return merchant_context
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to fetch merchant context: {e}")
            raise Exception(f"Context service error: {e}")

    def record_transaction_sync(self, user_id: str, transaction: TransactionRecord) -> dict:
        """
        Synchronous version of record_transaction (for CLI/Engine).
        
        Args:
            user_id: User identifier (kept for interface compatibility)
            transaction: Transaction record
            
        Returns:
            Confirmation dict
        """
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/context/transaction",
                    json=transaction.model_dump(mode='json'),
                    timeout=5.0,
                )
                response.raise_for_status()
                
                result = response.json()
                self.logger.info(f"Recorded transaction: {transaction.transaction_id}")
                return result
                
        except httpx.HTTPError as e:
            self.logger.error(f"Failed to record transaction: {e}")
            raise Exception(f"Context service error: {e}")
            
    # Alias to match ContextService interface if needed by ExecutionEngine
    def record_transaction(self, user_id: str, transaction: TransactionRecord) -> dict:
        """Alias for sync execution if called synchronously by Engine."""
        # Check if we are in an async loop provided by user? No, we can't easily detect intent.
        # But ExecutionEngine in CLI is sync. 
        # CAUTION: This shadows the async method if we are not careful.
        # But the async method defined above is `async def record_transaction(self, transaction)`.
        # Overloading by name isn't possible in Python like this. 
        # We should NOT rename it here. We will rely on Monkey Patching or just binding in main.py?
        # Better: Update ExecutionEngine to try `record_transaction` OR `record_transaction_sync`.
        # OR: define `record_transaction_sync` and pass a wrapper to ExecutionEngine.
        return self.record_transaction_sync(user_id, transaction)
