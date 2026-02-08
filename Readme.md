# CAPS: Context-Aware Agentic Payment System

<div align="center">

**A deterministic payment kernel designed for a world where AI reasons but never decides alone**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![ADK](https://img.shields.io/badge/Framework-Google_ADK-orange.svg)](https://github.com/google)
[![UPI Lite](https://img.shields.io/badge/Payment-UPI_Lite-green.svg)](https://www.npci.org.in/what-we-do/upi/upi-lite)

</div>

---

## Table of Contents

- [Project Overview](#-project-overview)
- [Core Philosophy](#-core-philosophy)
- [System Architecture](#-system-architecture)
- [Component Specifications](#-component-specifications)
- [System Workflow](#-system-workflow)
- [Fraud Prevention Strategy](#-fraud-prevention-strategy)
- [Policy & Risk Engine](#-policy--risk-engine)
- [Implementation Roadmap](#-implementation-roadmap)
- [Technology Stack](#-technology-stack)

---

## Project Overview

**One-Line Summary:** CAPS is a deterministic payment kernel that survives AI failure. It is designed for a world where AI reasons but never decides alone.

Traditional payment systems assume human operators with explicit intent. Agentic systems violate this assumption because intent is inferred, actions are chained, and failures can amplify automatically. CAPS addresses this by strictly decoupling the **reasoning layer** (LLM) from the **control plane** (Policy Engine).

### Why CAPS Matters

> [!IMPORTANT]
> In agentic payment systems, the risks are fundamentally different:
> - **Intent is inferred**, not explicit
> - **Actions can chain** automatically
> - **Failures amplify** without human intervention
> - **Prompt injection** can become financial fraud

CAPS creates a trust boundary between AI reasoning and payment execution, ensuring that no money moves unless all deterministic safety gates pass.

---

## 🧭 Core Philosophy

### 1. **Trust Gradient**
Trust decreases as data moves up the stack (towards the LLM) and increases as it moves down (towards the Ledger).

```mermaid
graph TD
    A[User Input] -->|Low Trust| B[LLM Intent Interpreter]
    B -->|Untrusted Suggestion| C[Schema Validator]
    C -->|Validated Structure| D[Policy Engine]
    D -->|High Trust| E[Execution Sandbox]
    E -->|Cryptographic Guarantee| F[Immutable Ledger]
    
    style A fill:#ff6b6b
    style B fill:#feca57
    style C fill:#48dbfb
    style D fill:#1dd1a1
    style E fill:#5f27cd
    style F fill:#00d2d3
```

### 2. **Fail-Closed**
The system defaults to a denial state for any ambiguity.

### 3. **Zero-Trust Reasoning**
The LLM is treated as an untrusted user input source. It interprets natural language but has **zero authority** to authorize transactions.

---

## 🏗️ System Architecture

### High-Level Architecture

```mermaid
graph TB
    subgraph "Interaction Layer"
        UI[User Interface]
        Voice[Voice Input]
    end
    
    subgraph "Reasoning Layer (Untrusted)"
        LLM[LLM Intent Interpreter]
    end
    
    subgraph "Deterministic Control Plane (Trust Boundary)"
        Validator[Schema Validator]
        Context[Context Evaluator]
        Policy[Policy & Risk Engine]
        Router[Decision Router]
    end
    
    subgraph "Execution Layer"
        Consent[Consent Manager]
        Sandbox[Execution Sandbox]
    end
    
    subgraph "Audit Layer"
        Ledger[(Immutable Audit Ledger)]
    end
    
    UI --> LLM
    Voice --> LLM
    LLM -->|JSON Intent| Validator
    Validator -->|Valid Schema| Context
    Context -->|Grounded Context| Policy
    Policy -->|Decision| Router
    Router -->|APPROVE| Consent
    Router -->|DENY/ESCALATE| Ledger
    Consent -->|Signed Token| Sandbox
    Sandbox --> Ledger
    
    style LLM fill:#feca57
    style Policy fill:#1dd1a1
    style Sandbox fill:#5f27cd
    style Ledger fill:#00d2d3
```

### Architectural Layers

| Layer | Purpose | Trust Level |
|-------|---------|-------------|
| **Interaction Layer** | Captures human intent via UI or Voice | ⚠️ Low |
| **LLM Intent Interpreter** | Translates natural language into structured JSON | ⚠️ Zero Trust |
| **Deterministic Control Plane** | Schema Validator, Context Evaluator, and Policy Engine | ✅ High Trust |
| **Execution Sandbox** | Mock UPI Lite execution with cryptographic invariants | ✅ Highest Trust |
| **Immutable Audit Ledger** | Write-only, hash-chained record of all actions | 🔒 Cryptographic Trust |

---

## 🧩 Component Specifications

### 3.1. Interaction Layer (Frontend)

**Role:** Input capture and decision visualization.

**Behavior:** Displays the machine's decision to the user. Prevents "dark patterns" by forcing explicit consent visibility for every action proposed by the agent.

> [!WARNING]
> The frontend cannot execute payments directly. All requests must pass through the API gateway to the Intent Interpreter.

---

### 3.2. LLM Intent Interpreter (Reasoning Layer)

**Role:** Semantic translation. Converts unstructured text into strict JSON schema.

**Example Transformation:**

```
User Input: "Pay the canteen 50 rupees"
```

```json
{
  "intent_type": "PAYMENT",
  "amount": 50,
  "currency": "INR",
  "merchant_vpa": "canteen@vit",
  "confidence_score": 0.95
}
```

> [!CAUTION]
> **Safety Mechanism:** The LLM is never provided with sensitive context (balances, hard limits) in its system prompt. This prevents prompt injection attacks where a user might instruct the model to "ignore safety rules."

---

### 3.3. Schema Validator (Trust Gate 1)

**Role:** Syntactic validation.

**Logic:** Enforces strict typing. If the LLM outputs a string where a float is required, or adds hallucinated fields, the request is instantly rejected with a `PARSE_ERROR`.

**Fraud Prevention:** Prevents payload smuggling and stops the LLM from hallucinating unauthorized parameters.

---

### 3.4. Context Evaluator

**Role:** Ground truth retrieval.

**Function:** Fetches real-time data strictly *after* the intent is parsed.

**Data Sources:**
- Wallet Balance
- Daily Spending Velocity
- User Location / Device Fingerprint
- Merchant Reputation Score

> [!NOTE]
> **Design Principle:** Context is injected into the Policy Engine, not the LLM. This prevents the AI from "gaming" the rules.

---

### 3.5. Policy & Risk Engine (The Core)

This is a deterministic state machine that evaluates the tuple `(parsed_intent, user_context, system_state)`. It utilizes a multi-layered defense model.

```mermaid
graph TD
    Start([Intent Received]) --> L1[Layer 1: Hard Invariants]
    L1 -->|Pass| L2[Layer 2: Velocity & Temporal]
    L1 -->|Fail| Deny[DENY]
    L2 -->|Pass| L3[Layer 3: Agentic Threat Defense]
    L2 -->|Fail| Cool[COOLDOWN/ESCALATE]
    L3 -->|Pass| L4[Layer 4: Behavioral Analysis]
    L3 -->|Fail| Kill[DENY + Session Kill]
    L4 -->|Pass| Approve[APPROVE]
    L4 -->|Fail| Verify[REQUIRE_REAUTH]
    
    style Deny fill:#ff6b6b
    style Approve fill:#1dd1a1
    style Cool fill:#feca57
    style Kill fill:#ee5a6f
    style Verify fill:#48dbfb
```

#### Layer 1: Hard Invariants (UPI Lite)

| Invariant | Rule | Action on Violation |
|-----------|------|---------------------|
| Transaction Amount | ≤ ₹500 INR | ❌ DENY |
| Daily Spend | ≤ ₹2000 INR | ❌ DENY |
| Wallet Balance | ≥ Transaction Amount | ❌ DENY |

#### Layer 2: Velocity & Temporal Logic

- **Rule:** Max 10 transactions per 5 minutes
- **Rule:** Detect rapid repetition of identical amounts (Draining Attack)
- **Rule:** Flag night-time spikes or rapid merchant switching
- **Action:** Violation results in `COOLDOWN` or `ESCALATE`

#### Layer 3: Agentic Threat Defense

| Threat | Defense Mechanism |
|--------|-------------------|
| **Recursive Execution** | Execution events are write-only. Agent cannot read "Success" and trigger new payment in a loop |
| **Confused Deputy** | Consent tokens are bound to specific intents. Cannot reuse old consent for new transaction |
| **Intent Splitting** | Detects if large transaction is broken into micro-transactions (e.g., 10 × ₹199) |

#### Layer 4: Behavioral Analysis

- New devices, geolocation mismatches, session anomalies trigger additional verification

---

### 3.6. Decision Router

**Role:** Explicit control flow.

```mermaid
stateDiagram-v2
    [*] --> PolicyDecision
    PolicyDecision --> RequestConsent: APPROVE
    PolicyDecision --> Terminate: DENY
    PolicyDecision --> BiometricAuth: VERIFY
    PolicyDecision --> PauseAgent: COOLDOWN
    
    RequestConsent --> Execute
    BiometricAuth --> Execute: Success
    BiometricAuth --> Terminate: Failure
    Execute --> [*]
    Terminate --> [*]
    PauseAgent --> [*]
```

---

### 3.7. Mock Execution Engine (Sandbox)

**Role:** Simulator for UPI Lite execution.

**Security:** Uses idempotency keys and payload hashing.

> [!CAUTION]
> The execution payload must match the approved intent hash **exactly**. Any deviation causes an abort.

---

### 3.8. Audit Ledger

**Role:** Forensic storage.

**Structure:** Append-only, hash-chained log.

**Requirement:** Every decision (Approved or Denied) is logged. This allows full reconstruction of the system state for post-incident analysis.

```mermaid
graph LR
    A[Block 1] -->|Hash| B[Block 2]
    B -->|Hash| C[Block 3]
    C -->|Hash| D[Block 4]
    
    A1[Intent ID<br/>Decision<br/>Timestamp] -.-> A
    B1[Intent ID<br/>Decision<br/>Timestamp] -.-> B
    C1[Intent ID<br/>Decision<br/>Timestamp] -.-> C
    D1[Intent ID<br/>Decision<br/>Timestamp] -.-> D
    
    style A fill:#00d2d3
    style B fill:#00d2d3
    style C fill:#00d2d3
    style D fill:#00d2d3
```

---

## System Workflow

### Complete Transacion Lifecycle
```mermaid
    sequenceDiagram
    actor User
    participant UI as Interaction Layer
    participant LLM as Intent Interpreter
    participant Val as Schema Validator
    participant Router as Decision Router
    participant Context as Context Evaluator
    participant Policy as Policy Engine
    participant Router as Decision Router
    participant Consent as Consent Manager
    participant Sandbox as Execution Sandbox
    participant Ledger as Audit Ledger
    
    User->>UI: "Pay canteen ₹50"
    UI->>LLM: Natural Language
    LLM->>Val: JSON Intent
    
    alt Invalid Schema
        Val->>Ledger: Log PARSE_ERROR
        Val->>UI: Show Error
    else Valid Schema
        Val->>Router: Valid Intent
        Router->>Context: Fetch Auth Context
        Context-->>Router: Balance, Velocity, Geo
        Router->>Policy: Evaluate (Intent + Context)
        Policy-->>Router: Result (APPROVE/DENY/VERIFY)
        
        alt Policy Result: DENY
            Router->>Ledger: Log Policy Violation
            Router->>UI: Reject Transaction
        else Policy Result: APPROVE
            Router->>Consent: Request Human Authorization
            Consent->>User: Display Consent Modal
            User->>Consent: Biometric Signature
            Consent-->>Router: Signed JWT
            Router->>Sandbox: Execute (Intent + JWT)
            Note over Sandbox: Validate JWT Hash == Intent Hash
            Sandbox->>Ledger: Append Immutable Entry
            Sandbox->>UI: Success Confirmation
        end
    end
```

### Step-by-Step Flow

1. **Input:** User speaks or types a command
2. **Interpretation:** LLM Agent converts text to JSON Intent
3. **Validation:** Schema Validator ensures JSON integrity
4. **Contextualization:** System fetches Balance and Velocity data
5. **Evaluation:** Policy Engine runs deterministic checks (Layers 1-4)
6. **Routing:** Decision Router determines the next step
7. **Authorization:** User signs a Consent Token (JWT)
8. **Execution:** Sandbox validates the Token and logs the transaction
9. **Feedback:** User receives a confirmation message

---

## Fraud Prevention Strategy

CAPS addresses specific fraud vectors inherent to Agentic AI systems.

### Fraud Vector Comparison

| Fraud Vector | Traditional System | CAPS Defense |
|--------------|-------------------|--------------|
| **Hallucination** | N/A | LLM output is treated as suggestion. Strict schema validation rejects unknown merchants |
| **Prompt Injection** | N/A | LLM has no access to system tools or bank APIs. It only outputs text |
| **Wallet Draining** | Rate limiting | Velocity limits (Layer 2) + hard caps (Layer 1) prevent rapid fund depletion |
| **Replay Attacks** | Session tokens | Consent tokens are single-use and bound by `intent_id` and timestamps |
| **Silent Automation** | Assumed safe | Mandatory human consent step for every transaction (Human-in-the-loop) |
| **Intent Splitting** | N/A | Pattern detection identifies micro-transaction sequences (e.g., 10 × ₹199) |

### Attack Surface Visualization

```mermaid
graph TB
    subgraph "Attack Vectors"
        A1[Prompt Injection]
        A2[Hallucination]
        A3[Wallet Draining]
        A4[Replay Attack]
        A5[Silent Automation]
        A6[Intent Splitting]
    end
    
    subgraph "Defense Layers"
        D1[Zero-Trust LLM<br/>No System Access]
        D2[Schema Validation<br/>Strict Typing]
        D3[Velocity Controls<br/>Rate Limiting]
        D4[Single-Use Tokens<br/>Cryptographic Binding]
        D5[Mandatory Consent<br/>Human-in-Loop]
        D6[Pattern Detection<br/>Intent Analysis]
    end
    
    A1 -.->|Blocked by| D1
    A2 -.->|Blocked by| D2
    A3 -.->|Blocked by| D3
    A4 -.->|Blocked by| D4
    A5 -.->|Blocked by| D5
    A6 -.->|Blocked by| D6
    
    style D1 fill:#1dd1a1
    style D2 fill:#1dd1a1
    style D3 fill:#1dd1a1
    style D4 fill:#1dd1a1
    style D5 fill:#1dd1a1
    style D6 fill:#1dd1a1
    
    style A1 fill:#ff6b6b
    style A2 fill:#ff6b6b
    style A3 fill:#ff6b6b
    style A4 fill:#ff6b6b
    style A5 fill:#ff6b6b
    style A6 fill:#ff6b6b
```

---

## Policy & Risk Engine

The Policy & Risk Engine is a deterministic, zero-trust control layer that treats both the user and the agent as potential risk sources.

### Decision Outputs

```
APPROVE | DENY | ESCALATE | REQUIRE_REAUTH | COOLDOWN
```

> [!IMPORTANT]
> This engine never consumes free-form LLM output — only validated structured intents + context snapshots.

---

### UPI Lite–Specific Risk Constraints

#### Balance & Limit Invariants

```python
txn_amount ≤ per_txn_cap (₹200-500)
daily_spend + txn_amount ≤ daily_cap (₹2000)
wallet_balance ≥ txn_amount
reload_frequency ≤ allowed_reload_rate
No overdraft / no auto-top-up without explicit consent
```

**Violation → DENY**

---

### Velocity & Burst Controls

Detect scripted or agent-driven abuse:

- Too many transactions in short window (e.g., N txns / 5 min)
- Repeated same-amount micro-payments (₹199 loops)
- Rapid merchant switching (spray pattern)
- Night-time anomaly vs user baseline

**Violation → COOLDOWN or ESCALATE**

---

### Agentic Payment–Specific Fraud Vectors

> [!CAUTION]
> These threats do not exist in traditional UPI, only in agent-mediated flows.

#### Agent Overreach Protection

**Rule:** Agent cannot chain actions:
- One intent → one execution
- No implicit retries unless explicit idempotency key

**Rule:** Agent cannot modify after approval:
- `merchant_id`
- `amount`
- `payee_vpa`

**Violation → DENY + Agent Session Kill**

---

#### Prompt / Reasoning Injection Defense

- Policy engine **ignores** LLM reasoning text
- Only consumes: `{intent_type, amount, merchant_id, user_id, consent_token}`
- Any attempt to smuggle logic via fields → `DENY`

---

#### 🔁 Recursive Agent Loops

Prevent self-triggering agents:

**Agent cannot trigger payments based on:**
- Previous payment success
- Webhook callbacks
- Internal logs

**Violation → HARD DENY**

---

### Merchant & Payee Risk Controls

#### Merchant Allow/Deny Lists

- Explicit UPI Lite merchant whitelist
- **Block:**
  - Newly registered VPAs
  - High-risk MCC categories
  - VPAs with abnormal refund/chargeback ratio

#### VPA Impersonation Detection

- Lookalike VPAs (typosquatting)
- Known brand keyword misuse
- Sudden merchant name changes

**Violation → ESCALATE**

---

### User Context & Behavioral Anomalies

#### Device & Session Integrity

- Device fingerprint mismatch
- New device + payment attempt
- Emulator / rooted device signals
- Session age < threshold

**Violation → REQUIRE_REAUTH**

---

#### Behavioral Drift Detection

- User usually does P2P → now merchant payments
- Average ₹50 txns → sudden ₹200 max attempts
- Time-of-day deviation

**Violation → ESCALATE**

---

### Consent & Mandate Enforcement

#### Explicit Consent Tokens

Every payment requires:
- `consent_token` scoped to:
  - Merchant
  - Amount range
  - Expiry
- Token non-reusable unless explicitly marked recurring

**No token → DENY**

---

#### Anti-Confused-Deputy Rule

Agent cannot reuse:
- Old consent
- Consent from different merchant
- Consent from different intent type

**Violation → DENY**

---

### Replay, Idempotency & Tampering Defense

#### Replay Attacks

- Unique `intent_id`
- Duplicate `intent_id` → NO-OP
- Modified payload with same ID → DENY

#### Payload Integrity

```
Hash(intent + context snapshot)
```

Any mismatch between approval & execution → **DENY**

---

### Escalation & Human-in-the-Loop Paths

**Escalation triggers:**
- Conflicting signals (safe amount but risky merchant)
- User behavior anomaly + agent confidence < threshold
- Edge-case rule collisions

**Escalation actions:**
- Ask user for clarification
- Require biometric / UPI PIN
- Route to manual review (future)

---

### Auditability & Compliance

Each policy decision logs:
- `intent_id`
- `policy_version`
- Rules triggered
- Decision outcome
- Cryptographic hashes

**Logs are:**
- Append-only
- Tamper-evident
- Replayable for forensic analysis

---

## Core Design Principle

> **The agent can suggest.**  
> **The system decides.**  
> **The wallet obeys only math and rules.**

Even if:
- LLM hallucinates
- Agent is compromised
- User prompt is malicious

**No money moves unless all deterministic gates pass.**

---

## Implementation Roadmap

```mermaid
gantt
    title CAPS Implementation Timeline
    dateFormat  YYYY-MM-DD
    section Phase 1
    Foundation & Agent Setup           :p1, 2026-01-01, 14d
    section Phase 2
    Context Engineering                :p2, after p1, 14d
    section Phase 3
    Policy Engine                      :p3, after p2, 21d
    section Phase 4
    Control Flow & Execution           :p4, after p3, 14d
    section Phase 5
    Safety & Auditing                  :p5, after p4, 14d
    section Phase 6
    Sandbox Testing                    :p6, after p5, 10d
    section Phase 7
    Modularization                     :p7, after p6, 7d
```

### Phase 1: Foundation & Agent Setup

**Goal:** Establish the local ADK environment and basic intent parsing.

**Tasks:**
- Initialize Antigravity/ADK environment
- Configure Gemini-based LLM Agent
- Define the JSON schema for Payment Intents

**Deliverable:** An agent that accepts text and outputs valid JSON objects

---

### Phase 2: Context Engineering

**Goal:** Ground the agent in reality without polluting the prompt.

**Tasks:**
- Build a Mock Context Service (REST API)
- Implement ADK OpenAPI Tool for `get_user_context()`
- Integrate context retrieval into the session memory, not the prompt

**Deliverable:** Agent can "see" user balance and location

---

### Phase 3: The Policy Engine

**Goal:** Implement the deterministic decision logic.

**Tasks:**
- Develop the Rule Engine (Python microservice)
- Implement Layer 1 (Hard Limits) and Layer 2 (Velocity) checks
- Expose the engine via an ADK Function Tool (`check_policy()`)

**Deliverable:** System correctly approves/denies requests based on mock balance

---

### Phase 4: Control Flow & Execution

**Goal:** Connect the brain to the hands.

**Tasks:**
- Implement the Decision Router using an ADK Sequential Agent
- Build the Mock Execution Engine with idempotency checks
- Create the `simulate_payment()` tool

**Deliverable:** End-to-end flow where valid intents result in logged "transactions"

---

### Phase 5: Safety & Auditing

**Goal:** Harden the system for security.

**Tasks:**
- Implement the Immutable Audit Ledger
- Add structured logging to all ADK tool callbacks
- Implement Consent Manager (JWT generation and validation)

**Deliverable:** A secure, auditable log of all actions

---

### Phase 6: Sandbox Testing

**Goal:** Stress test and edge-case verification.

**Tasks:**
- Simulate attacks (Prompt Injection, Intent Splitting)
- Verify "Fail-Closed" behavior on system errors
- Refine fallback logic for ambiguous intents

**Deliverable:** A stability report and hardened code

---

### Phase 7: Modularization

**Goal:** Prepare for scale.

**Tasks:**
- Refactor components into standalone Antigravity Skills
- Document API boundaries
- Prepare for potential integration with real PSP adapters

---

##  Technology Stack

| Component | Technology |
|-----------|-----------|
| **Core Framework** | Google Agent Development Kit (ADK) / Antigravity |
| **Language** | Python 3.10+ |
| **LLM** | Gemini (via Vertex AI or local distillation) |
| **Database** | SQLite / Redis (for local MVP state and ledger) |
| **Transport** | REST / gRPC for component communication |
| **Format** | JSON for all internal data interchange |
| **Testing** | pytest, locust (for load testing) |
| **Deployment** | Docker, Kubernetes (future) |

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

<div align="center">

**Built for a safer AI-powered payment future**

</div>
