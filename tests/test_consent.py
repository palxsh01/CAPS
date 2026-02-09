
import pytest
import time
from caps.security.consent import ConsentManager

def test_consent_manager():
    manager = ConsentManager(secret_key="test-secret")
    
    user_id = "user_1"
    merchant = "merchant@upi"
    amount = 500.0
    
    # 1. Issue Token
    token = manager.issue_token(user_id, merchant, amount)
    assert token is not None
    assert len(token.split('.')) == 3
    
    # 2. Validate Token (Valid case)
    claims = manager.validate_token(token, merchant, amount)
    assert claims.sub == user_id
    assert claims.aud == merchant
    assert claims.scope.max_amount == amount
    
    # 3. Validate Token (Replay Attack)
    with pytest.raises(ValueError, match="Token already used"):
        manager.validate_token(token, merchant, amount)
        
    # 4. Validate Token (Wrong Audience/Confused Deputy)
    token2 = manager.issue_token(user_id, merchant, amount)
    with pytest.raises(ValueError, match="audience mismatch"):
        manager.validate_token(token2, "attacker@upi", amount)
        
    # 5. Validate Token (Scope Violation - Amount)
    token3 = manager.issue_token(user_id, merchant, amount)
    with pytest.raises(ValueError, match="exceeds authorized limit"):
        manager.validate_token(token3, merchant, amount + 1.0)

    # 6. Validate Token (Expired)
    token_expired = manager.issue_token(user_id, merchant, amount, validity_seconds=-10)
    with pytest.raises(ValueError, match="Token expired"):
        manager.validate_token(token_expired, merchant, amount)

    print("Consent Manager tests passed!")

if __name__ == "__main__":
    test_consent_manager()
