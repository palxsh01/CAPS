# Phase 2 Setup: Context Service

This document explains how to run and test the Context Service introduced in Phase 2.

## Quick Start

### 1. Start the Context Service

In one terminal:

```bash
cd /Users/atharvamendhulkar/Desktop/CAPS
source venv/bin/activate
python scripts/run_context_service.py
```

The service will start on `http://127.0.0.1:8001`

### 2. Test the Context API (Optional)

In another terminal:

```bash
source venv/bin/activate
python scripts/test_context_api.py
```

### 3. Run the CLI Demo

With the context service running:

```bash
source venv/bin/activate
python -m caps.main
```

Try:
- `"Pay canteen@vit 100 rupees"` (trusted merchant)
- `"Pay scam@merchant 50 rupees"` (suspicious merchant)
- `"Check my balance"` (balance inquiry)

---

## What's New in Phase 2

### Context Service Features

**User Context Provides:**
- Wallet balance
- Daily spending
- Transaction velocity (last 5 min)
- Device fingerprint status
- Location
- Account age

**Merchant Context Provides:**
- Reputation score (0-1)
- Whitelist status
- Transaction history
- Refund rate
- Fraud reports

### Security Architecture

> [!IMPORTANT]
> **Zero-Trust Principle Maintained**
> 
> Context data is fetched AFTER schema validation and NEVER sent to the LLM.
> The LLM only sees the natural language input, nothing more.

**Flow:**
```
User Input → LLM → Schema Validator → Context Service → Display
           (blind)  (Trust Gate 1)    (ground truth)
```

---

## API Endpoints

### GET /context/user/{user_id}
Get user context including balance and velocity.

**Example:**
```bash
curl http://127.0.0.1:8001/context/user/user_test
```

### GET /context/merchant/{merchant_vpa}
Get merchant reputation and risk data.

**Example:**
```bash
curl http://127.0.0.1:8001/context/merchant/canteen@vit
```

### POST /context/transaction
Record a transaction for velocity tracking.

### GET /context/stats
View service statistics.

---

## Mock Data Profiles

### Users

| User ID | Balance | Daily Spend | Velocity | Device |
|---------|---------|-------------|----------|--------|
| `user_normal` | ₹1500 | ₹200 | 1 | Known |
| `user_low_balance` | ₹50 | ₹450 | 0 | Known |
| `user_high_velocity` | ₹2000 | ₹1800 | 8 | Known |
| `user_new_device` | ₹1000 | ₹0 | 0 | **New** |

### Merchants

| Merchant VPA | Reputation | Whitelisted | Refund Rate |
|--------------|-----------|-------------|-------------|
| `canteen@vit` | 0.95 | ✅ Yes | 1% |
| `shop@upi` | 0.85 | ✅ Yes | 2.5% |
| `newstore@upi` | 0.50 | ❌ No | 4% |
| `scam@merchant` | 0.15 | ❌ No | 45% |

---

## Running Tests

```bash
# Test context service
pytest tests/test_context_service.py -v

# Test integration
pytest tests/test_context_integration.py -v

# All Phase 1 + 2 tests
pytest tests/ -v
```

---

## Troubleshooting

**Error: Connection refused**
- Make sure context service is running: `python scripts/run_context_service.py`

**Error: Port already in use**
- Change port in `.env`:
  ```
  CONTEXT_SERVICE_PORT=8002
  ```

---

## Next Steps: Phase 3

Once Phase 2 is verified, we'll implement:
- Policy Engine with multi-layered rules
- Risk evaluation using context data
- Decision making (APPROVE/DENY/COOLDOWN/ESCALATE)
