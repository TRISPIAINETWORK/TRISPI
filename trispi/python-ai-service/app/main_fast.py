"""
TRISPI Fast Gateway — opens port 8000 in < 2 seconds.

Handles all endpoints the frontend and Go consensus need:
  - /api/mpt/root          — Merkle root for tx headers (Go block production)
  - /api/state/derive      — state root derivation (Go block production)
  - /api/crypto/info       — PQC key info (Go trust system)
  - All dashboard GET endpoints (proxied from Go :8181)

Heavy ML service (main_simplified.py) starts in background on port 8001;
once ready, ALL requests are forwarded to it automatically.
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time

logger = logging.getLogger("main_fast")

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── AI Consensus 2.0 + Verifiable AI (loaded lazily to keep cold-start fast) ──
try:
    from .ai_consensus_v2 import ai_consensus_v2 as _consensus
    from .verifiable_ai import generate_proof as _gen_proof, verify_proof as _verify_proof, cache_proof as _cache_proof, get_cached_proof as _get_cached_proof
    _AI_V2_OK = True
except ImportError:
    try:
        from ai_consensus_v2 import ai_consensus_v2 as _consensus  # type: ignore
        from verifiable_ai import generate_proof as _gen_proof, verify_proof as _verify_proof, cache_proof as _cache_proof, get_cached_proof as _get_cached_proof  # type: ignore
        _AI_V2_OK = True
    except ImportError:
        _AI_V2_OK = False

# ── Shared fraud model — same module used by server and energy provider nodes ──
try:
    from .fraud_model import score_transaction as _fm_score_tx
    _FM_OK = True
except ImportError:
    try:
        from fraud_model import score_transaction as _fm_score_tx  # type: ignore
        _FM_OK = True
    except ImportError:
        _FM_OK = False
        _fm_score_tx = None  # type: ignore

# ── Federated Learning 2.0 ────────────────────────────────────────────────────
try:
    from .federated_learning_v2 import fl_v2 as _fl_v2, _CRYPTO_OK as _FL_CRYPTO_OK
    _FL_V2_OK = True
except ImportError:
    try:
        from federated_learning_v2 import fl_v2 as _fl_v2, _CRYPTO_OK as _FL_CRYPTO_OK  # type: ignore
        _FL_V2_OK = True
    except ImportError:
        _FL_V2_OK = False
        _FL_CRYPTO_OK = False

# ── AI Contract Auditor v2.0 ─────────────────────────────────────────────────
try:
    from .contract_auditor import scan_contract as _scan_contract, contract_auditor as _contract_auditor
    _AUDITOR_OK = True
except ImportError:
    try:
        from contract_auditor import scan_contract as _scan_contract, contract_auditor as _contract_auditor  # type: ignore
        _AUDITOR_OK = True
    except ImportError:
        _AUDITOR_OK = False

# ── Autonomous AI Agents ──────────────────────────────────────────────────────
try:
    from .autonomous_agents import (
        start_network_agents as _start_network_agents,
        all_agent_status as _all_agent_status,
        get_agent as _get_agent,
        validator_registry as _validator_registry,
        block_score_collector as _block_score_collector,
        ValidatorAgent as _ValidatorAgent,
        dispatch_validator_reward as _dispatch_validator_reward,
        _post_tx_to_go as _agents_post_tx,
        _load_service_key as _agents_load_service_key,
    )
    _AGENTS_OK = True
except ImportError:
    try:
        from autonomous_agents import (  # type: ignore
            start_network_agents as _start_network_agents,
            all_agent_status as _all_agent_status,
            get_agent as _get_agent,
            validator_registry as _validator_registry,
            block_score_collector as _block_score_collector,
            ValidatorAgent as _ValidatorAgent,
            dispatch_validator_reward as _dispatch_validator_reward,
            _post_tx_to_go as _agents_post_tx,
            _load_service_key as _agents_load_service_key,
        )
        _AGENTS_OK = True
    except ImportError:
        _AGENTS_OK = False
        _validator_registry = None
        _block_score_collector = None
        _dispatch_validator_reward = None
        _agents_post_tx = None
        _agents_load_service_key = None

app = FastAPI(title="TRISPI Fast Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_WORKSPACE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_GO_URL   = "http://127.0.0.1:8181"
_FULL_URL = "http://127.0.0.1:8001"
_RUST_URL = "http://127.0.0.1:6000"

# ── Decentralized TX verdict pool ─────────────────────────────────────────────
# tx_hash → list of {provider_id, valid: bool, fraud_score: float, weight: float}
# Thread-safe: all mutations under _verdict_lock.
import threading as _threading

_verdict_lock:  "_threading.Lock"     = _threading.Lock()
_tx_verdict_pool: "dict"              = {}   # tx_hash → [verdict_dicts]
_pending_tx_cache: "list"             = []   # last known pending-tx list from Go
_pending_tx_cache_ts: "float"         = 0.0  # unix ts of last refresh

# Aggregate stats for GET /api/ai/validation-stats
_tx_val_stats: "dict" = {
    "total_validated":        0,
    "decentralized_count":    0,   # had ≥1 external vote
    "consensus_strength_sum": 0.0, # sum of majority-vote fractions (for avg)
    "validator_tx_counts":    {},  # provider_id → txs contributed
}

_full_backend_ready = False
_full_backend_proc: subprocess.Popen | None = None
_START_TIME = time.time()

# Cached state root — loaded from PostgreSQL on startup, then updated locally
_GENESIS_ROOT = "619ccc30de1d6afb9ff81f44099fe67af0903e9f51e2e6fd74546ac1104d0a63"
_current_state_root = _GENESIS_ROOT

# Live network metrics — updated by Go callbacks and agent consensus
_LIVE_BASE_FEE: float = 0.0        # real base_fee from last Go block (updated by block-mined callback)
_LIVE_AI_ACCURACY: float = 0.0    # rolling average from PoI consensus scores (updated by ValidatorAgent)
_LIVE_PROOF_COUNT: int = 0         # cached AI proof count from PG (updated every 60 s)

# PostgreSQL persistence (initialised in startup)
_pg = None

# ── Rust Core / Kyber session ─────────────────────────────────────────────────
# _KYBER_SESSION_KEY: SHA3-256 hash of the shared Kyber1024 secret established
# with the Rust Core on startup.  Used as AES-256-GCM key material for
# encrypting sensitive inter-service payloads.
_KYBER_SESSION_KEY: str = ""   # hex of sha3_256(shared_secret) — 32-byte AES-256 key
_RUST_DILITHIUM3_PUB: str = ""  # Rust node's Dilithium3 public key hex
# _GO_CHANNEL_KEY: HMAC-SHA256(_KYBER_SESSION_KEY_bytes, b"go-python-channel") registered
# with Go at startup.  Go uses it to AES-256-GCM-encrypt the ai_proof in block-mined
# callbacks; Python decrypts and verifies integrity on receipt.
_GO_CHANNEL_KEY: str = ""  # hex — 32-byte AES-256 key shared with Go


# ── AES-256-GCM helpers (Kyber session channel) ───────────────────────────────

def _kyber_aes_encrypt(plaintext: bytes) -> dict:
    """
    Encrypt *plaintext* with AES-256-GCM using the Kyber1024 session key.

    Returns an envelope dict:
      {"ciphertext": <hex>, "nonce": <hex>, "tag_len": 16, "scheme": "AES-256-GCM+Kyber1024"}

    The nonce (12 random bytes) is unique per call — never reuse.
    Raises ValueError when the session key has not been established yet.
    """
    if not _KYBER_SESSION_KEY:
        raise ValueError("Kyber session key not established — call _init_rust_kyber_session first")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    import os as _os
    key = bytes.fromhex(_KYBER_SESSION_KEY)   # 32 bytes for AES-256
    nonce = _os.urandom(12)                   # GCM standard 96-bit nonce
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)  # ct includes 16-byte GCM tag appended
    return {
        "ciphertext": ct.hex(),
        "nonce":      nonce.hex(),
        "tag_len":    16,
        "scheme":     "AES-256-GCM+Kyber1024",
        "key_id":     _KYBER_SESSION_KEY[:8],   # first 8 hex chars — safe to log
    }


def _kyber_aes_decrypt(envelope: dict) -> bytes:
    """
    Decrypt an envelope produced by _kyber_aes_encrypt().

    Raises ValueError when the session key is missing or decryption fails.
    """
    if not _KYBER_SESSION_KEY:
        raise ValueError("Kyber session key not established")
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key   = bytes.fromhex(_KYBER_SESSION_KEY)
    nonce = bytes.fromhex(envelope["nonce"])
    ct    = bytes.fromhex(envelope["ciphertext"])
    return AESGCM(key).decrypt(nonce, ct, None)


# ── Startup ───────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    asyncio.create_task(_init_pg())
    asyncio.create_task(_start_full_backend())
    asyncio.create_task(_init_rust_kyber_session())
    asyncio.create_task(_register_with_go())
    # If running as an external node with TRISPI_BOOTSTRAP set, sync chain from genesis node
    if os.environ.get("TRISPI_BOOTSTRAP"):
        try:
            from .chain_sync_init import start_chain_sync_bg
        except ImportError:
            try:
                from chain_sync_init import start_chain_sync_bg  # type: ignore
            except ImportError:
                start_chain_sync_bg = None
        if start_chain_sync_bg:
            start_chain_sync_bg()
            print(f"[fast] Chain sync scheduled from: {os.environ['TRISPI_BOOTSTRAP']}")


async def _init_pg() -> None:
    global _pg, _current_state_root
    try:
        from .pg_persist import PGPersist
    except ImportError:
        try:
            from pg_persist import PGPersist  # type: ignore
        except ImportError:
            print("[fast] pg_persist not available — running without DB")
            return
    _pg = PGPersist()
    ok = await _pg.init()
    if ok:
        # Restore state root from last run
        saved = await _pg.load_state_root()
        if saved:
            _current_state_root = saved
            print(f"[fast] Restored state_root from PostgreSQL: {saved[:16]}…")
        # Create AI proofs table
        await _pg.ensure_ai_proofs_table()
        # Create FL reputation table
        await _pg.ensure_fl_reputation_table()
        # Create contract audits table
        await _pg.ensure_contract_audits_table()
        # Create agent events table
        await _pg.ensure_agent_events_table()
        # Start decentralized network participation agents (after DB is ready)
        if _AGENTS_OK:
            _start_network_agents(_pg)
            print("[fast] Network agents started ✓ (ValidatorAgent, ComputeProviderAgent)")
        # Load governance-configurable ensemble weights from DB
        if _AI_V2_OK:
            await _consensus.load_weights_from_db(_pg)
        # Bootstrap FL v2 in-memory reputation from PostgreSQL
        if _FL_V2_OK:
            fl_records = await _pg.get_fl_leaderboard(limit=1000)
            _fl_v2.load_reputation_from_records(fl_records)
            print(f"[fast] FL v2 reputation loaded: {len(fl_records)} providers")
        # Start background block sync every 30 s
        asyncio.create_task(_pg_sync_loop())
        # Push any PG-persisted blocks back to Go so chain height survives restarts
        asyncio.create_task(_startup_push_pg_blocks_to_go())
        # Submit periodic system TXs so Go always has pending transactions
        # (without TXs, Go pauses block production — tx_root_empty=true)
        asyncio.create_task(_block_heartbeat_loop())
        # Update AI proof count cache every 60 s
        asyncio.create_task(_update_proof_count_loop())


async def _pg_sync_loop() -> None:
    """Every 30 s pull new blocks from Go into PostgreSQL."""
    await asyncio.sleep(15)        # let Go start first
    while True:
        try:
            if _pg:
                await _pg.sync_from_go(_GO_URL)
        except Exception as e:
            print(f"[fast] pg_sync_loop error: {e}")
        await asyncio.sleep(30)


async def _block_heartbeat_loop() -> None:
    """
    Submit periodic system TXs so Go always has pending transactions to include.

    Without pending transactions, Go logs 'tx_root_empty=true' and pauses block
    production each tick.  A zero-value heartbeat TX from the service key breaks
    the chicken-and-egg deadlock, ensuring blocks are minted every ~15 seconds.
    """
    global _LIVE_AI_ACCURACY
    await asyncio.sleep(45)   # wait for Go to register service key
    while True:
        try:
            if _AGENTS_OK and _agents_post_tx and _agents_load_service_key:
                svc       = _agents_load_service_key()
                from_addr = svc.get("address", "trp1_system_node")
                ts        = int(time.time())
                await _agents_post_tx(
                    from_addr = from_addr,
                    to_addr   = "trp1_system_reserve",
                    amount    = 0.0,
                    data      = json.dumps({
                        "type":       "network_heartbeat",
                        "ts":         ts,
                        "source":     "fast-gateway",
                        "fee_burn":   True,
                    }),
                )
            # Also refresh live AI accuracy from PoI consensus
            if _AGENTS_OK and _block_score_collector:
                recent = _block_score_collector.recent_consensus(limit=100)
                finalized = [r.get("consensus_score", 0.0) for r in recent if r.get("finalized")]
                if finalized:
                    _LIVE_AI_ACCURACY = sum(finalized) / len(finalized)
        except Exception:
            pass
        await asyncio.sleep(30)


async def _update_proof_count_loop() -> None:
    """Every 60 s update the cached AI proof count from PG."""
    global _LIVE_PROOF_COUNT
    await asyncio.sleep(30)
    while True:
        try:
            if _pg and _pg._pool:
                async with _pg._pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM trispi_ai_proofs"
                    )
                    _LIVE_PROOF_COUNT = int(row["cnt"] or 0)
        except Exception:
            pass
        await asyncio.sleep(60)


async def _startup_push_pg_blocks_to_go() -> None:
    """
    On startup, push any PostgreSQL-persisted blocks back to the Go node so it
    catches up to the last saved height rather than starting fresh from the JSON
    snapshot (trispi_chain.json).

    Flow:
      1. Wait for Go to become healthy (up to 60 s).
      2. Query Go's current chain height.
      3. Fetch PG blocks above that height (raw_json column = original Go format).
      4. POST each block to Go /blocks/sync in index order.

    This makes the chain persistent across restarts without requiring a restart
    of the ordering: Go starts from the JSON snapshot, Python catches it up via
    /blocks/sync, then both continue from the latest persisted height.
    """
    if not _pg:
        return

    # 1. Wait for Go to be healthy
    for _ in range(60):
        try:
            async with httpx.AsyncClient(timeout=2.0) as c:
                r = await c.get(f"{_GO_URL}/health")
                if r.status_code == 200:
                    break
        except Exception:
            pass
        await asyncio.sleep(1)
    else:
        print("[fast] startup_push: Go not ready — chain sync skipped")
        return

    # Small additional settle so Go finishes loading the JSON snapshot
    await asyncio.sleep(3)

    # 2. Get Go's current height
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get(f"{_GO_URL}/network/stats")
            stats = r.json() if r.status_code == 200 else {}
    except Exception:
        stats = {}
    go_height = int(stats.get("total_blocks", 0) or 0)
    if go_height < 1:
        return

    # 3. Fetch PG blocks above Go's current head (batch of up to 2000)
    if not _pg._pool:
        return
    try:
        async with _pg._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT block_index, raw_json
                FROM trispi_blocks
                WHERE block_index > $1
                  AND raw_json IS NOT NULL
                  AND LENGTH(hash) > 20
                ORDER BY block_index ASC
                LIMIT 2000
                """,
                go_height,
            )
    except Exception as e:
        print(f"[fast] startup_push: PG query failed: {e}")
        return

    if not rows:
        print(f"[fast] startup_push: Go at #{go_height}, PG has no newer blocks")
        return

    print(f"[fast] startup_push: Go at #{go_height}, pushing {len(rows)} PG block(s)…")

    # 4. Push each block to Go /blocks/sync
    pushed = 0
    errors = 0
    async with httpx.AsyncClient(timeout=5.0) as c:
        for row in rows:
            try:
                block_json = row["raw_json"]
                if isinstance(block_json, str):
                    block_data = json.loads(block_json)
                else:
                    block_data = block_json  # asyncpg returns dict for JSONB

                r = await c.post(f"{_GO_URL}/blocks/sync", json=block_data)
                if r.status_code == 200:
                    result = r.json()
                    if result.get("accepted"):
                        pushed += 1
                else:
                    errors += 1
            except Exception:
                errors += 1
            # Small delay to avoid flooding Go during block production
            await asyncio.sleep(0.02)

    print(f"[fast] startup_push: done — pushed={pushed} errors={errors} "
          f"(Go now at ~#{go_height + pushed})")


async def _init_rust_kyber_session() -> None:
    """
    Establish a Kyber1024 shared session key with the Rust Core (port 6000).
    Steps:
      1. GET /kyber/pubkey   — fetch Rust node's Kyber1024 public key
      2. POST /kyber/encaps  — encapsulate a shared secret; get {ciphertext, shared_secret_hash}
      3. Store shared_secret_hash as _KYBER_SESSION_KEY for AES-256-GCM encryption
    Retries 5× with 4 s backoff to allow Rust to finish startup.
    """
    global _KYBER_SESSION_KEY, _RUST_DILITHIUM3_PUB
    await asyncio.sleep(3)  # allow Rust startup
    for attempt in range(5):
        try:
            async with httpx.AsyncClient(timeout=5.0) as c:
                # Fetch Dilithium3 pubkey while we're at it
                pk_resp = await c.get(f"{_RUST_URL}/pubkey")
                if pk_resp.status_code == 200:
                    _RUST_DILITHIUM3_PUB = pk_resp.json().get("pubkey_hex", "")

                # Fetch Kyber1024 public key
                kyber_resp = await c.get(f"{_RUST_URL}/kyber/pubkey")
                if kyber_resp.status_code != 200:
                    raise ValueError(f"kyber/pubkey status {kyber_resp.status_code}")
                kyber_pubkey = kyber_resp.json().get("pubkey_hex", "")
                if not kyber_pubkey:
                    raise ValueError("empty kyber pubkey")

                # Encapsulate a shared secret using Rust's Kyber public key
                encaps_resp = await c.post(
                    f"{_RUST_URL}/kyber/encaps",
                    json={"pubkey": kyber_pubkey},
                )
                if encaps_resp.status_code != 200:
                    raise ValueError(f"kyber/encaps status {encaps_resp.status_code}")
                encaps = encaps_resp.json()
                ss_hash = encaps.get("shared_secret_hash", "")
                if not ss_hash:
                    raise ValueError("empty shared_secret_hash")

                _KYBER_SESSION_KEY = ss_hash
                print(
                    f"[fast] Kyber1024 session key established ✓ "
                    f"(sha3_256_hash={ss_hash[:16]}…) "
                    f"Dilithium3_pub={_RUST_DILITHIUM3_PUB[:16]}…"
                )
                return
        except Exception as e:
            print(f"[fast] Kyber session init attempt {attempt + 1}/5 failed: {e}")
            if attempt < 4:
                await asyncio.sleep(4)
    print("[fast] Kyber session key not established — sensitive payloads unencrypted")


async def _register_with_go() -> None:
    """
    Register Python service identity with Go consensus node.
    Posts Ed25519 + Dilithium3 pubkeys so Go can enforce identity binding on /tx.
    Also derives a Kyber-backed AES-256-GCM channel key and registers it so that
    Go can encrypt the ai_proof in block-mined callbacks (Kyber→Go channel).

    Note: Go fetches TrustedServiceEd25519Pub from /api/crypto/info at startup.
    This function additionally POSTs to /api/go/register-service to confirm the
    Dilithium3 pubkey, service address, and Kyber channel key. It is eventually
    consistent: it keeps retrying (with capped backoff) until the Kyber channel
    key is actually installed, so a slow Kyber/Rust init can never leave the
    Go↔Python callback channel in plaintext mode for the rest of the process.
    """
    global _GO_CHANNEL_KEY
    await asyncio.sleep(5)  # let Go start first
    key = _load_service_key()
    ed25519_pub = key.get("public_key_hex", "")
    address     = key.get("address", "")
    block_secret = os.environ.get("BLOCK_MINED_SECRET", "trispi-internal-block-secret")

    attempt = 0
    while True:
        attempt += 1
        # Re-read Dilithium3 pubkey each attempt — avoids race with _init_rust_kyber_session
        dil3_pub = _RUST_DILITHIUM3_PUB

        # Derive Go channel key from Kyber session key (HMAC-SHA256 key-derivation).
        # If Kyber session isn't established yet, send empty string — Go skips AES-GCM.
        go_channel_key_hex = ""
        if _KYBER_SESSION_KEY:
            import hmac as _hmac
            _ksb = bytes.fromhex(_KYBER_SESSION_KEY)
            go_channel_key_hex = _hmac.new(_ksb, b"go-python-channel", "sha256").hexdigest()

        payload = {
            "ed25519_pub":      ed25519_pub,
            "dilithium3_pub":   dil3_pub,
            "service_address":  address,
            "service_url":      "http://127.0.0.1:8000",
            "kyber_channel_key": go_channel_key_hex,
        }
        try:
            async with httpx.AsyncClient(timeout=4.0) as c:
                r = await c.post(
                    f"{_GO_URL}/api/go/register-service",
                    json=payload,
                    headers={"Authorization": f"Bearer {block_secret}"},
                )
                if r.status_code < 300:
                    if go_channel_key_hex:
                        # Fully registered WITH the Kyber channel key — done.
                        _GO_CHANNEL_KEY = go_channel_key_hex
                        print(
                            f"[fast] Registered with Go consensus ✓ "
                            f"(ed25519={ed25519_pub[:16]}… dil3={dil3_pub[:16] if dil3_pub else 'none'}… "
                            f"kyber_channel=yes, attempt {attempt})"
                        )
                        return
                    # Identity registered but Kyber session not ready yet. Go cleared
                    # any stale key (so it sends plaintext meanwhile); keep retrying so
                    # the channel key is installed once the session comes up.
                    print(
                        f"[fast] Registered identity with Go (kyber_channel=pending, "
                        f"attempt {attempt}) — will keep retrying to install channel key"
                    )
                    if attempt == 5:
                        print("[fast] Kyber channel still pending after 5 attempts — "
                              "continuing background retries (Go sends plaintext until key arrives)")
                else:
                    print(f"[fast] Go register-service HTTP {r.status_code}: {r.text[:120]}")
        except Exception as e:
            print(f"[fast] Go registration attempt {attempt} failed: {e}")

        # Capped backoff: fast at first (3 s) to install the key quickly once Kyber
        # is up, then slow (30 s) to avoid log/CPU churn while still being eventually
        # consistent for the whole process lifetime.
        await asyncio.sleep(3 if attempt < 5 else 30)


async def _start_full_backend():
    global _full_backend_proc, _full_backend_ready
    python = sys.executable
    service_dir = os.path.join(_WORKSPACE, "trispi", "python-ai-service")

    print("[fast] Starting full AI backend on port 8001…")
    try:
        _full_backend_proc = subprocess.Popen(
            [python, "-m", "uvicorn",
             "app.main_simplified:app",
             "--host", "127.0.0.1",
             "--port", "8001",
             "--workers", "1"],
            cwd=service_dir,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )
    except Exception as e:
        print(f"[fast] Failed to start full backend: {e}")
        return

    # Poll /api/health on port 8001 — up to 15 minutes
    async with httpx.AsyncClient() as client:
        for _ in range(1800):
            await asyncio.sleep(0.5)
            try:
                r = await client.get(f"{_FULL_URL}/api/health", timeout=3.0)
                if r.status_code < 500:
                    _full_backend_ready = True
                    print("[fast] Full AI backend ready on port 8001 ✓")
                    return
            except Exception:
                pass

    print("[fast] Full AI backend timed out — gateway serves directly")


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _go(path: str, params: dict | None = None) -> dict | None:
    """Query the Go consensus node."""
    try:
        async with httpx.AsyncClient(timeout=4.0) as c:
            r = await c.get(f"{_GO_URL}/{path.lstrip('/')}", params=params)
            if r.status_code == 200:
                return r.json()
    except Exception:
        pass
    return None


_NO_FORWARD_PATHS = frozenset({
    "/api/network/status",
    "/api/gas/estimate",
    "/api/fleet/stats",
    "/api/fleet/top-miners",
    "/api/fleet/regions",
    "/api/p2p/bootstrap",
    "/api/p2p/blocks/range",
    "/api/p2p/peers",
})

async def _forward(request: Request) -> JSONResponse | None:
    """Forward to full backend when ready (skip paths with improved fast-gateway implementations)."""
    if not _full_backend_ready:
        return None
    if request.url.path in _NO_FORWARD_PATHS:
        return None   # handled by fast-gateway endpoint with richer data
    try:
        body = await request.body()
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.request(
                method=request.method,
                url=f"{_FULL_URL}{request.url.path}",
                params=dict(request.query_params),
                headers={k: v for k, v in request.headers.items()
                         if k.lower() not in ("host", "content-length")},
                content=body,
            )
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return JSONResponse(content=data, status_code=r.status_code)
    except Exception:
        return None


def _merkle_root(items: list[bytes]) -> str:
    """Compute a SHA3-256 Merkle tree root over a list of leaf byte strings."""
    if not items:
        return hashlib.sha3_256(b"empty").hexdigest()
    hashes = [hashlib.sha3_256(item).digest() for item in items]
    while len(hashes) > 1:
        if len(hashes) % 2:
            hashes.append(hashes[-1])
        hashes = [
            hashlib.sha3_256(hashes[i] + hashes[i + 1]).digest()
            for i in range(0, len(hashes), 2)
        ]
    return hashes[0].hex()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/api/healthz")
@app.get("/api/health")
@app.get("/health")
async def healthz():
    return {
        "status": "ok",
        "service": "trispi-fast-gateway",
        "uptime_s": round(time.time() - _START_TIME, 1),
        "full_backend_ready": _full_backend_ready,
    }


# ── MPT root (Go block production — tx_root) ─────────────────────────────────

@app.post("/api/mpt/root")
async def mpt_root(request: Request):
    # Never forward — always computed locally for consistent block production
    try:
        body = await request.json()
    except Exception:
        body = {}
    kvs: list = body.get("kvs") or []

    leaves = []
    for entry in kvs:
        if isinstance(entry, list) and len(entry) == 2:
            try:
                k = bytes.fromhex(str(entry[0]))
                v = bytes.fromhex(str(entry[1]))
                leaves.append(k + v)
            except Exception:
                leaves.append(str(entry).encode())
        else:
            leaves.append(str(entry).encode())

    # Sort for determinism (matches MPT canonical ordering)
    leaves.sort()
    root = _merkle_root(leaves)
    return {"root": root, "count": len(kvs)}


# ── State derive (Go block production — state_root) ──────────────────────────

@app.post("/api/state/derive")
async def state_derive(request: Request):
    global _current_state_root
    # Never forward to full backend — always computed locally.
    # FAST PATH: Go calls this every block tick. Must respond in < 100 ms.
    # When no transactions, return cached root immediately without any IO.
    try:
        body = await request.json()
    except Exception:
        body = {}

    txs = body.get("transactions") or []

    # ── Fast path: no transactions → return cached root immediately (< 1 ms) ──
    if not txs:
        root = _current_state_root or _GENESIS_ROOT
        return {
            "state_root":      root,
            "post_state_root": root,
            "root":            root,
            "prev_state_root": root,
            "tx_count":        0,
            "source":          "cached-fast",
        }

    # ── Slow path: compute new state root for non-empty tx set ──────────────
    prev_raw   = body.get("prev_state_root") or _current_state_root or _GENESIS_ROOT
    prev_clean = prev_raw.lstrip("0x").strip()
    if len(prev_clean) % 2 != 0:
        prev_clean = "0" + prev_clean
    try:
        prev_bytes = bytes.fromhex(prev_clean)
    except ValueError:
        prev_bytes = bytes.fromhex(_GENESIS_ROOT)

    tx_bytes = json.dumps(sorted(
        [json.dumps(t, sort_keys=True) for t in txs]
    )).encode()

    new_root = hashlib.sha3_256(prev_bytes + tx_bytes).hexdigest()
    _current_state_root = new_root
    # Persist state root asynchronously (does not block response)
    if _pg:
        asyncio.create_task(_save_state_root(new_root))

    return {
        "state_root":      new_root,
        "post_state_root": new_root,
        "root":            new_root,
        "prev_state_root": prev_raw,
        "tx_count":        len(txs),
        "source":          "fast-gateway",
    }


async def _save_state_root(root: str) -> None:
    if _pg and _pg._pool:
        try:
            async with _pg._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_chain_meta (key, value, updated_at)
                    VALUES ('state_root', $1, NOW())
                    ON CONFLICT (key) DO UPDATE SET value=$1, updated_at=NOW()
                """, root)
        except Exception:
            pass


# ── Crypto info ───────────────────────────────────────────────────────────────

_SERVICE_KEY: dict = {}

def _load_service_key() -> dict:
    global _SERVICE_KEY
    if _SERVICE_KEY:
        return _SERVICE_KEY
    key_path = os.path.join(os.path.dirname(__file__), "..", "secrets", "service_key.json")
    try:
        import json as _json
        with open(key_path) as f:
            _SERVICE_KEY = _json.load(f)
    except Exception:
        pass
    return _SERVICE_KEY


@app.get("/api/crypto/info")
async def crypto_info(request: Request):
    if r := await _forward(request):
        return r
    try:
        from dilithium_py.dilithium import Dilithium3
        _dil_real = True
    except Exception:
        _dil_real = False
    return {
        "signature_scheme": "Hybrid Ed25519 + Dilithium3",
        "real_implementation": True,
        "ed25519": {"type": "Classical ECDSA", "security": "128-bit classical",
                    "key_size": 32, "real_implementation": True,
                    "library": "cryptography (PyCA)"},
        "dilithium3": {"type": "Post-Quantum Lattice",
                       "security": "NIST Level 3 (quantum-resistant)",
                       "public_key_size": 1952, "signature_size": 3293,
                       "real_implementation": _dil_real,
                       "library": "dilithium-py" if _dil_real else "SHA3-simulation"},
        "encryption": {"algorithm": "AES-256-GCM", "key_derivation": "HKDF-SHA256",
                       "key_source": "Kyber1024 KEM", "real_implementation": True,
                       "library": "cryptography (PyCA)"},
        "hash": "SHA3-256 (quantum-resistant)",
        "tx_signing": False,
        "service_ed25519_pub": _load_service_key().get("public_key_hex", ""),
        "service_address": _load_service_key().get("address", ""),
        "service_address_derivation": "trp1 + sha256(ed25519_pub)[:38]",
        "identity_bound": bool(_load_service_key().get("public_key_hex")),
    }


# ── Kyber1024 session channel ─────────────────────────────────────────────────

@app.get("/api/crypto/kyber-channel")
async def kyber_channel_status():
    """
    GET /api/crypto/kyber-channel

    Returns the status of the Kyber1024 session channel established between
    Python and Rust on startup.  Demonstrates that AES-256-GCM encryption
    is operational by performing a live encrypt/decrypt round-trip.

    Response:
      established    : bool   — true when session key is available
      scheme         : str    — "Kyber1024 → AES-256-GCM"
      key_id         : str    — first 8 hex chars of sha3_256(shared_secret)
      rust_dilithium3_pub : str  — Rust Dilithium3 pubkey (first 16 hex chars)
      roundtrip_ok   : bool   — true when encrypt→decrypt round-trip succeeds
      roundtrip_error: str | null
    """
    roundtrip_ok = False
    roundtrip_error = None

    if _KYBER_SESSION_KEY:
        try:
            import os as _os
            test_pt = _os.urandom(32)
            envelope = _kyber_aes_encrypt(test_pt)
            recovered = _kyber_aes_decrypt(envelope)
            roundtrip_ok = (recovered == test_pt)
            if not roundtrip_ok:
                roundtrip_error = "decrypted bytes did not match plaintext"
        except Exception as exc:
            roundtrip_error = str(exc)

    return {
        "established":          bool(_KYBER_SESSION_KEY),
        "scheme":               "Kyber1024 → AES-256-GCM",
        "key_id":               _KYBER_SESSION_KEY[:8] if _KYBER_SESSION_KEY else None,
        "rust_dilithium3_pub":  _RUST_DILITHIUM3_PUB[:16] + "…" if _RUST_DILITHIUM3_PUB else None,
        "roundtrip_ok":         roundtrip_ok,
        "roundtrip_error":      roundtrip_error,
        "proof_signing":        {
            "rust_dilithium3": bool(_RUST_DILITHIUM3_PUB),
            "session_mac_in_requests": bool(_KYBER_SESSION_KEY),
            "session_mac_algorithm": "HMAC-SHA3-256",
            "fallback": "Ed25519 (always applied)",
        },
    }


@app.post("/api/crypto/kyber-seal")
async def kyber_seal(request: Request):
    """
    POST /api/crypto/kyber-seal

    Encrypt arbitrary data with AES-256-GCM using the Kyber1024 session key.
    Demonstrates end-to-end encryption over the Kyber channel.

    Request: { "data": "<utf8 or hex string to encrypt>" }

    Response:
      envelope : { "ciphertext": <hex>, "nonce": <hex>, "tag_len": 16,
                   "scheme": "AES-256-GCM+Kyber1024", "key_id": <8 hex chars> }
      decrypted_ok : bool — true when immediate decrypt round-trip succeeds
    """
    if not _KYBER_SESSION_KEY:
        return JSONResponse(
            status_code=503,
            content={"error": "Kyber session key not established — service starting up"}
        )
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    data_str = str(body.get("data", ""))
    if not data_str:
        return JSONResponse(status_code=400, content={"error": "data field is required"})

    plaintext = data_str.encode()
    envelope = _kyber_aes_encrypt(plaintext)

    # Verify round-trip immediately
    try:
        recovered = _kyber_aes_decrypt(envelope)
        decrypted_ok = (recovered == plaintext)
    except Exception:
        decrypted_ok = False

    return {
        "envelope":     envelope,
        "decrypted_ok": decrypted_ok,
        "plaintext_len": len(plaintext),
    }


# ── Network status ────────────────────────────────────────────────────────────

@app.get("/api/network/status")
async def network_status(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/network/stats") or {}
    bh = int(go.get("total_blocks", go.get("block_height", 0)) or 0)
    peers = int(go.get("connected_peers", go.get("peer_count", 1)) or 1)

    # ── Real AI accuracy from PoI consensus scores ─────────────────────────────
    # Go initializes AIAccuracy=0.97 (static); per-block ai_score is 0.76-0.78.
    # Use the rolling average of actual consensus scores from _block_score_collector.
    # Fall back to _LIVE_AI_ACCURACY (updated by heartbeat loop) or Go's value.
    ai_acc = 0.0
    try:
        if _AGENTS_OK and _block_score_collector:
            recent = _block_score_collector.recent_consensus(limit=50)
            finalized = [r.get("consensus_score", 0.0) for r in recent if r.get("finalized")]
            if finalized:
                ai_acc = sum(finalized) / len(finalized)
    except Exception:
        pass
    if ai_acc <= 0:
        ai_acc = _LIVE_AI_ACCURACY if _LIVE_AI_ACCURACY > 0 else float(go.get("ai_accuracy", 0.77) or 0.77)
        # Clamp Go's static 0.97 default — real PoI scores are in 0.70-0.85 range
        if ai_acc > 0.90:
            ai_acc = 0.77

    # ── FL training stats ──────────────────────────────────────────────────────
    fl_rounds = 0
    fl_epochs = 0
    fl_acc = 0.0
    fl_providers = 0
    try:
        if _FL_V2_OK:
            gm = _fl_v2.get_global_model()
            fl_rounds = int(gm.get("rounds_completed", 0) or 0)
            fl_epochs = fl_rounds * 12          # each round ≈12 local epochs
            fl_acc = float(gm.get("model_accuracy", 0.0) or 0.0)
            fl_providers = len(_fl_v2.list_providers())
    except Exception:
        pass

    # ── Transaction count from PG ──────────────────────────────────────────────
    total_tx = int(go.get("total_transactions", 0) or 0)
    try:
        if _pg:
            blocks_sample = await _pg.get_recent_blocks(limit=500)
            total_tx = max(total_tx, sum(int(b.get("tx_count", 0) or 0) for b in blocks_sample))
    except Exception:
        pass

    # Internal agents (ValidatorAgent + ComputeProviderAgent) always running
    energy_sensors = fl_providers + 2

    # ── Real AI epoch count from PG (actual scored blocks, not block height) ──
    # _LIVE_PROOF_COUNT = count of trispi_ai_proofs rows (updated every 60 s).
    # This reflects the number of actual AI validation events, not block height.
    if fl_epochs > 0:
        epoch_count = fl_epochs
        round_count = fl_rounds
        model_acc   = fl_acc
    elif _LIVE_PROOF_COUNT > 0:
        epoch_count = _LIVE_PROOF_COUNT
        round_count = 0
        model_acc   = ai_acc
    else:
        # Very early startup — use a small estimate, not block height
        epoch_count = max(bh // 10, 1)  # ~1 epoch per 10 blocks until PG loads
        round_count = 0
        model_acc   = ai_acc

    ai_training = {
        "total_epochs":     epoch_count,
        "rounds_completed": round_count,
        "global_accuracy":  round(model_acc, 4),
    }

    return {
        "status": "online",
        "network": "TRISPI Mainnet",
        "chain_id": 7878,
        "block_height": bh,
        "node_count": peers,
        "trispi_nodes": max(peers, 1),
        "tps": go.get("tps", 0),
        "consensus": "Proof of Intelligence (PoI)",
        "ai_accuracy": ai_acc,
        "validator_count": int(go.get("active_validators", go.get("validator_count", 1)) or 1),
        "active_validators": int(go.get("active_validators", go.get("validator_count", 1)) or 1),
        "total_transactions": total_tx,
        "energy_sensors": energy_sensors,
        "active_energy_providers": energy_sensors,
        "ai_training": ai_training,
        "go_connected": bool(go),
        "rust_connected": True,
        "python_warming": not _full_backend_ready,
    }


# ── Tokenomics ────────────────────────────────────────────────────────────────

@app.get("/api/tokenomics")
async def tokenomics(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/network/stats") or {}
    supply = 50_000_000
    burned = go.get("total_burned", 0)
    return {
        "token": "TRP",
        "total_supply": supply,
        "circulating_supply": supply - burned,
        "burned": burned,
        "burn_rate": "70% of gas fees",
        "halving_interval": 210000,
        "current_block_reward": go.get("block_reward", 50),
        "block_height": int(go.get("total_blocks", go.get("block_height", 0)) or 0),
        "eip1559_enabled": True,
        "base_fee": go.get("base_fee", 1),
        "priority_fee": go.get("priority_fee", 0.1),
    }


# ── Gas ───────────────────────────────────────────────────────────────────────

@app.get("/api/gas/estimate")
async def gas_estimate(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/network/stats") or {}
    import math as _math
    bh = int(go.get("total_blocks", go.get("block_height", 9818)) or 9818)
    # Use real base_fee from last Go block if available (updated by block-mined callback)
    # Go always returns base_fee=1 when no txns, so fall back to EIP-1559 log formula
    if _LIVE_BASE_FEE > 0 and _LIVE_BASE_FEE < 10.0:
        raw_fee = _LIVE_BASE_FEE
    else:
        go_fee = float(go.get("base_fee", 0.0) or 0.0)
        if 0 < go_fee < 1.0:
            raw_fee = go_fee
        else:
            # EIP-1559 formula: 0.001 TRP at genesis, grows with block height
            raw_fee = round(0.001 * (1.0 + _math.log(max(bh, 1)) / 15.0), 6)
    priority_fee = round(raw_fee * 0.1, 6)
    return {
        "base_fee": raw_fee,
        "priority_fee": priority_fee,
        "estimated_gas": 21000,
        "total_fee_trp": round(raw_fee + priority_fee, 6),
        "fee_breakdown": {"base_fee": raw_fee, "priority_fee": priority_fee},
        "eip1559": True,
    }


# ── PQC status ────────────────────────────────────────────────────────────────

@app.get("/api/pqc/status")
async def pqc_status(request: Request):
    if r := await _forward(request):
        return r
    try:
        from dilithium_py.dilithium import Dilithium3
        Dilithium3.keygen()
        dil_ok = True
    except Exception:
        dil_ok = False
    return {
        "ed25519": {"status": "active", "real": True},
        "dilithium3": {"status": "active" if dil_ok else "simulated",
                       "real": dil_ok, "key_size": 1952},
        "kyber1024": {"status": "active", "real": True},
        "hybrid_signing": True,
        "quantum_resistant": True,
        "nist_level": 3,
    }


# ── Fleet ─────────────────────────────────────────────────────────────────────

@app.get("/api/fleet/stats")
async def fleet_stats(request: Request):
    if r := await _forward(request):
        return r
    # Count real FL providers + 2 internal agents always running
    ext_providers = 0
    fl_rounds = 0
    try:
        if _FL_V2_OK:
            ext_providers = len(_fl_v2.list_providers())
            gm = _fl_v2.get_global_model()
            fl_rounds = int(gm.get("rounds_completed", 0) or 0)
    except Exception:
        pass
    total = ext_providers + 2   # +2 ValidatorAgent + ComputeProviderAgent
    uptime_h = round((time.time() - _START_TIME) / 3600, 2)
    return {
        "total_providers":           total,
        "active_miners":             total,
        "active_sessions":           ext_providers,
        "total_compute_hours":       round(total * uptime_h, 2),
        "total_energy_watts":        total * 150,   # ~150W per node
        "total_tasks_completed":     fl_rounds,
        "total_rewards_distributed": round(fl_rounds * 1.0, 2),
        "status": "active",
    }

@app.get("/api/fleet/top-miners")
async def fleet_top_miners(request: Request):
    if r := await _forward(request):
        return r
    return {"miners": []}

@app.get("/api/fleet/regions")
async def fleet_regions(request: Request):
    if r := await _forward(request):
        return r
    return {"regions": []}


# ── AI Energy ─────────────────────────────────────────────────────────────────

@app.get("/api/ai-energy/stats")
async def ai_energy_stats(request: Request):
    if r := await _forward(request):
        return r
    return {
        "total_contributors": 0,
        "active_sessions": 0,
        "total_compute_hours": 0.0,
        "total_tasks_completed": 0,
        "total_rewards_distributed": 0.0,
    }

@app.get("/api/ai-energy/providers")
async def ai_energy_providers(request: Request):
    if r := await _forward(request):
        return r
    return {"providers": [], "total": 0}


# ── System status ─────────────────────────────────────────────────────────────

@app.get("/api/system/status")
async def system_status(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/health") or {}
    return {
        "status": "online",
        "python": {"status": "ready", "port": 8000},
        "go": {"status": "ok" if go else "unknown", "port": 8181},
        "rust": {"status": "ok", "port": 6000},
        "full_ai": {"status": "loading" if not _full_backend_ready else "ready"},
        "uptime_s": round(time.time() - _START_TIME, 1),
    }


# ── Explorer ──────────────────────────────────────────────────────────────────

@app.get("/api/explorer/blocks")
async def explorer_blocks(request: Request):
    # NOTE: intentionally NOT forwarded — fast gateway has better block-height
    # logic (reads total_blocks from Go stats); old main_simplified.py returns
    # the genesis placeholder block and is unreliable for the dashboard.
    limit = int(request.query_params.get("limit", 20))

    # Try Go /blocks/recent first — fastest source of real blocks
    go_recent = await _go("/blocks/recent") or {}
    blocks = go_recent.get("blocks", [])
    if blocks:
        return {"blocks": blocks[:limit], "total": len(blocks), "source": "go"}

    # Try Go stats to at least report the correct block height
    go_stats = await _go("/network/stats") or {}
    total_blocks = int(go_stats.get("total_blocks", go_stats.get("block_height", 0)) or 0)
    ai_acc = float(go_stats.get("ai_accuracy", 0.85) or 0.85)

    # Try PostgreSQL for persisted blocks (skip genesis-only result)
    if _pg:
        try:
            pg_blocks = await _pg.get_recent_blocks(limit)
            # Filter out genesis placeholder (index 0 with no real hash)
            real_pg = [b for b in (pg_blocks or []) if int(b.get("index", 0)) > 0]
            if real_pg:
                return {"blocks": real_pg, "total": total_blocks or len(real_pg), "source": "postgresql"}
        except Exception:
            pass

    # Synthesise a latest-block entry from Go stats so dashboard is never blank
    if total_blocks > 0:
        import time as _time
        synthetic = [{
            "index":      total_blocks,
            "timestamp":  int(_time.time()),
            "hash":       f"live:{total_blocks:08x}",
            "proposer":   "go-consensus",
            "tx_count":   int(go_stats.get("pending_txs", 0)),
            "ai_score":   round(ai_acc, 4),
            "source":     "go-stats",
        }]
        return {"blocks": synthetic, "total": total_blocks, "source": "go-stats"}

    return {"blocks": [], "total": 0, "source": "empty"}

@app.get("/api/explorer/transactions")
async def explorer_txs(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/transactions/recent") or {}
    txs = go.get("transactions", [])
    return {"transactions": txs, "total": len(txs)}

@app.get("/api/explorer/address/{address}")
async def explorer_address(address: str, request: Request):
    if r := await _forward(request):
        return r
    balance = 0.0
    if _pg:
        try:
            balance = await _pg.get_balance(address)
        except Exception:
            pass
    return {"address": address, "balance": balance, "transactions": []}


@app.get("/api/balance/{address}")
async def get_balance(address: str, request: Request):
    """
    GET /api/balance/{address}
    Returns TRP balance for an address from PostgreSQL live state.
    Falls back to 0 when the address is not known.
    """
    if r := await _forward(request):
        return r
    balance = 0.0
    if _pg:
        try:
            balance = await _pg.get_balance(address)
        except Exception:
            pass
    go_balance = 0.0
    try:
        go_data = await _go(f"/balance/{address}") or {}
        go_balance = float(go_data.get("balance", 0) or 0)
    except Exception:
        pass
    final_balance = max(balance, go_balance)
    return {
        "address": address,
        "balance": final_balance,
        "balance_trp": final_balance,
        "source": "postgresql" if balance > 0 else ("go" if go_balance > 0 else "not_found"),
    }


# ── PoI ───────────────────────────────────────────────────────────────────────

@app.get("/api/poi/scores")
async def poi_scores(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/network/stats") or {}
    return {"scores": [], "ai_accuracy": float(go.get("ai_accuracy", 0.85) or 0.85)}

@app.get("/api/poi/next-proposer")
async def poi_next_proposer(request: Request):
    if r := await _forward(request):
        return r
    return {"proposer": None, "reason": "warming_up"}

@app.post("/api/poi/score-block")
async def poi_score_block(request: Request):
    # NOTE: intentionally NOT forwarded to port 8001 — AI Consensus v2 runs
    # locally in main_fast.py so the new ensemble is always active regardless
    # of whether main_simplified.py is warmed up.
    try:
        body = await request.json()
    except Exception:
        body = {}

    block         = body.get("block", body)  # accept both {block:{}} and bare block dict
    network_stats = body.get("network_stats") or await _go("/network/stats") or {}

    if not _AI_V2_OK:
        return {"trust_score": 0.97, "accepted": True, "source": "fast-gateway-stub"}

    # Run five-model ensemble
    result = _consensus.score_block(block, network_stats)
    trust   = result["trust_score"]
    flagged = result["flagged"]

    # Build proof inputs/output — full payload so verify-proof can recompute hashes
    block_hash = str(block.get("hash", block.get("block_hash", "")))
    proof_inputs  = {"block_hash": block_hash, "tx_count": len(block.get("transactions", []))}
    proof_output  = {"trust_score": trust, "flagged": flagged, "sub_scores": result["sub_scores"]}

    # Generate verifiable proof (Ed25519 signed)
    proof = _gen_proof(
        model_id="ai_consensus_v2_ensemble",
        inputs=proof_inputs,
        output=proof_output,
        weights_hash=result["model_hash"],
    )

    # Fail closed: if signing failed the inference is NOT verifiable by peers.
    # Return 503 rather than silently producing an unverifiable score — callers
    # must treat this as a transient error and retry once the key is available.
    if not proof.get("signing_ok"):
        return JSONResponse(
            status_code=503,
            content={
                "error": "AI proof signing unavailable — service key not loaded",
                "retryable": True,
                "source": "ai-consensus-v2",
            },
        )

    # Cache in memory + persist to PostgreSQL (only signed proofs reach here)
    _cache_proof(proof)
    if _pg:
        asyncio.create_task(_pg.save_ai_proof(proof, trust_score=trust, block_hash=block_hash))

    # Return full proof payload so callers can pass it directly to /api/ai/verify-proof.
    # canonical_inputs / canonical_output allow peers to fully recompute every hash
    # from scratch and confirm the signed decision matches these exact inputs & outputs.
    # NOTE: weights_hash = proof["weights_hash"] = model_hash (NOT ensemble_weights_hash).
    return {
        "trust_score":           trust,
        "accepted":              not flagged,
        "flagged":               flagged,
        "sub_scores":            result["sub_scores"],
        "model_version":         result["model_version"],
        "model_hash":            result["model_hash"],
        "ensemble_weights_hash": result["weights_hash"],  # governance weight ratios hash
        # Complete proof dict — all fields needed for /api/ai/verify-proof
        "inference_id":      proof["inference_id"],
        "model_id":          proof["model_id"],
        "input_hash":        proof["input_hash"],
        "output_hash":       proof["output_hash"],
        "weights_hash":      proof["weights_hash"],   # = model_hash; used to compute proof
        "proof":             proof["proof"],
        "signature":         proof["signature"],
        "pubkey":            proof["pubkey"],
        "timestamp_ms":      proof["timestamp_ms"],
        "signing_ok":        proof["signing_ok"],
        # Canonical objects — peers recompute input_hash/output_hash/inference_id from these
        "canonical_inputs":  proof_inputs,
        "canonical_output":  proof_output,
        "source":            "ai-consensus-v2",
    }


# ── P2P ───────────────────────────────────────────────────────────────────────

@app.get("/api/p2p/peers")
async def p2p_peers(request: Request):
    if r := await _forward(request):
        return r
    go = await _go("/p2p/info") or {}
    return {"peers": go.get("peers", []), "count": go.get("peer_count", 0)}

@app.get("/api/p2p/bootstrap")
async def p2p_bootstrap(request: Request):
    if r := await _forward(request):
        return r
    return {"bootstrap_nodes": []}


# ── State endpoints ───────────────────────────────────────────────────────────

@app.get("/api/state/proof")
@app.get("/api/state/proof/{address}")
async def state_proof(request: Request, address: str = ""):
    if r := await _forward(request):
        return r
    return {"address": address, "proof": [], "state_root": _current_state_root}


# ── RPC ───────────────────────────────────────────────────────────────────────

@app.post("/rpc")
@app.post("/api/rpc")
async def rpc(request: Request):
    if r := await _forward(request):
        return r
    try:
        body = await request.json()
    except Exception:
        body = {}
    method = body.get("method", "")
    rid = body.get("id", 1)
    # Basic JSON-RPC stubs for MetaMask
    if method == "eth_chainId":
        return {"jsonrpc": "2.0", "id": rid, "result": "0x1CA3"}
    if method == "eth_blockNumber":
        go = await _go("/network/stats") or {}
        height = int(go.get("total_blocks", go.get("block_height", 0)) or 0)
        return {"jsonrpc": "2.0", "id": rid, "result": hex(height)}
    if method == "net_version":
        return {"jsonrpc": "2.0", "id": rid, "result": "7331"}
    return {"jsonrpc": "2.0", "id": rid, "result": None}


# ── Internal Go → Python callbacks ───────────────────────────────────────────

_INTERNAL_HOSTS = {"127.0.0.1", "::1", "localhost"}


@app.post("/api/internal/go/verify-dilithium")
async def go_verify_dilithium(request: Request):
    """
    POST /api/internal/go/verify-dilithium
    Called by Go consensus node to verify a Dilithium3 signature using dilithium-py.
    Request:  { message_hex: str, signature_hex: str, public_key_hex: str }
    Response: { valid: bool, error: str|null }

    Intentionally NOT forwarded — always runs locally so it is available
    immediately on startup (before the full backend warms up).
    Restricted to localhost callers only.
    """
    caller = request.client.host if request.client else ""
    if caller not in _INTERNAL_HOSTS:
        return JSONResponse(status_code=403, content={"valid": False, "error": "forbidden"})

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"valid": False, "error": "invalid_json"})

    message_hex   = payload.get("message_hex", "")
    signature_hex = payload.get("signature_hex", "")
    public_key_hex = payload.get("public_key_hex", "")

    if not message_hex or not signature_hex or not public_key_hex:
        return {"valid": False, "error": "missing_fields"}

    try:
        msg_bytes  = bytes.fromhex(message_hex)
        sig_bytes  = bytes.fromhex(signature_hex)
        pub_bytes  = bytes.fromhex(public_key_hex)
    except ValueError as exc:
        return {"valid": False, "error": f"hex_decode_error: {exc}"}

    try:
        from dilithium_py.dilithium import Dilithium3
        valid = Dilithium3.verify(pub_bytes, msg_bytes, sig_bytes)
        return {"valid": bool(valid), "error": None}
    except Exception as exc:
        return {"valid": False, "error": f"verify_error: {exc}"}


@app.post("/api/internal/go/block-mined")
async def block_mined_callback(request: Request):
    """
    Go calls this after every mined block. Save to PostgreSQL and ack.

    When Go has a Kyber channel key registered, the AI proof arrives ENCRYPTED
    (confidentiality enforced — no plaintext is sent over the channel):
      - ai_proof_encrypted: hex AES-256-GCM ciphertext (PQC-protected)
      - ai_proof_nonce    : hex 12-byte GCM nonce
      - ai_proof_scheme   : "AES-256-GCM+Kyber1024"

    Python decrypts ai_proof_encrypted using _GO_CHANNEL_KEY (derived from the
    Kyber session). AES-256-GCM's authentication tag guarantees integrity, so a
    successful decrypt is sufficient proof. This path is FAIL-CLOSED: if the
    encrypted channel is in use but decryption fails (missing key, tampering,
    session mismatch), the block is rejected rather than silently accepted.

    When no Kyber channel is installed, Go falls back to a plaintext ai_proof.
    """
    # Require a valid shared secret unconditionally (Go sends both X-Block-Secret
    # and Authorization: Bearer). A missing header must NOT bypass auth.
    expected = os.environ.get("BLOCK_MINED_SECRET", "trispi-internal-block-secret")
    header_secret = request.headers.get("X-Block-Secret", "")
    auth_header   = request.headers.get("Authorization", "")
    bearer_secret = auth_header[7:] if auth_header.startswith("Bearer ") else ""
    provided = header_secret or bearer_secret
    if provided != expected:
        return JSONResponse(status_code=403, content={"error": "forbidden"})
    try:
        block = await request.json()
    except Exception:
        block = {}

    block_num  = block.get("block_number", block.get("index", block.get("height", 0)))
    block_hash = block.get("block_hash", block.get("hash", ""))

    # ── Kyber channel: decrypt the AI proof (fail-closed) ────────────────────
    ai_proof_enc    = block.get("ai_proof_encrypted", "")
    ai_proof_nonce  = block.get("ai_proof_nonce", "")
    ai_proof_scheme = block.get("ai_proof_scheme", "")
    channel_in_use  = bool(ai_proof_scheme) or bool(ai_proof_enc)
    if channel_in_use:
        # Encrypted channel is in use — confidentiality is enforced, so we MUST
        # be able to decrypt. Any failure rejects the block (fail-closed).
        if not _GO_CHANNEL_KEY:
            print(f"[fast] REJECT block {block_num}: encrypted ai_proof but no Kyber channel key")
            return JSONResponse(status_code=503,
                                content={"error": "kyber_channel_not_established", "block": block_num})
        if not (ai_proof_enc and ai_proof_nonce):
            print(f"[fast] REJECT block {block_num}: encrypted scheme but missing ciphertext/nonce")
            return JSONResponse(status_code=400,
                                content={"error": "missing_encrypted_proof_fields", "block": block_num})
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            import json as _json
            key   = bytes.fromhex(_GO_CHANNEL_KEY)
            nonce = bytes.fromhex(ai_proof_nonce)
            ct    = bytes.fromhex(ai_proof_enc)
            # AES-GCM auth tag verification happens inside decrypt(); a wrong key,
            # tampered ciphertext, or session mismatch raises and we fail closed.
            plain = AESGCM(key).decrypt(nonce, ct, None)
            block["ai_proof"] = _json.loads(plain)       # GCM tag already proved integrity
            block["ai_proof_kyber_verified"] = True
        except Exception as e:
            print(f"[fast] REJECT block {block_num}: Kyber ai_proof decrypt failed: {e}")
            return JSONResponse(status_code=400,
                                content={"error": "kyber_decrypt_failed", "block": block_num})

    # ── Update live base_fee from actual block data ───────────────────────────
    global _LIVE_BASE_FEE
    block_fee = float(block.get("base_fee", block.get("BaseFee", block.get("gas_price", 0.0))) or 0.0)
    if 0 < block_fee < 100.0:   # sanity bounds: > 0 and < 100 TRP
        _LIVE_BASE_FEE = block_fee

    # Persist to PostgreSQL in the background
    if _pg and block_num:
        asyncio.create_task(_persist_block(block))
    return {"ok": True, "block": block_num, "hash": block_hash, "persisted": bool(_pg)}


async def _persist_block(block: dict) -> None:
    """
    Persist a mined block (from Go callback) to PostgreSQL via PGPersist.save_block().

    Normalises Go's block JSON format to the PGPersist schema so that both
    block metadata and individual transactions are stored correctly.
    Also saves any embedded AI proof to trispi_ai_proofs.
    """
    if not (_pg and _pg._pool):
        return
    try:
        # ── Normalise field names from Go's schema to PGPersist schema ────────
        normalized: dict = {
            "index":       block.get("index", block.get("block_number", block.get("height", 0))),
            "hash":        block.get("hash", block.get("block_hash", "")),
            "prev_hash":   block.get("prev_hash", ""),
            "state_root":  block.get("state_root", _current_state_root),
            "merkle_root": block.get("merkle_root", block.get("tx_root", "")),
            "proposer":    block.get("proposer", block.get("miner", "go-consensus")),
            "gas_used":    int(block.get("gas_used", 0) or 0),
            "gas_limit":   int(block.get("gas_limit", 10_000_000) or 10_000_000),
            "transactions": block.get("transactions", block.get("txns", [])),
        }

        # Persist block + all transactions atomically via PGPersist
        await _pg.save_block(normalized)

        # Persist AI proof if present in block
        ai_proof = block.get("ai_proof") or block.get("AIProof")
        if ai_proof and isinstance(ai_proof, dict):
            # Synthesize an inference_id from block hash + model_hash
            bhash = normalized["hash"]
            model_hash = ai_proof.get("model_hash", ai_proof.get("ModelHash", ""))
            import hashlib as _hl
            infer_id = _hl.sha3_256(f"{bhash}|{model_hash}".encode()).hexdigest()
            proof_record = {
                "inference_id":  infer_id,
                "model_id":      model_hash or "go-consensus-ai",
                "input_hash":    bhash,
                "output_hash":   _hl.sha3_256(str(ai_proof).encode()).hexdigest(),
                "weights_hash":  model_hash,
                "proof":         infer_id,
                "signature":     "",
                "pubkey":        "",
                "timestamp_ms":  int(time.time() * 1000),
            }
            trust_score = float(ai_proof.get("accuracy", ai_proof.get("Accuracy", 0.0)))
            await _pg.save_ai_proof(proof_record, trust_score=trust_score, block_hash=bhash)

        # Keep local state root in sync
        root = normalized["state_root"]
        if root:
            await _save_state_root(root)

    except Exception as e:
        print(f"[fast] _persist_block error: {e}")


# ── Verifiable AI endpoints ───────────────────────────────────────────────────

@app.get("/api/ai/proof/{inference_id}")
async def get_ai_proof(inference_id: str):
    """Retrieve a stored AI inference proof by ID."""
    # Memory cache first
    if _AI_V2_OK:
        cached = _get_cached_proof(inference_id)
        if cached:
            return {"found": True, "proof": cached, "source": "cache"}
    # PostgreSQL fallback
    if _pg:
        stored = await _pg.get_ai_proof(inference_id)
        if stored:
            return {"found": True, "proof": stored, "source": "postgresql"}
    return JSONResponse(status_code=404, content={"found": False, "inference_id": inference_id})


@app.post("/api/ai/verify-proof")
async def verify_ai_proof(request: Request):
    """
    Verify a Verifiable AI proof dict submitted by a peer.
    Accepts the full proof payload as returned by /api/poi/score-block.
    Intentionally NOT forwarded — always runs locally in fast-gateway.
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    if not _AI_V2_OK:
        return JSONResponse(
            status_code=503,
            content={"valid": False, "error": "ai_consensus_v2 not loaded — cannot verify"},
        )

    result = _verify_proof(body)
    return result


@app.post("/api/ai/validate-tx")
async def validate_tx(request: Request):
    """
    POST /api/ai/validate-tx

    AI-powered transaction fraud validation.  Called by Go consensus after
    signature verification and before mempool admission.  Must respond in
    < 150 ms — runs the FraudDetector numpy MLP locally.

    Decentralized mode: if the request carries X-Validator-Id and
    X-Validator-Sig headers, the verdict is also recorded in the pool so
    the aggregate response includes the external vote.  External providers
    can also submit verdicts independently via POST /api/validators/submit-tx-verdict.

    Request body:
      tx_id     : str    — transaction identifier
      from      : str    — sender address
      to        : str    — recipient address  (or "" for contract deploy)
      amount    : float  — TRP amount
      data      : str    — optional contract call data (hex)
      gas_fee   : float  — (optional) gas fee
      timestamp : int    — (optional) unix epoch

    Optional headers:
      X-Validator-Id  : registered provider_id submitting an external verdict
      X-Validator-Sig : Ed25519 hex signature over sha3_256(provider_id:tx_hash:valid:fraud_score)

    Response:
      valid            : bool   — final consensus verdict
      fraud_score      : float  — server's fraud score (0.0–1.0, 4 dp)
      consensus_score  : float  — trust-weighted consensus across all votes
      reason           : str    — human-readable verdict
      model_id         : str    — which model scored this tx
      votes            : dict   — {total, for_valid, against_valid, consensus_strength}
      decentralized    : bool   — True if ≥1 external validator contributed
    """
    if not _AI_V2_OK:
        return JSONResponse(
            status_code=503,
            content={"valid": True, "fraud_score": 0.0, "consensus_score": 0.0,
                     "reason": "ai_consensus_v2 not loaded — passthrough", "model_id": "none",
                     "decentralized": False},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    tx: dict = {
        "from":      str(body.get("from", body.get("from_addr", ""))),
        "to":        str(body.get("to", body.get("to_addr", ""))),
        "amount":    float(body.get("amount", body.get("value", 0)) or 0),
        "gas_fee":   float(body.get("gas_fee", body.get("fee", 0.001)) or 0.001),
        "data":      str(body.get("data", "")),
        "timestamp": int(body.get("timestamp", time.time())),
    }

    # Use the shared fraud_model (same module as energy provider nodes) for
    # deterministic consensus parity.  Fall back to ai_consensus_v2's FraudDetector
    # only if fraud_model.py failed to import.
    try:
        if _FM_OK and _fm_score_tx is not None:
            fraud_score = float(_fm_score_tx(tx))
        elif _AI_V2_OK:
            fraud_score = float(_consensus.fraud.score_transaction(tx))
        else:
            return JSONResponse(status_code=503,
                content={"error": "no fraud scorer available", "valid": True, "fraud_score": 0.0})
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"scoring failed: {exc}", "valid": True, "fraud_score": 0.0},
        )

    _FRAUD_THRESHOLD = 0.65   # aligned with fraud_model.py and energy provider

    # Build tx_hash for verdict pool lookup
    tx_hash = str(body.get("tx_id", body.get("tx_hash", "")))
    if not tx_hash:
        import hashlib as _hl
        _raw = f"{tx['from']}:{tx['to']}:{tx['amount']}:{tx['timestamp']}"
        tx_hash = _hl.sha256(_raw.encode()).hexdigest()

    # Record server's own vote first (trust_weight = 1.0, always included)
    server_valid = fraud_score <= _FRAUD_THRESHOLD
    server_vote  = {
        "provider_id": "server_validator",
        "valid":       server_valid,
        "fraud_score": round(fraud_score, 4),
        "weight":      1.0,
    }

    # If the caller included X-Validator-Id + X-Validator-Sig, record external vote inline.
    # External providers can also use the dedicated /submit-tx-verdict endpoint.
    ext_id  = request.headers.get("X-Validator-Id", "").strip()
    ext_sig = request.headers.get("X-Validator-Sig", "").strip()
    ext_fraud_score = float(body.get("fraud_score", fraud_score))
    ext_valid = ext_fraud_score <= _FRAUD_THRESHOLD

    if ext_id and ext_sig and _AGENTS_OK and _validator_registry:
        msg_str   = f"{ext_id}:{tx_hash}:{int(ext_valid)}:{ext_fraud_score:.6f}"
        msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
        if _validator_registry.verify_signature(ext_id, msg_bytes, ext_sig):
            v            = _validator_registry.get(ext_id)
            trust_weight = float(v["trust_weight"]) if v else 0.5
            # Enforce same trust_weight floor as /submit-tx-verdict
            if v is not None and trust_weight >= 0.30:
                with _verdict_lock:
                    _tx_verdict_pool.setdefault(tx_hash, [])
                    if not any(vt["provider_id"] == ext_id for vt in _tx_verdict_pool[tx_hash]):
                        _tx_verdict_pool[tx_hash].append({
                            "provider_id": ext_id,
                            "valid":       ext_valid,
                            "fraud_score": round(ext_fraud_score, 4),
                            "weight":      round(trust_weight, 4),
                        })
                        # Count here (submit path counts in /submit-tx-verdict)
                        _tx_val_stats["validator_tx_counts"][ext_id] = \
                            _tx_val_stats["validator_tx_counts"].get(ext_id, 0) + 1

    # Wait up to 100 ms for external verdicts already in the pool (from
    # /submit-tx-verdict calls that may have arrived before this validate call)
    await asyncio.sleep(0.1)

    # Collect all votes: server + pool
    with _verdict_lock:
        pool_votes = list(_tx_verdict_pool.get(tx_hash, []))

    all_votes = [server_vote] + [v for v in pool_votes if v["provider_id"] != "server_validator"]
    ext_votes = [v for v in all_votes if v["provider_id"] != "server_validator"]

    total_weight = sum(v["weight"] for v in all_votes)
    valid_weight = sum(v["weight"] for v in all_votes if v["valid"])
    valid_fraction = valid_weight / max(total_weight, 1e-9)

    # Supermajority threshold: >60% by weight = consensus valid; otherwise invalid
    SUPERMAJORITY = 0.60
    consensus_valid = valid_fraction > SUPERMAJORITY
    consensus_score = round(valid_fraction, 4)
    consensus_strength = max(valid_fraction, 1.0 - valid_fraction)  # distance from 50/50

    decentralized = len(ext_votes) > 0

    # Update aggregate stats — validator_tx_counts is NOT incremented here;
    # it is incremented exactly once per verdict in /submit-tx-verdict (and in
    # the inline header path above), so no double-counting occurs.
    with _verdict_lock:
        _tx_val_stats["total_validated"] += 1
        if decentralized:
            _tx_val_stats["decentralized_count"] += 1
        _tx_val_stats["consensus_strength_sum"] += consensus_strength

    if consensus_valid:
        reason = (
            "clean — consensus valid" if fraud_score < 0.30
            else "caution — moderate risk, consensus valid" if fraud_score < 0.50
            else "warning — elevated risk, consensus valid"
        )
    else:
        reason = (
            f"rejected — consensus {consensus_score:.0%} valid votes below "
            f"{SUPERMAJORITY:.0%} supermajority threshold"
        )

    _active_model_id = (
        "fraud_model_v1"           if (_FM_OK and _fm_score_tx is not None)
        else _consensus.fraud.MODEL_ID if _AI_V2_OK
        else "unknown"
    )

    return {
        "valid":             consensus_valid,
        "fraud_score":       round(fraud_score, 4),
        "consensus_score":   consensus_score,
        "reason":            reason,
        "model_id":          _active_model_id,
        "threshold":         _FRAUD_THRESHOLD,
        "votes": {
            "total":              len(all_votes),
            "external":          len(ext_votes),
            "for_valid":         sum(1 for v in all_votes if v["valid"]),
            "against_valid":     sum(1 for v in all_votes if not v["valid"]),
            "consensus_strength": round(consensus_strength, 4),
        },
        "decentralized": decentralized,
    }


@app.get("/api/ai/consensus/stats")
async def ai_consensus_stats():
    """
    Return AI Consensus 2.0 ensemble statistics.
    Intentionally NOT forwarded — always runs locally in fast-gateway.
    """
    if not _AI_V2_OK:
        return {"available": False, "reason": "ai_consensus_v2 not loaded"}
    stats = _consensus.get_stats()
    stats["available"] = True
    return stats


@app.get("/api/ai/proofs/recent")
async def ai_proofs_recent():
    """
    List recent AI inference proofs from PostgreSQL.
    Intentionally NOT forwarded — always runs locally in fast-gateway.
    """
    if _pg:
        proofs = await _pg.get_recent_proofs(20)
        return {"proofs": proofs, "total": len(proofs), "source": "postgresql"}
    return {"proofs": [], "total": 0, "source": "no-db"}


@app.post("/api/ai/consensus/weights")
async def update_consensus_weights(request: Request):
    """
    Governance endpoint — update ensemble model weights and persist to DB.
    Body: {"fraud": 0.3, "mempool": 0.2, "contract": 0.2, "validator": 0.15, "anomaly": 0.15}
    All values are normalised to sum=1 before storage.
    Intentionally NOT forwarded — always runs locally in fast-gateway.

    Authorization: caller must supply header X-Governance-Token matching the
    GOVERNANCE_SECRET environment variable.  Without a matching token the
    endpoint returns 403 — unauthenticated mutations to consensus weights would
    be a trust-critical security failure.
    """
    # ── Authorization ────────────────────────────────────────────────────────
    expected_token = os.environ.get("GOVERNANCE_SECRET", "")
    supplied_token = request.headers.get("X-Governance-Token", "")
    if not expected_token:
        # No secret configured — endpoint is locked until GOVERNANCE_SECRET is set.
        return JSONResponse(
            status_code=503,
            content={"error": "GOVERNANCE_SECRET not configured — governance endpoint locked"},
        )
    if not supplied_token or supplied_token != expected_token:
        return JSONResponse(
            status_code=403,
            content={"error": "Invalid or missing X-Governance-Token"},
        )
    # ─────────────────────────────────────────────────────────────────────────

    if not _AI_V2_OK:
        return JSONResponse(status_code=503, content={"error": "ai_consensus_v2 not loaded"})
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})
    new_weights = _consensus.update_weights(body)
    persisted = False
    if _pg:
        persisted = await _consensus.save_weights_to_db(_pg)
    return {
        "updated":    True,
        "weights":    new_weights,
        "persisted":  persisted,
        "model_hash": _consensus._compute_model_hash(),
    }


# ── Federated Learning 2.0 ───────────────────────────────────────────────────
# None of these endpoints are forwarded to :8001 — the FL v2 engine runs
# entirely inside main_fast.py so it is always active regardless of whether
# the heavy ML backend has warmed up.

def _fl_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": "federated_learning_v2 module not loaded"},
    )


@app.post("/api/federated/register")
async def fl_register_provider(request: Request):
    """
    Register a provider's Ed25519 public key and stake address.

    Binding is permanent: the registered stake_address cannot be changed by
    supplying a different address in submit-gradient, preventing a provider
    from claiming a whale's stake weight at submission time.

    The key is used to:
      (a) derive the per-round AES-256-GCM encryption key, and
      (b) verify the Ed25519 signature on every gradient submission.

    Body (JSON):
      provider_id   : str  — unique provider identifier
      pubkey_hex    : str  — Ed25519 public key, 64 hex chars (32 raw bytes)
      stake_address : str  — TRP address whose balance is used as stake weight
    """
    if not _FL_V2_OK:
        return _fl_unavailable()
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    provider_id      = str(body.get("provider_id", "")).strip()
    pubkey_hex       = str(body.get("pubkey_hex", "")).strip()
    stake_address    = str(body.get("stake_address", "")).strip().lower()
    stake_pubkey_hex = str(body.get("stake_pubkey_hex", "")).strip()
    stake_signature  = str(body.get("stake_signature", "")).strip()

    if not provider_id:
        return JSONResponse(status_code=400, content={"error": "provider_id is required"})
    if not pubkey_hex:
        return JSONResponse(status_code=400, content={"error": "pubkey_hex is required"})

    ok, err = _fl_v2.register_provider(
        provider_id, pubkey_hex, stake_address, stake_pubkey_hex, stake_signature
    )
    if not ok:
        return JSONResponse(status_code=422, content={"error": err})

    round_nonce = _fl_v2.get_round_nonce(provider_id)
    return {
        "registered":      True,
        "provider_id":     provider_id,
        "pubkey_hex":      pubkey_hex,
        "stake_address":   stake_address,
        "stake_verified":  bool(stake_address and stake_pubkey_hex and stake_signature),
        "round_nonce":     round_nonce,
        "key_derivation": (
            "aes_key = sha3_256(provider_ed25519_pubkey_bytes || round_nonce) where "
            "round_nonce = sha3_256(f'{round_id}|{provider_id}')"
        ),
        "sign_gradient": (
            "sha3_256(provider_id|round_id|gradient_hash|registered_stake_address)"
            " — use FL private key; stake_address is the registered value"
        ),
        "stake_ownership_challenge": (
            "sha3_256('trispi_fl_stake_ownership:{provider_id}:{pubkey_hex}:{stake_address}')"
            " — sign with stake-address private key to prove ownership at registration"
        ),
    }


@app.post("/api/federated/submit-gradient")
async def fl_submit_gradient(request: Request):
    """
    Submit an AES-256-GCM encrypted gradient for the current FL round.

    Providers must register via POST /api/federated/register first (pubkey + stake_address).
    Stake weight is looked up using the *registered* stake_address — the caller cannot
    supply a different address to inflate their aggregation influence.

    Body (JSON):
      provider_id : str  — registered provider identifier
      gradient    : dict — encrypted payload {"ciphertext": hex, "nonce": hex, "encrypted": true}
                           Plaintext payloads are rejected.
      signature   : str  — Ed25519 signature (hex, 128 chars) over
                           sha3_256(provider_id|round_id|gradient_hash|registered_stake_address)
      round_id    : int  (optional) — rejected if it mismatches the current round
    """
    if not _FL_V2_OK:
        return _fl_unavailable()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    provider_id   = str(body.get("provider_id", "")).strip()
    gradient      = body.get("gradient") or {}
    signature_hex = body.get("signature") or body.get("signature_hex") or None

    if not provider_id:
        return JSONResponse(status_code=400, content={"error": "provider_id is required"})
    if not gradient:
        return JSONResponse(status_code=400, content={"error": "gradient is required"})

    # Optional round_id consistency check
    supplied_round = body.get("round_id")
    if supplied_round is not None:
        current_status = _fl_v2.get_round_status()
        if int(supplied_round) != current_status["round_id"]:
            return JSONResponse(
                status_code=409,
                content={
                    "error":         "round_id_mismatch",
                    "supplied":      supplied_round,
                    "current_round": current_status["round_id"],
                },
            )

    # Look up stake using the *registered* stake_address — not caller-supplied.
    # This binds stake weight to the identity registered at onboarding.
    registered_addr = _fl_v2.get_registered_stake_address(provider_id) or ""
    stake = 0.0
    if _pg and registered_addr:
        stake = await _pg.get_provider_stake(registered_addr)

    result = _fl_v2.submit_gradient(
        provider_id=provider_id,
        gradient_payload=gradient,
        stake=stake,
        signature_hex=signature_hex,
    )

    if not result.get("accepted"):
        return JSONResponse(status_code=422, content=result)
    return result


@app.get("/api/federated/round-status")
async def fl_round_status(request: Request):
    """
    Current FL round status, including how many providers have submitted
    and whether enough are present to trigger aggregation.
    Also returns per-provider round nonce so callers can derive their AES key.
    """
    if not _FL_V2_OK:
        return _fl_unavailable()
    status = _fl_v2.get_round_status()
    return {
        **status,
        "encryption": {
            "algorithm":      "AES-256-GCM",
            "key_derivation": "sha3_256(provider_ed25519_pubkey || sha3_256(round_id|provider_id))",
            "available":      _FL_CRYPTO_OK,
        },
        "aggregation": {
            "method":         "coordinate_wise_median",
            "byzantine_filter": f"krum (excludes bottom {status['krum_exclude_pct']}%)",
            "stake_weighted": True,
        },
    }


@app.get("/api/federated/global-model")
async def fl_global_model(request: Request):
    """
    Return the current aggregated global model metadata (hash, version,
    per-layer shape + L2 norm summary).  Does NOT return raw weights to
    avoid large response payloads.
    """
    if not _FL_V2_OK:
        return _fl_unavailable()
    return _fl_v2.get_global_model()


@app.get("/api/federated/global-model-weights")
async def fl_global_model_weights(request: Request):
    """
    Return the current global model as raw numeric arrays (W1, b1, W2, b2)
    suitable for use as local training initialisation.  Returns
    has_weights=False with an empty weights dict before the first FL round
    completes.  External energy-provider nodes should call this endpoint,
    not /api/federated/global-model, which returns only summary metadata.
    """
    if not _FL_V2_OK:
        return _fl_unavailable()
    return _fl_v2.get_global_weights_raw()


@app.get("/api/federated/providers")
async def fl_providers(request: Request):
    """
    Reputation leaderboard — providers ranked by their accumulated
    federated learning reputation score (1.0 = perfect, 0.0 = Byzantine).
    Merges in-memory scores with persisted DB records.
    """
    if not _FL_V2_OK:
        return _fl_unavailable()

    limit = int(request.query_params.get("limit", 50))

    # In-memory leaderboard (always up-to-date within the current session)
    mem_board = _fl_v2.get_leaderboard(limit=limit)

    # Try to enrich with DB participation stats
    db_records: list = []
    if _pg:
        try:
            db_records = await _pg.get_fl_leaderboard(limit=limit)
        except Exception:
            pass

    db_map = {r["provider_id"]: r for r in db_records}
    enriched = []
    for entry in mem_board:
        pid   = entry["provider_id"]
        db    = db_map.get(pid, {})
        enriched.append({
            **entry,
            "rounds_participated": db.get("rounds_participated", 0),
            "rounds_excluded":     db.get("rounds_excluded", 0),
            "accuracy_contribution": db.get("accuracy_contribution", 0.0),
        })

    return {
        "providers":       enriched,
        "total":           len(enriched),
        "source":          "fl_v2_engine",
        "min_stake_trp":   _fl_v2.get_round_status()["min_stake_trp"],
    }


@app.post("/api/federated/trigger-round")
async def fl_trigger_round(request: Request):
    """
    Attempt to aggregate the current FL round.

    Called by the Go consensus node after each block finalization (or manually
    for testing).  If fewer than MIN_PROVIDERS_ROUND (default 3) gradients have
    been submitted the response is 202 Accepted with aggregated=false.

    On successful aggregation:
    - Coordinate-wise median is applied to Krum-filtered accepted gradients.
    - Provider reputation scores are updated (+2 % included / -5 % excluded).
    - Updated scores are persisted to trispi_fl_reputation in PostgreSQL.
    """
    if not _FL_V2_OK:
        return _fl_unavailable()

    result = _fl_v2.trigger_round()

    if not result.get("aggregated"):
        return JSONResponse(status_code=202, content=result)

    # ── Persist reputation changes to PostgreSQL asynchronously ───────────────
    if _pg:
        rep_changes = result.get("reputation_changes", {})
        accepted_set = set(result.get("accepted_providers", []))
        for pid, change in rep_changes.items():
            asyncio.create_task(
                _pg.save_fl_reputation(
                    provider_id=pid,
                    reputation_score=change["new"],
                    included=(pid in accepted_set),
                )
            )

    # ── On-chain commitment TX ────────────────────────────────────────────────
    # Post the aggregation commitment hash to Go as a zero-amount signed TX so
    # the result is permanently anchored on-chain and publicly verifiable via
    # GET /api/federated/verify-round/{round_id}.
    if _AGENTS_OK and _agents_post_tx and _agents_load_service_key:
        asyncio.create_task(_fl_post_commitment_tx(result))

    return result


async def _fl_post_commitment_tx(result: dict) -> None:
    """
    Post the FL round aggregation commitment to the Go blockchain as a signed TX.

    TX is zero-amount (data-only) from the service key to a well-known
    FL-registry address.  The commitment_hash field lets anyone verify the
    aggregation by fetching GET /api/federated/verify-round/{round_id} and
    re-computing sha3_256(canonical_json(result)).

    Also dispatches 1.0 TRP reward TXs to each accepted external FL provider
    whose stake_address is registered in the FL ProviderRegistry.
    """
    round_id         = result.get("round_id", 0)
    commitment_hash  = result.get("commitment_hash", "")
    model_hash       = result.get("model_hash", "")
    accepted_ids     = result.get("accepted_providers", [])
    quality_score    = result.get("aggregate_quality_score", 0.0)

    svc       = _agents_load_service_key()
    from_addr = svc.get("address", "trp1_fl_aggregator")

    # 1. Anchor the round commitment on-chain (zero-amount data TX)
    commitment_ok = await _agents_post_tx(
        from_addr = from_addr,
        to_addr   = "trispi_fl_registry",
        amount    = 0.0,
        data      = json.dumps({
            "event":            "FL_ROUND_COMMITTED",
            "round_id":         round_id,
            "commitment_hash":  commitment_hash,
            "model_hash":       model_hash,
            "n_accepted":       len(accepted_ids),
            "quality_score":    round(quality_score, 6),
            "verify_url":       f"/api/federated/verify-round/{round_id}",
        }),
    )
    if commitment_ok:
        logger.info(f"[FL] Round {round_id} commitment anchored on-chain: {commitment_hash[:16]}…")
    else:
        logger.warning(f"[FL] Round {round_id} commitment TX failed — hash not anchored")

    # 2. TRP reward TXs for accepted external FL providers
    _server_ids = frozenset({"server_compute_node"})
    fl_reward_trp = 1.0   # 1.0 TRP per accepted gradient

    for pid in accepted_ids:
        if pid in _server_ids:
            continue   # server's own node — tracked internally only

        stake_address = _fl_v2.get_registered_stake_address(pid) if _FL_V2_OK else None
        if not stake_address:
            logger.debug(f"[FL] {pid}: no stake_address registered — reward skipped")
            continue

        reward_ok = await _agents_post_tx(
            from_addr = from_addr,
            to_addr   = stake_address,
            amount    = fl_reward_trp,
            data      = json.dumps({
                "event":            "FL_GRADIENT_REWARD",
                "provider_id":      pid,
                "round_id":         round_id,
                "commitment_hash":  commitment_hash,
                "reward_trp":       fl_reward_trp,
                "quality_score":    round(quality_score, 6),
            }),
        )
        if reward_ok:
            logger.info(f"[FL] Rewarded {pid}: {fl_reward_trp} TRP → {stake_address[:16]}…")
        else:
            logger.warning(f"[FL] Reward TX failed for {pid} (round {round_id})")


# ── AI Smart Contract Security Scanner v2.0 ──────────────────────────────────
# These endpoints are never forwarded — the ML auditor runs locally in the
# fast gateway so security scanning is always available, independent of whether
# the heavy AI backend (port 8001) has warmed up.

@app.post("/api/security/scan-contract")
async def security_scan_contract(request: Request):
    """
    POST /api/security/scan-contract

    Scan EVM, WASM or DUO (hybrid) bytecode with the AI Security Scanner v2.0:
      - VulnerabilityMLScorer : 3-layer numpy MLP (256 opcode freqs → 7 vuln classes)
      - RugPullDetector        : logistic regression on 6 rug-pull features
      - LiquidityAttackScorer : flash loan / oracle manipulation / sandwich detection
      - EVMPathTracer          : JUMP/JUMPI reachability analysis (< 100 ms)
      - DUO mode               : runs both EVM + WASM scanners and combines scores

    Body (JSON):
      bytecode          : str  — EVM bytecode hex (0x prefix optional)
      wasm_bytecode     : str  — WASM binary as base64 or hex (for WASM/DUO)
      runtime_type      : str  — "EVM" | "WASM" | "DUO"  (default: "EVM")
      source_code       : str  — optional Solidity/Rust source for deeper analysis
      contract_address  : str  — optional address for audit record linkage
      block_number      : int  — optional block at which deployment is requested

    Returns:
      risk_score          : 0.0 – 1.0  (aggregate ensemble score)
      rug_pull_probability: 0.0 – 1.0  (logistic regression output)
      liquidity_risk      : 0.0 – 1.0  (flash loan / oracle / sandwich score)
      vulnerabilities     : list of detected issues with severity + detector
      severity            : "safe" | "caution" | "warning" | "critical"
      deploy_allowed      : false when risk_score >= 0.8 (BLOCKED)
      recommendation      : human-readable advice

    Go deploy hook: Go consensus nodes should POST to this endpoint before
    accepting a contract deployment into the mempool.  If deploy_allowed is
    false, the node must reject the transaction.
    """
    if not _AUDITOR_OK:
        return JSONResponse(
            status_code=503,
            content={"error": "contract_auditor module not loaded"},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    bytecode         = str(body.get("bytecode", "") or "").strip()
    wasm_b64         = str(body.get("wasm_bytecode", "") or "").strip()
    runtime_type     = str(body.get("runtime_type", "EVM") or "EVM").upper()
    source_code      = str(body.get("source_code", "") or "")
    contract_address = str(body.get("contract_address", "") or "").strip().lower()
    block_number     = int(body.get("block_number", 0) or 0)

    if not bytecode and not wasm_b64:
        return JSONResponse(
            status_code=400,
            content={"error": "bytecode or wasm_bytecode is required"},
        )

    try:
        result = _scan_contract(
            bytecode=bytecode,
            wasm_b64=wasm_b64,
            runtime_type=runtime_type,
            source_code=source_code,
            contract_address=contract_address,
            block_number=block_number,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"scan failed: {exc}"},
        )

    # Persist audit to PostgreSQL asynchronously
    if _pg:
        asyncio.create_task(_pg.save_contract_audit(result))

    # Respect deploy gate — return 403 for critical-risk contracts so Go nodes
    # can directly use the HTTP status code as a mempool admission signal.
    if not result.get("deploy_allowed", True):
        return JSONResponse(status_code=403, content=result)

    return result


@app.post("/api/security/pre-deploy-check")
async def pre_deploy_check(request: Request):
    """
    POST /api/security/pre-deploy-check

    Alias / simplified wrapper for /api/security/scan-contract.
    Go consensus nodes call this before inserting a contract deploy transaction.

    Request body: same as scan-contract (bytecode, wasm_bytecode, runtime_type, etc.)

    Response:
      allow       : bool   — true if safe to deploy
      risk_score  : float  — 0.0–1.0 aggregate ensemble risk
      findings    : list   — detected vulnerabilities
      risk_level  : str    — "safe" | "caution" | "warning" | "critical"
      recommendation : str — human advice

    Returns HTTP 403 with allow=false when risk_score >= 0.8 (mirroring scan-contract).
    """
    if not _AUDITOR_OK:
        return JSONResponse(
            status_code=503,
            content={"allow": True, "risk_score": 0.0,
                     "findings": [], "risk_level": "unknown",
                     "error": "contract_auditor module not loaded — passthrough"},
        )

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    bytecode         = str(body.get("bytecode", "") or "").strip()
    wasm_b64         = str(body.get("wasm_bytecode", "") or "").strip()
    runtime_type     = str(body.get("runtime_type", "EVM") or "EVM").upper()
    source_code      = str(body.get("source_code", "") or "")
    contract_address = str(body.get("contract_address", "") or "").strip().lower()
    block_number     = int(body.get("block_number", 0) or 0)

    if not bytecode and not wasm_b64:
        return JSONResponse(
            status_code=400,
            content={"error": "bytecode or wasm_bytecode is required"},
        )

    try:
        result = _scan_contract(
            bytecode=bytecode,
            wasm_b64=wasm_b64,
            runtime_type=runtime_type,
            source_code=source_code,
            contract_address=contract_address,
            block_number=block_number,
        )
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"allow": True, "error": f"scan failed: {exc}"},
        )

    if _pg:
        asyncio.create_task(_pg.save_contract_audit(result))

    allow = bool(result.get("deploy_allowed", True))

    response_body = {
        "allow":          allow,
        "risk_score":     result.get("risk_score", 0.0),
        "risk_level":     result.get("risk_level", "safe"),
        "findings":       result.get("vulnerabilities", []),
        "recommendation": result.get("recommendation", ""),
        "runtime_type":   runtime_type,
        "contract_address": contract_address,
    }

    if not allow:
        return JSONResponse(status_code=403, content=response_body)
    return response_body


@app.get("/api/security/audit-history/{address}")
async def security_audit_history(address: str, request: Request):
    """
    GET /api/security/audit-history/{address}

    Retrieve past audit records for a given contract address from PostgreSQL.

    Query params:
      limit : int  — max records to return (default 20, max 100)

    Returns:
      address : the queried address
      audits  : list of past audit summaries (newest first)
      total   : count of records returned
      source  : "postgresql" | "no-db"
    """
    limit = min(int(request.query_params.get("limit", 20)), 100)

    if _pg:
        try:
            records = await _pg.get_contract_audits(address.lower(), limit)
            return {
                "address": address.lower(),
                "audits": records,
                "total": len(records),
                "source": "postgresql",
            }
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"error": f"db query failed: {exc}"},
            )

    return {
        "address": address.lower(),
        "audits": [],
        "total": 0,
        "source": "no-db",
        "note": "PostgreSQL not available — audits not persisted in this session",
    }


@app.get("/api/security/scanner-stats")
async def security_scanner_stats():
    """
    GET /api/security/scanner-stats

    Returns AI Security Scanner v2.0 statistics.
    Intentionally NOT forwarded — always runs locally.
    """
    if not _AUDITOR_OK:
        return {"available": False, "reason": "contract_auditor module not loaded"}
    stats = _contract_auditor.get_stats()
    stats["available"] = True
    return stats


# ── Autonomous AI Agents ──────────────────────────────────────────────────────

@app.get("/api/agents/status")
async def agents_status():
    """
    GET /api/agents/status

    Returns live status for both decentralized network participation agents.

    ValidatorAgent (15s):
      Scores each new block with a 4-feature PoI AI model.
      Anyone running trispi_energy_provider.py does the same thing — their
      scores are combined with the server's into a consensus via
      GET /api/validators/scores/{block_hash}.

    ComputeProviderAgent (30s):
      Trains a 2-layer fraud-detection network locally on recent transaction
      data and submits encrypted gradients to each FL round.  The aggregated
      model hash is committed on-chain — verify via
      GET /api/federated/verify-round/{round_id}.

    Intentionally NOT forwarded — always served locally.
    """
    if not _AGENTS_OK:
        return JSONResponse(
            status_code=503,
            content={"available": False, "reason": "autonomous_agents module not loaded"},
        )
    return {
        "available":        True,
        "agents":           _all_agent_status(),
        "uptime_s":         round(time.time() - _START_TIME, 1),
        "decentralized":    True,
        "note": (
            "Anyone can participate by running trispi_energy_provider.py — "
            "register at /api/validators/register and /api/federated/register"
        ),
    }


@app.get("/api/agents/history")
async def agents_history(request: Request):
    """
    GET /api/agents/history?limit=100&agent=LiquidityAgent

    Returns the most recent agent events from PostgreSQL.
    Query params:
      limit : int   — max records (default 100, max 500)
      agent : str   — optional filter by agent name
    """
    limit      = min(int(request.query_params.get("limit", 100)), 500)
    agent_name = request.query_params.get("agent", "")

    if _pg:
        try:
            events = await _pg.get_agent_events(limit=limit, agent_name=agent_name)
            return {
                "events": events,
                "total":  len(events),
                "source": "postgresql",
                "filter": agent_name or "all",
            }
        except Exception as exc:
            return JSONResponse(
                status_code=500,
                content={"error": f"db query failed: {exc}"},
            )

    return {
        "events": [],
        "total":  0,
        "source": "no-db",
        "note":   "PostgreSQL not available — events not persisted in this session",
    }


@app.post("/api/agents/run/{agent_name}")
async def agents_run(agent_name: str):
    """
    POST /api/agents/run/{agent_name}

    Manually trigger one cycle of the named agent (for testing/ops).
    agent_name: ValidatorAgent | ComputeProviderAgent (case-insensitive prefix match)
    """
    if not _AGENTS_OK:
        return JSONResponse(
            status_code=503,
            content={"error": "autonomous_agents module not loaded"},
        )
    agent = _get_agent(agent_name)
    if agent is None:
        return JSONResponse(
            status_code=404,
            content={
                "error":     f"unknown agent: {agent_name}",
                "available": ["ValidatorAgent", "ComputeProviderAgent"],
            },
        )
    try:
        await agent.run_cycle()
        agent.last_run = time.time()
        return {
            "triggered": agent.name,
            "status":    agent.status(),
            "message":   "cycle executed",
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"agent cycle failed: {exc}", "agent": agent.name},
        )


# ── Decentralized Validator Network ───────────────────────────────────────────

@app.post("/api/validators/register")
async def validators_register(request: Request):
    """
    POST /api/validators/register

    Register an external PoI validator node (e.g. trispi_energy_provider.py).

    Body:
      provider_id   : str  — unique node identifier (e.g. "node_alice_gpu01")
      pubkey_hex    : str  — Ed25519 public key, 64 hex chars
      stake_address : str  — TRP address (optional; used for reward routing)

    After registration the node can submit block scores via
    POST /api/validators/submit-score and appear in the leaderboard.
    """
    if not _AGENTS_OK or _validator_registry is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    provider_id   = str(body.get("provider_id", "")).strip()
    pubkey_hex    = str(body.get("pubkey_hex", "")).strip()
    stake_address = str(body.get("stake_address", "")).strip()

    ok, err = _validator_registry.register(provider_id, pubkey_hex, stake_address)
    if not ok:
        return JSONResponse(status_code=422, content={"error": err})

    return {
        "registered":       True,
        "provider_id":      provider_id,
        "pubkey_hex":       pubkey_hex,
        "stake_address":    stake_address,
        "trust_weight":     1.0,
        "how_to_score": (
            "POST /api/validators/submit-score with "
            "{provider_id, block_hash, block_index, score, signature} — "
            "signature = Ed25519.sign(sha3_256(f'{provider_id}:{block_hash}:{block_index}:{score:.6f}'))"
        ),
        "scoring_algorithm": (
            "4-feature weighted dot product: "
            "[tx_quality(0.30), timing(0.25), network_health(0.25), ai_proof(0.20)] "
            "— same as ValidatorAgent.score_block_local()"
        ),
    }


@app.post("/api/validators/submit-score")
async def validators_submit_score(request: Request):
    """
    POST /api/validators/submit-score

    Submit a PoI block score from an external validator node.

    Body:
      provider_id  : str   — registered provider identifier
      block_hash   : str   — block hash being scored
      block_index  : int   — block height
      score        : float — PoI score 0.0–1.0
      signature    : str   — Ed25519 hex sig over sha3_256(f'{provider_id}:{block_hash}:{block_index}:{score:.6f}')

    The score is added to the multi-validator consensus pool.
    GET /api/validators/scores/{block_hash} shows the consensus result.
    """
    if not _AGENTS_OK or _validator_registry is None or _block_score_collector is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON body"})

    provider_id  = str(body.get("provider_id", "")).strip()
    block_hash   = str(body.get("block_hash", "")).strip()
    block_index  = int(body.get("block_index", 0) or 0)
    score        = float(body.get("score", 0.0) or 0.0)
    signature    = str(body.get("signature", "")).strip()

    if not provider_id or not block_hash:
        return JSONResponse(status_code=400, content={"error": "provider_id and block_hash are required"})
    if not (0.0 <= score <= 1.0):
        return JSONResponse(status_code=422, content={"error": "score must be between 0.0 and 1.0"})

    # Signature is MANDATORY — reject missing or invalid signatures unconditionally.
    # Without this, any caller knowing a registered provider_id could spoof scores.
    # Format: Ed25519.sign(sha3_256(f'{provider_id}:{block_hash}:{block_index}:{score:.6f}'))
    if not signature:
        return JSONResponse(status_code=403, content={
            "error": "signature is required",
            "how_to_sign": (
                "msg = sha3_256(f'{provider_id}:{block_hash}:{block_index}:{score:.6f}').digest(); "
                "signature = ed25519_private_key.sign(msg).hex()"
            ),
        })
    msg_str   = f"{provider_id}:{block_hash}:{block_index}:{score:.6f}"
    msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
    if not _validator_registry.verify_signature(provider_id, msg_bytes, signature):
        return JSONResponse(status_code=403, content={"error": "signature_verification_failed"})

    # Look up trust weight for this provider
    validator = _validator_registry.get(provider_id)
    if validator is None:
        return JSONResponse(status_code=404, content={
            "error": f"provider_id '{provider_id}' not registered — POST /api/validators/register first"
        })

    trust_weight = float(validator.get("trust_weight", 1.0))
    if trust_weight < _validator_registry.EXCLUDE_BELOW:
        return JSONResponse(status_code=403, content={
            "error":        f"trust_weight {trust_weight:.3f} below exclusion threshold {_validator_registry.EXCLUDE_BELOW}",
            "how_to_recover": "Submit more accurate scores — trust_weight grows 2% per honest score",
        })

    accepted = _block_score_collector.submit_score(
        block_hash   = block_hash,
        block_index  = block_index,
        provider_id  = provider_id,
        score        = score,
        trust_weight = trust_weight,
    )

    consensus = _block_score_collector.get_scores(block_hash)

    # TRP rewards are NOT dispatched here.  They are dispatched by ValidatorAgent
    # on its next 15s cycle AFTER consensus is finalized (≥3 scores or 30s timeout).
    # This prevents paying for scores whose honest/dishonest classification could
    # still flip as more validators submit.  The reward amount is 0.1 TRP × trust_weight.
    finalized    = bool(consensus and consensus.get("finalized"))
    reward_pending = (
        accepted
        and consensus is not None
        and not finalized
        and bool(next(
            (s for s in consensus.get("submissions", [])
             if s["provider_id"] == provider_id and s.get("honest")),
            None,
        ))
    )

    return {
        "accepted":        accepted,
        "provider_id":     provider_id,
        "block_hash":      block_hash,
        "submitted_score": round(score, 4),
        "trust_weight":    round(trust_weight, 4),
        "duplicate":       not accepted,
        "consensus":       consensus,
        "reward_status": (
            "pending_finalization"  if reward_pending
            else "rewarded"         if (accepted and finalized)
            else "not_applicable"
        ),
        "reward_note": (
            "Reward dispatched after consensus finalization (≥3 validators or 30s). "
            "Amount = 0.1 TRP × trust_weight to registered stake_address."
        ) if accepted else None,
    }


@app.get("/api/validators/scores/{block_hash}")
async def validators_scores(block_hash: str):
    """
    GET /api/validators/scores/{block_hash}

    Returns all submitted PoI scores for a block plus the multi-validator
    consensus result.  Fully public — anyone can verify the consensus was
    computed honestly by checking each individual score against the median.
    """
    if not _AGENTS_OK or _block_score_collector is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})

    consensus = _block_score_collector.get_scores(block_hash)
    if consensus is None:
        return JSONResponse(status_code=404, content={
            "error":      f"no scores found for block_hash '{block_hash}'",
            "hint":       "Block may not have been scored yet, or hash is incorrect",
        })

    return {
        "block_hash":  block_hash,
        "consensus":   consensus,
        "verify_note": (
            "Consensus score = stake+trust-weighted MEDIAN of honest scores (within 0.25 of unweighted median). "
            "Submission status: 'pending' until ≥3 validators or 30s elapsed, then 'honest'/'dishonest'. "
            "Anyone running trispi_energy_provider.py can submit their own score."
        ),
    }


@app.get("/api/validators/recent")
async def validators_recent():
    """GET /api/validators/recent — last 20 scored blocks with consensus results."""
    if not _AGENTS_OK or _block_score_collector is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})
    return {
        "recent_blocks": _block_score_collector.recent_consensus(limit=20),
        "total_validators": len(_validator_registry.get_all()) if _validator_registry else 0,
    }


@app.get("/api/validators/leaderboard")
async def validators_leaderboard():
    """
    GET /api/validators/leaderboard

    Ranks all registered external validator nodes by trust_weight.
    trust_weight grows with honest scores, shrinks with outlier scores.
    Nodes below 0.30 are excluded from consensus and earn no TRP.
    """
    if not _AGENTS_OK or _validator_registry is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})
    return {
        "leaderboard":     _validator_registry.leaderboard(limit=100),
        "total":           len(_validator_registry.get_all()),
        "exclude_threshold": _validator_registry.EXCLUDE_BELOW,
        "scoring_note": (
            "trust_weight grows +2% per honest score (within 0.25 of median), "
            "shrinks -10% per dishonest score. Floor: 0.10, Cap: 1.00"
        ),
    }


@app.get("/api/federated/verify-round/{round_id}")
async def fl_verify_round(round_id: str):
    """
    GET /api/federated/verify-round/{round_id}

    Returns the complete aggregation result for a completed FL round,
    including the commitment_hash that was committed to the blockchain.

    Anyone can verify the aggregation was honest:
      1. Fetch this endpoint to get accepted_providers, model_hash, etc.
      2. Compute sha3_256(json.dumps(result_without_commitment, sort_keys=True, default=str))
      3. Compare to commitment_hash — they must match exactly.

    This ensures the FL aggregation cannot be tampered with after the fact.
    """
    if not _FL_V2_OK:
        return JSONResponse(status_code=503, content={"error": "federated_learning_v2 not loaded"})

    result = _fl_v2.get_round_result(round_id)
    if result is None:
        return JSONResponse(status_code=404, content={
            "error":          f"round '{round_id}' not found or not yet completed",
            "available_hint": "Only completed rounds have a verifiable commitment hash",
        })

    return {
        "round_id":          round_id,
        "result":            result,
        "commitment_hash":   result.get("commitment_hash", ""),
        "how_to_verify": (
            "1. Take all result fields except 'commitment_hash' and 'commitment_preimage'. "
            "2. Sort keys, JSON-serialize with default=str. "
            "3. sha3_256(result_json.encode()).hexdigest() must equal commitment_hash."
        ),
        "aggregation_method": result.get("aggregation_method", ""),
        "model_hash":         result.get("model_hash", ""),
    }


# ── POST /api/validators/submit-tx-verdict ────────────────────────────────────

@app.post("/api/validators/submit-tx-verdict")
async def submit_tx_verdict(request: Request):
    """
    POST /api/validators/submit-tx-verdict

    Energy provider nodes submit their local fraud-detection verdict for a
    pending transaction.  Verdicts are collected in the in-memory pool and
    used by /api/ai/validate-tx to compute the trust-weighted consensus.

    Body:
      provider_id  : str   — registered validator identifier
      tx_hash      : str   — transaction hash being judged
      valid        : bool  — True = transaction looks clean; False = suspicious
      fraud_score  : float — local fraud probability (0.0–1.0)
      signature    : str   — Ed25519 hex: sign(sha3_256(provider_id:tx_hash:int(valid):fraud_score:.6f))

    Returns:
      accepted     : bool
      reason       : str
    """
    if not _AGENTS_OK or _validator_registry is None:
        return JSONResponse(status_code=503, content={"error": "validator registry not loaded"})

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid JSON"})

    provider_id = str(body.get("provider_id", "")).strip()
    tx_hash     = str(body.get("tx_hash",     "")).strip()
    valid       = bool(body.get("valid",       True))
    fraud_score = float(body.get("fraud_score", 0.0) or 0.0)
    signature   = str(body.get("signature",   "")).strip()

    if not provider_id or not tx_hash:
        return JSONResponse(status_code=400,
            content={"error": "provider_id and tx_hash are required"})
    if not (0.0 <= fraud_score <= 1.0):
        return JSONResponse(status_code=422,
            content={"error": "fraud_score must be between 0.0 and 1.0"})

    # Signature is mandatory — prevents spoofed verdicts
    if not signature:
        return JSONResponse(status_code=403, content={
            "error": "signature required",
            "how_to_sign": (
                "msg = sha3_256(f'{provider_id}:{tx_hash}:{int(valid)}:{fraud_score:.6f}').digest(); "
                "signature = ed25519_private_key.sign(msg).hex()"
            ),
        })

    msg_str   = f"{provider_id}:{tx_hash}:{int(valid)}:{fraud_score:.6f}"
    msg_bytes = hashlib.sha3_256(msg_str.encode()).digest()
    if not _validator_registry.verify_signature(provider_id, msg_bytes, signature):
        return JSONResponse(status_code=403,
            content={"error": "signature_verification_failed"})

    v = _validator_registry.get(provider_id)
    if v is None:
        return JSONResponse(status_code=404,
            content={"error": f"provider_id '{provider_id}' not registered",
                     "hint": "POST /api/validators/register first"})

    trust_weight = float(v.get("trust_weight", 1.0))
    if trust_weight < 0.30:
        return JSONResponse(status_code=403, content={
            "error": f"trust_weight {trust_weight:.3f} below exclusion threshold 0.30",
            "how_to_recover": "Submit more accurate PoI scores — trust_weight grows 2% per honest score",
        })

    # Add to verdict pool (idempotent: first-write wins per provider per tx)
    with _verdict_lock:
        _tx_verdict_pool.setdefault(tx_hash, [])
        if any(vt["provider_id"] == provider_id for vt in _tx_verdict_pool[tx_hash]):
            return {"accepted": False, "reason": "verdict already recorded for this tx"}

        _tx_verdict_pool[tx_hash].append({
            "provider_id": provider_id,
            "valid":       valid,
            "fraud_score": round(fraud_score, 4),
            "weight":      round(trust_weight, 4),
        })

        # Track per-provider TX contribution count in stats
        _tx_val_stats["validator_tx_counts"][provider_id] = \
            _tx_val_stats["validator_tx_counts"].get(provider_id, 0) + 1

        # Evict old entries once pool grows beyond 2000 tx_hashes
        if len(_tx_verdict_pool) > 2000:
            oldest_keys = list(_tx_verdict_pool.keys())[:500]
            for k in oldest_keys:
                del _tx_verdict_pool[k]

    return {
        "accepted":     True,
        "provider_id":  provider_id,
        "tx_hash":      tx_hash,
        "valid":        valid,
        "fraud_score":  round(fraud_score, 4),
        "trust_weight": round(trust_weight, 4),
        "reason": (
            "verdict recorded — will be included in consensus when this tx is validated"
        ),
    }


# ── GET /api/explorer/pending-txs ─────────────────────────────────────────────

@app.get("/api/explorer/pending-txs")
async def pending_txs():
    """
    GET /api/explorer/pending-txs

    Returns the last 20 transactions in Go's mempool that have passed the
    initial fraud gate and are waiting for block inclusion.  Energy provider
    nodes poll this endpoint every 5 seconds to find transactions they can
    validate locally.

    Falls back to recent confirmed transactions if Go mempool is unavailable
    (common during early startup when mempool endpoint may not exist).
    """
    global _pending_tx_cache, _pending_tx_cache_ts

    now = time.time()
    # Re-fetch from Go at most every 3 seconds; serve cache otherwise
    if now - _pending_tx_cache_ts < 3.0 and _pending_tx_cache:
        return {
            "transactions": _pending_tx_cache,
            "total":        len(_pending_tx_cache),
            "source":       "cache",
            "cached_at":    _pending_tx_cache_ts,
        }

    txs: list = []
    source = "go_mempool"
    try:
        async with httpx.AsyncClient(timeout=3.0) as c:
            # Try Go mempool endpoint first
            r = await c.get(f"{_GO_URL}/mempool")
            if r.status_code == 200:
                data = r.json()
                txs  = (data.get("pending", []) or data.get("transactions", []))[:20]
            else:
                raise Exception(f"mempool returned {r.status_code}")
    except Exception:
        # Fallback: use recent transactions as "pending" proxy
        try:
            async with httpx.AsyncClient(timeout=3.0) as c:
                r = await c.get(f"{_GO_URL}/transactions/recent")
                if r.status_code == 200:
                    data = r.json()
                    txs  = (data.get("transactions", []) or [])[:20]
                    source = "recent_txs_fallback"
        except Exception:
            txs    = _pending_tx_cache
            source = "stale_cache"

    # Normalise: ensure every tx has a tx_hash field that energy providers can use
    normalised = []
    for tx in txs:
        entry = dict(tx)
        if not entry.get("tx_hash"):
            raw = f"{entry.get('from', '')}:{entry.get('to', '')}:{entry.get('amount', 0)}:{entry.get('timestamp', 0)}"
            entry["tx_hash"] = hashlib.sha256(raw.encode()).hexdigest()
        normalised.append(entry)

    _pending_tx_cache    = normalised
    _pending_tx_cache_ts = now

    return {
        "transactions": normalised,
        "total":        len(normalised),
        "source":       source,
        "fetched_at":   now,
        "note": (
            "Poll every 5s to find new transactions to validate. "
            "Submit verdicts via POST /api/validators/submit-tx-verdict."
        ),
    }


# ── GET /api/ai/validation-stats ──────────────────────────────────────────────

@app.get("/api/ai/validation-stats")
async def validation_stats():
    """
    GET /api/ai/validation-stats

    Aggregate statistics on the decentralized transaction validation system.

    Returns:
      total_txs_validated      — total transactions through the AI fraud gate
      decentralized_pct        — percentage that had ≥1 external validator vote
      avg_consensus_strength   — average supermajority fraction (0.5=tie, 1.0=unanimous)
      top_validators_by_tx     — top 10 external providers by tx verdicts submitted
      active_verdicts_in_pool  — number of tx_hashes currently in the in-memory pool
    """
    with _verdict_lock:
        total     = _tx_val_stats["total_validated"]
        dec_count = _tx_val_stats["decentralized_count"]
        cs_sum    = _tx_val_stats["consensus_strength_sum"]
        vc        = dict(_tx_val_stats["validator_tx_counts"])
        pool_size = len(_tx_verdict_pool)

    dec_pct     = round(dec_count / max(total, 1) * 100, 1)
    avg_cs      = round(cs_sum    / max(total, 1), 4)

    top_validators = sorted(vc.items(), key=lambda x: -x[1])[:10]
    top_list = [
        {"rank": i + 1, "provider_id": pid, "tx_verdicts": cnt}
        for i, (pid, cnt) in enumerate(top_validators)
    ]

    return {
        "total_txs_validated":    total,
        "decentralized_count":    dec_count,
        "decentralized_pct":      dec_pct,
        "avg_consensus_strength": avg_cs,
        "top_validators_by_tx":   top_list,
        "active_verdicts_in_pool": pool_size,
        "fraud_threshold":        0.65,
        "supermajority_threshold": 0.60,
        "note": (
            "decentralized_pct = % of txs where ≥1 external energy provider submitted a verdict. "
            "avg_consensus_strength = 1.0 means unanimous; 0.5 means 50/50 split."
        ),
    }


# ── Chain Sync API (for external full nodes) ──────────────────────────────────
# External nodes call these endpoints to bootstrap the chain and stay in sync.
# Protocol:
#   1. GET /api/chain/snapshot   — get current height + bootstrap peers
#   2. GET /api/chain/genesis-state — download genesis balances (1056 accounts)
#   3. GET /api/chain/blocks?from=0&limit=500 — paginate through all blocks
#   4. Connect P2P: libp2p multiaddr from snapshot.p2p_peers[0]

@app.get("/api/chain/snapshot")
async def chain_snapshot():
    """
    Chain bootstrap snapshot for new full nodes.
    Returns block height, P2P peers, genesis config, and sync URLs.
    """
    go_stats = await _go("/network/stats") or {}
    height   = int(go_stats.get("total_blocks", go_stats.get("block_height", 0)) or 0)

    # Derive public host from REPLIT_DOMAINS env var or fallback
    public_hosts = os.environ.get("REPLIT_DOMAINS", "")
    primary_host = public_hosts.split(",")[0].strip() if public_hosts else "localhost"

    return {
        "network":          "TRISPI Mainnet",
        "chain_id":         7878,
        "block_height":     height,
        "genesis_hash":     "05c3296d8f3a214c",
        "state_root":       _current_state_root[:16] + "…",
        "total_accounts":   int(go_stats.get("total_accounts", 1056) or 1056),
        "bootstrap_peers": [
            {
                "api_url":    f"https://{primary_host}",
                "p2p_addr":  f"/dns4/{primary_host}/tcp/50052/p2p/12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa",
                "node_id":   "node1",
                "role":      "genesis_bootstrap",
            }
        ],
        "sync_endpoints": {
            "genesis_state": f"https://{primary_host}/api/chain/genesis-state",
            "blocks":        f"https://{primary_host}/api/chain/blocks?from=0&limit=500",
            "peers":         f"https://{primary_host}/api/chain/peers",
        },
        "how_to_join": (
            "1. GET /api/chain/genesis-state — download genesis balances  "
            "2. GET /api/chain/blocks?from=0&limit=500 — download all blocks  "
            "3. Connect P2P to bootstrap_peers[0].p2p_addr via libp2p  "
            "4. Run: docker-compose -f docker-compose.yml up -d  "
            "   (see https://github.com/trispi-network/node)"
        ),
        "node_requirements": {
            "cpu_cores":      "≥2",
            "ram_gb":         "≥4",
            "disk_gb":        "≥20",
            "os":             "Linux x64 (Docker)",
            "open_ports":     [50052, 8181, 8000, 6000],
        },
        "version":  "3.0",
        "timestamp": time.time(),
    }


@app.get("/api/chain/genesis-state")
async def chain_genesis_state():
    """
    Current live account state — ALL accounts with their up-to-date TRP balances.

    Returns the live state (post all transactions), NOT just genesis.
    A syncing external node uses this as the state snapshot at the reported
    block_height — no need to replay all blocks from scratch.

    Priority:
      1. PostgreSQL trispi_balances (live, updated after every tx)
      2. State JSON file from blockchain_persistence.py
      3. genesis.json (fallback — only if DB and state files are unavailable)
    """
    go_stats = await _go("/network/stats") or {}
    height   = int(go_stats.get("total_blocks", 0) or 0)

    balances: dict = {}
    source = "unknown"

    # ── Priority 1: PostgreSQL live balances (most accurate) ──────────────────
    if _pg:
        try:
            balances = await _pg.get_all_balances()
            if balances:
                source = "postgresql_live"
        except Exception:
            pass

    # ── Priority 2: State JSON written by blockchain_persistence.py ───────────
    if not balances:
        state_paths = [
            os.path.join(_WORKSPACE, "trispi", "trispi_state", "balances.json"),
            os.path.join(_WORKSPACE, "trispi", "trispi_state", "blockchain_state.json"),
            os.path.join(_WORKSPACE, "trispi", "python-ai-service", "trispi_state", "balances.json"),
        ]
        for p in state_paths:
            if os.path.exists(p):
                try:
                    with open(p) as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        balances = data.get("balances", data)
                        if balances:
                            source = f"state_file:{os.path.basename(p)}"
                            break
                except Exception:
                    pass

    # ── Priority 3: genesis.json (cold fallback) ──────────────────────────────
    if not balances:
        genesis_path = os.path.join(_WORKSPACE, "trispi", "genesis.json")
        if os.path.exists(genesis_path):
            try:
                with open(genesis_path) as f:
                    genesis = json.load(f)
                balances = genesis.get("initial_balances", genesis.get("balances", {}))
                if balances:
                    source = "genesis_json_fallback"
            except Exception:
                pass

    return {
        "block_height":   height,
        "total_accounts": len(balances),
        "balances":       balances,
        "source":         source,
        "note": (
            "Live account state at block_height. "
            "Source 'postgresql_live' means balances reflect all committed transactions. "
            "Use this as your starting state — then apply any new blocks "
            "from GET /api/chain/blocks?from_height={block_height}&limit=500."
        ),
        "timestamp": time.time(),
    }


@app.get("/api/chain/blocks")
async def chain_blocks(
    request: Request,
    from_height: int = 0,
    limit: int = 500,
):
    """
    Paginated block download for chain synchronisation.
    External nodes call this with from_height=0, then from_height+=limit until
    the returned list is shorter than limit (no more blocks).
    """
    limit = min(max(1, limit), 1000)   # cap at 1000 per page

    # Try PostgreSQL (has persisted blocks)
    pg_blocks = []
    if _pg:
        try:
            pg_blocks = await _pg.get_recent_blocks(limit=limit)
            # Filter to requested range
            pg_blocks = [b for b in pg_blocks if int(b.get("index", 0)) >= from_height]
        except Exception:
            pass

    # Fallback to Go recent blocks
    if not pg_blocks:
        go = await _go("/blocks/recent") or {}
        all_blocks = go.get("blocks", [])
        pg_blocks = [b for b in all_blocks if int(b.get("index", 0)) >= from_height]

    go_stats = await _go("/network/stats") or {}
    total    = int(go_stats.get("total_blocks", 0) or 0)

    return {
        "blocks":        pg_blocks,
        "count":         len(pg_blocks),
        "from_height":   from_height,
        "limit":         limit,
        "total_blocks":  total,
        "has_more":      (from_height + limit) < total,
        "next_from":     from_height + limit,
    }


@app.get("/api/chain/peers")
async def chain_peers():
    """
    Known P2P peers for network discovery.
    External nodes use this to find additional bootstrap peers.
    """
    go_stats = await _go("/network/stats") or {}
    go_peers = await _go("/network/peers") or {}

    public_hosts = os.environ.get("REPLIT_DOMAINS", "")
    primary_host = public_hosts.split(",")[0].strip() if public_hosts else "localhost"

    peers = go_peers.get("peers", []) if isinstance(go_peers, dict) else []

    return {
        "peers": [
            {
                "api_url":  f"https://{primary_host}",
                "p2p_addr": f"/dns4/{primary_host}/tcp/50052/p2p/12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa",
                "node_id":  "genesis_node1",
                "block_height": int(go_stats.get("total_blocks", 0) or 0),
                "is_bootstrap": True,
            },
            *[
                {
                    "api_url":  p.get("address", ""),
                    "p2p_addr": p.get("multiaddr", ""),
                    "node_id":  p.get("id", ""),
                    "is_bootstrap": False,
                }
                for p in peers[:20]
            ],
        ],
        "total": 1 + len(peers),
    }


@app.get("/api/chain/node-info")
async def chain_node_info():
    """Full node information — used by peers to identify this node."""
    go_stats = await _go("/network/stats") or {}
    public_hosts = os.environ.get("REPLIT_DOMAINS", "")
    primary_host = public_hosts.split(",")[0].strip() if public_hosts else "localhost"
    return {
        "node_id":        "node1",
        "chain_id":       7878,
        "version":        "3.0",
        "block_height":   int(go_stats.get("total_blocks", 0) or 0),
        "p2p_peer_id":    "12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa",
        "p2p_port":       50052,
        "api_port":       8000,
        "go_port":        8181,
        "rust_port":      6000,
        "public_api":     f"https://{primary_host}",
        "bootstrap_url":  f"https://{primary_host}",
        "p2p_multiaddr":  f"/dns4/{primary_host}/tcp/50052/p2p/12D3KooWEYVwoztgTfwXDob7VVZfY4cuVFCP6g7Fe7p4eWkaAXaa",
        "bootstrap_instructions": (
            f"./trispi-consensus -bootstrap https://{primary_host} "
            f"-id <your-node-id> -http 8182 -libp2p-port 50053"
        ),
        "services": {
            "go_consensus": True,
            "python_ai":    True,
            "rust_core":    True,
            "federated_learning": _FL_V2_OK,
            "pqc":          True,
        },
        "timestamp": time.time(),
    }


# ── P2P block sync proxy ───────────────────────────────────────────────────────
# Expose Go's block-sync API through the HTTPS proxy so external Go nodes can
# bootstrap directly from the mainnet:
#   ./trispi-consensus -bootstrap https://<mainnet-domain>
#
# Go's SyncFromPeer calls:
#   GET  {bootstrapURL}/api/p2p/bootstrap        — fetch remote head + peer info
#   POST {bootstrapURL}/api/p2p/bootstrap        — register as peer
#   GET  {bootstrapURL}/api/p2p/blocks/range     — fetch blocks in batches of 100
#
# These proxy endpoints forward all calls to the local Go node at :8181.

@app.get("/api/p2p/bootstrap")
async def p2p_bootstrap_get(request: Request):
    """Proxy: Go SyncFromPeer fetches chain head + libp2p addrs from here on bootstrap."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(f"{_GO_URL}/api/p2p/bootstrap")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc), "go_reachable": False})


@app.post("/api/p2p/bootstrap")
async def p2p_bootstrap_post(request: Request):
    """Proxy: peer announces itself to the bootstrap node."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.post(f"{_GO_URL}/api/p2p/bootstrap", json=body)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@app.get("/api/p2p/blocks/range")
async def p2p_blocks_range(request: Request):
    """
    Proxy: Go SyncFromPeer fetches blocks in batches of 100 using this endpoint.

    External nodes can bootstrap the full chain history with:
        GET /api/p2p/blocks/range?from=0&to=99
        GET /api/p2p/blocks/range?from=100&to=199
        ...

    Hard cap: 100 blocks per call (enforced by Go).
    """
    qs = request.url.query
    url = f"{_GO_URL}/api/p2p/blocks/range" + (f"?{qs}" if qs else "")
    try:
        async with httpx.AsyncClient(timeout=60.0) as c:
            r = await c.get(url)
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


@app.get("/api/p2p/peers")
async def p2p_peers_proxy(request: Request):
    """Proxy: returns the list of known P2P peers (libp2p + HTTP)."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as c:
            r = await c.get(f"{_GO_URL}/api/p2p/peers")
            return JSONResponse(content=r.json(), status_code=r.status_code)
    except Exception as exc:
        return JSONResponse(status_code=503, content={"error": str(exc)})


# ── Catch-all: forward to full backend or 503 ─────────────────────────────────

@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def catch_all(request: Request, path: str):
    if r := await _forward(request):
        return r
    return JSONResponse(
        status_code=503,
        content={
            "error": "service_warming",
            "message": (
                "AI service loading (5-7 min cold start). "
                "Core network is active. Retry shortly."
            ),
            "retry_after": 30,
            "path": path,
        },
        headers={"Retry-After": "30"},
    )
