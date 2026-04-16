"""
TRISPI Python SDK — Client for TRISPI AI Blockchain
Token: TRP | Consensus: Proof of Intelligence (PoI)

Install: pip install requests
"""

import time
import requests
from typing import Any, Optional


class TrispiClient:
    """
    Python client for the TRISPI blockchain API.

    Example:
        client = TrispiClient("http://localhost:8000")
        wallet = client.create_wallet()
        client.send_transaction(wallet["address"], "trp1recipient", 100)
    """

    def __init__(self, base_url: str = "http://localhost:8000", timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, path: str, **kwargs) -> Any:
        resp = self.session.get(f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json: dict, **kwargs) -> Any:
        resp = self.session.post(f"{self.base_url}{path}", json=json, timeout=self.timeout, **kwargs)
        resp.raise_for_status()
        return resp.json()

    # ── Health ──────────────────────────────────────────────────────────────

    def health(self) -> dict:
        return self._get("/health")

    def system_status(self) -> dict:
        return self._get("/api/system/status")

    # ── Wallet ──────────────────────────────────────────────────────────────

    def create_wallet(self) -> dict:
        return self._get("/api/wallet/create")

    def get_balance(self, address: str) -> dict:
        return self._get(f"/api/wallet/balances/{address}")

    def send_transaction(
        self,
        sender: str,
        recipient: str,
        amount: float,
        private_key: Optional[str] = None,
    ) -> dict:
        return self._post("/api/transaction/send", {
            "sender": sender,
            "recipient": recipient,
            "amount": amount,
            "private_key": private_key,
        })

    # ── Tokenomics ──────────────────────────────────────────────────────────

    def get_tokenomics(self) -> dict:
        return self._get("/api/tokenomics")

    def get_token_price(self, symbol: str = "TRP") -> dict:
        return self._get(f"/api/dex/price/{symbol}")

    def get_founder_wallet(self) -> dict:
        return self._get("/api/founder")

    # ── Network ─────────────────────────────────────────────────────────────

    def get_network_overview(self) -> dict:
        return self._get("/api/network/overview")

    def get_network_stats(self) -> dict:
        return self._get("/api/network/stats")

    def get_pqc_status(self) -> dict:
        return self._get("/api/pqc/status")

    # ── Energy Provider ─────────────────────────────────────────────────────

    def register_energy_device(
        self,
        device_id: str,
        device_type: str,
        cpu_cores: int,
        wallet_address: str,
        gpu_memory_mb: int = 0,
    ) -> dict:
        """
        Register a new energy-providing device.
        Returns dict with 'api_key' — store it securely, it cannot be recovered.
        """
        return self._post("/api/energy/register", {
            "device_id": device_id,
            "device_type": device_type,
            "cpu_cores": cpu_cores,
            "gpu_memory_mb": gpu_memory_mb,
            "wallet_address": wallet_address,
        })

    def submit_energy_reading(
        self,
        device_id: str,
        api_key: str,
        power_watts: float,
        temperature_c: float,
        cpu_usage_pct: float,
        gpu_usage_pct: float = 0.0,
        timestamp: Optional[int] = None,
    ) -> dict:
        """Submit a power reading. Returns TRP reward credited to wallet."""
        return self._post("/api/energy/proxy/reading", {
            "device_id": device_id,
            "api_key": api_key,
            "power_watts": power_watts,
            "temperature_c": temperature_c,
            "cpu_usage_pct": cpu_usage_pct,
            "gpu_usage_pct": gpu_usage_pct,
            "timestamp": timestamp or int(time.time()),
        })

    def get_energy_status(self) -> dict:
        return self._get("/api/energy/status")

    # ── Smart Contracts ─────────────────────────────────────────────────────

    def deploy_contract(
        self,
        code: str,
        runtime: str,
        deployer: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        return self._post("/api/contracts/deploy", {
            "code": code,
            "runtime": runtime,
            "deployer": deployer,
            "metadata": metadata or {},
        })

    def get_contracts(self) -> list:
        return self._get("/api/contracts")

    # ── Explorer ────────────────────────────────────────────────────────────

    def get_explorer_stats(self) -> dict:
        return self._get("/api/explorer/stats")

    def get_recent_blocks(self, limit: int = 10) -> dict:
        return self._get("/api/explorer/recent-blocks", params={"limit": limit})

    def get_recent_transactions(self, limit: int = 20) -> dict:
        return self._get("/api/explorer/recent-transactions", params={"limit": limit})

    def get_block(self, block_number: int) -> dict:
        return self._get(f"/api/block/{block_number}")

    # ── Staking ─────────────────────────────────────────────────────────────

    def stake(self, address: str, amount: float) -> dict:
        return self._post("/api/staking/stake", {"address": address, "amount": amount})

    def unstake(self, address: str, amount: float) -> dict:
        return self._post("/api/staking/unstake", {"address": address, "amount": amount})

    def get_staking_info(self, address: str) -> dict:
        return self._get(f"/api/staking/info/{address}")

    # ── Governance ──────────────────────────────────────────────────────────

    def get_proposals(self) -> list:
        return self._get("/api/governance/proposals")

    def create_proposal(self, title: str, description: str, proposer: str) -> dict:
        return self._post("/api/governance/proposals", {
            "title": title,
            "description": description,
            "proposer": proposer,
        })

    def vote(self, proposal_id: str, voter: str, vote_for: bool) -> dict:
        return self._post("/api/governance/vote", {
            "proposal_id": proposal_id,
            "voter": voter,
            "vote_for": vote_for,
        })
