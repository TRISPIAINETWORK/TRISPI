#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Starting TRISPI Backend Services ==="

# ── Shared secrets ──
# BLOCK_MINED_SECRET is used by Go consensus to call back into the Python service.
export BLOCK_MINED_SECRET="${BLOCK_MINED_SECRET:-trispi-internal-block-secret}"
# GOVERNANCE_SECRET gates POST /api/ai/consensus/weights.
# Must be set explicitly in the environment before starting the backend.
# When unset the endpoint stays locked (returns 503) — there is no fallback
# default to prevent accidental exposure of the governance control path.
export GOVERNANCE_SECRET="${GOVERNANCE_SECRET:-}"

# ── Kill stale processes so they don't hold ports across workflow restarts ──
pkill -9 -f 'uvicorn.*main_simplified' 2>/dev/null || true
pkill -9 -f 'trispi-consensus' 2>/dev/null || true
# NOTE: trispi_core (Rust) is managed by the separate "TRISPI Rust Core" workflow — do NOT kill it here.

# Wait for port 8181 (Go HTTP) and 8000 (Python) to drain before launching fresh processes.
for port in 8181 8000; do
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    ss -tln 2>/dev/null | grep -q ":${port} " || break
    sleep 0.5
  done
done
sleep 1

# ── [1/2] Go Consensus Node (HTTP :8181, P2P :50052) ──
echo "[1/2] Starting Go Consensus Node (HTTP :8181, P2P :50052)..."
cd go-consensus
chmod +x trispi-consensus 2>/dev/null || true

# Optional bootstrap: set TRISPI_BOOTSTRAP=https://<mainnet-node> so this node
# syncs the full chain from the mainnet on startup instead of starting from the
# local JSON snapshot.  Example:
#   TRISPI_BOOTSTRAP=https://fffgfggffff.replit.app bash start_backend.sh
#
# The mainnet node itself does NOT set TRISPI_BOOTSTRAP — it IS the bootstrap source.
BOOTSTRAP_FLAGS=""
if [ -n "${TRISPI_BOOTSTRAP:-}" ]; then
  BOOTSTRAP_FLAGS="-bootstrap $TRISPI_BOOTSTRAP"
  echo "[bootstrap] Chain will sync from: $TRISPI_BOOTSTRAP"
fi

BLOCK_MINED_SECRET="$BLOCK_MINED_SECRET" \
  TRISPI_ALLOW_FALLBACK_ROOTS=1 \
  ./trispi-consensus -id node1 -http 8181 -port 50051 -libp2p-port 50052 \
  $BOOTSTRAP_FLAGS &
GO_PID=$!
cd ..

# ── Health-gate: Go (:8181) ──
GO_STATUS="[TIMEOUT]"
for i in $(seq 1 15); do
  if curl -sf http://127.0.0.1:8181/health >/dev/null 2>&1; then
    GO_STATUS="[OK] (${i}s)"
    break
  fi
  sleep 1
done
echo "[Go] $GO_STATUS"

# ── Health-gate: Rust Core (:6000) — managed by separate workflow, just check presence ──
RUST_STATUS="[NOT RUNNING]"
for i in $(seq 1 5); do
  if curl -sf http://127.0.0.1:6000/health >/dev/null 2>&1; then
    RUST_STATUS="[OK] (${i}s)"
    break
  fi
  if bash -c "echo >/dev/tcp/127.0.0.1/6000" 2>/dev/null; then
    RUST_STATUS="[OK via TCP] (${i}s)"
    break
  fi
  sleep 1
done
echo "[Rust] $RUST_STATUS"

# ── [2/2] Python AI Service (port 8000 via fast gateway) ──
# main_fast.py opens port 8000 in < 2 seconds and then spawns main_simplified.py
# on port 8001 in the background.  All AI v2 endpoints run in main_fast.py and
# are never forwarded so they are always available regardless of warm-up state.
echo "[2/2] Starting Python AI Service (port 8000)..."
cd python-ai-service
BLOCK_MINED_SECRET="$BLOCK_MINED_SECRET" \
  uvicorn app.main_fast:app --host 0.0.0.0 --port 8000 --workers 1 &
UV_PID=$!
cd ..

# ── Background health watchdog: poll Python every 30s and log status ──
(
  # Give Python time to start up (~30s for model loading)
  sleep 45
  while kill -0 "$UV_PID" 2>/dev/null; do
    if curl -sf http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
      echo "[watchdog] Python AI Service :8000 OK ($(date -Iseconds))"
    else
      echo "[watchdog] Python AI Service :8000 NOT RESPONDING ($(date -Iseconds))"
    fi
    sleep 30
  done
  echo "[watchdog] Python AI Service exited ($(date -Iseconds))"
) &
WATCHDOG_PID=$!

cleanup() {
  kill "$WATCHDOG_PID"       2>/dev/null || true
  kill -TERM "$UV_PID"       2>/dev/null || true
  kill -TERM "$GO_PID"       2>/dev/null || true
  sleep 1
  kill -KILL "$UV_PID"       2>/dev/null || true
  kill -KILL "$GO_PID"       2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait "$UV_PID"
