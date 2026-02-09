"""Consent Manager - Secure Token Management for High-Risk Actions.

Implements JWT-based consent tokens with:
- Cryptographic signing (HMAC-SHA256)
- Scoping (merchant, amount, expiration)
- Anti-confused-deputy protection (audience checks)
- Single-use enforcement (JTI tracking)
"""

import hmac
import hashlib
import json
import base64
import time
import uuid
from typing import Optional, Dict, Any, Set
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator

# Secret key for signing (in production, use KMS/HSM)
CONSENT_SECRET_KEY = "caps-consent-secret-key-change-in-production"


class ConsentScope(BaseModel):
    """Scope of the consent token."""
    merchant_vpa: str
    max_amount: float
    currency: str = "INR"
    action: str = "payment"


class ConsentClaims(BaseModel):
    """JWT Claims for consent token."""
    iss: str = "caps-policy-engine"  # Issuer
    sub: str                         # Subject (User ID)
    aud: str                         # Audience (Merchant VPA)
    exp: int                         # Expiration (Unix timestamp)
    iat: int                         # Issued At
    jti: str                         # Unique Token ID
    scope: ConsentScope              # The actual consent grant


class ConsentManager:
    """
    Manages generation and validation of secure consent tokens.
    """
    
    def __init__(self, secret_key: str = CONSENT_SECRET_KEY):
        self.secret_key = secret_key.encode()
        self.used_tokens: Set[str] = set()  # In-memory revocation list
    
    def issue_token(
        self,
        user_id: str,
        merchant_vpa: str,
        amount: float,
        validity_seconds: int = 300  # 5 minutes default
    ) -> str:
        """
        Issue a signed consent token.
        
        Args:
            user_id: User granting consent
            merchant_vpa: Merchant receiving payment
            amount: Authorized amount
            validity_seconds: Token validity duration
            
        Returns:
            JWT string
        """
        now = int(time.time())
        
        scope = ConsentScope(
            merchant_vpa=merchant_vpa,
            max_amount=amount,
        )
        
        claims = ConsentClaims(
            sub=user_id,
            aud=merchant_vpa,
            exp=now + validity_seconds,
            iat=now,
            jti=uuid.uuid4().hex,
            scope=scope
        )
        
        return self._encode_jwt(claims.model_dump())
    
    def validate_token(
        self,
        token: str,
        merchant_vpa: str,
        amount: float,
    ) -> ConsentClaims:
        """
        Validate a consent token for a specific action.
        
        Args:
            token: JWT string
            merchant_vpa: Use context (who is using it)
            amount: Amount being transacted
            
        Returns:
            Validated claims
            
        Raises:
            ValueError: If token is invalid, expired, or scoped incorrectly
        """
        try:
            claims_dict = self._decode_jwt(token)
            claims = ConsentClaims(**claims_dict)
        except Exception as e:
            raise ValueError(f"Invalid token format: {str(e)}")
        
        # 1. Check Expiration
        if claims.exp < time.time():
            raise ValueError("Token expired")
        
        # 2. Check Single Use (Replay Protection)
        if claims.jti in self.used_tokens:
            raise ValueError("Token already used (replay detected)")
        
        # 3. Anti-Confused-Deputy (Audience Check)
        # Ensure the token was issued FOR this merchant
        if claims.aud != merchant_vpa:
            raise ValueError(f"Token audience mismatch. Intended for {claims.aud}, used for {merchant_vpa}")
        
        # 4. Scope Validation
        if claims.scope.merchant_vpa != merchant_vpa:
             raise ValueError("Scope mismatch: Merchant VPA")
             
        if amount > claims.scope.max_amount:
            raise ValueError(f"Amount {amount} exceeds authorized limit {claims.scope.max_amount}")
            
        # Mark as used (Primitive replay protection)
        # In a real system, store JTI in Redis/DB with TTL
        self.mark_as_used(claims.jti)
        
        return claims

    def mark_as_used(self, jti: str) -> None:
        """Mark a token ID as used."""
        self.used_tokens.add(jti)

    def _encode_jwt(self, payload: Dict[str, Any]) -> str:
        """Create HS256 JWT."""
        header = {"typ": "JWT", "alg": "HS256"}
        
        header_b64 = self._base64url_encode(json.dumps(header).encode())
        payload_b64 = self._base64url_encode(json.dumps(payload).encode())
        
        signing_input = f"{header_b64}.{payload_b64}".encode()
        signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        signature_b64 = self._base64url_encode(signature)
        
        return f"{header_b64}.{payload_b64}.{signature_b64}"

    def _decode_jwt(self, token: str) -> Dict[str, Any]:
        """Decode and verify HS256 JWT."""
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid JWT structure")
            
        header_b64, payload_b64, signature_b64 = parts
        
        # Verify Signature
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_signature = hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        
        if not hmac.compare_digest(self._base64url_encode(expected_signature), signature_b64):
            raise ValueError("Invalid signature")
            
        # Decode Payload
        payload_json = self._base64url_decode(payload_b64).decode()
        return json.loads(payload_json)

    @staticmethod
    def _base64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

    @staticmethod
    def _base64url_decode(data: str) -> bytes:
        rem = len(data) % 4
        if rem > 0:
            data += '=' * (4 - rem)
        return base64.urlsafe_b64decode(data)
