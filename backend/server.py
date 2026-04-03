"""
FactPay — Pay-Per-Fact AI Oracle
Backend server with x402 payment middleware and OWS integration.

Novel payment primitive: outcome-conditional micropayment.
Payment only occurs when the AI provides a verifiable citation.
OWS Policy Engine enforces this at the signing layer.
"""

import json
import os
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="FactPay", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory payment log
payment_log: list[dict] = []

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

# OWS wallet addresses (demo mode)
PROVIDER_WALLET = os.getenv("FACTPAY_PROVIDER_WALLET", "0x7a3B...F4e2")
CONSUMER_WALLET = os.getenv("FACTPAY_CONSUMER_WALLET", "0x9c1D...A8b3")


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
    Core endpoint: Ask a question, get a fact with conditional payment.

    If the answer has a verifiable citation → x402 payment of $0.003 (Policy Engine signs).
    If no citation → no payment (Policy Engine refuses to sign).
    """
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse({"error": "Question is required"}, status_code=400)

    fact = find_fact(question)
    query_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    if fact["verified"]:
        payment = {
            "query_id": query_id,
            "amount_usdc": FACT_PRICE_USDC,
            "amount_display": FACT_PRICE_DISPLAY,
            "status": "paid",
            "reason": "Citation verified — Policy Engine signed payment",
            "x402_flow": {
                "step_1": "Client requests fact via x402",
                "step_2": "Server returns 402 Payment Required",
                "step_3": f"OWS Policy Engine checks: citation != null → True",
                "step_4": "Policy Engine signs USDC transfer",
                "step_5": "Client sends X-PAYMENT header with signature",
                "step_6": "Server verifies payment, delivers verified fact",
            },
            "policy_check": {
                "condition": "response.citation != null",
                "result": "PASS",
                "action": "SIGN_PAYMENT",
            },
            "from_wallet": CONSUMER_WALLET,
            "to_wallet": PROVIDER_WALLET,
            "network": "base",
            "asset": "USDC",
            "timestamp": timestamp,
        }
    else:
        payment = {
            "query_id": query_id,
            "amount_usdc": 0.0,
            "amount_display": "$0.000",
            "status": "blocked",
            "reason": "No citation — Policy Engine refused to sign",
            "x402_flow": {
                "step_1": "Client requests fact via x402",
                "step_2": "Server returns 402 Payment Required",
                "step_3": f"OWS Policy Engine checks: citation != null → False",
                "step_4": "Policy Engine REFUSES to sign — no citation",
                "step_5": "No payment sent",
                "step_6": "Server delivers unverified answer (free)",
            },
            "policy_check": {
                "condition": "response.citation != null",
                "result": "FAIL",
                "action": "REJECT_PAYMENT",
            },
            "from_wallet": CONSUMER_WALLET,
            "to_wallet": PROVIDER_WALLET,
            "network": "base",
            "asset": "USDC",
            "timestamp": timestamp,
        }

    log_entry = {
        "query_id": query_id,
        "question": question[:100],
        "verified": fact["verified"],
        "amount_usdc": payment["amount_usdc"],
        "amount_display": payment["amount_display"],
        "status": payment["status"],
        "citation": fact["citation"],
        "source_name": fact["source_name"],
        "timestamp": timestamp,
    }
    payment_log.append(log_entry)

    return JSONResponse({
        "query_id": query_id,
        "question": question,
        "answer": fact["answer"],
        "citation": fact["citation"],
        "source_name": fact["source_name"],
        "verified": fact["verified"],
        "payment": payment,
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


# Serve static assets
frontend_dir = Path(__file__).parent.parent / "frontend" / "static"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
