#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║        TRISPI Energy Provider Node  —  trispi_energy_provider.py           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Run this script on any PC/GPU to earn TRP by contributing compute to the   ║
║  TRISPI blockchain network.  No blockchain knowledge required.               ║
║                                                                              ║
║  USAGE                                                                       ║
║    python trispi_energy_provider.py --node http://<server>:8000             ║
║    python trispi_energy_provider.py --node http://localhost:8000            ║
║    python trispi_energy_provider.py --help                                  ║
║                                                                              ║
║  REQUIREMENTS  (pip install httpx numpy cryptography)                       ║
║    httpx       — async HTTP client                                           ║
║    numpy       — matrix math for the local AI models                        ║
║    cryptography — Ed25519 key generation and signing                        ║
║                                                                              ║
║  WHAT THIS NODE DOES                                                         ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │ Loop 1 — PoI Validator (every 15 seconds)                           │    ║
║  │   Detects new blocks → runs 4-feature AI scoring model locally →    │    ║
║  │   signs score with Ed25519 → submits to network consensus pool →    │    ║
║  │   earns 0.1 TRP per accepted score                                  │    ║
║  │                                                                     │    ║
║  │ Loop 2 — FL Compute Provider (every 30 seconds)                     │    ║
║  │   Polls for open FL rounds → downloads model → trains locally on   │    ║
║  │   recent tx data → submits encrypted gradient → earns 1.0 TRP per  │    ║
║  │   gradient accepted into aggregation                                │    ║
║  │                                                                     │    ║
║  │ Loop 3 — TX Validator (every 5 seconds)                             │    ║
║  │   Polls pending transactions → runs local fraud detection AI →      │    ║
║  │   submits verdict → earns 0.01 TRP per accepted verdict             │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
║  KEYS  (~/.trispi/provider_key.json)                                         ║
║    Generated automatically on first run.  Back up this file.                ║
║    Your TRP address is derived from the public key.                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import time
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Dependency checks ─────────────────────────────────────────────────────────

_MISSING = []
try:
    import httpx
except ImportError:
    _MISSING.append("httpx")

try:
    import numpy as np
except ImportError:
    _MISSING.append("numpy")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
        PrivateFormat,
        NoEncryption,
    )
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_OK = True
except ImportError:
    _MISSING.append("cryptography")
    _CRYPTO_OK = False

if _MISSING:
    print(f"\n[ERROR] Missing dependencies: {', '.join(_MISSING)}")
    print(f"  Install with:  pip install {' '.join(_MISSING)}\n")
    sys.exit(1)

# Optional: GPU acceleration via PyTorch
_TORCH_OK = False
_GPU_NAME  = "CPU mode"
try:
    import torch
    _TORCH_OK = True
    if torch.cuda.is_available():
        _GPU_NAME = torch.cuda.get_device_name(0)
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        _GPU_NAME = "Apple MPS"
    else:
        _GPU_NAME = "CPU (torch)"
except ImportError:
    pass


# ── CPU / RAM stats (no external deps) ───────────────────────────────────────

def _sys_stats() -> Tuple[float, float]:
    """
    Return (cpu_percent, ram_mb) using only stdlib.
    On Linux, reads /proc/stat and /proc/self/status.
    Returns (0.0, 0.0) on other platforms.
    """
    cpu_pct = 0.0
    ram_mb  = 0.0
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    ram_mb = float(line.split()[1]) / 1024.0
                    break
    except Exception:
        pass
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        fields = list(map(int, line.split()[1:]))
        idle   = fields[3]
        total  = sum(fields)
        # Store in module-level vars for delta calculation
        prev = _sys_stats._prev  # type: ignore[attr-defined]
        if prev:
            d_idle  = idle  - prev[0]
            d_total = total - prev[1]
            cpu_pct = max(0.0, (1.0 - d_idle / max(d_total, 1)) * 100.0)
        _sys_stats._prev = (idle, total)  # type: ignore[attr-defined]
    except Exception:
        pass
    return cpu_pct, ram_mb

_sys_stats._prev = None  # type: ignore[attr-defined]


# ── AES-256-GCM gradient encryption ──────────────────────────────────────────

def _derive_aes_key(pubkey_hex: str, provider_id: str, round_id: int) -> bytes:
    """
    Derive the per-provider per-round AES-256-GCM key — identical to server.

        round_nonce = sha3_256(f"{round_id}|{provider_id}")  (raw bytes)
        aes_key     = sha3_256(provider_pubkey_bytes || round_nonce)  (raw bytes)
    """
    pubkey_bytes = bytes.fromhex(pubkey_hex)
    round_nonce  = hashlib.sha3_256(f"{round_id}|{provider_id}".encode()).digest()
    return hashlib.sha3_256(pubkey_bytes + round_nonce).digest()


def _encrypt_gradient(weights: Dict, aes_key: bytes) -> Dict:
    """Encrypt a weights dict with AES-256-GCM.  Returns {"ciphertext", "nonce", "encrypted"}."""
    plaintext = json.dumps(weights, sort_keys=True, default=str).encode()
    nonce     = os.urandom(12)
    ct        = AESGCM(aes_key).encrypt(nonce, plaintext, None)
    return {"ciphertext": ct.hex(), "nonce": nonce.hex(), "encrypted": True}


# ── Key management ────────────────────────────────────────────────────────────

KEY_DIR  = Path.home() / ".trispi"
KEY_FILE = KEY_DIR / "provider_key.json"


def _derive_trp_address(pubkey_bytes: bytes) -> str:
    """TRP address = 'trp1' + first 40 hex chars of sha3_256(pubkey_bytes)."""
    return "trp1" + hashlib.sha3_256(pubkey_bytes).hexdigest()[:40]


def load_or_create_key() -> Dict[str, str]:
    """
    Load the Ed25519 keypair from ~/.trispi/provider_key.json, or generate
    a fresh one on first run.  The private key is stored with 600 permissions.
    """
    KEY_DIR.mkdir(parents=True, exist_ok=True)

    if KEY_FILE.exists():
        with open(KEY_FILE) as f:
            data = json.load(f)
        # Validate
        if data.get("private_key_hex") and data.get("public_key_hex") and data.get("address"):
            return data

    print("\n[KEY] Generating new Ed25519 keypair...")
    priv_key  = Ed25519PrivateKey.generate()
    pub_key   = priv_key.public_key()
    priv_bytes = priv_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    pub_bytes  = pub_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    address    = _derive_trp_address(pub_bytes)

    data = {
        "private_key_hex": priv_bytes.hex(),
        "public_key_hex":  pub_bytes.hex(),
        "address":         address,
        "created_at":      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    with open(KEY_FILE, "w") as f:
        json.dump(data, f, indent=2)
    os.chmod(KEY_FILE, 0o600)

    print(f"[KEY] Keypair saved to {KEY_FILE}")
    print(f"[KEY] Your TRP address: {address}")
    print(f"[KEY] IMPORTANT: Back up {KEY_FILE} — it holds your private key!\n")
    return data


def _sign_message(key_data: Dict, message: bytes) -> str:
    """Sign message bytes with Ed25519 private key.  Returns hex signature."""
    priv_bytes = bytes.fromhex(key_data["private_key_hex"])
    priv_key   = Ed25519PrivateKey.from_private_bytes(priv_bytes)
    return priv_key.sign(message).hex()


# ── Local PoI scoring model ───────────────────────────────────────────────────

def score_block_local(block: Dict, network_stats: Optional[Dict] = None) -> float:
    """
    4-feature Proof of Intelligence scoring model (numpy, no external deps).

    MUST match ValidatorAgent.score_block_local() on the server exactly —
    scores deviating >0.25 from the consensus median are classified as dishonest
    and receive no TRP reward (and trust_weight is penalised -5%).

    Features and weights:
      block_liveness (0.35) — 0.75 baseline + 0.25 * tx_fill_ratio
        Empty blocks score 0.75 (network alive, no user activity yet).
        Full 50-tx blocks score 1.0.

      timing_score   (0.25) — 1.0 if block produced within ±5 s of 15 s target.
        Subtract 3 s propagation from elapsed time before scoring.

      network_health (0.20) — peer_count / 20 (capped at 1.0).
        TRISPI needs ≥4 peers for BFT; full credit at 20 peers.

      ai_proof       (0.20) — Go's per-block AI score or proof accuracy (0.60–0.85).
        Falls back to 0.75 when no proof attached.

    Returns a float in [0.0, 1.0].
    """
    ns = network_stats or {}

    # Feature 1: block production liveness
    tx_count       = int(block.get("tx_count", 0) or len(block.get("transactions", []) or []))
    block_liveness = 0.75 + 0.25 * float(min(1.0, tx_count / 50.0))

    # Feature 2: block timing regularity (15 s target)
    ai_score_go = float(block.get("ai_score", block.get("AIScore", 0.0)) or 0.0)
    block_ts    = float(block.get("timestamp", 0) or 0)
    if block_ts > 0:
        elapsed  = time.time() - block_ts
        adjusted = max(0.0, elapsed - 3.0)   # subtract ~3 s propagation
        timing   = float(max(0.0, 1.0 - abs(adjusted - 15.0) / 30.0))
    elif ai_score_go > 0:
        timing = ai_score_go
    else:
        timing = 0.75   # assume on-schedule

    # Feature 3: network consensus health
    peer_count     = int(ns.get("peer_count", ns.get("p2p_peers", 5)) or 5)
    network_health = float(min(1.0, peer_count / 20.0))

    # Feature 4: AI proof integrity
    ai_proof = block.get("ai_proof") or block.get("AIProof") or {}
    if isinstance(ai_proof, dict) and ai_proof.get("accuracy", 0) > 0:
        has_proof = float(min(1.0, ai_proof["accuracy"]))
    elif block.get("trust_score"):
        has_proof = float(min(1.0, block["trust_score"]))
    elif ai_score_go > 0:
        has_proof = ai_score_go
    else:
        has_proof = 0.75

    weights  = np.array([0.35, 0.25, 0.20, 0.20], dtype=np.float32)
    features = np.array([block_liveness, timing, network_health, has_proof], dtype=np.float32)
    return float(np.clip(np.dot(weights, features), 0.0, 1.0))


# ── Shared fraud detection model ──────────────────────────────────────────────
# Try to import the canonical fraud_model.py that the server also uses so both
# sides of consensus run identical logic.  Falls back to the inline 5-feature
# numpy implementation when the server package is not on sys.path (standalone
# invocation from a different machine).

def _local_score_transaction(tx: Dict) -> float:
    """
    Fallback 5-feature fraud detection (numpy only).  Matches fraud_model.py
    exactly so standalone providers reach the same verdicts as the server.

    Features / weights (sum = 1.0):
      amount_anomaly     0.30 — z-score deviation from historical mean
      address_age_score  0.25 — new addresses are higher risk
      velocity_score     0.20 — rapid successive txs from one address
      pattern_score      0.15 — round-number amounts (bot signature)
      graph_score        0.10 — one-sided send/receive ratio
    """
    amt     = float(tx.get("amount", 0) or 0)
    avg     = float(tx.get("sender_avg_tx",   50.0) or 50.0)
    std     = float(tx.get("sender_std_tx",  200.0) or 200.0)
    if std < 1.0:
        std = 1.0
    z = abs(amt - avg) / std

    # 1. amount_anomaly
    f1 = float(np.clip(z / 5.0, 0.0, 1.0))
    # 2. address_age_score
    if tx.get("is_new_sender"):
        f2 = 1.0
    else:
        count = float(tx.get("sender_tx_count", 100) or 100)
        f2 = float(np.clip(1.0 - (count / 50.0), 0.0, 1.0))
    # 3. velocity_score
    if tx.get("rapid_succession"):
        f3 = 1.0
    else:
        vel = float(tx.get("sender_tx_last_60s", 0) or 0)
        f3 = float(np.clip(vel / 5.0, 0.0, 1.0))
    # 4. pattern_score
    risk = 0.0
    if amt > 0 and amt == int(amt) and int(amt) % 10 == 0:
        risk = max(risk, 0.6)
    if amt >= 10_000 and amt == int(amt):
        risk = max(risk, 0.8)
    data = str(tx.get("data", "") or "")
    if amt == 0 and len(data) > 200:
        risk = max(risk, 0.5)
    f4 = float(np.clip(risk, 0.0, 1.0))
    # 5. graph_score
    recv  = float(tx.get("sender_recv_count", 10) or 10)
    send  = float(tx.get("sender_send_count", 10) or 10)
    total = recv + send
    f5    = 0.5 if total < 1 else float(np.clip(abs(recv - send) / total * 0.8, 0.0, 1.0))

    weights  = np.array([0.30, 0.25, 0.20, 0.15, 0.10], dtype=np.float32)
    features = np.array([f1, f2, f3, f4, f5], dtype=np.float32)
    return float(np.clip(np.dot(weights, features), 0.0, 1.0))


# Try to import the server-side canonical module (available when running from
# inside the repo); otherwise use the inline fallback above.
try:
    import os as _os, sys as _sys
    _here = _os.path.dirname(_os.path.abspath(__file__))
    _app_dir = _os.path.join(_here, "python-ai-service", "app")
    if _app_dir not in _sys.path:
        _sys.path.insert(0, _app_dir)
    from fraud_model import score_transaction as score_transaction_local  # type: ignore
except Exception:
    score_transaction_local = _local_score_transaction  # type: ignore


# ── Local FL gradient computation ─────────────────────────────────────────────

def _build_features(txs: List[Dict], n: int = 20) -> "np.ndarray":
    """Build (n, 4) feature matrix from last n transactions."""
    X = np.zeros((n, 4), dtype=np.float32)
    for i, tx in enumerate(txs[:n]):
        amt     = float(tx.get("amount", 0) or 0)
        X[i, 0] = min(1.0, amt / 10_000.0)
        X[i, 1] = 1.0 if amt > 1_000 else 0.0
        X[i, 2] = 1.0 if (amt > 0 and amt % 100 == 0) else 0.0
        X[i, 3] = min(1.0, i / max(n, 1))
    return X


def _validate_raw_weights(w: Optional[Dict]) -> Optional[Dict]:
    """
    Accept model_weights only when every required key maps to a numeric list
    (i.e. raw arrays from /api/federated/global-model-weights).  Reject dicts
    whose values are metadata objects like {"shape": ..., "norm": ...} — those
    come from /api/federated/global-model and cannot be used as tensors.
    Returns None on any type mismatch so callers fall back to random init.
    """
    if not w:
        return None
    required = {"W1", "b1", "W2", "b2"}
    if not required.issubset(w.keys()):
        return None
    for k in required:
        v = w[k]
        # Must be a list (or nested list) of numbers, NOT a dict
        if not isinstance(v, list):
            return None
        # Spot-check: first leaf element must be a real number
        leaf = v[0] if v else None
        while isinstance(leaf, list):
            leaf = leaf[0] if leaf else None
        if not isinstance(leaf, (int, float)):
            return None
    return w


def compute_gradient(txs: List[Dict], model_weights: Optional[Dict] = None) -> Dict[str, List]:
    """
    One step of mini-batch SGD on a 2-layer fraud-detection network.

    Architecture: Input(4) → Hidden(8, ReLU) → Output(2, sigmoid)
    Loss: cross-entropy.  LR: 0.01.

    If PyTorch + CUDA/MPS is available, uses GPU tensors for the update.
    Otherwise falls back to pure numpy.  Both paths produce the same shapes.

    model_weights: optional dict of raw numeric arrays from
    /api/federated/global-model-weights to use as initialisation.  Values that
    are metadata dicts (from /api/federated/global-model) are silently rejected
    and random initialisation is used instead.
    """
    # Guard: reject summary-metadata weights (values are dicts, not numeric lists)
    model_weights = _validate_raw_weights(model_weights)

    n = max(len(txs), 10)
    X = _build_features(txs, n)
    y = (X[:, 0] > 0.7).astype(np.float32)

    # ── GPU path (PyTorch) ────────────────────────────────────────────────────
    if _TORCH_OK:
        try:
            import torch
            device = (
                torch.device("cuda") if torch.cuda.is_available()
                else torch.device("mps")
                if (hasattr(torch.backends, "mps") and torch.backends.mps.is_available())
                else torch.device("cpu")
            )
            Xt = torch.tensor(X, device=device)
            yt = torch.tensor(y, device=device).unsqueeze(1).expand(-1, 2)

            # Initialise from global model weights if available; else random
            if model_weights and "W1" in model_weights:
                W1 = torch.tensor(model_weights["W1"], dtype=torch.float32, device=device)
                b1 = torch.tensor(model_weights["b1"], dtype=torch.float32, device=device)
                W2 = torch.tensor(model_weights["W2"], dtype=torch.float32, device=device)
                b2 = torch.tensor(model_weights["b2"], dtype=torch.float32, device=device)
            else:
                W1 = torch.randn(4, 8, device=device) * 0.1
                b1 = torch.zeros(8, device=device)
                W2 = torch.randn(8, 2, device=device) * 0.1
                b2 = torch.zeros(2, device=device)

            for t in [W1, b1, W2, b2]:
                t.requires_grad_(True)

            h    = torch.clamp(Xt @ W1 + b1, min=0.0)
            logit = h @ W2 + b2
            loss  = torch.nn.functional.binary_cross_entropy_with_logits(logit, yt)
            loss.backward()

            lr = 0.01
            with torch.no_grad():
                W1_new = (W1 - lr * W1.grad).cpu().tolist()  # type: ignore[operator]
                b1_new = (b1 - lr * b1.grad).cpu().tolist()  # type: ignore[operator]
                W2_new = (W2 - lr * W2.grad).cpu().tolist()  # type: ignore[operator]
                b2_new = (b2 - lr * b2.grad).cpu().tolist()  # type: ignore[operator]

            return {"W1": W1_new, "b1": b1_new, "W2": W2_new, "b2": b2_new}
        except Exception:
            pass  # fall through to numpy path

    # ── Numpy path (CPU fallback) ─────────────────────────────────────────────
    rng = np.random.RandomState(int(time.time()) // 60)
    if model_weights and "W1" in model_weights:
        W1 = np.array(model_weights["W1"], dtype=np.float32)
        b1 = np.array(model_weights["b1"], dtype=np.float32)
        W2 = np.array(model_weights["W2"], dtype=np.float32)
        b2 = np.array(model_weights["b2"], dtype=np.float32)
    else:
        W1 = rng.randn(4, 8).astype(np.float32) * 0.1
        b1 = np.zeros(8, dtype=np.float32)
        W2 = rng.randn(8, 2).astype(np.float32) * 0.1
        b2 = np.zeros(2, dtype=np.float32)

    h    = np.maximum(0.0, X @ W1 + b1)
    out  = 1.0 / (1.0 + np.exp(-(h @ W2 + b2)))
    lr   = 0.01
    d_out = out - y[:, None]
    dW2  = (h.T @ d_out) * lr / n
    dh   = (d_out @ W2.T) * (h > 0)
    dW1  = (X.T @ dh) * lr / n

    return {
        "W1": (W1 - dW1).tolist(),
        "b1": b1.tolist(),
        "W2": (W2 - dW2).tolist(),
        "b2": b2.tolist(),
    }


# ── EnergyProvider node ───────────────────────────────────────────────────────

class EnergyProvider:
    """
    Runs three background loops to earn TRP by contributing compute.
    All state is collected in self.stats for the live dashboard.
    """

    def __init__(self, node_url: str, key_data: Dict, provider_id: str) -> None:
        self.node_url    = node_url.rstrip("/")
        self.key_data    = key_data
        self.provider_id = provider_id
        self.address     = key_data["address"]   # display address (trp1-prefixed)
        self.start_time  = time.time()

        # FL stake address: sha3_256(pubkey_bytes).hexdigest() — server's canonical derivation
        pub_bytes = bytes.fromhex(key_data["public_key_hex"])
        self.fl_stake_address = hashlib.sha3_256(pub_bytes).hexdigest()

        self.stats: Dict[str, Any] = {
            "poi_scores_submitted":   0,
            "poi_scores_accepted":    0,
            "poi_trp_earned":         0.0,
            "fl_rounds_participated": 0,
            "fl_gradients_accepted":  0,
            "fl_trp_earned":          0.0,
            "tx_verdicts_submitted":  0,
            "tx_verdicts_accepted":   0,
            "tx_trp_earned":          0.0,
            "last_block_height":      0,
            "last_fl_round":          -1,
            "last_error":             "",
            "connected":              False,
            "peer_count":             0,
            "current_block":          0,
            "cpu_pct":                0.0,
            "ram_mb":                 0.0,
        }
        self._lock                  = threading.Lock()
        self._registered_validator  = False
        self._registered_fl         = False
        self._seen_tx_hashes: set   = set()

    # ── HTTP helpers ─────────────────────────────────────────────────────────

    def _get(self, path: str, timeout: float = 5.0) -> Optional[Dict]:
        try:
            r = httpx.get(f"{self.node_url}{path}", timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception as exc:
            with self._lock:
                self.stats["last_error"] = f"GET {path}: {exc}"
        return None

    def _post(self, path: str, body: Dict, timeout: float = 10.0) -> Optional[Dict]:
        try:
            r = httpx.post(f"{self.node_url}{path}", json=body, timeout=timeout)
            return r.json()
        except Exception as exc:
            with self._lock:
                self.stats["last_error"] = f"POST {path}: {exc}"
        return None

    # ── Registration ─────────────────────────────────────────────────────────

    def _register_validator(self) -> bool:
        if self._registered_validator:
            return True
        result = self._post("/api/validators/register", {
            "provider_id":   self.provider_id,
            "pubkey_hex":    self.key_data["public_key_hex"],
            "stake_address": self.address,
        })
        if result and (result.get("registered") or "already_registered" in str(result.get("error", ""))):
            self._registered_validator = True
            return True
        return False

    def _register_fl(self) -> bool:
        if self._registered_fl:
            return True
        pubkey_hex    = self.key_data["public_key_hex"]
        stake_address = self.fl_stake_address  # sha3_256(pubkey_bytes).hexdigest()

        # Prove stake-address ownership:
        #   challenge = sha3_256("trispi_fl_stake_ownership:{pid}:{pubkey_hex}:{stake_addr}")
        #   signature = Ed25519.sign(challenge.digest())
        # Using the same key for FL and staking (single-key energy provider).
        challenge_raw = (
            f"trispi_fl_stake_ownership:{self.provider_id}:{pubkey_hex}:{stake_address}"
        ).encode()
        challenge_bytes = hashlib.sha3_256(challenge_raw).digest()
        stake_signature = _sign_message(self.key_data, challenge_bytes)

        result = self._post("/api/federated/register", {
            "provider_id":      self.provider_id,
            "pubkey_hex":       pubkey_hex,
            "stake_address":    stake_address,
            "stake_pubkey_hex": pubkey_hex,       # same key used for both FL and staking
            "stake_signature":  stake_signature,
        })
        if result and (result.get("registered") or "already_registered" in str(result.get("error", ""))):
            self._registered_fl = True
            return True
        return False

    # ── Loop 1: PoI Validator ─────────────────────────────────────────────────

    def run_poi_loop(self) -> None:
        """Detect new blocks, fetch them, score locally, submit signed score."""
        while True:
            try:
                stats = self._get("/api/network/status")
                if stats is None:
                    with self._lock:
                        self.stats["connected"] = False
                    time.sleep(5)
                    continue

                with self._lock:
                    self.stats["connected"]     = True
                    self.stats["peer_count"]    = int(
                        stats.get("p2p_peers", stats.get("peer_count", 0)) or 0
                    )
                    self.stats["current_block"] = int(
                        stats.get("block_height") or stats.get("total_blocks") or 0
                    )

                height = self.stats["current_block"]
                if height <= self.stats["last_block_height"]:
                    time.sleep(3)
                    continue

                # Fetch the latest block — try both explorer and chain endpoints
                blocks_resp = (
                    self._get("/api/chain/blocks?limit=1")
                    or self._get("/api/explorer/blocks?limit=1")
                    or {}
                )
                blocks      = blocks_resp.get("blocks", [])
                if not blocks:
                    time.sleep(5)
                    continue
                block = blocks[0]

                block_hash  = str(block.get("hash", "") or "")
                block_index = int(block.get("index", height) or height)
                if not block_hash:
                    time.sleep(5)
                    continue

                score = score_block_local(block, stats)

                with self._lock:
                    self.stats["last_block_height"] = height

                # Register if needed
                if not self._register_validator():
                    time.sleep(5)
                    continue

                # Sign: sha3_256(f'{provider_id}:{block_hash}:{block_index}:{score:.6f}')
                msg_str   = f"{self.provider_id}:{block_hash}:{block_index}:{score:.6f}"
                msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
                sig_hex   = _sign_message(self.key_data, msg_bytes)

                result = self._post("/api/validators/submit-score", {
                    "provider_id": self.provider_id,
                    "block_hash":  block_hash,
                    "block_index": block_index,
                    "score":       score,
                    "signature":   sig_hex,
                })

                with self._lock:
                    self.stats["poi_scores_submitted"] += 1
                    if result and result.get("accepted"):
                        self.stats["poi_scores_accepted"] += 1
                        self.stats["poi_trp_earned"]      += 0.1

            except Exception as exc:
                with self._lock:
                    self.stats["last_error"] = f"[PoI] {exc}"

            time.sleep(15)

    # ── Loop 2: FL Compute Provider ───────────────────────────────────────────

    def run_fl_loop(self) -> None:
        """Poll for open FL rounds, download global model, compute gradient, submit encrypted."""
        while True:
            try:
                fl_status = self._get("/api/federated/round-status")
                if fl_status is None:
                    time.sleep(10)
                    continue

                round_id     = int(fl_status.get("round_id", 0) or 0)
                round_status = str(fl_status.get("status", "") or "")

                if round_status != "open" or round_id == self.stats["last_fl_round"]:
                    time.sleep(10)
                    continue

                if not self._register_fl():
                    time.sleep(10)
                    continue

                # Step 1: Download current global model weights (raw numeric arrays).
                # Use /global-model-weights — /global-model only returns metadata dicts
                # (shape/norm summaries) which cannot be used as training initialisers.
                raw_model     = self._get("/api/federated/global-model-weights") or {}
                model_weights = raw_model.get("weights") if raw_model.get("has_weights") else None

                # Step 2: Fetch last 20 tx records as training data (spec: last 20 transactions)
                recent = self._get("/api/explorer/transactions") or {}
                txs    = recent.get("transactions", [])[:20]

                # Step 3: Compute gradient update against the global model (torch if available)
                gradient = compute_gradient(txs, model_weights=model_weights)

                # Step 4: Encrypt with AES-256-GCM (server rejects plaintext)
                #   aes_key = sha3_256(provider_pubkey || sha3_256(f"{round_id}|{provider_id}"))
                aes_key   = _derive_aes_key(self.key_data["public_key_hex"], self.provider_id, round_id)
                encrypted = _encrypt_gradient(gradient, aes_key)

                # Step 5: Sign over plaintext gradient hash + registered FL stake address
                grad_json     = json.dumps(gradient, sort_keys=True, default=str)
                gradient_hash = hashlib.sha3_256(grad_json.encode()).hexdigest()
                # Use fl_stake_address — this matches what the server stored at registration
                msg_str   = f"{self.provider_id}|{round_id}|{gradient_hash}|{self.fl_stake_address}"
                msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
                sig_hex   = _sign_message(self.key_data, msg_bytes)

                result = self._post("/api/federated/submit-gradient", {
                    "provider_id":   self.provider_id,
                    "gradient":      encrypted,   # AES-256-GCM encrypted packet
                    "signature_hex": sig_hex,
                    "round_id":      round_id,
                })

                with self._lock:
                    self.stats["fl_rounds_participated"] += 1
                    self.stats["last_fl_round"]           = round_id
                    if result and result.get("accepted"):
                        self.stats["fl_gradients_accepted"] += 1
                        self.stats["fl_trp_earned"]          += 1.0

            except Exception as exc:
                with self._lock:
                    self.stats["last_error"] = f"[FL] {exc}"

            time.sleep(30)

    # ── Loop 3: TX Validator ──────────────────────────────────────────────────

    def run_tx_loop(self) -> None:
        """Poll pending transactions, score them for fraud, submit verdict."""
        while True:
            try:
                pending = self._get("/api/explorer/pending-txs") or {}
                txs     = pending.get("transactions", [])

                for tx in txs:
                    tx_hash = str(tx.get("tx_hash") or tx.get("hash") or "")
                    if not tx_hash or tx_hash in self._seen_tx_hashes:
                        continue
                    self._seen_tx_hashes.add(tx_hash)

                    # Keep memory bounded
                    if len(self._seen_tx_hashes) > 10_000:
                        self._seen_tx_hashes = set(list(self._seen_tx_hashes)[-5_000:])

                    fraud_score = score_transaction_local(tx)
                    valid       = fraud_score < 0.65

                    msg_str   = f"{self.provider_id}:{tx_hash}:{int(valid)}:{fraud_score:.6f}"
                    msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
                    sig_hex   = _sign_message(self.key_data, msg_bytes)

                    result = self._post("/api/validators/submit-tx-verdict", {
                        "provider_id": self.provider_id,
                        "tx_hash":     tx_hash,
                        "valid":       valid,
                        "fraud_score": fraud_score,
                        "signature":   sig_hex,
                    })

                    with self._lock:
                        self.stats["tx_verdicts_submitted"] += 1
                        if result and result.get("accepted"):
                            self.stats["tx_verdicts_accepted"] += 1
                            self.stats["tx_trp_earned"]         += 0.01

            except Exception as exc:
                with self._lock:
                    self.stats["last_error"] = f"[TX] {exc}"

            time.sleep(5)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def run_dashboard(self) -> None:
        """Redraw terminal dashboard every 3 seconds using ANSI codes."""
        while True:
            try:
                cpu_pct, ram_mb = _sys_stats()
                with self._lock:
                    self.stats["cpu_pct"] = cpu_pct
                    self.stats["ram_mb"]  = ram_mb
                self._draw_dashboard()
            except Exception:
                pass
            time.sleep(3)

    def _draw_dashboard(self) -> None:
        with self._lock:
            s = dict(self.stats)

        uptime    = int(time.time() - self.start_time)
        h, rem    = divmod(uptime, 3600)
        m, sec    = divmod(rem, 60)
        uptime_s  = f"{h:02d}:{m:02d}:{sec:02d}"
        total_trp = s["poi_trp_earned"] + s["fl_trp_earned"] + s["tx_trp_earned"]
        addr_short = self.address[:20] + "…"

        status_dot = "🟢" if s["connected"] else "🔴"

        cpu_str = f"{s['cpu_pct']:.1f}%"
        ram_str = f"{s['ram_mb']:.0f} MB"
        compute_line = f"{_GPU_NAME}   CPU {cpu_str}  RAM {ram_str}"

        lines = [
            "\033[2J\033[H",   # clear screen, move to top
            "╔══════════════════════════════════════════════════════════╗",
            "║          TRISPI Energy Provider Node                    ║",
            "╠══════════════════════════════════════════════════════════╣",
            f"║  Address  : {addr_short:<44} ║",
            f"║  Node     : {self.node_url:<44} ║",
            f"║  Uptime   : {uptime_s:<10}  {status_dot} {'Connected' if s['connected'] else 'Disconnected':<32} ║",
            f"║  Compute  : {compute_line:<44} ║",
            f"║  Block    : #{s['current_block']:<5}  Peers: {s['peer_count']:<34} ║",
            "╠══════════════════════════════════════════════════════════╣",
            "║  EARNINGS                                               ║",
            f"║  Total TRP earned this session: {total_trp:<26.4f} ║",
            "╠═════════════════════════╦═══════════════════════════════╣",
            "║  PoI VALIDATOR          ║  FL COMPUTE PROVIDER          ║",
            f"║  Scores submitted: {s['poi_scores_submitted']:<5}  ║  Rounds: {s['fl_rounds_participated']:<21} ║",
            f"║  Scores accepted:  {s['poi_scores_accepted']:<5}  ║  Gradients accepted: {s['fl_gradients_accepted']:<9} ║",
            f"║  TRP earned: {s['poi_trp_earned']:<11.4f}  ║  TRP earned: {s['fl_trp_earned']:<17.4f} ║",
            "╠═════════════════════════╩═══════════════════════════════╣",
            "║  TX VALIDATOR                                           ║",
            f"║  Verdicts submitted: {s['tx_verdicts_submitted']:<5}  Accepted: {s['tx_verdicts_accepted']:<5}  TRP: {s['tx_trp_earned']:<7.4f} ║",
            "╠══════════════════════════════════════════════════════════╣",
        ]
        if s["last_error"]:
            err = s["last_error"][:56]
            lines.append(f"║  Last error: {err:<44} ║")
        else:
            lines.append("║  Status: All loops running normally                     ║")
        lines.append("╚══════════════════════════════════════════════════════════╝")
        lines.append("  Press Ctrl+C to stop and see session summary.\n")

        print("\n".join(lines), end="", flush=True)

    # ── Start ─────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start all three loops as daemon threads + dashboard."""
        threads = [
            threading.Thread(target=self.run_poi_loop, daemon=True, name="PoI-Validator"),
            threading.Thread(target=self.run_fl_loop,  daemon=True, name="FL-Compute"),
            threading.Thread(target=self.run_tx_loop,  daemon=True, name="TX-Validator"),
            threading.Thread(target=self.run_dashboard, daemon=True, name="Dashboard"),
        ]
        for t in threads:
            t.start()

        print(f"\n[TRISPI] Energy provider node started.")
        print(f"[TRISPI] Provider ID : {self.provider_id}")
        print(f"[TRISPI] TRP Address : {self.address}")
        print(f"[TRISPI] Node        : {self.node_url}")
        print(f"[TRISPI] Compute     : {_GPU_NAME}\n")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self._print_summary()

    def _print_summary(self) -> None:
        with self._lock:
            s = dict(self.stats)
        total_trp = s["poi_trp_earned"] + s["fl_trp_earned"] + s["tx_trp_earned"]
        uptime    = int(time.time() - self.start_time)
        h, rem    = divmod(uptime, 3600)
        m, sec    = divmod(rem, 60)

        print("\n\n╔══════════════════════════════════════════════════════════╗")
        print("║               SESSION SUMMARY                           ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  Uptime           : {h:02d}:{m:02d}:{sec:02d}                             ║")
        print(f"║  Total TRP earned : {total_trp:.4f} TRP                         ║")
        print(f"║  Blocks validated : {s['poi_scores_accepted']}                               ║")
        print(f"║  FL rounds        : {s['fl_gradients_accepted']}                               ║")
        print(f"║  TX verdicts      : {s['tx_verdicts_accepted']}                               ║")
        print("╠══════════════════════════════════════════════════════════╣")
        print(f"║  Your TRP address : {self.address[:38]}  ║")
        print("╚══════════════════════════════════════════════════════════╝\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    global KEY_FILE  # may be overridden by --keyfile
    parser = argparse.ArgumentParser(
        description="TRISPI Energy Provider Node — earn TRP by contributing GPU/CPU compute",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trispi_energy_provider.py --node http://localhost:8000
  python trispi_energy_provider.py --node http://my-trispi-server.com:8000 --id my_gpu_rig_1

The script generates a keypair on first run and saves it to ~/.trispi/provider_key.json
Back up that file — it holds your private key and TRP address.
        """,
    )
    parser.add_argument(
        "--node", "--server",
        default="http://localhost:8000",
        dest="node",
        help="TRISPI node URL (default: http://localhost:8000). Alias: --server",
    )
    parser.add_argument(
        "--id",
        default=None,
        help=(
            "Provider identifier visible in the leaderboard. "
            "Defaults to 'node_<first 8 chars of pubkey>'"
        ),
    )
    parser.add_argument(
        "--wallet",
        default=None,
        help="TRP wallet address (trp1...) — earnings are credited here. Alias for --id with 'trp1' prefix.",
    )
    parser.add_argument(
        "--keyfile",
        default=None,
        help=f"Path to keypair JSON file (default: {KEY_FILE})",
    )
    parser.add_argument(
        "--gpu", "--gpu-mb",
        action="store_true",
        dest="gpu",
        help="Enable GPU acceleration for FL gradient computation (requires torch)",
    )
    args = parser.parse_args()

    # Load or generate keypair
    if args.keyfile:
        KEY_FILE = Path(args.keyfile)
    key_data = load_or_create_key()

    # Derive provider ID — wallet takes precedence, then --id, then pubkey
    provider_id = args.wallet or args.id or f"node_{key_data['public_key_hex'][:8]}"

    # Check connectivity
    print(f"[TRISPI] Connecting to {args.node} ...")
    try:
        r = httpx.get(f"{args.node}/api/network/status", timeout=8.0)
        if r.status_code == 200:
            stats = r.json()
            block = int(stats.get("block_height") or stats.get("total_blocks") or 0)
            peers = int(stats.get("p2p_peers", stats.get("peer_count", 0)) or 0)
            print(f"[TRISPI] Connected! Block #{block}, {peers} p2p peers")
        else:
            print(f"[WARN] Node returned HTTP {r.status_code} — will retry in background")
    except Exception as exc:
        print(f"[WARN] Cannot reach node: {exc} — will retry in background")

    provider = EnergyProvider(
        node_url    = args.node,
        key_data    = key_data,
        provider_id = provider_id,
    )
    provider.start()


if __name__ == "__main__":
    main()
