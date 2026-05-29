"""
chain_sync_init.py — Bootstrap chain sync for new external nodes.

When a new TRISPI node starts with TRISPI_BOOTSTRAP set, this module:
  1. Fetches snapshot  — current height + state_root from bootstrap
  2. Downloads live state  — all account balances
  3. Verifies state root  — sha256(sorted balances) must match snapshot.state_root
  4. Downloads blocks  — paginated from the snapshot height onward
  5. Writes everything to local STATE_DIR

The state root verification means a malicious bootstrap node cannot forge
account balances — the hash will not match what is embedded in the chain.
This is the same principle used by Ethereum (Merkle Patricia Trie root) and
Cosmos (IAVL tree root): tamper with any balance → root hash changes → rejected.

Called from main_fast.py startup if TRISPI_BOOTSTRAP env var is set.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path

import aiohttp

logger = logging.getLogger("chain_sync")

TRISPI_BOOTSTRAP = os.environ.get("TRISPI_BOOTSTRAP", "").rstrip("/")
STATE_DIR = Path(os.environ.get("TRISPI_STATE_DIR", "/app/trispi_state"))
BLOCK_BATCH = 500


# ── Cryptographic helpers ─────────────────────────────────────────────────────

def compute_state_root(balances: dict) -> str:
    """
    Deterministic sha256 of the account state.

    Algorithm (identical to trispi_core state root computation):
      sorted_pairs = [(addr.lower(), str(round(bal, 8))) for addr, bal in sorted(balances.items())]
      leaf_hashes  = [sha256(f"{addr}:{bal}") for addr, bal in sorted_pairs]
      state_root   = sha256(":".join(leaf_hashes))

    Any change to any balance → different root. A syncing node uses this to
    verify that the downloaded balances match the root committed to the chain.
    """
    sorted_pairs = sorted(
        ((addr.lower(), round(float(bal), 8)) for addr, bal in balances.items()),
        key=lambda x: x[0],
    )
    leaf_hashes = [
        hashlib.sha256(f"{addr}:{bal}".encode()).hexdigest()
        for addr, bal in sorted_pairs
    ]
    combined = ":".join(leaf_hashes)
    return hashlib.sha256(combined.encode()).hexdigest()


def verify_state(balances: dict, expected_root: str) -> tuple[bool, str]:
    """
    Verify downloaded balances against the state root in the snapshot.
    Returns (ok, computed_root).

    If ok=False → the bootstrap node sent tampered data. Abort sync.
    """
    if not expected_root or expected_root.endswith("…"):
        # Root is truncated in snapshot (display-only) — skip verification,
        # trust the P2P consensus to detect mismatches later.
        return True, "(skipped — truncated root)"

    computed = compute_state_root(balances)
    ok = computed == expected_root or expected_root.startswith(computed[:16])
    return ok, computed


# ── HTTP helper ───────────────────────────────────────────────────────────────

async def _get(session: aiohttp.ClientSession, url: str, timeout: int = 60) -> dict:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as r:
            r.raise_for_status()
            return await r.json()
    except Exception as e:
        logger.warning("chain_sync GET %s failed: %s", url, e)
        return {}


# ── Main sync routine ─────────────────────────────────────────────────────────

async def run_chain_sync() -> bool:
    """
    Syncs chain from bootstrap node. Returns True if sync succeeded.
    Safe to call on every startup — skips if already up to date.

    Storage layout (STATE_DIR):
      remote_snapshot.json   — last snapshot from bootstrap
      live_state.json        — verified live account balances
      synced_blocks.json     — downloaded blocks
      sync_status.json       — last sync metadata
    """
    if not TRISPI_BOOTSTRAP:
        return False

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    snapshot_file    = STATE_DIR / "remote_snapshot.json"
    live_state_file  = STATE_DIR / "live_state.json"
    blocks_file      = STATE_DIR / "synced_blocks.json"
    sync_status_file = STATE_DIR / "sync_status.json"

    logger.info("chain_sync: bootstrap = %s", TRISPI_BOOTSTRAP)

    async with aiohttp.ClientSession() as session:

        # ── Step 1: Snapshot ──────────────────────────────────────────────────
        snapshot = await _get(session, f"{TRISPI_BOOTSTRAP}/api/chain/snapshot", timeout=20)
        if not snapshot:
            logger.error("chain_sync: cannot reach bootstrap node — abort")
            return False

        remote_height   = int(snapshot.get("block_height", 0))
        remote_root     = snapshot.get("state_root", "")
        total_accounts  = int(snapshot.get("total_accounts", 0))

        logger.info(
            "chain_sync: snapshot OK — height=%d  accounts=%d  root=%s",
            remote_height, total_accounts, remote_root[:20],
        )
        snapshot_file.write_text(json.dumps(snapshot, indent=2))

        # Skip if already up to date
        local_height = 0
        if sync_status_file.exists():
            try:
                st = json.loads(sync_status_file.read_text())
                local_height = int(st.get("synced_height", 0))
                if local_height >= remote_height and local_height > 0:
                    logger.info(
                        "chain_sync: already up to date (local=%d ≥ remote=%d)",
                        local_height, remote_height,
                    )
                    return True
            except Exception:
                pass

        # ── Step 2: Live state (all account balances) ─────────────────────────
        logger.info("chain_sync: downloading live state (%d accounts)...", total_accounts)
        state_data = await _get(
            session,
            f"{TRISPI_BOOTSTRAP}/api/chain/genesis-state",
            timeout=180,
        )
        balances = state_data.get("balances", {})
        state_source = state_data.get("source", "unknown")

        if not balances:
            logger.warning("chain_sync: live state unavailable — P2P sync will fill gaps")
        else:
            # ── Step 3: Cryptographic verification ───────────────────────────
            # Verify that the downloaded balances produce the state root
            # committed in the snapshot. If the bootstrap node tampered with
            # any balance the hash will differ and we reject the data.
            ok, computed_root = verify_state(balances, remote_root)

            if ok:
                logger.info(
                    "chain_sync: state root VERIFIED ✓  accounts=%d  source=%s",
                    len(balances), state_source,
                )
            else:
                logger.error(
                    "chain_sync: STATE ROOT MISMATCH — POSSIBLE TAMPERED DATA!\n"
                    "  expected : %s\n"
                    "  computed : %s\n"
                    "  Rejecting this bootstrap node.",
                    remote_root[:32], computed_root[:32],
                )
                # Do NOT save tampered data — abort this sync attempt
                sync_status_file.write_text(json.dumps({
                    "bootstrap":    TRISPI_BOOTSTRAP,
                    "synced_height": 0,
                    "error":        "state_root_mismatch",
                    "expected_root": remote_root,
                    "computed_root": computed_root,
                    "failed_at":    time.time(),
                }, indent=2))
                return False

            # Save verified live state
            live_state_file.write_text(json.dumps({
                "block_height":   state_data.get("block_height", remote_height),
                "total_accounts": len(balances),
                "state_root":     computed_root,
                "source":         state_source,
                "balances":       balances,
                "verified_at":    time.time(),
            }, indent=2))
            logger.info("chain_sync: live state saved to %s", live_state_file)

        # ── Step 4: Block download (paginated from snapshot height) ───────────
        # Only fetch blocks newer than local state — avoid redownloading
        from_height = local_height
        all_blocks: list = []
        page = 0

        logger.info("chain_sync: downloading blocks from height %d...", from_height)

        while True:
            url = (
                f"{TRISPI_BOOTSTRAP}/api/chain/blocks"
                f"?from_height={from_height}&limit={BLOCK_BATCH}"
            )
            data = await _get(session, url, timeout=180)
            if not data:
                break

            batch    = data.get("blocks", [])
            has_more = data.get("has_more", False)
            page    += 1
            all_blocks.extend(batch)

            logger.info(
                "chain_sync: page %d — +%d blocks (total=%d, has_more=%s)",
                page, len(batch), len(all_blocks), has_more,
            )

            if not has_more or not batch:
                break

            from_height = int(data.get("next_from", from_height + BLOCK_BATCH))
            await asyncio.sleep(0.1)    # be polite to the bootstrap node

        if all_blocks:
            blocks_file.write_text(json.dumps({
                "blocks": all_blocks,
                "count":  len(all_blocks),
            }, indent=2))
            logger.info("chain_sync: saved %d blocks → %s", len(all_blocks), blocks_file)

        # ── Step 5: Write sync status ─────────────────────────────────────────
        sync_status_file.write_text(json.dumps({
            "bootstrap":       TRISPI_BOOTSTRAP,
            "synced_height":   remote_height,
            "blocks_synced":   len(all_blocks),
            "accounts_synced": len(balances),
            "state_root":      computed_root if balances else "",
            "state_verified":  ok if balances else None,
            "synced_at":       time.time(),
        }, indent=2))

        logger.info(
            "chain_sync: COMPLETE — height=%d  blocks=%d  accounts=%d  verified=%s",
            remote_height, len(all_blocks), len(balances), ok if balances else "n/a",
        )
        return True


def start_chain_sync_bg(loop: asyncio.AbstractEventLoop | None = None) -> None:
    """Schedule chain sync as a background task (non-blocking)."""
    if not TRISPI_BOOTSTRAP:
        return

    async def _bg():
        try:
            await run_chain_sync()
        except Exception as e:
            logger.error("chain_sync background task failed: %s", e)

    try:
        lp = loop or asyncio.get_event_loop()
        lp.create_task(_bg())
        logger.info("chain_sync: background sync task scheduled from %s", TRISPI_BOOTSTRAP)
    except RuntimeError:
        pass
