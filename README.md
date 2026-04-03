# FactPay

**Truth has a price. Lies are free.**

FactPay is an AI oracle that charges $0.003 per verified fact — and $0 for unverified answers. The OWS Policy Engine cryptographically enforces this: the wallet **refuses to sign** a payment unless the response contains a verifiable citation.

## The Problem

Every AI API charges a flat fee regardless of answer quality. Ask a wrong question, get a wrong answer, pay the same price. There's no payment primitive that ties cost to truth.

## The Solution

FactPay introduces **outcome-conditional micropayments** — a new x402 payment primitive where the payment is conditional on response quality:

- **Verified fact with citation** → OWS Policy Engine signs payment ($0.003 USDC)
- **Unverified answer, no citation** → Policy Engine refuses to sign ($0.000)

The wallet itself becomes the quality gate. Not application logic — cryptographic enforcement.

## How It Works

```
User asks question
    ↓
FactPay queries fact service via x402
    ↓
Service returns: answer + citation (or null)
    ↓
OWS Policy Engine checks: citation != null?
    ├── YES → Signs USDC payment → Delivers verified fact ($0.003)
    └── NO  → Refuses to sign → Delivers free answer ($0.000)
```

## Quick Start

```bash
# Clone
git clone https://github.com/marchantdev/factpay.git
cd factpay

# Install dependencies
pip install fastapi uvicorn httpx python-dotenv

# Run
cd backend && uvicorn server:app --host 0.0.0.0 --port 8402

# Open http://localhost:8402
```

## Demo

Ask verified questions and see payments flow. Ask unverifiable questions and watch the wallet refuse.

**Try these:**
- "When was OWS launched?" → ✅ Verified, $0.003
- "What is x402?" → ✅ Verified, $0.003
- "What is the GDP of Mars?" → ⚠ Unverified, $0.000
- "What color is sadness?" → ⚠ Unverified, $0.000

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Chat UI   │────▶│  FactPay Server  │────▶│  Fact Data APIs │
│  (HTML/JS)  │◀────│  (FastAPI + x402) │◀────│  (x402-gated)   │
└──────┬──────┘     └────────┬─────────┘     └─────────────────┘
       │                     │
       │              ┌──────▼──────┐
       └─────────────▶│  OWS Wallet │
                      │  + Policy   │
                      │    Engine   │
                      └─────────────┘
```

### Components

| Component | Technology | Role |
|-----------|-----------|------|
| Chat UI | HTML/CSS/JS | User interface with payment visualization |
| Backend | FastAPI | x402 payment middleware, fact lookup |
| OWS Wallet | OWS CLI/SDK | Consumer + provider wallets |
| Policy Engine | OWS Policy Engine | Citation-conditional signing |
| Settlement | USDC on Base | Payment currency |

## OWS Integration

- **Consumer wallet**: Pays for verified facts
- **Provider wallet**: Receives payments
- **Policy Engine**: Enforces `citation != null` before signing
- **x402 flow**: Full HTTP 402 Payment Required lifecycle
- **MoonPay skill**: `moonpay-x402` for payment requests

## Novel Payment Primitive

FactPay introduces the **outcome-conditional micropayment** — the first x402 payment model where the response determines whether payment occurs.

| Existing x402 | FactPay |
|---------------|---------|
| Pay per API call (flat fee) | Pay per **verified fact** |
| Payment regardless of quality | Payment conditional on citation |
| App-layer logic controls payment | OWS Policy Engine controls signing |

## Technology Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn
- **Frontend**: Vanilla HTML/CSS/JS (no build step)
- **Wallet**: OWS (`@open-wallet-standard/core`)
- **Payment**: x402 protocol, USDC on Base L2
- **Fonts**: Inter + JetBrains Mono

## Project Structure

```
factpay/
├── backend/
│   ├── server.py          # FastAPI server with x402 flow
│   └── requirements.txt   # Python dependencies
├── frontend/
│   └── index.html         # Chat UI with payment visualization
├── package.json           # Node.js config for OWS
└── README.md              # This file
```

## License

MIT
