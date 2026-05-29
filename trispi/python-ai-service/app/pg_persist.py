"""
TRISPI PostgreSQL Persistence
==============================
Saves blocks, transactions and balances to Replit's managed PostgreSQL so data
survives container restarts between deployments.

Usage (from main_fast.py):
    from pg_persist import PGPersist
    pg = PGPersist()
    await pg.init()                          # create tables if missing, load state
    await pg.save_block(block_dict)
    await pg.update_balance(addr, amount)
    state_root = await pg.load_state_root()
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import Any

logger = logging.getLogger("pg_persist")

try:
    import asyncpg
    _ASYNCPG = True
except ImportError:
    _ASYNCPG = False
    logger.warning("asyncpg not installed — PostgreSQL persistence disabled")


class PGPersist:
    def __init__(self) -> None:
        self._pool: Any = None
        self._enabled = _ASYNCPG and bool(os.environ.get("DATABASE_URL"))
        self._dsn = os.environ.get("DATABASE_URL", "")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def init(self) -> bool:
        if not self._enabled:
            logger.info("[pg] PostgreSQL disabled (no DATABASE_URL or asyncpg)")
            return False
        try:
            self._pool = await asyncpg.create_pool(
                dsn=self._dsn, min_size=1, max_size=5, command_timeout=10
            )
            await self._ensure_schema()
            logger.info("[pg] Connected to PostgreSQL ✓")
            return True
        except Exception as e:
            logger.error(f"[pg] Connection failed: {e}")
            self._enabled = False
            return False

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()

    # ── Schema ─────────────────────────────────────────────────────────────────

    async def _ensure_schema(self) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trispi_blocks (
                    id          BIGSERIAL PRIMARY KEY,
                    block_index BIGINT UNIQUE NOT NULL,
                    hash        TEXT NOT NULL,
                    prev_hash   TEXT NOT NULL,
                    state_root  TEXT NOT NULL DEFAULT '',
                    merkle_root TEXT NOT NULL DEFAULT '',
                    proposer    TEXT NOT NULL DEFAULT '',
                    gas_used    BIGINT NOT NULL DEFAULT 0,
                    gas_limit   BIGINT NOT NULL DEFAULT 10000000,
                    tx_count    INT NOT NULL DEFAULT 0,
                    raw_json    JSONB,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS trispi_transactions (
                    id          BIGSERIAL PRIMARY KEY,
                    tx_hash     TEXT UNIQUE NOT NULL,
                    block_index BIGINT,
                    from_addr   TEXT NOT NULL DEFAULT '',
                    to_addr     TEXT NOT NULL DEFAULT '',
                    amount      DOUBLE PRECISION NOT NULL DEFAULT 0,
                    gas_fee     DOUBLE PRECISION NOT NULL DEFAULT 0,
                    status      TEXT NOT NULL DEFAULT 'confirmed',
                    raw_json    JSONB,
                    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS trispi_balances (
                    address     TEXT PRIMARY KEY,
                    balance     DOUBLE PRECISION NOT NULL DEFAULT 0,
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS trispi_chain_meta (
                    key         TEXT PRIMARY KEY,
                    value       TEXT NOT NULL,
                    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_blocks_index ON trispi_blocks(block_index DESC);
                CREATE INDEX IF NOT EXISTS idx_txs_block   ON trispi_transactions(block_index);
                CREATE INDEX IF NOT EXISTS idx_txs_from    ON trispi_transactions(from_addr);
                CREATE INDEX IF NOT EXISTS idx_txs_to      ON trispi_transactions(to_addr);
            """)

    # ── Blocks ─────────────────────────────────────────────────────────────────

    async def save_block(self, block: dict) -> None:
        if not self._enabled or not self._pool:
            return
        try:
            idx         = int(block.get("index") or block.get("block_index") or 0)
            bh          = str(block.get("hash") or "")
            prev        = str(block.get("prev_hash") or "")
            state_root  = str(block.get("state_root") or "")
            merkle_root = str(block.get("merkle_root") or "")
            proposer    = str(block.get("proposer") or "")
            gas_used    = int(block.get("gas_used") or 0)
            gas_limit   = int(block.get("gas_limit") or 10_000_000)
            txs         = block.get("transactions") or []
            tx_count    = len(txs)

            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_blocks
                        (block_index, hash, prev_hash, state_root, merkle_root,
                         proposer, gas_used, gas_limit, tx_count, raw_json)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                    ON CONFLICT (block_index) DO NOTHING
                """, idx, bh, prev, state_root, merkle_root,
                     proposer, gas_used, gas_limit, tx_count,
                     json.dumps(block))

                # Save transactions
                for tx in txs:
                    tx_hash = str(
                        tx.get("hash") or tx.get("tx_hash") or
                        hashlib.sha3_256(json.dumps(tx, sort_keys=True).encode()).hexdigest()
                    )
                    await conn.execute("""
                        INSERT INTO trispi_transactions
                            (tx_hash, block_index, from_addr, to_addr,
                             amount, gas_fee, status, raw_json)
                        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                        ON CONFLICT (tx_hash) DO NOTHING
                    """, tx_hash, idx,
                         str(tx.get("from") or tx.get("from_addr") or ""),
                         str(tx.get("to") or tx.get("to_addr") or ""),
                         float(tx.get("amount") or tx.get("value") or 0),
                         float(tx.get("gas_fee") or tx.get("fee") or 0),
                         "confirmed",
                         json.dumps(tx))

                # Persist latest state root as chain meta
                if state_root:
                    await conn.execute("""
                        INSERT INTO trispi_chain_meta (key, value, updated_at)
                        VALUES ('state_root', $1, NOW())
                        ON CONFLICT (key) DO UPDATE SET value=$1, updated_at=NOW()
                    """, state_root)
                await conn.execute("""
                    INSERT INTO trispi_chain_meta (key, value, updated_at)
                    VALUES ('last_block', $1, NOW())
                    ON CONFLICT (key) DO UPDATE SET value=$1, updated_at=NOW()
                """, str(idx))

        except Exception as e:
            logger.error(f"[pg] save_block failed: {e}")

    # ── Balances ───────────────────────────────────────────────────────────────

    async def update_balance(self, address: str, balance: float) -> None:
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_balances (address, balance, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (address)
                    DO UPDATE SET balance = $2, updated_at = NOW()
                """, address.lower(), balance)
        except Exception as e:
            logger.error(f"[pg] update_balance failed: {e}")

    async def get_balance(self, address: str) -> float:
        if not self._enabled or not self._pool:
            return 0.0
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT balance FROM trispi_balances WHERE address = $1",
                    address.lower()
                )
                return float(row["balance"]) if row else 0.0
        except Exception:
            return 0.0

    async def get_top_balances(self, limit: int = 20) -> list[dict]:
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT address, balance FROM trispi_balances ORDER BY balance DESC LIMIT $1",
                    limit
                )
                return [{"address": r["address"], "balance": float(r["balance"])} for r in rows]
        except Exception:
            return []

    async def get_all_balances(self) -> dict[str, float]:
        """
        Returns ALL current live account balances as {address: balance}.
        Used by chain sync endpoint so external nodes get the live state,
        not just the genesis snapshot.
        """
        if not self._enabled or not self._pool:
            return {}
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT address, balance FROM trispi_balances WHERE balance > 0 ORDER BY balance DESC"
                )
                return {r["address"]: float(r["balance"]) for r in rows}
        except Exception as e:
            logger.error(f"[pg] get_all_balances failed: {e}")
            return {}

    async def get_account_count(self) -> int:
        """Total number of accounts with non-zero balance."""
        if not self._enabled or not self._pool:
            return 0
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) as cnt FROM trispi_balances WHERE balance > 0"
                )
                return int(row["cnt"]) if row else 0
        except Exception:
            return 0

    # ── State root ─────────────────────────────────────────────────────────────

    async def load_state_root(self) -> str | None:
        if not self._enabled or not self._pool:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM trispi_chain_meta WHERE key='state_root'"
                )
                return row["value"] if row else None
        except Exception:
            return None

    async def load_last_block_index(self) -> int:
        if not self._enabled or not self._pool:
            return 0
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT value FROM trispi_chain_meta WHERE key='last_block'"
                )
                return int(row["value"]) if row else 0
        except Exception:
            return 0

    # ── Recent blocks (for explorer) ───────────────────────────────────────────

    async def get_recent_blocks(self, limit: int = 20) -> list[dict]:
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT block_index, hash, prev_hash, state_root, merkle_root,
                           proposer, gas_used, tx_count, created_at
                    FROM trispi_blocks
                    ORDER BY block_index DESC
                    LIMIT $1
                """, limit)
                return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_block_count(self) -> int:
        if not self._enabled or not self._pool:
            return 0
        try:
            async with self._pool.acquire() as conn:
                return await conn.fetchval("SELECT COUNT(*) FROM trispi_blocks")
        except Exception:
            return 0

    # ── AI Proofs ──────────────────────────────────────────────────────────────

    async def ensure_ai_proofs_table(self) -> None:
        """Create trispi_ai_proofs table if it does not exist."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trispi_ai_proofs (
                        inference_id  TEXT PRIMARY KEY,
                        model_id      TEXT NOT NULL DEFAULT '',
                        input_hash    TEXT NOT NULL DEFAULT '',
                        output_hash   TEXT NOT NULL DEFAULT '',
                        weights_hash  TEXT NOT NULL DEFAULT '',
                        proof         TEXT NOT NULL DEFAULT '',
                        signature     TEXT NOT NULL DEFAULT '',
                        pubkey        TEXT NOT NULL DEFAULT '',
                        trust_score   DOUBLE PRECISION,
                        block_hash    TEXT NOT NULL DEFAULT '',
                        timestamp_ms  BIGINT NOT NULL DEFAULT 0,
                        raw_json      JSONB,
                        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_ai_proofs_block
                        ON trispi_ai_proofs(block_hash);
                    CREATE INDEX IF NOT EXISTS idx_ai_proofs_created
                        ON trispi_ai_proofs(created_at DESC);
                """)
        except Exception as e:
            logger.error(f"[pg] ensure_ai_proofs_table failed: {e}")

    async def save_ai_proof(self, proof: dict, trust_score: float = 0.0, block_hash: str = "") -> None:
        """Persist a Verifiable AI proof to PostgreSQL."""
        if not self._enabled or not self._pool:
            return
        try:
            ts_ms = int(proof.get("timestamp_ms", 0))
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_ai_proofs
                        (inference_id, model_id, input_hash, output_hash, weights_hash,
                         proof, signature, pubkey, trust_score, block_hash, timestamp_ms, raw_json)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                    ON CONFLICT (inference_id) DO NOTHING
                """,
                    proof.get("inference_id", ""),
                    proof.get("model_id", ""),
                    proof.get("input_hash", ""),
                    proof.get("output_hash", ""),
                    proof.get("weights_hash", ""),
                    proof.get("proof", ""),
                    proof.get("signature", ""),
                    proof.get("pubkey", ""),
                    float(trust_score),
                    block_hash,
                    ts_ms,
                    json.dumps(proof),
                )
        except Exception as e:
            logger.error(f"[pg] save_ai_proof failed: {e}")

    async def get_ai_proof(self, inference_id: str) -> dict | None:
        """Retrieve a stored AI proof by inference_id."""
        if not self._enabled or not self._pool:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT raw_json FROM trispi_ai_proofs WHERE inference_id = $1",
                    inference_id,
                )
                if row and row["raw_json"]:
                    data = row["raw_json"]
                    return data if isinstance(data, dict) else json.loads(data)
                return None
        except Exception:
            return None

    async def get_recent_proofs(self, limit: int = 20) -> list[dict]:
        """Get the most recently created AI proofs."""
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT inference_id, model_id, trust_score, block_hash, timestamp_ms, created_at
                    FROM trispi_ai_proofs
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
                return [dict(r) for r in rows]
        except Exception:
            return []

    # ── Federated Learning reputation ─────────────────────────────────────────

    async def ensure_fl_reputation_table(self) -> None:
        """Create trispi_fl_reputation table if it does not exist."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trispi_fl_reputation (
                        provider_id           TEXT PRIMARY KEY,
                        rounds_participated   INT NOT NULL DEFAULT 0,
                        rounds_excluded       INT NOT NULL DEFAULT 0,
                        accuracy_contribution DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        reputation_score      DOUBLE PRECISION NOT NULL DEFAULT 1.0,
                        updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                    CREATE INDEX IF NOT EXISTS idx_fl_rep_score
                        ON trispi_fl_reputation(reputation_score DESC);
                """)
        except Exception as e:
            logger.error(f"[pg] ensure_fl_reputation_table failed: {e}")

    async def save_fl_reputation(
        self,
        provider_id: str,
        reputation_score: float,
        included: bool,
        accuracy_contribution: float = 0.0,
    ) -> None:
        """Upsert a provider's reputation after a federated learning round."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                if included:
                    await conn.execute("""
                        INSERT INTO trispi_fl_reputation
                            (provider_id, rounds_participated, rounds_excluded,
                             accuracy_contribution, reputation_score, updated_at)
                        VALUES ($1, 1, 0, $2, $3, NOW())
                        ON CONFLICT (provider_id) DO UPDATE SET
                            rounds_participated   = trispi_fl_reputation.rounds_participated + 1,
                            accuracy_contribution = trispi_fl_reputation.accuracy_contribution + $2,
                            reputation_score      = $3,
                            updated_at            = NOW()
                    """, provider_id, accuracy_contribution, reputation_score)
                else:
                    await conn.execute("""
                        INSERT INTO trispi_fl_reputation
                            (provider_id, rounds_participated, rounds_excluded,
                             accuracy_contribution, reputation_score, updated_at)
                        VALUES ($1, 1, 1, 0, $2, NOW())
                        ON CONFLICT (provider_id) DO UPDATE SET
                            rounds_participated = trispi_fl_reputation.rounds_participated + 1,
                            rounds_excluded     = trispi_fl_reputation.rounds_excluded + 1,
                            reputation_score    = $2,
                            updated_at          = NOW()
                    """, provider_id, reputation_score)
        except Exception as e:
            logger.error(f"[pg] save_fl_reputation failed: {e}")

    async def get_fl_reputation(self, provider_id: str) -> dict | None:
        """Retrieve reputation record for a single provider."""
        if not self._enabled or not self._pool:
            return None
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM trispi_fl_reputation WHERE provider_id = $1",
                    provider_id,
                )
                return dict(row) if row else None
        except Exception:
            return None

    async def get_fl_leaderboard(self, limit: int = 50) -> list[dict]:
        """Return providers ranked by reputation_score descending."""
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT provider_id, rounds_participated, rounds_excluded,
                           accuracy_contribution, reputation_score, updated_at
                    FROM trispi_fl_reputation
                    ORDER BY reputation_score DESC
                    LIMIT $1
                """, limit)
                return [dict(r) for r in rows]
        except Exception:
            return []

    async def get_provider_stake(self, address: str) -> float:
        """Convenience: look up TRP stake for a provider from trispi_balances."""
        return await self.get_balance(address)

    # ── Contract Audits ────────────────────────────────────────────────────────

    async def ensure_contract_audits_table(self) -> None:
        """Create trispi_contract_audits table if it does not exist."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                # Step 1: create the table and basic indexes (no block_number index yet,
                # since block_number may not exist on pre-existing tables)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trispi_contract_audits (
                        id               BIGSERIAL PRIMARY KEY,
                        contract_address TEXT NOT NULL DEFAULT '',
                        contract_type    TEXT NOT NULL DEFAULT 'EVM',
                        bytecode_hash    TEXT NOT NULL DEFAULT '',
                        block_number     BIGINT NOT NULL DEFAULT 0,
                        risk_score       DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        rug_pull_prob    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        liquidity_risk   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
                        risk_level       TEXT NOT NULL DEFAULT 'safe',
                        deploy_allowed   BOOLEAN NOT NULL DEFAULT TRUE,
                        vuln_count       INT NOT NULL DEFAULT 0,
                        recommendation   TEXT NOT NULL DEFAULT '',
                        raw_json         JSONB,
                        scanned_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audits_address
                        ON trispi_contract_audits(contract_address);
                    CREATE INDEX IF NOT EXISTS idx_audits_scanned
                        ON trispi_contract_audits(scanned_at DESC);
                    CREATE INDEX IF NOT EXISTS idx_audits_risk
                        ON trispi_contract_audits(risk_score DESC);
                """)
                # Step 2: migration — add block_number to tables that predate it.
                # Must run before the block_number index below.
                await conn.execute("""
                    ALTER TABLE trispi_contract_audits
                    ADD COLUMN IF NOT EXISTS block_number BIGINT NOT NULL DEFAULT 0;
                """)
                # Step 3: block_number compound index — safe now that column exists
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_audits_addr_block
                        ON trispi_contract_audits(contract_address, block_number DESC);
                """)
        except Exception as e:
            logger.error(f"[pg] ensure_contract_audits_table failed: {e}")

    async def save_contract_audit(self, audit: dict) -> None:
        """Persist a contract audit result to PostgreSQL."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_contract_audits
                        (contract_address, contract_type, bytecode_hash,
                         block_number,
                         risk_score, rug_pull_prob, liquidity_risk,
                         risk_level, deploy_allowed, vuln_count,
                         recommendation, raw_json, scanned_at)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,
                            to_timestamp($13))
                """,
                    str(audit.get("contract_address", "")),
                    str(audit.get("contract_type", "EVM")),
                    str(audit.get("bytecode_hash", "")),
                    int(audit.get("block_number", 0)),
                    float(audit.get("risk_score", 0.0)),
                    float(audit.get("rug_pull_probability", 0.0)),
                    float(audit.get("liquidity_risk", 0.0)),
                    str(audit.get("risk_level", "safe")),
                    bool(audit.get("deploy_allowed", True)),
                    int(audit.get("vulnerability_count", 0)),
                    str(audit.get("recommendation", "")),
                    json.dumps(audit),
                    float(audit.get("scanned_at", time.time())),
                )
        except Exception as e:
            logger.error(f"[pg] save_contract_audit failed: {e}")

    async def get_contract_audits(
        self, address: str = "", limit: int = 20
    ) -> list[dict]:
        """Return recent audits, optionally filtered by contract address."""
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                if address:
                    rows = await conn.fetch("""
                        SELECT contract_address, contract_type, bytecode_hash,
                               block_number,
                               risk_score, rug_pull_prob, liquidity_risk,
                               risk_level, deploy_allowed, vuln_count,
                               recommendation, scanned_at
                        FROM trispi_contract_audits
                        WHERE contract_address = $1
                        ORDER BY scanned_at DESC
                        LIMIT $2
                    """, address.lower(), limit)
                else:
                    rows = await conn.fetch("""
                        SELECT contract_address, contract_type, bytecode_hash,
                               block_number,
                               risk_score, rug_pull_prob, liquidity_risk,
                               risk_level, deploy_allowed, vuln_count,
                               recommendation, scanned_at
                        FROM trispi_contract_audits
                        ORDER BY scanned_at DESC
                        LIMIT $1
                    """, limit)
                result = []
                for r in rows:
                    row = dict(r)
                    if "scanned_at" in row and row["scanned_at"]:
                        row["scanned_at"] = row["scanned_at"].isoformat()
                    result.append(row)
                return result
        except Exception:
            return []

    # ── Agent Events ───────────────────────────────────────────────────────────

    async def ensure_agent_events_table(self) -> None:
        """Create trispi_agent_events table if it does not exist."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trispi_agent_events (
                        id          BIGSERIAL PRIMARY KEY,
                        agent_name  TEXT NOT NULL DEFAULT '',
                        event_type  TEXT NOT NULL DEFAULT '',
                        payload     JSONB,
                        created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_agent_events_agent
                        ON trispi_agent_events(agent_name);
                    CREATE INDEX IF NOT EXISTS idx_agent_events_type
                        ON trispi_agent_events(event_type);
                    CREATE INDEX IF NOT EXISTS idx_agent_events_created
                        ON trispi_agent_events(created_at DESC);
                """)
        except Exception as e:
            logger.error(f"[pg] ensure_agent_events_table failed: {e}")

    async def save_agent_event(
        self, agent_name: str, event_type: str, payload: dict
    ) -> None:
        """Persist an autonomous agent event to PostgreSQL."""
        if not self._enabled or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO trispi_agent_events
                        (agent_name, event_type, payload)
                    VALUES ($1, $2, $3)
                """, agent_name, event_type, json.dumps(payload))
        except Exception as e:
            logger.error(f"[pg] save_agent_event failed: {e}")

    async def get_agent_events(
        self, limit: int = 100, agent_name: str = ""
    ) -> list[dict]:
        """Return recent agent events, optionally filtered by agent name."""
        if not self._enabled or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                if agent_name:
                    rows = await conn.fetch("""
                        SELECT id, agent_name, event_type, payload, created_at
                        FROM trispi_agent_events
                        WHERE agent_name = $1
                        ORDER BY created_at DESC
                        LIMIT $2
                    """, agent_name, limit)
                else:
                    rows = await conn.fetch("""
                        SELECT id, agent_name, event_type, payload, created_at
                        FROM trispi_agent_events
                        ORDER BY created_at DESC
                        LIMIT $1
                    """, limit)
                result = []
                for r in rows:
                    row = dict(r)
                    if "created_at" in row and row["created_at"]:
                        row["created_at"] = row["created_at"].isoformat()
                    if "payload" in row and isinstance(row["payload"], str):
                        try:
                            row["payload"] = json.loads(row["payload"])
                        except Exception:
                            pass
                    result.append(row)
                return result
        except Exception:
            return []

    # ── Sync from Go ───────────────────────────────────────────────────────────

    async def sync_from_go(self, go_url: str = "http://127.0.0.1:8181") -> int:
        """Pull latest blocks from Go consensus node and save to PostgreSQL."""
        if not self._enabled:
            return 0
        try:
            import httpx
            last_idx = await self.load_last_block_index()
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{go_url}/blocks/recent?limit=50")
                if r.status_code != 200:
                    return 0
                data = r.json()
            blocks = data.get("blocks") or []
            saved = 0
            for block in blocks:
                idx = int(block.get("index") or 0)
                if idx > last_idx:
                    await self.save_block(block)
                    saved += 1
            if saved:
                logger.info(f"[pg] Synced {saved} new blocks from Go")
            return saved
        except Exception as e:
            logger.debug(f"[pg] sync_from_go: {e}")
            return 0
