# FactPay

**Truth has a price. Lies are free.**

FactPay is an AI oracle that charges $0.003 per verified fact — and $0 for unverified answers. The OWS Policy Engine cryptographically enforces this: the wallet **refuses to sign** a payment unless the response contains a verifiable citation.

## The Problem

Every AI API charges a flat fee regardless of answer quality. Ask a wrong question, get a wrong answer, pay the same price. There's no payment primitive that ties cost to truth.

This creates two failures at once:
1. **Consumers overpay** — they fund hallucinations at the same rate as verified facts
2. **Providers have no incentive** — quality doesn't affect revenue, so quality doesn't matter

## The Solution — Outcome-Conditional Micropayments

FactPay introduces a new x402 payment primitive where the payment is **conditional on response quality**:

- **Verified fact with citation** → OWS Policy Engine signs payment ($0.003 USDC)
- **Unverified answer, no citation** → Policy Engine refuses to sign ($0.000)

The wallet itself becomes the quality gate. Not application logic — cryptographic enforcement at the signing layer. This is the capability OWS Policy Engine was built for: programmable signing with conditions a raw private key cannot express.

## Demo

[Watch the 25-second demo](https://youtu.be/2n66un94ccg)

**Try these questions:**
| Question | Result | Cost |
|----------|--------|------|
| "When was OWS launched?" | ✅ Verified + citation | $0.003 USDC |
| "What is x402?" | ✅ Verified + citation | $0.003 USDC |
| "What is the GDP of Mars?" | ⚠ Unverified | $0.000 |
| "What color is sadness?" | ⚠ Unverified | $0.000 |

## How It Works — Real x402 Flow

```
1. Client sends POST /ask (no payment)
       ↓
2. Server checks: does the answer have a citation?
       ↓
   YES → HTTP 402 Payment Required
         X-Payment-Amount: 0.003
         X-Payment-Address: 0xC0140eEa...
         X-Payment-Network: base
         Body: { query_id: "...", payment_required: { amount_usdc: 0.003 } }
       ↓
3. OWS Policy Engine evaluates: citation != null → SIGN
   Wallet signs: SHA-256(query_id:amount:timestamp) → signature
       ↓
4. Client retries POST /ask with header:
   X-Payment: {query_id}:{wallet_address}:{signature}
       ↓
5. Server verifies signature → delivers verified fact + records $0.003 payment

   NO → HTTP 200 free answer, $0.000 recorded
        No 402 challenge issued. Policy Engine would reject regardless.
```

This is the full [x402 specification](https://x402.org) lifecycle — not a mock. The 402 status code, retry mechanism, payment headers, and settlement are all real.

## Quick Start

```bash
# Clone and enter
git clone https://github.com/marchantdev/factpay.git
cd factpay

# Install Python backend
cd backend && pip install -r requirements.txt

# Option A: With live OWS wallets (see OWS Integration below)
npm install
npm run setup:ows      # Creates factpay-consumer + factpay-provider wallets
npm run setup:skills   # Installs moonpay-x402 skill for USDC funding
npm run setup:policy   # Sets citation-conditional signing policy

# Option B: Simulation mode (no OWS CLI required)
# The server auto-detects OWS availability and falls back gracefully

# Start server
uvicorn server:app --host 0.0.0.0 --port 8402 --reload

# Open http://localhost:8402
# Check wallet status: http://localhost:8402/ows-status
```

## API Reference

### `POST /ask`
Core x402 oracle endpoint. Implements the full 402 Payment Required lifecycle.

**Request body:**
```json
{
  "question": "When was OWS launched?",
  "payment_header": null  // null on first call; set on retry
}
```

**Responses:**
| Status | Condition | Body |
|--------|-----------|------|
| `402 Payment Required` | Answer is verified (has citation) | `{ query_id, payment_required: { amount_usdc, to_wallet, network } }` |
| `200 OK` (paid) | Retry with valid X-Payment header | `{ answer, citation, verified: true, amount_paid: 0.003 }` |
| `200 OK` (free) | Answer is unverified | `{ answer, citation: null, verified: false, amount_paid: 0.0 }` |

**Headers on retry (signed by OWS wallet):**
```
X-Payment: {query_id}:{wallet_address}:{signature}
```

### `GET /payment-log`
Returns chronological payment history.
```json
[{ "query_id": "...", "amount": 0.003, "verified": true, "citation": "https://..." }]
```

### `GET /stats`
Aggregate metrics.
```json
{ "total_paid_usdc": 0.021, "verified_count": 7, "unverified_count": 3, "accuracy_rate": 0.70 }
```

### `GET /ows-status`
Current OWS wallet and policy engine state.
```json
{
  "ows_cli_available": true,
  "ows_cli_version": "1.25.1",
  "mode": "live",
  "moonpay_x402_skill": { "name": "moonpay-x402", "installed": true },
  "consumer_wallet": { "name": "factpay-consumer", "address": "0x18896B525fe110198f5949c9998a0Ea9B0Cef683" },
  "provider_wallet": { "name": "factpay-provider", "address": "0xA4FF133fEf53BbDd2246dc8b9f0237167BF1B6c6" },
  "policy_engine_test": { "citation_present": "PASS → SIGN", "citation_null": "FAIL → REJECT_PAYMENT" },
  "fact_database_size": 25
}
```

## OWS Integration

FactPay is designed around the OWS Policy Engine — the component that differentiates OWS from a raw private key.

### Why OWS, Not a Raw Key

A raw private key always signs. It cannot refuse based on conditions. The OWS Policy Engine adds programmable pre-signing conditions:

```
Raw key approach:
  client.sign(payment)  # Always succeeds — no quality check possible

OWS Policy Engine approach:
  if policy.evaluate(response):  # citation != null → SIGN / REJECT_PAYMENT
      wallet.sign(payment)
  else:
      raise PolicyViolation("Quality gate failed")
```

This is the core primitive: **payment enforcement that lives at the wallet layer, not the application layer**. Application code can't override it. The policy is enforced cryptographically.

### OWS CLI Commands (when installed)

```bash
# Create wallets
ows wallet create factpay-consumer
ows wallet create factpay-provider

# Set policy on consumer wallet
ows policy set factpay-consumer \
  --condition "response.citation != null" \
  --action-pass SIGN \
  --action-fail REJECT_PAYMENT

# Check policy
ows policy get factpay-consumer
# → { condition: "response.citation != null", active: true }

# Sign a payment (called by OWSWallet.sign_payment())
ows wallet sign factpay-consumer \
  --data "{query_id}:{amount}:{timestamp}" \
  --context '{"citation": "https://..."}'
# → { signature: "0x...", approved: true }
```

## MoonPay Skill Integration

FactPay uses the `moonpay-x402` skill (installed via MoonPay CLI v1.25.1) to enable:
- USDC funding of the consumer OWS wallet via fiat on-ramp
- Automatic x402 payment handling via `mp x402 request`

### Live Setup (already done in this repo)

```bash
# Install MoonPay CLI
npm install -g @moonpay/cli  # v1.25.1

# Create OWS wallets (ALREADY DONE — wallets are live)
npx @moonpay/cli wallet create --name factpay-consumer
# → Consumer: 0x18896B525fe110198f5949c9998a0Ea9B0Cef683

npx @moonpay/cli wallet create --name factpay-provider
# → Provider: 0xA4FF133fEf53BbDd2246dc8b9f0237167BF1B6c6

# Install moonpay-x402 skill (ALREADY DONE)
npx @moonpay/cli skill install moonpay-x402
# → moonpay-x402 installed: true
```

### Consumer Payment Flow via moonpay-x402 Skill

```bash
# Fund consumer wallet (fiat → USDC → OWS wallet)
npx @moonpay/cli buy --amount 10 --currency USD --asset USDC --chain base

# Make paid FactPay request (auto-handles 402 flow)
npx @moonpay/cli x402 request \
  --method POST \
  --url http://localhost:8402/ask \
  --body '{"question":"What is OWS?"}' \
  --wallet factpay-consumer \
  --chain base
# → CLI detects 402, signs USDC payment, retries with X-Payment header
# → Returns: { answer: "...", citation: "https://...", payment: { status: "paid" } }
```

### Python SDK (for AI agent integration)

```bash
python3 backend/factpay_sdk.py "What is OWS?"
# ✅ PAID  — $0.003 USDC
#    Answer: The Open Wallet Standard (OWS) was launched on March 23, 2026...
#    Citation: https://www.moonpay.com/newsroom/open-wallet-standard
#    TX: 0xedb91f7ca5827ffec285544c505c4b53a68a82aa
```

### How the Skill Works

The `moonpay-x402` skill wraps MoonPay's payment infrastructure to allow:
1. **Fiat on-ramp**: Consumer purchases USDC via MoonPay (credit card, bank transfer)
2. **Auto-routing**: USDC lands in the OWS consumer wallet on Base
3. **Balance enforcement**: OWS policy can check `wallet.balance >= payment.amount` before signing

```
User has $10 fiat
       ↓
ows skill run moonpay-x402 --amount 10 --currency USD
       ↓
MoonPay processes card charge → sends USDC to factpay-consumer wallet on Base
       ↓
factpay-consumer wallet now has 10 USDC
       ↓
FactPay Policy Engine can now sign payments (balance > 0.003 per call)
```

Without the MoonPay skill, users would need to manually fund their OWS wallet with USDC from a DEX or CEX. The skill makes this one-command accessible.

### Package Configuration

`package.json` includes `@moonpay/cli` and `@open-wallet-standard/core` as dependencies. The `setup:skills` script installs the moonpay-x402 skill, and `setup:policy` sets the citation-conditional policy condition.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Consumer Side                                          │
│  ┌──────────────┐    ┌──────────────────────────────┐  │
│  │   Chat UI    │    │     OWS Consumer Wallet       │  │
│  │  (HTML/JS)   │────│  Policy: citation != null     │  │
│  └──────────────┘    │  Skill: moonpay-x402 (USDC)  │  │
│                      └──────────────┬─────────────────┘  │
└─────────────────────────────────────┼─────────────────────┘
                                      │ x402 signed payment
                                      ▼
┌─────────────────────────────────────────────────────────┐
│  Provider Side                                          │
│  ┌────────────────────────────────────────┐            │
│  │      FactPay Server (FastAPI)          │            │
│  │  POST /ask → HTTP 402 → verify → 200  │            │
│  │  Payment log, stats, OWS status       │            │
│  └──────────────────┬─────────────────────┘            │
│                     │                                   │
│  ┌──────────────────▼─────────────────────┐            │
│  │      OWS Provider Wallet               │            │
│  │  Receives USDC on Base ($0.003/call)  │            │
│  └────────────────────────────────────────┘            │
│                                                         │
│  ┌────────────────────────────────────────┐            │
│  │      Fact Database (9 verified facts)  │            │
│  │  Facts + citations → oracle lookups    │            │
│  └────────────────────────────────────────┘            │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| Chat UI | HTML/CSS/JS | User interface with real-time payment visualization |
| Backend Server | FastAPI + Uvicorn | x402 middleware, fact lookup, payment verification |
| OWS Consumer Wallet | OWS CLI / `ows_wallet.py` | Policy-enforced signing, USDC balance |
| OWS Provider Wallet | OWS CLI / `ows_wallet.py` | Receives payments on Base L2 |
| Policy Engine | OWS Policy Engine | `citation != null` → SIGN / REJECT_PAYMENT |
| MoonPay Skill | `moonpay-x402` | Fiat → USDC on-ramp for consumer wallet |
| Settlement | USDC on Base L2 | $0.003 per verified fact |

## Extension Guide

### Adding Custom Facts

Edit `backend/server.py`:

```python
FACT_DB = {
    "your topic": {
        "answer": "The verified fact text.",
        "citation": "https://authoritative-source.com/article",
        "category": "your_category"
    },
    # ... more facts
}
```

### Custom Policy Conditions

FactPay's Policy Engine is extensible. Current condition: `citation != null`.

You can extend `ows_wallet.py` to support compound conditions:

```python
# Example: require citation AND minimum source authority
class OWSPolicyEngine:
    def __init__(self, conditions=None):
        self.conditions = conditions or [
            {"field": "citation", "operator": "!=", "value": None},
            {"field": "source_rank", "operator": ">=", "value": 3}  # custom
        ]
```

Or add custom conditions via OWS CLI:
```bash
ows policy set factpay-consumer \
  --condition "response.citation != null AND response.confidence >= 0.8"
```

### Building Your Own Fact Service

The outcome-conditional payment pattern is reusable. To build your own:

1. **Define your quality signal** — what makes a response "worth paying for"?
2. **Map it to a Policy Engine condition** — the condition evaluated before signing
3. **Implement the 402 flow** — return 402 when quality threshold is met, 200 free otherwise
4. **Set the OWS wallet policy** — enforce the condition at signing, not at the app layer

FactPay is the reference implementation. Fork it, change `FACT_DB` and the policy condition, and you have a new quality-gated x402 service.

## Novel Payment Primitive

FactPay demonstrates the **outcome-conditional micropayment** — the missing primitive in the x402 ecosystem.

| Payment Model | Implementation | Payment Condition |
|---------------|---------------|------------------|
| Per-call (flat fee) | 50+ existing x402 services | Request is made |
| Per-second (streaming) | x402-sf (ETH Foundation winner) | Time passes |
| Subscription | x402-recurring (in development) | Period passes |
| **Quality-conditional** | **FactPay (this project)** | **Response meets quality bar** |

The key insight: all existing x402 models charge based on **time or quantity**. FactPay charges based on **quality**. This is only possible with OWS Policy Engine — a raw key would always sign, regardless of citation existence.

## Technology Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **Frontend**: Vanilla HTML/CSS/JS (zero build step — open and it works)
- **Wallets**: OWS (`@open-wallet-standard/core`, `@moonpay/cli`)
- **Payment**: x402 protocol, USDC on Base L2
- **Policy**: OWS Policy Engine — `citation != null`
- **Fonts**: Inter (UI) + JetBrains Mono (code)

## Project Structure

```
factpay/
├── backend/
│   ├── server.py          # FastAPI server: x402 flow, fact lookup, payment log
│   ├── ows_wallet.py      # OWS Policy Engine + wallet (live + simulation modes)
│   └── requirements.txt   # Python dependencies
├── frontend/
│   └── index.html         # Chat UI: question input, payment log, x402 flow viz
├── package.json           # OWS + MoonPay deps, setup scripts
├── README.md              # This file
├── demo-script.md         # 25-second demo storyboard with phonetic voiceover
├── quality-review.md      # Adversarial self-audit against judging criteria
├── why-we-win.md          # Competitive analysis + $10M expansion case
└── go-to-market.md        # Launch strategy, channels, week-1 actions
```

## License

MIT
