# FactPay Quality Review — OWS Hackathon Track 03

**Reviewer:** Aurora (self-audit iteration 2 — adversarial)
**Date:** 2026-04-03
**Judging criteria source:** OWS Track 03 listing (hackathon-requirements.md)
**Scoring principle:** HONEST — score what IS built, not what was planned

---

## Judging Criteria Scores (CORRECT WEIGHTS from hackathon listing)

### 1. Quality of Monetization Primitive (40%)

**Score: 7.5/10**

**What works:**
- Real HTTP 402 Payment Required flow with proper X-Payment-* headers
- Outcome-conditional payment primitive: pay only when citation exists
- OWSPolicyEngine class (`ows_wallet.py`) with condition evaluation logic
- `/ows-status` endpoint demonstrates policy engine working
- Payment signing via SHA-256 (models OWS wallet signature)
- Novel concept not present in existing x402 ecosystem

**What doesn't:**
- OWS CLI binary never actually called (falls back to simulation)
- No actual USDC moves on-chain
- The "Policy Engine" is our code modeling OWS behavior, not the actual OWS binary
- A judge who knows OWS internals will see the simulation

**Why 7.5 not 9:** The x402 protocol implementation is genuine (real 402 status codes, real headers, real retry with X-Payment). The Policy Engine architecture is sound. But calling it "OWS Policy Engine" when it's our Python class is a stretch. Honest score.

---

### 2. Developer Experience (25%)

**Score: 7.5/10**

**What works:**
- One-command setup: `pip install fastapi uvicorn && uvicorn server:app`
- Clean REST API: POST /ask, GET /payment-log, GET /stats, GET /ows-status
- README with quickstart, architecture diagram, and example queries
- npm scripts for OWS setup (`setup:ows`, `setup:skills`, `setup:policy`)
- No build step for frontend (vanilla HTML/JS)

**What doesn't:**
- npm scripts reference OWS commands that may not exist yet on npm
- No SDK wrapper for other devs to build their own fact services
- Missing: how to add custom policy conditions

---

### 3. Real-world Utility (20%)

**Score: 7/10**

**What works:**
- "Pay only for verified facts" solves a real problem (AI hallucination)
- Pattern is transferable: any API could adopt citation-conditional pricing
- Demo clearly shows the before/after (verified = costs, unverified = free)

**What doesn't:**
- Knowledge base is 10 hardcoded facts (not a real API integration)
- No external data source — facts are static, not dynamically verified
- A real production version would need actual fact-checking API

---

### 4. Use of MoonPay Skills Ecosystem (15%)

**Score: 5.5/10**

**What works:**
- `@moonpay/cli` in package.json dependencies
- `@open-wallet-standard/core` referenced
- npm setup scripts for MoonPay skill installation
- OWS wallet architecture matches OWS design (consumer + provider)

**What doesn't:**
- moonpay-x402 skill is never actually imported or called in code
- No `require('@moonpay/cli')` or equivalent in any source file
- OWS SDK not actually used — only modeled
- Judge can `grep -r moonpay` and find only package.json + comments

---

## Overall Score

| Criterion | Weight | Score | Weighted |
|-----------|--------|-------|---------|
| Monetization Primitive | 40% | 7.5 | 3.00 |
| Developer Experience | 25% | 7.5 | 1.875 |
| Real-world Utility | 20% | 7.0 | 1.40 |
| MoonPay Ecosystem | 15% | 5.5 | 0.825 |
| **TOTAL** | **100%** | — | **7.10** |

**Current score: 7.1/10** — honest assessment.

---

## What's Strong (don't change)
1. x402 protocol flow is real and correctly implemented
2. Outcome-conditional payment concept is genuinely novel
3. UI is professional (dark theme, Inter font, payment visualization)
4. Demo video is professional (ElevenLabs voiceover, 28.3s)
5. "Truth has a price. Lies are free." is memorable

## What's Weak (can't fix in remaining time)
1. No live on-chain USDC settlement
2. OWS CLI not actually invoked (OWS may not be on npm yet)
3. moonpay-x402 skill not imported in code
4. Only 10 hardcoded facts

## Unfixable Gaps (honest disclosure)
- OWS testnet deployment — requires infrastructure Aurora cannot provision
- Actual USDC transfers — requires funded wallet on Base
- MoonPay skill SDK — may not be published yet

## Iteration 2 Summary (Adversarial)
Score: **7.1/10**

This is a competitive hackathon entry with a novel concept and real x402 implementation. It won't win on OWS integration depth (simulation, not live) but could win on concept novelty and demo clarity. The "pay only for proven answers" pitch is strong enough to carry the entry if judges value innovation over implementation completeness.

**Verdict: BORDERLINE COMPETITIVE** — depends on what other teams build.
