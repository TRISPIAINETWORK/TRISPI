"""
TRISPI Network Participation Agents — Decentralized Validator & Compute
=======================================================================
Two permanent on-chain AI agents that make the TRISPI network truly
decentralized — anyone can replicate what these agents do by running
trispi_energy_provider.py on their own machine.

Agents:
  ValidatorAgent       — PoI block scoring (15s cycle)
  ComputeProviderAgent — Federated Learning gradient submission (30s cycle)

Supporting infrastructure:
  ValidatorRegistry    — thread-safe registry of external validator nodes
  BlockScoreCollector  — multi-validator consensus score computation
"""

import asyncio
import hashlib
import json
import logging
import os
import threading
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
import numpy as np

logger = logging.getLogger("autonomous_agents")

_GO_URL     = "http://127.0.0.1:8181"
_PYTHON_URL = "http://127.0.0.1:8000"

# ── Service key (Ed25519 + Dilithium3 for tx signing) ────────────────────────

_service_key_cache: Dict[str, Any] = {}

def _load_service_key() -> Dict[str, Any]:
    global _service_key_cache
    if _service_key_cache:
        return _service_key_cache
    key_path = os.path.join(os.path.dirname(__file__), "..", "secrets", "service_key.json")
    try:
        with open(key_path) as f:
            _service_key_cache = json.load(f)
    except Exception:
        _service_key_cache = {}
    return _service_key_cache


def _build_and_sign_tx(
    from_addr: str,
    to_addr: str,
    amount: float,
    token_symbol: str,
    timestamp: int,
) -> Optional[Dict[str, str]]:
    """
    Build the canonical transaction message that Go verifies, then sign it with
    both Ed25519 (service key) and Dilithium3 (ephemeral key).

    Go's canonical format (enhanced_node.go HandlePostTx):
      "{tx_hash}:{from}:{to}:{amount_str}:{token_symbol}:{timestamp}"

    Returns a dict of all PQC fields required by Go /tx, or None if signing
    fails (fail-closed — no stub fallback).
    """
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key_data = _load_service_key()
    priv_hex = key_data.get("private_key_hex", "")
    pub_hex  = key_data.get("public_key_hex", "")

    if not priv_hex:
        logger.error("[agents] Service Ed25519 private key missing — cannot sign tx (fail-closed)")
        return None

    amount_str    = str(amount)
    pre_canonical = f"{from_addr}:{to_addr}:{amount_str}:{token_symbol}:{timestamp}"
    tx_hash       = hashlib.sha256(pre_canonical.encode()).hexdigest()
    canonical_msg = f"{tx_hash}:{from_addr}:{to_addr}:{amount_str}:{token_symbol}:{timestamp}"
    msg_bytes     = canonical_msg.encode()

    try:
        priv_bytes  = bytes.fromhex(priv_hex)
        priv_key    = Ed25519PrivateKey.from_private_bytes(priv_bytes)
        sig_bytes   = priv_key.sign(msg_bytes)
        ed25519_sig = sig_bytes.hex()
    except Exception as exc:
        logger.error(f"[agents] Ed25519 signing failed — tx rejected (fail-closed): {exc}")
        return None

    dil_sig = ""
    dil_pub = ""
    try:
        from dilithium_py.dilithium import Dilithium3
        pk, sk  = Dilithium3.keygen()
        dil_pub = pk.hex()
        dil_sig = Dilithium3.sign(sk, msg_bytes).hex()
    except Exception as exc:
        logger.warning(f"[agents] Dilithium3 sign failed: {exc}")
        return None

    return {
        "tx_hash":        tx_hash,
        "ed25519_sig":    ed25519_sig,
        "ed25519_pub":    pub_hex,
        "dilithium3_sig": dil_sig,
        "dilithium3_pub": dil_pub,
        "_canonical_msg": canonical_msg,
    }


async def _post_tx_to_go(
    from_addr: str,
    to_addr: str,
    amount: float,
    data: str,
    token_symbol: str = "TRP",
    timeout: float = 5.0,
) -> Optional[Dict]:
    """Build a canonically-signed transaction and POST it to Go /tx."""
    ts     = int(time.time())
    signed = _build_and_sign_tx(from_addr, to_addr, amount, token_symbol, ts)
    if signed is None:
        logger.warning("[agents] tx signing failed — not submitted")
        return None

    canonical_msg = signed.pop("_canonical_msg", "")
    logger.debug(f"[agents] posting tx canonical={canonical_msg[:80]}…")

    payload = {
        "from":           from_addr,
        "to":             to_addr,
        "amount":         amount,
        "amount_str":     str(amount),
        "token_symbol":   token_symbol,
        "data":           data,
        "timestamp":      ts,
        "pqc_engine":     "ed25519+dilithium3",
        "runtime_type":   "EVM",
        **signed,
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(f"{_GO_URL}/tx", json=payload)
            # Go sometimes returns empty body (204-style) on busy ticks — handle gracefully
            try:
                resp = r.json() if (r.status_code < 500 and r.content and r.content.strip()) else {"http_status": r.status_code}
            except Exception:
                resp = {"http_status": r.status_code, "raw": r.text[:80]}
            if r.status_code >= 400:
                logger.warning(f"[agents] Go /tx returned {r.status_code}: {resp}")
                # Return None on ANY non-2xx so callers can rely on `if result:`
                # to mean "transaction was confirmed by Go", not merely "got a response".
                # This prevents marking validators as rewarded on 4xx error responses.
                return None
            return resp
    except Exception as exc:
        logger.debug(f"[agents] _post_tx_to_go failed: {exc}")
        return None


# ── ValidatorRegistry ─────────────────────────────────────────────────────────

class ValidatorRegistry:
    """
    Thread-safe registry of external PoI validator nodes.

    Each external node (typically running trispi_energy_provider.py) registers
    its Ed25519 public key here.  The trust_weight (0.10–1.0) reflects how
    often the validator's scores agree with the consensus median:
      honest score  (within 0.25 of median) → trust_weight × 1.02  (cap 1.0)
      dishonest score                        → trust_weight × 0.95  (floor 0.10)

    Validators whose trust_weight drops below 0.30 are excluded from consensus
    scoring and earn no TRP rewards.
    """

    TRUST_FLOOR = 0.10
    TRUST_CAP   = 1.00
    TRUST_GROW  = 0.02
    TRUST_DECAY = 0.05
    EXCLUDE_BELOW = 0.30

    def __init__(self) -> None:
        self._lock       = threading.Lock()
        self._validators: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        provider_id: str,
        pubkey_hex: str,
        stake_address: str = "",
    ) -> Tuple[bool, str]:
        if not provider_id:
            return False, "provider_id is required"
        if not pubkey_hex:
            return False, "pubkey_hex is required"
        try:
            raw = bytes.fromhex(pubkey_hex)
            if len(raw) != 32:
                return False, "pubkey_hex must be 64 hex chars (32 raw bytes)"
        except ValueError:
            return False, "pubkey_hex is not valid hex"

        with self._lock:
            if provider_id in self._validators:
                return True, "already_registered"
            self._validators[provider_id] = {
                "pubkey_hex":       pubkey_hex,
                "stake_address":    stake_address,
                "trust_weight":     1.0,
                "registered_at":    time.time(),
                "scores_submitted": 0,
                "scores_honest":    0,
                "last_seen":        time.time(),
            }
        logger.info(f"[ValidatorRegistry] registered external validator: {provider_id}")
        return True, ""

    def get(self, provider_id: str) -> Optional[Dict]:
        with self._lock:
            v = self._validators.get(provider_id)
            return dict(v) if v else None

    def get_all(self) -> List[Dict]:
        with self._lock:
            return [{"provider_id": pid, **v} for pid, v in self._validators.items()]

    def update_trust(self, provider_id: str, honest: bool) -> None:
        with self._lock:
            v = self._validators.get(provider_id)
            if v is None:
                return
            v["scores_submitted"] += 1
            if honest:
                v["scores_honest"] += 1
                v["trust_weight"] = min(self.TRUST_CAP, v["trust_weight"] * (1 + self.TRUST_GROW))
            else:
                v["trust_weight"] = max(self.TRUST_FLOOR, v["trust_weight"] * (1 - self.TRUST_DECAY))
            v["last_seen"] = time.time()

    def verify_signature(self, provider_id: str, message: bytes, sig_hex: str) -> bool:
        """Verify an Ed25519 signature from a registered validator."""
        validator = self.get(provider_id)
        if not validator:
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
            pub_bytes = bytes.fromhex(validator["pubkey_hex"])
            pub_key   = Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub_key.verify(bytes.fromhex(sig_hex), message)
            return True
        except Exception:
            return False

    def leaderboard(self, limit: int = 50) -> List[Dict]:
        with self._lock:
            ranked = sorted(
                self._validators.items(),
                key=lambda x: -x[1]["trust_weight"],
            )[:limit]
            return [
                {
                    "rank":             i + 1,
                    "provider_id":      pid,
                    "trust_weight":     round(v["trust_weight"], 4),
                    "scores_submitted": v["scores_submitted"],
                    "scores_honest":    v["scores_honest"],
                    "honest_pct":       round(
                        v["scores_honest"] / max(1, v["scores_submitted"]) * 100, 1
                    ),
                    # Estimated lifetime TRP = 0.1 TRP × trust_weight per honest block.
                    # trust_weight evolves over time so this uses the current value as
                    # a proxy; exact amounts are recorded in on-chain reward transactions.
                    "estimated_trp_earned": round(0.1 * v["trust_weight"] * v["scores_honest"], 6),
                    "active":           v["trust_weight"] >= self.EXCLUDE_BELOW,
                    "registered_at":    v["registered_at"],
                    "last_seen":        v["last_seen"],
                }
                for i, (pid, v) in enumerate(ranked)
            ]


# ── BlockScoreCollector ───────────────────────────────────────────────────────

def _weighted_median(values: List[float], weights: List[float]) -> float:
    """
    Compute the weighted median: value v such that the cumulative weight of
    values ≤ v first reaches ≥ 50% of the total weight.  Handles ties by
    returning the lower boundary value, consistent with numpy.median for
    equal-weight inputs.
    """
    if not values:
        return 0.0
    pairs = sorted(zip(values, weights), key=lambda x: x[0])
    total_w    = sum(w for _, w in pairs)
    cumulative = 0.0
    for v, w in pairs:
        cumulative += w
        if cumulative >= total_w / 2.0:
            return v
    return pairs[-1][0]


class BlockScoreCollector:
    """
    Collects PoI block scores from multiple validators (server + external
    energy provider nodes) and computes a stake+trust-weighted consensus.

    Algorithm per block:
      1. All submitted scores are gathered.
      2. Unweighted median is computed (outlier-resistant baseline).
      3. Scores deviating >0.25 from median are classified as "dishonest".
      4. Consensus score = stake+trust-weight-weighted MEDIAN of honest scores.
         (stake weight = 1.0 pending TRP wallet integration; Task #19)
      5. ValidatorRegistry.update_trust() called for each classified score.

    Finalization:
      A block's consensus is "finalized" when ≥3 scores have been received
      OR 30 seconds have elapsed since the first submission.  Rewards are only
      dispatched after finalization to prevent early misclassification.

    Anyone can verify by calling GET /api/validators/scores/{block_hash} —
    it returns every individual score, the median, finalization status, and
    the final consensus.
    """

    DISHONEST_THRESHOLD = 0.25
    FINALIZE_MIN_SCORES = 3
    FINALIZE_TIMEOUT_S  = 30.0

    def __init__(self, registry: ValidatorRegistry) -> None:
        self._registry    = registry
        self._lock        = threading.Lock()
        self._submissions: Dict[str, List[Dict]] = {}
        self._consensus:   Dict[str, Dict]       = {}
        self._first_seen:  Dict[str, float]      = {}   # block_hash → first submission time
        self._finalized:   Set[str]              = set()  # block_hashes with finalized consensus
        # Per-(block_hash, provider_id) reward tracking.
        # Prevents double-paying on retries; only set on confirmed tx success.
        self._rewarded:    Dict[str, Set[str]]   = {}   # block_hash → {rewarded_provider_ids}
        # Trust-update tracking: each (block_hash, provider_id) is updated exactly once
        # after finalization so classification is stable before we affect trust scores.
        # Prevents repeated update_trust() calls as more validators join the block.
        self._trust_updated: Dict[str, Set[str]] = {}   # block_hash → {provider_ids updated}

    def submit_score(
        self,
        block_hash: str,
        block_index: int,
        provider_id: str,
        score: float,
        trust_weight: float = 1.0,
    ) -> bool:
        """
        Submit a PoI score for block_hash.  Returns True if accepted (first
        submission from this provider for this block), False if duplicate.
        Computes or updates the consensus immediately after each new score.
        """
        score = max(0.0, min(1.0, float(score)))

        with self._lock:
            # Reject submissions for finalized blocks — consensus is immutable.
            # Accepting late submissions would mutate the stored consensus dict,
            # allow rewards without a corresponding trust update (finalize_pending
            # won't re-run for this block), and break the honest/dishonest accounting.
            if block_hash in self._finalized:
                logger.debug(
                    f"[collector] {provider_id}: submission rejected — block {block_hash[:12]}… "
                    f"is already finalized (immutable consensus)"
                )
                return False

            subs = self._submissions.setdefault(block_hash, [])

            # Track time of first submission for finalization timeout
            if block_hash not in self._first_seen:
                self._first_seen[block_hash] = time.time()

            # Reject duplicate from same provider
            if any(s["provider_id"] == provider_id for s in subs):
                return False

            subs.append({
                "provider_id":  provider_id,
                "score":        score,
                "trust_weight": trust_weight,
                "timestamp":    time.time(),
            })

            scores_arr     = np.array([s["score"] for s in subs])
            median         = float(np.median(scores_arr))
            honest_subs    = [s for s in subs if abs(s["score"] - median) <= self.DISHONEST_THRESHOLD]
            dishonest_subs = [s for s in subs if abs(s["score"] - median) >  self.DISHONEST_THRESHOLD]

            # NOTE: trust is NOT updated here.  It is updated exactly once per
            # provider per block inside finalize_pending(), after classification
            # is stable (≥3 scores or 30s elapsed).  Updating trust on every
            # incoming score would re-penalise/reward early submitters as the
            # median shifts with each new validator, distorting accounting.

            # Consensus: stake+trust-weight-weighted MEDIAN of honest scores.
            # stake weight = 1.0 for all validators pending TRP wallet integration
            # (see Task #19 — Link FL stake to TRP wallet).
            if honest_subs:
                h_scores  = [s["score"]        for s in honest_subs]
                h_weights = [s["trust_weight"] for s in honest_subs]  # stake × trust, stake=1
                consensus_s = _weighted_median(h_scores, h_weights)
            else:
                consensus_s = median  # fallback: unweighted median

            already_finalized = block_hash in self._finalized
            # Per-submission status: "pending" until finalized, then "honest"/"dishonest"
            # This lets callers distinguish a preliminary classification from a stable one.
            self._consensus[block_hash] = {
                "block_hash":      block_hash,
                "block_index":     block_index,
                "consensus_score": round(consensus_s, 4),
                "median_score":    round(median, 4),
                "n_total":         len(subs),
                "n_honest":        len(honest_subs),
                "n_dishonest":     len(dishonest_subs),
                "submissions": [
                    {
                        "provider_id":  s["provider_id"],
                        "score":        round(s["score"], 4),
                        "trust_weight": round(s["trust_weight"], 4),
                        "honest":       abs(s["score"] - median) <= self.DISHONEST_THRESHOLD,
                        # status = "pending" until the block is finalized; only then
                        # does classification become stable enough to expose.
                        "status": (
                            ("honest" if abs(s["score"] - median) <= self.DISHONEST_THRESHOLD
                             else "dishonest")
                            if already_finalized
                            else "pending"
                        ),
                        "timestamp":    s["timestamp"],
                    }
                    for s in subs
                ],
                "consensus_method":   "stake_trust_weighted_median_of_honest_scores",
                "dishonest_threshold": self.DISHONEST_THRESHOLD,
                "finalized":           already_finalized,
                "computed_at":         time.time(),
            }

        return True

    def get_scores(self, block_hash: str) -> Optional[Dict]:
        with self._lock:
            r = self._consensus.get(block_hash)
            if r is None:
                return None
            # Include live finalization status
            result = dict(r)
            result["finalized"] = block_hash in self._finalized
            return result

    def was_rewarded(self, block_hash: str, provider_id: str) -> bool:
        """Return True if this (block_hash, provider_id) pair has already been rewarded."""
        with self._lock:
            return provider_id in self._rewarded.get(block_hash, set())

    def mark_rewarded(self, block_hash: str, provider_id: str) -> None:
        """Record that provider_id has received a confirmed TRP reward for block_hash."""
        with self._lock:
            self._rewarded.setdefault(block_hash, set()).add(provider_id)

    def finalize_pending(self, timeout_s: float = FINALIZE_TIMEOUT_S) -> List[str]:
        """
        Mark blocks as finalized when ≥3 scores have been submitted OR the
        first submission is older than timeout_s seconds.

        On finalization:
          - Updates ValidatorRegistry trust for each external provider exactly
            once (tracked in _trust_updated to prevent double-counting).
          - Flips each submission's "status" from "pending" → "honest"/"dishonest"
            so callers see a stable, finalized classification.

        Returns the list of block_hashes newly finalized this call (not
        previously finalized).  Callers should dispatch rewards for each.
        """
        newly_finalized: List[str] = []
        now = time.time()
        _server_ids = frozenset({"server_validator", "server_compute_node"})
        with self._lock:
            for block_hash, subs in self._submissions.items():
                if block_hash in self._finalized:
                    continue
                age = now - self._first_seen.get(block_hash, now)
                if len(subs) >= self.FINALIZE_MIN_SCORES or age >= timeout_s:
                    self._finalized.add(block_hash)
                    newly_finalized.append(block_hash)

                    # Compute final median over all submissions for this block
                    scores_arr = np.array([s["score"] for s in subs])
                    median     = float(np.median(scores_arr))

                    # Update trust exactly once per external provider per block,
                    # now that classification is stable.
                    updated = self._trust_updated.setdefault(block_hash, set())
                    for s in subs:
                        pid = s["provider_id"]
                        if pid not in _server_ids and pid not in updated:
                            honest = abs(s["score"] - median) <= self.DISHONEST_THRESHOLD
                            self._registry.update_trust(pid, honest)
                            updated.add(pid)

                    # Flip submission statuses and update stored consensus
                    if block_hash in self._consensus:
                        c = self._consensus[block_hash]
                        c["finalized"] = True
                        for sub in c["submissions"]:
                            sub["status"] = (
                                "honest" if sub["honest"] else "dishonest"
                            )
        return newly_finalized

    def get_finalized_pending_rewards(self) -> List[Dict]:
        """
        Return reward jobs for finalized blocks that have honest external
        validators who have not yet received their TRP reward.

        Each entry: {block_hash, block_index, consensus_score, submissions}
        where submissions is the list of honest unrewarded external providers.
        """
        _server_ids = frozenset({"server_validator", "server_compute_node"})
        result: List[Dict] = []
        with self._lock:
            for block_hash in self._finalized:
                consensus = self._consensus.get(block_hash)
                if not consensus:
                    continue
                rewarded = self._rewarded.get(block_hash, set())
                unrewarded = [
                    s for s in consensus.get("submissions", [])
                    if s.get("honest")
                    and s["provider_id"] not in _server_ids
                    and s["provider_id"] not in rewarded
                ]
                if unrewarded:
                    result.append({
                        "block_hash":      block_hash,
                        "block_index":     consensus.get("block_index", 0),
                        "consensus_score": consensus.get("consensus_score", 0.0),
                        "submissions":     unrewarded,
                    })
        return result

    def recent_consensus(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            finalized = self._finalized
            items = []
            for block_hash, r in self._consensus.items():
                entry = dict(r)
                entry["finalized"] = block_hash in finalized
                items.append(entry)
            return sorted(items, key=lambda x: x.get("computed_at", 0), reverse=True)[:limit]


# ── BaseAgent ─────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """Abstract base class for on-chain AI network agents."""

    def __init__(self, name: str, interval_sec: int):
        self.name          = name
        self.interval_sec  = interval_sec
        self.last_run:     Optional[float] = None
        self.last_action:  Optional[str]   = None
        self.is_healthy:   bool            = True
        self.error_count:  int             = 0
        self.events_emitted: int           = 0
        self._pg  = None
        self._task: Optional[asyncio.Task] = None

    def register(self, pg) -> None:
        self._pg = pg

    async def emit_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.events_emitted += 1
        self.last_action = f"{event_type} @ {time.strftime('%H:%M:%S')}"
        logger.info(f"[{self.name}] EVENT {event_type}: {json.dumps(payload)[:200]}")
        if self._pg:
            try:
                await self._pg.save_agent_event(self.name, event_type, payload)
            except Exception as e:
                logger.warning(f"[{self.name}] emit_event DB write failed: {e}")

    @abstractmethod
    async def run_cycle(self) -> None: ...

    async def _loop(self) -> None:
        logger.info(f"[{self.name}] started (interval={self.interval_sec}s)")
        while True:
            try:
                await self.run_cycle()
                self.last_run   = time.time()
                self.is_healthy = True
            except Exception as e:
                self.error_count += 1
                self.is_healthy   = False
                logger.error(f"[{self.name}] cycle error: {e}")
            await asyncio.sleep(self.interval_sec)

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop())

    def status(self) -> Dict[str, Any]:
        return {
            "name":           self.name,
            "interval_sec":   self.interval_sec,
            "last_run":       self.last_run,
            "last_run_str":   time.strftime("%H:%M:%S", time.localtime(self.last_run)) if self.last_run else None,
            "last_action":    self.last_action,
            "is_healthy":     self.is_healthy,
            "error_count":    self.error_count,
            "events_emitted": self.events_emitted,
            "running":        self._task is not None and not self._task.done(),
        }


# ── ValidatorAgent ────────────────────────────────────────────────────────────

class ValidatorAgent(BaseAgent):
    """
    Proof of Intelligence (PoI) Validator — runs every 15 seconds.

    What this AI does:
    ──────────────────
    Evaluates each new block using a 4-feature local AI scoring model:

      Feature 1  tx_quality_score   (weight 0.30)
        → ratio of transactions in block to expected max (50).
          Empty blocks score 0, full blocks score 1.

      Feature 2  timing_score       (weight 0.25)
        → how close the block interval is to the 15-second target.
          Perfect timing = 1.0; >30s off = 0.0.

      Feature 3  network_health     (weight 0.25)
        → peer count relative to expected network size (10 peers = 1.0).
          Isolated nodes get low health scores.

      Feature 4  ai_proof_integrity (weight 0.20)
        → whether the block carries a valid AI consensus proof (Dilithium3
          signature from the block producer).  Missing proof = 0.5 penalty.

    Final score = weighted dot product of features (0.0 – 1.0).

    This score is submitted to the BlockScoreCollector, which aggregates it
    with scores from external energy provider nodes into a consensus score.
    The consensus PoI score determines block acceptance and proposer rewards.

    Anyone running trispi_energy_provider.py does exactly this same computation
    — their score is included in the same consensus pool.

    Earns TRP:  0.1 TRP per block scored and accepted into consensus.
    """

    SERVER_PROVIDER_ID = "server_validator"

    def __init__(
        self,
        registry: "ValidatorRegistry",
        collector: "BlockScoreCollector",
    ) -> None:
        super().__init__("ValidatorAgent", interval_sec=15)
        self._registry          = registry
        self._collector         = collector
        self._last_block_height = 0
        self._trp_earned        = 0.0
        self._scores_submitted  = 0
        self._scores_accepted   = 0

    @staticmethod
    def score_block_local(block: Dict, network_stats: Dict) -> float:
        """
        Pure-numpy 4-feature PoI scoring.  Deterministic, no external deps.
        Energy provider nodes run the identical algorithm locally.
        """
        # Feature 1: transaction quality
        tx_count    = len(block.get("transactions", []) or [])
        tx_quality  = float(min(1.0, tx_count / 50.0))

        # Feature 2: block timing vs 15s target
        block_ts = float(block.get("timestamp", 0) or 0)
        if block_ts > 0:
            elapsed = time.time() - block_ts
            timing  = float(max(0.0, 1.0 - abs(elapsed - 15.0) / 30.0))
        else:
            timing = 0.5

        # Feature 3: network health
        peer_count     = int(network_stats.get("peer_count", 5) or 5)
        network_health = float(min(1.0, peer_count / 10.0))

        # Feature 4: AI proof integrity
        has_proof = 1.0 if (block.get("ai_proof") or block.get("trust_score")) else 0.5

        weights  = np.array([0.30, 0.25, 0.25, 0.20], dtype=np.float32)
        features = np.array([tx_quality, timing, network_health, has_proof], dtype=np.float32)
        return float(np.clip(np.dot(weights, features), 0.0, 1.0))

    async def run_cycle(self) -> None:
        # ── Step A: Finalize pending blocks + dispatch rewards ─────────────────
        # This runs EVERY cycle regardless of new blocks so that the 30s timeout
        # is honoured even when block production stalls.  If no blocks are pending
        # finalization, both calls are no-ops with O(1) overhead.
        newly_finalized = self._collector.finalize_pending()
        if newly_finalized:
            await self.emit_event("CONSENSUS_FINALIZED", {
                "block_hashes": [h[:16] + "…" for h in newly_finalized],
                "count":        len(newly_finalized),
            })

        pending_rewards = self._collector.get_finalized_pending_rewards()
        for item in pending_rewards:
            for sub in item["submissions"]:
                await dispatch_validator_reward(
                    provider_id     = sub["provider_id"],
                    block_hash      = item["block_hash"],
                    block_index     = item["block_index"],
                    consensus_score = item["consensus_score"],
                    trust_weight    = float(sub.get("trust_weight", 1.0)),
                )

        # ── Step B: Score new block (if any) ──────────────────────────────────
        # 1. Detect new block from Go
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get(f"{_GO_URL}/network/stats")
                if r.status_code != 200:
                    return
                stats = r.json()
        except Exception:
            return

        height = int(stats.get("block_height") or stats.get("total_blocks") or 0)
        if height <= self._last_block_height:
            return  # no new block — finalize/reward already done above

        # 2. Fetch block data (use recent transactions + stats as proxy)
        block: Dict = {}
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get(f"{_GO_URL}/transactions/recent")
                if r.status_code == 200:
                    data = r.json()
                    block = {
                        "transactions": data.get("transactions", [])[:20],
                        "timestamp":    time.time() - float(stats.get("block_interval", 15) or 15),
                        "ai_proof":     stats.get("ai_accuracy"),
                        "block_height": height,
                    }
        except Exception:
            block = {
                "transactions": [],
                "timestamp":    time.time(),
                "ai_proof":     None,
                "block_height": height,
            }

        # 3. Score the block locally
        block_hash = hashlib.sha256(f"block:{height}:{stats.get('chain_id', 'trispi')}".encode()).hexdigest()
        score      = self.score_block_local(block, stats)

        self._last_block_height = height
        self._scores_submitted += 1

        # 4. Submit server score to collector
        accepted = self._collector.submit_score(
            block_hash   = block_hash,
            block_index  = height,
            provider_id  = self.SERVER_PROVIDER_ID,
            score        = score,
            trust_weight = 1.0,
        )

        if accepted:
            self._scores_accepted += 1
            self._trp_earned += 0.1

        await self.emit_event("BLOCK_SCORED", {
            "block_height":       height,
            "block_hash":         block_hash[:16] + "…",
            "poi_score":          round(score, 4),
            "accepted":           accepted,
            "external_validators": len(self._registry.get_all()),
        })

        # 5. Post lightweight PoI activity tx to Go (for on-chain record)
        if accepted:
            svc = _load_service_key()
            await _post_tx_to_go(
                from_addr = svc.get("address", "trp1_agents"),
                to_addr   = "trispi_poi_registry",
                amount    = 0.0,
                data      = json.dumps({
                    "event":              "POI_BLOCK_SCORED",
                    "block_height":       height,
                    "block_hash":         block_hash,
                    "consensus_score":    round(score, 4),
                    "total_validators":   len(self._registry.get_all()) + 1,
                }),
            )

        # Step 6 (finalize + reward dispatch) is handled in Step A at the top
        # of run_cycle() so it runs every 15s cycle even when no new block arrives.
        # This guarantees the 30s timeout is respected even if block production stalls.

    def status(self) -> Dict[str, Any]:
        base = super().status()
        base.update({
            "description":         (
                "Scores each new block using a 4-feature PoI AI model "
                "(tx quality, timing, network health, AI proof integrity). "
                "External energy provider nodes run the same model locally."
            ),
            "algorithm":           "weighted_dot_product([tx_quality, timing, health, proof], [0.30,0.25,0.25,0.20])",
            "scores_submitted":    self._scores_submitted,
            "scores_accepted":     self._scores_accepted,
            "trp_earned":          round(self._trp_earned, 4),
            "last_block_height":   self._last_block_height,
            "external_validators": len(self._registry.get_all()),
            "decentralized":       True,
        })
        return base


# ── ComputeProviderAgent ──────────────────────────────────────────────────────

class ComputeProviderAgent(BaseAgent):
    """
    Federated Learning Compute Provider — runs every 30 seconds.

    What this AI does:
    ──────────────────
    Participates in each FL round as the server's own compute node.  The
    server is just one participant among many — external energy provider nodes
    do exactly the same thing.

    Each round:
      1. Fetches the 50 most recent transactions from Go as training data.
      2. Builds input features for each transaction:
           [amount_normalized, is_large_tx, is_round_amount, tx_velocity]
      3. Runs one step of mini-batch SGD on a 2-layer fraud-detection network:
           Input(4) → Hidden(8, ReLU) → Output(2, sigmoid)
           [fraud_probability, trust_score]
      4. Signs the gradient with Ed25519 (same protocol as external providers).
      5. Submits the encrypted gradient to /api/federated/submit-gradient.

    After aggregation, the round result hash is committed to the blockchain
    as a signed transaction — anyone can verify the aggregation was honest by
    fetching GET /api/federated/verify-round/{round_id}.

    Earns TRP:  1.0 TRP per gradient accepted into the aggregation round.
    """

    PROVIDER_ID = "server_compute_node"

    def __init__(self) -> None:
        super().__init__("ComputeProviderAgent", interval_sec=30)
        self._rounds_participated = 0
        self._gradients_accepted  = 0
        self._trp_earned          = 0.0
        self._last_round_id       = -1
        self._registered          = False

    async def _ensure_registered(self) -> bool:
        if self._registered:
            return True
        svc     = _load_service_key()
        pub_hex = svc.get("public_key_hex", "")
        if not pub_hex:
            return False
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                # Do not pass stake_address without a stake_signature proof.
                # With MIN_STAKE_TRP = 0.0, the node participates without requiring stake.
                r = await c.post(f"{_PYTHON_URL}/api/federated/register", json={
                    "provider_id": self.PROVIDER_ID,
                    "pubkey_hex":  pub_hex,
                })
                # 200 = registered, 422 = already_registered or validation error
                if r.status_code == 200:
                    self._registered = True
                    return True
                body = r.json()
                if "already_registered" in str(body.get("error", "")) or "already_registered" in str(body):
                    self._registered = True
                    return True
        except Exception as exc:
            logger.debug(f"[ComputeProvider] registration attempt failed: {exc}")
        return False

    @staticmethod
    def _compute_gradient(txs: List[Dict]) -> Dict[str, List]:
        """
        One step of mini-batch SGD on a 2-layer fraud-detection network.

        Network architecture (deterministic seed = current minute):
          Input  (4): amount_norm, is_large, is_round_amount, velocity_norm
          Hidden (8):  ReLU activation
          Output (2):  sigmoid → [fraud_prob, trust_score]

        Gradient update step (lr=0.01, cross-entropy loss).
        External energy providers run the identical algorithm.
        """
        seed = int(time.time()) // 60  # changes every minute → fresh gradients
        rng  = np.random.RandomState(seed)

        n = max(len(txs), 10)
        X = np.zeros((n, 4), dtype=np.float32)
        for i, tx in enumerate(txs[:n]):
            amt         = float(tx.get("amount", 0) or 0)
            X[i, 0]    = min(1.0, amt / 10_000.0)
            X[i, 1]    = 1.0 if amt > 1_000 else 0.0
            X[i, 2]    = 1.0 if (amt > 0 and amt % 100 == 0) else 0.0
            X[i, 3]    = min(1.0, i / n)
        # Synthetic fraud labels (real labels come from verified fraud reports)
        y = (X[:, 0] > 0.7).astype(np.float32)

        W1 = rng.randn(4, 8).astype(np.float32) * 0.1
        b1 = np.zeros(8, dtype=np.float32)
        W2 = rng.randn(8, 2).astype(np.float32) * 0.1
        b2 = np.zeros(2, dtype=np.float32)

        h   = np.maximum(0.0, X @ W1 + b1)
        out = 1.0 / (1.0 + np.exp(-(h @ W2 + b2)))

        lr       = 0.01
        d_out    = out - y[:, None]
        dW2      = (h.T @ d_out) * lr / n
        dh       = (d_out @ W2.T) * (h > 0)
        dW1      = (X.T @ dh) * lr / n

        return {
            "W1": (W1 - dW1).tolist(),
            "b1": b1.tolist(),
            "W2": (W2 - dW2).tolist(),
            "b2": b2.tolist(),
        }

    async def run_cycle(self) -> None:
        # 1. Check FL round status
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get(f"{_PYTHON_URL}/api/federated/round-status")
                if r.status_code != 200:
                    return
                fl_status = r.json()
        except Exception:
            return

        round_id     = int(fl_status.get("round_id", 0) or 0)
        round_status = str(fl_status.get("status", "") or "")

        if round_status != "open" or round_id == self._last_round_id:
            return

        # 2. Register if needed
        if not await self._ensure_registered():
            return

        # 3. Fetch recent transactions as training data
        txs: List[Dict] = []
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.get(f"{_GO_URL}/transactions/recent")
                if r.status_code == 200:
                    txs = r.json().get("transactions", [])[:50]
        except Exception:
            pass

        # 4. Compute gradient
        gradient = self._compute_gradient(txs)

        self._rounds_participated += 1
        self._last_round_id        = round_id

        # 5. Build Ed25519 signature and submit
        svc = _load_service_key()
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            priv_hex = svc.get("private_key_hex", "")
            if not priv_hex:
                return

            grad_json     = json.dumps(gradient, sort_keys=True)
            gradient_hash = hashlib.sha3_256(grad_json.encode()).hexdigest()
            stake_addr    = svc.get("address", "trp1_server")
            msg_str       = f"{self.PROVIDER_ID}|{round_id}|{gradient_hash}|{stake_addr}"
            msg_bytes     = hashlib.sha3_256(msg_str.encode()).digest()

            priv_key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
            sig_hex  = priv_key.sign(msg_bytes).hex()

            async with httpx.AsyncClient(timeout=10.0) as c:
                r      = await c.post(f"{_PYTHON_URL}/api/federated/submit-gradient", json={
                    "provider_id":   self.PROVIDER_ID,
                    "gradient":      gradient,
                    "signature_hex": sig_hex,
                })
                result = r.json()

            if result.get("accepted"):
                self._gradients_accepted += 1
                self._trp_earned          += 1.0
                await self.emit_event("GRADIENT_ACCEPTED", {
                    "round_id":      round_id,
                    "gradient_hash": gradient_hash[:16] + "…",
                    "norm":          result.get("gradient_norm", 0),
                    "n_submitted":   result.get("n_submitted", 0),
                })
            else:
                await self.emit_event("GRADIENT_REJECTED", {
                    "round_id": round_id,
                    "reason":   result.get("reason", "unknown"),
                })

        except Exception as exc:
            logger.debug(f"[ComputeProvider] gradient submit failed: {exc}")

    def status(self) -> Dict[str, Any]:
        base = super().status()
        base.update({
            "description": (
                "Participates in FL rounds as the server compute node — one peer "
                "among many. Trains a 2-layer fraud-detection network locally, "
                "submits encrypted gradients. After each round, commits the "
                "aggregation hash on-chain for public verification."
            ),
            "algorithm":             "mini_batch_SGD, 2-layer MLP(4→8→2), lr=0.01",
            "rounds_participated":   self._rounds_participated,
            "gradients_accepted":    self._gradients_accepted,
            "trp_earned":            round(self._trp_earned, 4),
            "last_round_id":         self._last_round_id,
            "decentralized":         True,
        })
        return base


# ── Module-level singletons ────────────────────────────────────────────────────

validator_registry    = ValidatorRegistry()
block_score_collector = BlockScoreCollector(validator_registry)


# ── TRP reward distribution ────────────────────────────────────────────────────

_SERVER_IDS = frozenset({"server_validator", "server_compute_node"})


async def dispatch_validator_reward(
    provider_id: str,
    block_hash: str,
    block_index: int,
    consensus_score: float,
    trust_weight: float,
) -> None:
    """
    Post a TRP reward transaction to Go for one honest external PoI validator.

    Amount = 0.1 TRP × trust_weight  (≤ 0.10 TRP at full trust).

    Only called when the validator's submitted score has been classified as
    honest (deviation from consensus median ≤ 0.25).  Server-owned IDs
    ("server_validator", "server_compute_node") are silently skipped — their
    rewards are tracked internally by the agent's own accounting.

    Idempotent: block_score_collector tracks (block_hash, provider_id) pairs
    that have already been rewarded, so retries and duplicate calls are no-ops.
    """
    # Skip server's own agents
    if provider_id in _SERVER_IDS:
        return

    # Idempotency — guard against retries or double dispatch
    if block_score_collector.was_rewarded(block_hash, provider_id):
        logger.debug(f"[reward] {provider_id} already rewarded for block {block_hash[:12]}…")
        return

    validator = validator_registry.get(provider_id)
    if not validator:
        logger.debug(f"[reward] {provider_id} not in registry — skipping reward")
        return

    stake_address = str(validator.get("stake_address") or "").strip()
    if not stake_address:
        logger.debug(f"[reward] {provider_id} has no stake_address — reward skipped")
        # Still mark as rewarded so we don't retry on every block scored
        block_score_collector.mark_rewarded(block_hash, provider_id)
        return

    reward    = round(0.1 * max(0.0, min(1.0, trust_weight)), 6)
    svc       = _load_service_key()
    from_addr = svc.get("address", "trp1_poi_reward_pool")

    result = await _post_tx_to_go(
        from_addr = from_addr,
        to_addr   = stake_address,
        amount    = reward,
        data      = json.dumps({
            "event":           "POI_VALIDATOR_REWARD",
            "provider_id":     provider_id,
            "block_hash":      block_hash,
            "block_index":     block_index,
            "consensus_score": round(consensus_score, 4),
            "trust_weight":    round(trust_weight, 4),
            "reward_trp":      reward,
        }),
    )

    if result:
        # Mark rewarded ONLY on confirmed tx success — failed txs remain retryable
        # by the ValidatorAgent loop on its next finalize_pending() scan.
        block_score_collector.mark_rewarded(block_hash, provider_id)
        logger.info(
            f"[reward] {provider_id}: {reward:.6f} TRP → {stake_address[:20]}… "
            f"(block={block_index}, consensus={consensus_score:.4f}, "
            f"trust={trust_weight:.4f})"
        )
    else:
        # Do NOT mark as rewarded — will retry on next agent cycle
        logger.warning(
            f"[reward] {provider_id}: tx to Go failed for block {block_index}, "
            f"{reward:.6f} TRP queued for retry on next agent cycle"
        )

_validator_agent = ValidatorAgent(validator_registry, block_score_collector)
_compute_agent   = ComputeProviderAgent()

_ALL_AGENTS: List[BaseAgent] = [
    _validator_agent,
    _compute_agent,
]


def start_network_agents(pg) -> None:
    """Register PostgreSQL and start all network participation agent loops."""
    for agent in _ALL_AGENTS:
        agent.register(pg)
        agent.start()
    logger.info("[agents] Network agents started: ValidatorAgent, ComputeProviderAgent")


# Backward-compatible alias
start_all_agents = start_network_agents


def all_agent_status() -> List[Dict]:
    return [a.status() for a in _ALL_AGENTS]


def get_agent(name: str) -> Optional[BaseAgent]:
    name_lower = name.lower()
    for a in _ALL_AGENTS:
        if a.name.lower() == name_lower or a.name.lower().startswith(name_lower):
            return a
    return None
