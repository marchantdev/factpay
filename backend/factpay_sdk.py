"""
FactPay SDK — Python client for the FactPay x402 oracle.

Implements the consumer-side x402 payment flow with OWS wallet signing.
Use this as a reference implementation for building your own fact service
or integrating FactPay into an AI agent workflow.

Quick start:
    from factpay_sdk import FactPayClient

    client = FactPayClient("http://localhost:8402")

    # Ask a question — payment handled automatically
    result = client.ask("What is x402?")
    if result.paid:
        print(f"Answer: {result.answer}")
        print(f"Citation: {result.citation}")
        print(f"Paid: {result.amount_usdc} USDC")
    else:
        print(f"No citation: {result.answer}")  # Free response

MoonPay CLI integration:
    # Fund consumer wallet via moonpay-x402 skill:
    # npx @moonpay/cli skill install moonpay-x402
    # npx @moonpay/cli buy --amount 10 --currency USD --asset USDC --chain base
    #
    # Make paid request via CLI:
    # npx @moonpay/cli x402 request --method POST \
    #   --url http://localhost:8402/ask \
    #   --body '{"question":"What is OWS?"}' \
    #   --wallet factpay-consumer --chain base
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FactResult:
    """Result of a FactPay query."""
    query_id: str
    question: str
    answer: str
    citation: Optional[str]
    source_name: Optional[str]
    verified: bool
    paid: bool
    amount_usdc: float
    tx_hash: Optional[str]
    consumer_wallet: str
    provider_wallet: str

    @property
    def amount_display(self) -> str:
        return f"${self.amount_usdc:.3f}"


@dataclass
class OWSWalletConfig:
    """OWS wallet configuration for the consumer."""
    name: str = "factpay-consumer"
    address: str = ""
    network: str = "base"
    asset: str = "USDC"

    def build_payment_header(self, query_id: str, signature: str) -> str:
        """Build the X-Payment header for x402 requests."""
        return f"{query_id}:{self.address}:{signature}"


class FactPayClient:
    """
    FactPay x402 client — handles the full 402 payment flow.

    The OWS Policy Engine runs on the consumer wallet:
    - If the server returns a citation: wallet SIGNS the payment
    - If no citation: wallet REJECTS (you don't pay for hallucinations)

    This policy is enforced at the signing layer — not application logic.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8402",
        wallet: Optional[OWSWalletConfig] = None,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self.wallet = wallet or OWSWalletConfig()
        self.timeout = timeout
        self._session_payments: list = []

    def ask(self, question: str) -> FactResult:
        """
        Ask a question and pay automatically if a citation is found.

        Returns FactResult with paid=True if payment was made,
        paid=False if the answer was free (no citation available).
        """
        # Step 1: Initial request (no payment)
        response_data = self._post("/ask", {"question": question})

        if response_data.get("status_code") == 402:
            # Step 2: Payment required — evaluate policy and pay
            payment_info = response_data.get("payment_required", {})
            query_id = response_data.get("query_id", "")
            citation_present = response_data.get("has_citation", False)

            if citation_present:
                # Policy PASS: sign and pay
                sig = self._sign_payment(
                    query_id=query_id,
                    amount=payment_info.get("amount_usdc", 0.003),
                    to=payment_info.get("to_wallet", ""),
                )
                x_payment = f"{query_id}:{self.wallet.address}:{sig}"

                # Step 3: Retry with payment
                paid_response = self._post("/ask", {"question": question}, extra_headers={
                    "X-Payment": x_payment,
                })
                payment = paid_response.get("payment", {})
                return FactResult(
                    query_id=query_id,
                    question=question,
                    answer=paid_response.get("answer", ""),
                    citation=paid_response.get("citation"),
                    source_name=paid_response.get("source_name"),
                    verified=paid_response.get("verified", False),
                    paid=True,
                    amount_usdc=payment.get("amount_usdc", 0.003),
                    tx_hash=payment.get("tx_hash"),
                    consumer_wallet=payment.get("from_wallet", self.wallet.address),
                    provider_wallet=payment.get("to_wallet", ""),
                )

        # No payment required (free answer)
        payment = response_data.get("payment", {})
        return FactResult(
            query_id=response_data.get("query_id", ""),
            question=question,
            answer=response_data.get("answer", ""),
            citation=None,
            source_name=None,
            verified=False,
            paid=False,
            amount_usdc=0.0,
            tx_hash=None,
            consumer_wallet=self.wallet.address,
            provider_wallet=payment.get("to_wallet", ""),
        )

    def get_stats(self) -> dict:
        """Get aggregate payment statistics from the server."""
        return self._get("/stats")

    def get_ows_status(self) -> dict:
        """Get OWS wallet and policy engine status."""
        return self._get("/ows-status")

    def get_moonpay_skill(self) -> dict:
        """Get moonpay-x402 skill configuration."""
        return self._get("/moonpay-skill")

    def list_facts(self) -> dict:
        """List available fact topics."""
        return self._get("/facts")

    def _sign_payment(self, query_id: str, amount: float, to: str) -> str:
        """
        Sign a payment. In production, calls OWS wallet CLI:
            npx @moonpay/cli x402 request --wallet factpay-consumer ...

        This SDK uses deterministic signing for demonstration.
        Replace with OWSWallet.sign_payment() for production use.
        """
        import hashlib
        import time
        payload = f"{query_id}:{amount}:{to}:{int(time.time())}"
        return hashlib.sha256(payload.encode()).hexdigest()[:40]

    def _post(self, path: str, data: dict, extra_headers: dict = None) -> dict:
        url = self.base_url + path
        body = json.dumps(data).encode()
        headers = {"Content-Type": "application/json"}
        if extra_headers:
            headers.update(extra_headers)

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                result = json.loads(resp.read())
                result["status_code"] = resp.status
                return result
        except urllib.error.HTTPError as e:
            result = json.loads(e.read())
            result["status_code"] = e.code
            return result

    def _get(self, path: str) -> dict:
        url = self.base_url + path
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read())


# CLI example usage
if __name__ == "__main__":
    import sys

    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What is x402?"
    client = FactPayClient()

    print(f"\nFactPay SDK — asking: '{question}'")
    print("Consumer policy: response.citation != null → SIGN payment\n")

    result = client.ask(question)

    if result.paid:
        print(f"✅ PAID  — {result.amount_display} USDC")
        print(f"   Answer: {result.answer}")
        print(f"   Citation: {result.citation}")
        print(f"   Source: {result.source_name}")
        print(f"   TX: {result.tx_hash}")
    else:
        print(f"🆓 FREE  — No citation available")
        print(f"   Answer: {result.answer}")
        print(f"   Policy: OWS wallet refused to sign (citation == null)")
