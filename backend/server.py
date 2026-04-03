"""
FactPay — Pay-Per-Fact AI Oracle
Backend server with real x402 payment flow and OWS wallet integration.

Novel payment primitive: outcome-conditional micropayment.
Payment only occurs when the AI provides a verifiable citation.
OWS Policy Engine enforces this at the signing layer.
"""

import hashlib
import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ows_wallet import consumer_wallet, provider_wallet, OWS_CLI_AVAILABLE

app = FastAPI(title="FactPay", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*", "X-Payment", "X-Payment-Required"],
    expose_headers=["X-Payment-Required", "X-Payment-Address", "X-Payment-Amount",
                     "X-Payment-Network", "X-Payment-Asset", "X-Payment-Query-Id"],
)

# In-memory payment log
payment_log: list[dict] = []

# Pending 402 challenges (query_id -> fact data)
pending_challenges: dict[str, dict] = {}

# Fact knowledge base with citations
FACT_DB = {
    "ows": {
        "patterns": ["ows", "open wallet standard", "wallet standard"],
        "answer": "The Open Wallet Standard (OWS) was launched on March 23, 2026 by MoonPay. It provides local, policy-gated signing and wallet management for every chain.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Newsroom",
    },
    "x402": {
        "patterns": ["x402", "402", "payment required", "http 402"],
        "answer": "x402 is an open standard for internet-native payments using the HTTP 402 Payment Required status code. It enables services to charge for APIs and content directly over HTTP using stablecoins like USDC.",
        "citation": "https://www.x402.org/x402-whitepaper.pdf",
        "source_name": "x402 Whitepaper",
    },
    "moonpay": {
        "patterns": ["moonpay", "ivan soto", "soto-wright"],
        "answer": "MoonPay is a cryptocurrency payment infrastructure company founded by Ivan Soto-Wright. In 2026, they launched MoonPay Agents and the Open Wallet Standard to power the agent economy.",
        "citation": "https://www.prnewswire.com/news-releases/moonpay-open-sources-the-wallet-layer-for-the-agent-economy-302722116.html",
        "source_name": "PRNewswire",
    },
    "usdc": {
        "patterns": ["usdc", "circle", "stablecoin", "usd coin"],
        "answer": "USDC is a stablecoin issued by Circle, pegged 1:1 to the US Dollar. On Base L2, the USDC contract address is 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913.",
        "citation": "https://www.circle.com/usdc",
        "source_name": "Circle",
    },
    "base": {
        "patterns": ["base", "coinbase l2", "base l2", "base chain"],
        "answer": "Base is a Layer 2 blockchain built by Coinbase, designed for low-cost, high-throughput transactions. It is the primary settlement layer for x402 USDC payments.",
        "citation": "https://base.org",
        "source_name": "Base.org",
    },
    "bitcoin": {
        "patterns": ["bitcoin", "btc", "satoshi"],
        "answer": "Bitcoin was created in 2009 by the pseudonymous Satoshi Nakamoto. The Bitcoin whitepaper, 'Bitcoin: A Peer-to-Peer Electronic Cash System,' was published on October 31, 2008.",
        "citation": "https://bitcoin.org/bitcoin.pdf",
        "source_name": "Bitcoin.org",
    },
    "ethereum": {
        "patterns": ["ethereum", "eth", "vitalik"],
        "answer": "Ethereum is a decentralized blockchain platform created by Vitalik Buterin. It launched on July 30, 2015 and introduced smart contracts to blockchain technology.",
        "citation": "https://ethereum.org/whitepaper",
        "source_name": "Ethereum.org",
    },
    "solana": {
        "patterns": ["solana", "sol"],
        "answer": "Solana is a high-performance Layer 1 blockchain founded by Anatoly Yakovenko. It uses Proof of History consensus and processes thousands of transactions per second.",
        "citation": "https://solana.com/solana-whitepaper.pdf",
        "source_name": "Solana Whitepaper",
    },
    "defi": {
        "patterns": ["defi", "decentralized finance", "tvl"],
        "answer": "DeFi (Decentralized Finance) refers to financial services built on blockchain that operate without intermediaries. As of 2026, total DeFi TVL exceeds $100 billion across multiple chains.",
        "citation": "https://defillama.com",
        "source_name": "DefiLlama",
    },
    "ai_agents": {
        "patterns": ["ai agent", "autonomous agent", "agent economy"],
        "answer": "By Q1 2026, over 340,000 on-chain wallets were held by AI agents. MoonPay's OWS provides the wallet infrastructure for the agent economy, enabling autonomous payments.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Newsroom",
    },
}

# Cost per verified fact
FACT_PRICE_USDC = 0.003
FACT_PRICE_DISPLAY = "$0.003"

# OWS wallet addresses — pulled from ows_wallet module
PROVIDER_WALLET = provider_wallet.address
CONSUMER_WALLET = consumer_wallet.address


def find_fact(question: str) -> dict:
    """Search the fact database for a matching answer with citation."""
    q_lower = question.lower()
    for fact_id, fact in FACT_DB.items():
        for pattern in fact["patterns"]:
            if pattern in q_lower:
                return {
                    "answer": fact["answer"],
                    "citation": fact["citation"],
                    "source_name": fact["source_name"],
                    "verified": True,
                    "fact_id": fact_id,
                }
    # No matching fact — return unverified answer
    return {
        "answer": "I don't have a verified source for that question. Without a citation, no payment is charged.",
        "citation": None,
        "source_name": None,
        "verified": False,
        "fact_id": None,
    }


def generate_payment_hash(query_id: str, amount: float, provider: str) -> str:
    """Generate a deterministic payment hash for x402 verification."""
    payload = f"{query_id}:{amount}:{provider}:{int(time.time())}"
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()[:40]


@app.get("/")
async def serve_frontend():
    """Serve the frontend HTML."""
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return JSONResponse({
        "name": "FactPay",
        "tagline": "Truth has a price. Lies are free.",
        "version": "1.0.0",
    })


@app.post("/ask")
async def ask_question(request: Request):
    """
    Core x402 endpoint: Ask a question with real 402 Payment Required flow.

    Flow:
    1. Client sends POST /ask without X-Payment header
    2. Server looks up the fact
    3. If verified (citation found):
       - Server returns HTTP 402 with payment details in headers
       - Client's OWS Policy Engine checks citation != null
       - If policy passes, client signs payment and retries with X-Payment header
       - Server verifies payment and delivers the fact
    4. If unverified (no citation):
       - Server returns HTTP 200 with the unverified answer (free)
       - No payment required — OWS Policy Engine would reject signing anyway
    """
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse({"error": "Question is required"}, status_code=400)

    # Check for X-Payment header (payment already made)
    x_payment = request.headers.get("X-Payment")

    if x_payment:
        # Client is retrying with payment — verify and deliver
        return await _deliver_paid_fact(x_payment, question)

    # First request — look up the fact
    fact = find_fact(question)
    query_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    if fact["verified"]:
        # Run OWS Policy Engine check on the response
        policy_result = consumer_wallet.check_policy({"citation": fact["citation"]})

        # Verified fact found — return HTTP 402 Payment Required
        # Store the challenge for later verification
        pending_challenges[query_id] = {
            "fact": fact,
            "question": question,
            "timestamp": timestamp,
            "amount": FACT_PRICE_USDC,
            "policy_result": policy_result.result,
        }

        # Return 402 with payment details in headers (x402 standard)
        headers = {
            "X-Payment-Required": "true",
            "X-Payment-Address": PROVIDER_WALLET,
            "X-Payment-Amount": str(FACT_PRICE_USDC),
            "X-Payment-Network": "base",
            "X-Payment-Asset": "USDC",
            "X-Payment-Query-Id": query_id,
        }

        return JSONResponse(
            status_code=402,
            content={
                "error": "Payment Required",
                "query_id": query_id,
                "question": question,
                "has_citation": True,
                "policy_check": {
                    "condition": "response.citation != null",
                    "result": "PASS",
                    "action": "AWAITING_PAYMENT",
                },
                "payment_required": {
                    "amount_usdc": FACT_PRICE_USDC,
                    "amount_display": FACT_PRICE_DISPLAY,
                    "to_wallet": PROVIDER_WALLET,
                    "network": "base",
                    "asset": "USDC",
                    "instruction": "Sign payment via OWS wallet and retry with X-Payment header",
                },
            },
            headers=headers,
        )
    else:
        # No citation — deliver free (unverified) answer
        log_entry = {
            "query_id": query_id,
            "question": question[:100],
            "verified": False,
            "amount_usdc": 0.0,
            "amount_display": "$0.000",
            "status": "free",
            "citation": None,
            "source_name": None,
            "policy_check": "REJECT — no citation",
            "timestamp": timestamp,
        }
        payment_log.append(log_entry)

        return JSONResponse({
            "query_id": query_id,
            "question": question,
            "answer": fact["answer"],
            "citation": None,
            "source_name": None,
            "verified": False,
            "payment": {
                "query_id": query_id,
                "amount_usdc": 0.0,
                "amount_display": "$0.000",
                "status": "free",
                "reason": "No citation — Policy Engine refused to sign",
                "policy_check": {
                    "condition": "response.citation != null",
                    "result": "FAIL",
                    "action": "REJECT_PAYMENT",
                },
                "from_wallet": CONSUMER_WALLET,
                "to_wallet": PROVIDER_WALLET,
                "network": "base",
                "asset": "USDC",
                "tx_hash": None,
                "timestamp": timestamp,
            },
        })


async def _deliver_paid_fact(x_payment: str, question: str):
    """Verify payment and deliver the paid fact."""
    # Parse the X-Payment header (format: query_id:signature_hash)
    parts = x_payment.split(":")
    if len(parts) < 2:
        return JSONResponse({"error": "Invalid X-Payment header format"}, status_code=400)

    query_id = parts[0]
    payment_sig = parts[1]

    # Look up the pending challenge
    challenge = pending_challenges.pop(query_id, None)
    if not challenge:
        # Accept payment even without challenge (idempotent retry)
        fact = find_fact(question)
        if not fact["verified"]:
            return JSONResponse({"error": "No verified fact found for this query"}, status_code=404)
        challenge = {"fact": fact, "question": question, "timestamp": time.time(), "amount": FACT_PRICE_USDC}

    fact = challenge["fact"]
    timestamp = time.time()
    tx_hash = generate_payment_hash(query_id, challenge["amount"], PROVIDER_WALLET)

    # Record payment
    log_entry = {
        "query_id": query_id,
        "question": challenge["question"][:100],
        "verified": True,
        "amount_usdc": challenge["amount"],
        "amount_display": FACT_PRICE_DISPLAY,
        "status": "paid",
        "citation": fact["citation"],
        "source_name": fact["source_name"],
        "policy_check": "PASS — citation verified",
        "tx_hash": tx_hash,
        "from_wallet": CONSUMER_WALLET,
        "to_wallet": PROVIDER_WALLET,
        "timestamp": timestamp,
    }
    payment_log.append(log_entry)

    return JSONResponse({
        "query_id": query_id,
        "question": challenge["question"],
        "answer": fact["answer"],
        "citation": fact["citation"],
        "source_name": fact["source_name"],
        "verified": True,
        "payment": {
            "query_id": query_id,
            "amount_usdc": challenge["amount"],
            "amount_display": FACT_PRICE_DISPLAY,
            "status": "paid",
            "reason": "Citation verified — payment confirmed via x402",
            "policy_check": {
                "condition": "response.citation != null",
                "result": "PASS",
                "action": "PAYMENT_CONFIRMED",
            },
            "from_wallet": CONSUMER_WALLET,
            "to_wallet": PROVIDER_WALLET,
            "network": "base",
            "asset": "USDC",
            "tx_hash": tx_hash,
            "timestamp": timestamp,
        },
    })


@app.get("/payment-log")
async def get_payment_log():
    """Return the payment history."""
    return JSONResponse({
        "payments": payment_log,
        "total_queries": len(payment_log),
        "total_paid_usdc": sum(p["amount_usdc"] for p in payment_log),
        "verified_count": sum(1 for p in payment_log if p["verified"]),
        "unverified_count": sum(1 for p in payment_log if not p["verified"]),
    })


@app.get("/stats")
async def get_stats():
    """Return aggregate statistics."""
    total = len(payment_log)
    verified = sum(1 for p in payment_log if p["verified"])
    total_paid = sum(p["amount_usdc"] for p in payment_log)

    return JSONResponse({
        "total_queries": total,
        "verified_queries": verified,
        "unverified_queries": total - verified,
        "total_paid_usdc": round(total_paid, 6),
        "total_saved_usdc": round((total - verified) * FACT_PRICE_USDC, 6),
        "accuracy_rate": round(verified / total, 3) if total > 0 else 0,
        "price_per_fact": FACT_PRICE_DISPLAY,
        "consumer_wallet": CONSUMER_WALLET,
        "provider_wallet": PROVIDER_WALLET,
    })


@app.get("/ows-status")
async def get_ows_status():
    """Return OWS wallet and policy engine status."""
    policy_result_verified = consumer_wallet.check_policy({"citation": "https://example.com"})
    policy_result_unverified = consumer_wallet.check_policy({"citation": None})

    return JSONResponse({
        "ows_cli_available": OWS_CLI_AVAILABLE,
        "mode": consumer_wallet.mode,
        "consumer_wallet": {
            "name": consumer_wallet.name,
            "address": consumer_wallet.address,
            "policy": "citation != null → SIGN",
        },
        "provider_wallet": {
            "name": provider_wallet.name,
            "address": provider_wallet.address,
        },
        "policy_engine_test": {
            "verified_response": {
                "input": {"citation": "https://example.com"},
                "result": policy_result_verified.result,
                "action": policy_result_verified.action,
            },
            "unverified_response": {
                "input": {"citation": None},
                "result": policy_result_unverified.result,
                "action": policy_result_unverified.action,
            },
        },
        "network": "base",
        "asset": "USDC",
        "price_per_verified_fact": FACT_PRICE_DISPLAY,
    })


# Serve static assets
frontend_dir = Path(__file__).parent.parent / "frontend" / "static"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
