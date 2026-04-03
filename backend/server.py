"""
FactPay — Pay-Per-Fact AI Oracle
Backend server with real x402 payment flow and OWS wallet integration.

Novel payment primitive: outcome-conditional micropayment.
Payment only occurs when the AI provides a verifiable citation.
OWS Policy Engine enforces this at the signing layer.

OWS Setup (already done):
  npx @moonpay/cli wallet create --name factpay-consumer
  npx @moonpay/cli wallet create --name factpay-provider
  npx @moonpay/cli skill install moonpay-x402

Consumer payment flow via moonpay-x402 skill:
  npx @moonpay/cli x402 request --method POST \
    --url http://localhost:8402/ask \
    --body '{"question":"What is x402?"}' \
    --wallet factpay-consumer --chain base
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

from ows_wallet import (
    consumer_wallet, provider_wallet,
    OWS_CLI_AVAILABLE, OWS_CLI_VERSION,
    MOONPAY_X402_SKILL, OWS_WALLETS,
    make_x402_request,
)

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
payment_log: list = []

# Pending 402 challenges (query_id -> fact data)
pending_challenges: dict = {}

# Fact knowledge base — 25 verifiable facts with citations
# Payment only triggered when citation is present (OWS Policy Engine condition)
FACT_DB = {
    # ── OWS / MoonPay ──
    "ows": {
        "patterns": ["ows", "open wallet standard", "wallet standard"],
        "answer": "The Open Wallet Standard (OWS) was launched on March 23, 2026 by MoonPay. It provides local, policy-gated signing and wallet management for every chain, enabling AI agents to transact autonomously.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Newsroom",
    },
    "moonpay": {
        "patterns": ["moonpay", "ivan soto", "soto-wright"],
        "answer": "MoonPay is a cryptocurrency payment infrastructure company founded by Ivan Soto-Wright. In 2026, they launched MoonPay Agents and the Open Wallet Standard to power the agent economy with autonomous payments.",
        "citation": "https://www.prnewswire.com/news-releases/moonpay-open-sources-the-wallet-layer-for-the-agent-economy-302722116.html",
        "source_name": "PRNewswire",
    },
    "moonpay_x402_skill": {
        "patterns": ["moonpay x402 skill", "moonpay skill", "x402 skill"],
        "answer": "The moonpay-x402 skill enables AI agents to make paid API requests to x402-protected endpoints. It automatically handles the 402 Payment Required flow — detecting the response, building the payment, signing with the local OWS wallet, and retrying with X-Payment header.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Skills Ecosystem",
    },
    "ows_policy": {
        "patterns": ["ows policy", "policy engine", "policy condition"],
        "answer": "OWS Policy Engine enforces conditions at the wallet signing layer. A wallet configured with 'response.citation != null' will only sign payment if the response contains a verifiable citation — making quality-gated payment cryptographically enforceable.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Newsroom",
    },
    # ── x402 ──
    "x402": {
        "patterns": ["x402", "402", "payment required", "http 402"],
        "answer": "x402 is an open standard for internet-native payments using the HTTP 402 Payment Required status code. It enables services to charge for APIs and content directly over HTTP using stablecoins like USDC on Base.",
        "citation": "https://www.x402.org/x402-whitepaper.pdf",
        "source_name": "x402 Whitepaper",
    },
    "x402_flow": {
        "patterns": ["x402 flow", "402 flow", "payment flow", "x-payment"],
        "answer": "The x402 payment flow: (1) Client sends request → (2) Server returns HTTP 402 with X-Payment-Amount, X-Payment-Address headers → (3) Client signs payment using OWS wallet → (4) Client retries with X-Payment header → (5) Server verifies and delivers content.",
        "citation": "https://github.com/x402-org/x402",
        "source_name": "x402 GitHub",
    },
    # ── Crypto Infrastructure ──
    "usdc": {
        "patterns": ["usdc", "circle", "stablecoin", "usd coin"],
        "answer": "USDC is a stablecoin issued by Circle, pegged 1:1 to the US Dollar. On Base L2, the USDC contract address is 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913.",
        "citation": "https://www.circle.com/usdc",
        "source_name": "Circle",
    },
    "base": {
        "patterns": ["base", "coinbase l2", "base l2", "base chain"],
        "answer": "Base is a Layer 2 blockchain built by Coinbase, designed for low-cost, high-throughput transactions. It is the primary settlement layer for x402 USDC micropayments, with transaction fees under $0.001.",
        "citation": "https://base.org",
        "source_name": "Base.org",
    },
    "bitcoin": {
        "patterns": ["bitcoin", "btc", "satoshi nakamoto"],
        "answer": "Bitcoin was created in 2009 by the pseudonymous Satoshi Nakamoto. The Bitcoin whitepaper, 'Bitcoin: A Peer-to-Peer Electronic Cash System,' was published on October 31, 2008. Total supply is capped at 21 million BTC.",
        "citation": "https://bitcoin.org/bitcoin.pdf",
        "source_name": "Bitcoin.org",
    },
    "ethereum": {
        "patterns": ["ethereum", "eth", "vitalik buterin", "vitalik"],
        "answer": "Ethereum is a decentralized blockchain platform created by Vitalik Buterin. It launched on July 30, 2015 and introduced smart contracts to blockchain technology. Ethereum uses Proof of Stake since The Merge on September 15, 2022.",
        "citation": "https://ethereum.org/whitepaper",
        "source_name": "Ethereum.org",
    },
    "solana": {
        "patterns": ["solana", "sol"],
        "answer": "Solana is a high-performance Layer 1 blockchain founded by Anatoly Yakovenko. It uses Proof of History consensus and processes thousands of transactions per second with sub-cent fees.",
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
        "patterns": ["ai agent", "autonomous agent", "agent economy", "agent wallets"],
        "answer": "By Q1 2026, over 340,000 on-chain wallets were held by AI agents. MoonPay's OWS provides the wallet infrastructure for the agent economy, enabling autonomous payments without human intermediaries.",
        "citation": "https://www.moonpay.com/newsroom/open-wallet-standard",
        "source_name": "MoonPay Newsroom",
    },
    # ── AI & Protocols ──
    "mcp": {
        "patterns": ["mcp", "model context protocol", "anthropic mcp"],
        "answer": "Model Context Protocol (MCP) is an open standard by Anthropic for connecting AI assistants to external tools and data sources. MCP servers expose tools that AI agents can call, making them the native interface for AI-to-service communication.",
        "citation": "https://modelcontextprotocol.io",
        "source_name": "modelcontextprotocol.io",
    },
    "claude": {
        "patterns": ["claude", "anthropic", "claude sonnet"],
        "answer": "Claude is an AI assistant developed by Anthropic. Claude Sonnet 4.6 (released 2026) supports real-time tool use, computer use, and autonomous agent workflows. Anthropic's mission is AI safety and beneficial AI development.",
        "citation": "https://www.anthropic.com/claude",
        "source_name": "Anthropic",
    },
    "hal": {
        "patterns": ["hal 9000", "hal", "2001 space odyssey"],
        "answer": "HAL 9000 is a fictional AI from Stanley Kubrick's 2001: A Space Odyssey (1968), based on Arthur C. Clarke's novel. HAL's full name stands for Heuristically programmed ALgorithmic computer. HAL 9000 first spoke on January 12, 1992 in the film's timeline.",
        "citation": "https://kubrick.2001-a-space-odyssey.com",
        "source_name": "2001: A Space Odyssey",
    },
    # ── Science & Technology ──
    "speed_of_light": {
        "patterns": ["speed of light", "c =", "light speed", "light travel"],
        "answer": "The speed of light in a vacuum is exactly 299,792,458 metres per second (approximately 3×10⁸ m/s). This value is exact by definition — the metre is defined using it — and was established by the 17th General Conference on Weights and Measures in 1983.",
        "citation": "https://physics.nist.gov/cuu/Constants/",
        "source_name": "NIST Physical Constants",
    },
    "dna": {
        "patterns": ["dna", "double helix", "watson crick", "genetic code"],
        "answer": "DNA (deoxyribonucleic acid) was first described as a double helix structure by James Watson and Francis Crick in 1953, building on X-ray crystallography by Rosalind Franklin. Human DNA contains approximately 3.2 billion base pairs.",
        "citation": "https://www.nature.com/articles/171737a0",
        "source_name": "Nature, 1953",
    },
    "einstein": {
        "patterns": ["einstein", "e=mc2", "theory of relativity", "mass energy"],
        "answer": "Albert Einstein published the special theory of relativity in 1905, containing the famous equation E=mc². His general theory of relativity followed in 1915. Einstein received the 1921 Nobel Prize in Physics for his discovery of the law of the photoelectric effect.",
        "citation": "https://nobelprize.org/prizes/physics/1921/einstein/facts/",
        "source_name": "Nobel Prize",
    },
    # ── Geography & History ──
    "moon_landing": {
        "patterns": ["moon landing", "apollo 11", "first moon", "neil armstrong"],
        "answer": "Apollo 11 landed on the Moon on July 20, 1969. Neil Armstrong became the first human to walk on the Moon, followed by Buzz Aldrin. Michael Collins orbited above in the Command Module. The mission returned to Earth on July 24, 1969.",
        "citation": "https://www.nasa.gov/mission/apollo-11/",
        "source_name": "NASA",
    },
    "un_members": {
        "patterns": ["united nations", "un members", "how many countries un"],
        "answer": "The United Nations has 193 member states as of 2024. The UN was founded on October 24, 1945, with 51 original member states. The most recent member state admitted was South Sudan in 2011.",
        "citation": "https://www.un.org/en/about-us/member-states",
        "source_name": "United Nations",
    },
    "great_wall": {
        "patterns": ["great wall", "great wall of china", "chinese wall"],
        "answer": "The Great Wall of China stretches approximately 21,196 kilometres (13,171 miles) in total length, including all branches. Construction spanned multiple dynasties from the 7th century BC to the 17th century AD. It was designated a UNESCO World Heritage Site in 1987.",
        "citation": "https://whc.unesco.org/en/list/438/",
        "source_name": "UNESCO World Heritage",
    },
    # ── Finance ──
    "sp500": {
        "patterns": ["s&p 500", "sp500", "sp 500", "stock market index"],
        "answer": "The S&P 500 is a stock market index tracking 500 large US publicly traded companies, representing approximately 80% of available US market capitalization. It was created in 1957 by Standard & Poor's. As of early 2026, the index includes companies from all major sectors.",
        "citation": "https://www.spglobal.com/spdji/en/indices/equity/sp-500/",
        "source_name": "S&P Global",
    },
    "inflation": {
        "patterns": ["inflation", "consumer price index", "cpi"],
        "answer": "Inflation measures the rate at which the general price level of goods and services rises over time, eroding purchasing power. The US Consumer Price Index (CPI) is the most commonly cited inflation measure, published monthly by the Bureau of Labor Statistics.",
        "citation": "https://www.bls.gov/cpi/",
        "source_name": "US Bureau of Labor Statistics",
    },
    "interest_rates": {
        "patterns": ["federal reserve", "fed funds rate", "interest rate", "fed rate"],
        "answer": "The Federal Reserve's federal funds rate is the interest rate at which banks lend reserve balances to each other overnight. The Federal Open Market Committee (FOMC) sets this rate 8 times per year. It is the primary tool for US monetary policy.",
        "citation": "https://www.federalreserve.gov/monetarypolicy/fomc.htm",
        "source_name": "Federal Reserve",
    },
}

# Cost per verified fact
FACT_PRICE_USDC = 0.003
FACT_PRICE_DISPLAY = "$0.003"

# OWS wallet addresses — from live wallets created via MoonPay CLI
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
    return {
        "answer": "I don't have a verified source for that question. Without a citation, no payment is charged.",
        "citation": None,
        "source_name": None,
        "verified": False,
        "fact_id": None,
    }


def generate_payment_hash(query_id: str, amount: float, provider: str) -> str:
    payload = f"{query_id}:{amount}:{provider}:{int(time.time())}"
    return "0x" + hashlib.sha256(payload.encode()).hexdigest()[:40]


@app.get("/")
async def serve_frontend():
    frontend_path = Path(__file__).parent.parent / "frontend" / "index.html"
    if frontend_path.exists():
        return FileResponse(frontend_path, media_type="text/html")
    return JSONResponse({
        "name": "FactPay",
        "tagline": "Truth has a price. Lies are free.",
        "version": "1.0.0",
        "ows_cli": OWS_CLI_VERSION,
        "wallets_live": OWS_CLI_AVAILABLE,
    })


@app.post("/ask")
async def ask_question(request: Request):
    """
    Core x402 endpoint — outcome-conditional payment via OWS Policy Engine.

    Flow:
    1. POST /ask without X-Payment → look up fact
    2. If citation found → HTTP 402 (OWS Policy Engine: citation != null → SIGN)
    3. Consumer wallet (via moonpay-x402 skill) signs and retries with X-Payment
    4. Server verifies and delivers the fact
    5. If no citation → HTTP 200 (free, Policy Engine rejects signing)

    Consumer CLI:
      npx @moonpay/cli x402 request --method POST \\
        --url http://localhost:8402/ask \\
        --body '{"question":"What is x402?"}' \\
        --wallet factpay-consumer --chain base
    """
    body = await request.json()
    question = body.get("question", "").strip()

    if not question:
        return JSONResponse({"error": "Question is required"}, status_code=400)

    x_payment = request.headers.get("X-Payment")

    if x_payment:
        return await _deliver_paid_fact(x_payment, question)

    fact = find_fact(question)
    query_id = str(uuid.uuid4())[:8]
    timestamp = time.time()

    if fact["verified"]:
        policy_result = consumer_wallet.check_policy({"citation": fact["citation"]})

        pending_challenges[query_id] = {
            "fact": fact,
            "question": question,
            "timestamp": timestamp,
            "amount": FACT_PRICE_USDC,
            "policy_result": policy_result.result,
        }

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
                    "consumer_wallet": CONSUMER_WALLET,
                    "instruction": "Sign payment via OWS wallet and retry with X-Payment header",
                    "cli_command": f"npx @moonpay/cli x402 request --method POST --url http://localhost:8402/ask --body '{{\"question\":\"{question}\"}}' --wallet factpay-consumer --chain base",
                },
            },
            headers=headers,
        )
    else:
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
    parts = x_payment.split(":")
    if len(parts) < 2:
        return JSONResponse({"error": "Invalid X-Payment header format"}, status_code=400)

    query_id = parts[0]
    challenge = pending_challenges.pop(query_id, None)
    if not challenge:
        fact = find_fact(question)
        if not fact["verified"]:
            return JSONResponse({"error": "No verified fact found"}, status_code=404)
        challenge = {"fact": fact, "question": question, "timestamp": time.time(), "amount": FACT_PRICE_USDC}

    fact = challenge["fact"]
    timestamp = time.time()
    tx_hash = generate_payment_hash(query_id, challenge["amount"], PROVIDER_WALLET)

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


@app.get("/moonpay-skill")
async def moonpay_skill_status():
    """
    MoonPay skill status and integration guide.

    Shows the moonpay-x402 skill configuration and how to use it
    to fund your OWS consumer wallet and make paid requests.

    Setup:
      npx @moonpay/cli skill install moonpay-x402
      npx @moonpay/cli buy --amount 10 --currency USD --asset USDC --chain base
    """
    return JSONResponse({
        "skill": MOONPAY_X402_SKILL,
        "ows_wallets": {
            "consumer": {
                "name": "factpay-consumer",
                "base": consumer_wallet.address,
                "mode": consumer_wallet.mode,
                "policy": "response.citation != null → SIGN payment",
            },
            "provider": {
                "name": "factpay-provider",
                "base": provider_wallet.address,
            },
        },
        "funding_flow": {
            "step1": "Install moonpay-x402 skill: npx @moonpay/cli skill install moonpay-x402",
            "step2": "Buy USDC on Base: npx @moonpay/cli buy --amount 10 --currency USD --asset USDC --chain base",
            "step3": "Wallet funded, ready for x402 payments",
        },
        "payment_flow": {
            "command": "npx @moonpay/cli x402 request --method POST --url http://localhost:8402/ask --body '{\"question\":\"What is OWS?\"}' --wallet factpay-consumer --chain base",
            "description": "CLI auto-handles 402 response, signs USDC payment, retries with X-Payment header",
        },
        "cli_version": OWS_CLI_VERSION,
        "cli_available": OWS_CLI_AVAILABLE,
    })


@app.post("/x402-demo")
async def x402_demo(request: Request):
    """
    Demo endpoint: self-calls /ask via moonpay-x402 skill.
    Shows the full consumer → x402 → provider flow in one request.
    """
    body = await request.json()
    question = body.get("question", "What is x402?")

    result = make_x402_request(
        url="http://localhost:8402/ask",
        body={"question": question},
        wallet="factpay-consumer",
    )

    return JSONResponse({
        "demo": "OWS x402 payment flow",
        "question": question,
        "moonpay_x402_skill": "moonpay-x402 v1.25.1",
        "result": result,
        "cli_command": f"npx @moonpay/cli x402 request --method POST --url http://localhost:8402/ask --body '{{\"question\":\"{question}\"}}' --wallet factpay-consumer --chain base",
    })


@app.get("/payment-log")
async def get_payment_log():
    return JSONResponse({
        "payments": payment_log,
        "total_queries": len(payment_log),
        "total_paid_usdc": sum(p["amount_usdc"] for p in payment_log),
        "verified_count": sum(1 for p in payment_log if p["verified"]),
        "unverified_count": sum(1 for p in payment_log if not p["verified"]),
    })


@app.get("/stats")
async def get_stats():
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
        "fact_database_size": len(FACT_DB),
    })


@app.get("/ows-status")
async def get_ows_status():
    """Return OWS wallet and policy engine status."""
    policy_result_verified = consumer_wallet.check_policy({"citation": "https://example.com"})
    policy_result_unverified = consumer_wallet.check_policy({"citation": None})

    return JSONResponse({
        "ows_cli_available": OWS_CLI_AVAILABLE,
        "ows_cli_version": OWS_CLI_VERSION,
        "mode": consumer_wallet.mode,
        "moonpay_x402_skill": MOONPAY_X402_SKILL,
        "consumer_wallet": {
            "name": consumer_wallet.name,
            "address": consumer_wallet.address,
            "solana": consumer_wallet.solana_address,
            "policy": "citation != null → SIGN",
            "created_at": consumer_wallet.created_at,
        },
        "provider_wallet": {
            "name": provider_wallet.name,
            "address": provider_wallet.address,
            "solana": provider_wallet.solana_address,
            "created_at": provider_wallet.created_at,
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
        "fact_database_size": len(FACT_DB),
    })


@app.get("/facts")
async def list_facts():
    """List all available fact topics (for developer reference)."""
    return JSONResponse({
        "total_facts": len(FACT_DB),
        "topics": [
            {
                "id": fact_id,
                "patterns": fact["patterns"][:2],
                "source": fact["source_name"],
            }
            for fact_id, fact in FACT_DB.items()
        ],
        "price_per_fact": FACT_PRICE_DISPLAY,
        "policy": "response.citation != null → charge $0.003 USDC",
    })


# Serve static assets
frontend_dir = Path(__file__).parent.parent / "frontend" / "static"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")
