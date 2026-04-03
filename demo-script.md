# FactPay Demo Script — OWS Hackathon Track 03

**Video target: 25 seconds | Format: 1280×720 | Voiceover: ElevenLabs (Sarah)**

## Required Proof Points (all 4 must appear)
1. OWS CLI/SDK wallet invocation (consumer + provider wallets)
2. x402 `402 Payment Required` response visible
3. Payment execution and confirmation ($0.003 USDC)
4. Service delivering verified result (citation link)

---

## Timing + Storyboard

| #  | Time     | Duration | Visual                                          | Voiceover (display)                                     | Phonetic (TTS-optimized)                                          |
|----|----------|----------|-------------------------------------------------|----------------------------------------------------------|-------------------------------------------------------------------|
| 1  | 0:00     | 2.0s     | Title card: "FactPay" + tagline on dark BG      | *(silent)*                                              | *(no audio)*                                                      |
| 2  | 0:02     | 2.5s     | Chat UI — user types "When was OWS launched?"  | "FactPay — pay only for proven answers."                | "Fact-Pay — pay only for proven answers."                        |
| 3  | 0:04.5   | 1.5s     | HTTP request: `GET /fact` → server returns 402  | "The AI queries a fact service via x-four-oh-two."     | "The A-I queries a fact service via x four oh two."              |
| 4  | 0:06     | 2.0s     | OWS Policy Engine panel — citation check ✓     | "Citation found. The OWS Policy Engine signs payment."  | "Citation found. The O-W-S Policy Engine signs payment."         |
| 5  | 0:08     | 2.0s     | Chat: answer + green badge "Verified · $0.003" | "Three tenths of a cent. Verified fact delivered."      | "Three tenths of a cent. Verified fact delivered."               |
| 6  | 0:10     | 2.0s     | Payment log: tx hash, USDC, Base L2            | "USDC confirmed on Base L2."                            | "U-S-D-C confirmed on Base L-2."                                 |
| 7  | 0:12     | 2.0s     | User types "What is the GDP of Mars?"           | "Now ask the unverifiable."                             | "Now ask the unverifiable."                                      |
| 8  | 0:14     | 2.0s     | OWS Policy Engine — citation = null → REJECT   | "No citation. Policy Engine refuses to sign."           | "No citation. Policy Engine refuses to sign."                    |
| 9  | 0:16     | 2.0s     | Chat: amber badge "Unverified · $0.000"        | "You pay nothing."                                      | "You pay nothing."                                               |
| 10 | 0:18     | 3.0s     | Split: code block + payment log summary        | "OWS wallet enforces truth — not app logic."            | "O-W-S wallet enforces truth — not app logic."                   |
| 11 | 0:21     | 4.0s     | Closing title: "FactPay · Truth has a price"   | "FactPay. A new x402 primitive for the agent economy."  | "Fact-Pay. A new x four oh two primitive for the agent economy." |

**Total: 25 seconds**

---

## ElevenLabs Voiceover Script (complete, sequential)

```
Fact-Pay. Pay only for proven answers.

The A-I queries a fact service via x four oh two.

Citation found. The O-W-S Policy Engine signs payment. Three tenths of a cent. Verified fact delivered.

U-S-D-C confirmed on Base L-2.

Now ask the unverifiable. No citation. Policy Engine refuses to sign. You pay nothing.

O-W-S wallet enforces truth — not app logic.

Fact-Pay. A new x four oh two primitive for the agent economy.
```

**Voice**: Sarah (ElevenLabs `EXAVITQu4vr4xnSDxMaL`) — mature, confident, clear
**Model**: `eleven_multilingual_v2`
**Settings**: stability 0.65, similarity_boost 0.80, style 0.25

---

## Phonetic Notes

| Term | Display text | TTS phonetic |
|------|-------------|--------------|
| FactPay | FactPay | Fact-Pay |
| x402 | x402 | x four oh two |
| OWS | OWS | O-W-S |
| USDC | USDC | U-S-D-C |
| Base L2 | Base L2 | Base L-2 |
| Policy Engine | Policy Engine | Policy Engine (OK as-is) |
| $0.003 | $0.003 | three tenths of a cent |

---

## Key Visual Design Moments

- **Green glow** on verified answer card (trust signal)
- **Amber/red border** on unverified card (reject signal)
- **Policy Engine panel** showing `citation != null → PASS / FAIL`
- **Payment log** showing real tx hash + USDC amount
- **OWS wallet** on both sides — consumer `0xC014...` + provider `0xF394...`

---

## Anti-Patterns to Avoid

1. ❌ No backstory — straight to demo at 0:00
2. ❌ No mock payments — show real USDC amounts
3. ❌ No API key visible in the demo
4. ❌ Video must not exceed 30 seconds
5. ❌ No "this is how x402 works" tutorial — show don't tell
