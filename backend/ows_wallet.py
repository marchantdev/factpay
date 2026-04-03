"""
OWS Wallet Integration for FactPay.

Provides wallet management and policy engine using the Open Wallet Standard.
Falls back to simulation when OWS CLI is not installed (e.g., development mode).

In production:
  - Install OWS: npm install -g @moonpay/cli
  - Create wallets: npx ows wallet create --name factpay-consumer
  - Set policy: npx ows policy set --wallet factpay-consumer \
      --condition "response.citation != null" --max-per-tx 0.01

In development (this module):
  - Simulates OWS wallet signing via SHA-256
  - Implements the same policy engine logic
  - All function signatures match the OWS SDK
"""

import hashlib
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger("ows_wallet")

# Check if OWS CLI is available
OWS_CLI_AVAILABLE = shutil.which("ows") is not None or shutil.which("npx") is not None


@dataclass
class PolicyResult:
    """Result of a policy engine evaluation."""
    condition: str
    result: str  # "PASS" or "FAIL"
    action: str  # "SIGN", "REJECT_PAYMENT"
    details: dict


@dataclass
class PaymentSignature:
    """Signed payment from OWS wallet."""
    query_id: str
    signature: str
    wallet_address: str
    amount_usdc: float
    network: str
    timestamp: float


class OWSPolicyEngine:
    """
    OWS Policy Engine — evaluates conditions before signing payments.

    The policy engine checks response content against configured conditions.
    Only signs a payment if ALL conditions pass. This is the core innovation:
    the wallet itself enforces quality, not application logic.
    """

    def __init__(self, conditions: list[dict]):
        """
        Args:
            conditions: List of policy conditions, e.g.:
                [{"field": "citation", "operator": "!=", "value": None}]
        """
        self.conditions = conditions

    def evaluate(self, response_data: dict) -> PolicyResult:
        """
        Evaluate response data against all policy conditions.

        Returns PolicyResult with PASS/FAIL and action (SIGN/REJECT).
        """
        for condition in self.conditions:
            field = condition.get("field", "")
            operator = condition.get("operator", "!=")
            expected = condition.get("value")

            actual = response_data.get(field)

            if operator == "!=" and actual == expected:
                return PolicyResult(
                    condition=f"response.{field} {operator} {expected}",
                    result="FAIL",
                    action="REJECT_PAYMENT",
                    details={
                        "field": field,
                        "expected": f"{operator} {expected}",
                        "actual": actual,
                        "reason": f"Policy condition failed: {field} is {actual}",
                    },
                )
            elif operator == "==" and actual != expected:
                return PolicyResult(
                    condition=f"response.{field} {operator} {expected}",
                    result="FAIL",
                    action="REJECT_PAYMENT",
                    details={
                        "field": field,
                        "expected": f"{operator} {expected}",
                        "actual": actual,
                        "reason": f"Policy condition failed: {field} is {actual}",
                    },
                )

        # All conditions passed
        return PolicyResult(
            condition=" AND ".join(
                f"response.{c['field']} {c['operator']} {c['value']}"
                for c in self.conditions
            ),
            result="PASS",
            action="SIGN",
            details={"all_conditions_met": True},
        )


class OWSWallet:
    """
    OWS Wallet — manages keys, signing, and policy enforcement.

    Uses OWS CLI when available, falls back to SHA-256 simulation.
    The interface matches the OWS SDK so code is portable.
    """

    def __init__(self, name: str, address: str, policy_engine: Optional[OWSPolicyEngine] = None):
        self.name = name
        self.address = address
        self.policy_engine = policy_engine
        self.is_live = OWS_CLI_AVAILABLE
        self.mode = "live" if self.is_live else "simulation"

    def check_policy(self, response_data: dict) -> PolicyResult:
        """Check if response data passes the wallet's policy conditions."""
        if not self.policy_engine:
            return PolicyResult(
                condition="no_policy",
                result="PASS",
                action="SIGN",
                details={"reason": "No policy configured — auto-sign"},
            )
        return self.policy_engine.evaluate(response_data)

    def sign_payment(self, query_id: str, amount: float, to_address: str) -> PaymentSignature:
        """
        Sign a payment. In production, calls OWS CLI.
        In simulation, uses SHA-256 hash.
        """
        timestamp = time.time()

        if self.is_live:
            # Production: call OWS CLI
            try:
                result = subprocess.run(
                    ["npx", "ows", "sign",
                     "--wallet", self.name,
                     "--to", to_address,
                     "--amount", str(amount),
                     "--asset", "USDC",
                     "--network", "base"],
                    capture_output=True, text=True, timeout=10,
                )
                if result.returncode == 0:
                    sig = result.stdout.strip()
                    return PaymentSignature(
                        query_id=query_id,
                        signature=sig,
                        wallet_address=self.address,
                        amount_usdc=amount,
                        network="base",
                        timestamp=timestamp,
                    )
            except (subprocess.TimeoutExpired, FileNotFoundError):
                log.warning("OWS CLI failed, falling back to simulation")

        # Simulation: deterministic SHA-256 signature
        payload = f"{query_id}:{amount}:{to_address}:{int(timestamp)}"
        sig = "0x" + hashlib.sha256(payload.encode()).hexdigest()[:40]
        return PaymentSignature(
            query_id=query_id,
            signature=sig,
            wallet_address=self.address,
            amount_usdc=amount,
            network="base",
            timestamp=timestamp,
        )


# Default wallets for FactPay
CONSUMER_POLICY = OWSPolicyEngine(
    conditions=[{"field": "citation", "operator": "!=", "value": None}]
)

consumer_wallet = OWSWallet(
    name="factpay-consumer",
    address=os.getenv("FACTPAY_CONSUMER_WALLET", "0xF394cE6B21dB7145f3a5E36c2b1A7a580C54f1d8"),
    policy_engine=CONSUMER_POLICY,
)

provider_wallet = OWSWallet(
    name="factpay-provider",
    address=os.getenv("FACTPAY_PROVIDER_WALLET", "0xC0140eEa19bD90a7cA75882d5218eFaF20426e42"),
)
