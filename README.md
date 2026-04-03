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

## How It Works — Real x402 Flow

```
1. Client sends POST /ask (no payment)
        ↓
2. Server checks: does the answer have a citation?
        ↓
   YES → Server returns HTTP 402 Payment Required
         Headers: X-Payment-Amount, X-Payment-Address, X-Payment-Network
         Body: { payment_required: { amount_usdc: 0.003, to_wallet: "0xC014..." } }
        ↓
3. OWS Policy Engine checks: citation != null → SIGN
        ↓
4. Client retries POST /ask with X-Payment header (signed by OWS wallet)
        ↓
5. Server verifies payment → delivers verified fact ($0.003)

   NO → Server returns HTTP 200 with free answer ($0.000)
        No 402 challenge. Policy Engine would reject signing anyway.
```

## Quick Start

```bash
# Clone
git clone https://github.com/marchantdev/factpay.git
cd factpay

# Install Python dependencies
pip install fastapi uvicorn

# Install OWS + MoonPay skills (optional — falls back to simulation mode)
npm install
npm run setup:ows      # Create consumer + provider wallets
npm run setup:skills   # Install moonpay-x402 skill
npm run setup:policy   # Set citation-conditional policy

# Run
cd backend && uvicorn server:app --host 0.0.0.0 --port 8402

# Open http://localhost:8402
# Check OWS status: http://localhost:8402/ows-status
```

## Demo

[Watch the 25-second demo video](https://youtu.be/2n66un94ccg)

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
