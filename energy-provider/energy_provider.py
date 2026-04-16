#!/usr/bin/env python3
"""
TRISPI Energy Provider — earn TRP by contributing CPU/GPU compute.

This script registers your machine as an energy provider and sends
periodic power readings to the TRISPI network in exchange for TRP rewards.

Usage:
    pip install requests psutil
    python energy_provider.py

    # With a custom node URL and wallet:
    TRISPI_NODE_URL=http://localhost:8000 \
    TRISPI_WALLET=trp1YOUR_WALLET \
    DEVICE_ID=my-gpu-server-1 \
    python energy_provider.py
"""

import os
import sys
import time
import json
import signal
import logging
import platform
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install requests: pip install requests")
    sys.exit(1)

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available — using estimated readings. Install with: pip install psutil")

# ── Configuration ─────────────────────────────────────────────────────────────

NODE_URL     = os.environ.get("TRISPI_NODE_URL", "http://localhost:8000")
WALLET       = os.environ.get("TRISPI_WALLET", "trp1ENTER_YOUR_WALLET_ADDRESS_HERE")
DEVICE_ID    = os.environ.get("DEVICE_ID", f"provider-{platform.node()}")
DEVICE_TYPE  = os.environ.get("DEVICE_TYPE", "cpu")     # cpu | gpu | asic
CPU_CORES    = int(os.environ.get("CPU_CORES", os.cpu_count() or 4))
GPU_MEM_MB   = int(os.environ.get("GPU_MEMORY_MB", 0))
INTERVAL_SEC = int(os.environ.get("READING_INTERVAL", 30))
STATE_FILE   = Path(os.environ.get("STATE_FILE", "trispi_provider_state.json"))

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("trispi-provider")

# ── Helpers ───────────────────────────────────────────────────────────────────

def save_state(data: dict) -> None:
    STATE_FILE.write_text(json.dumps(data, indent=2))

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}

def get_readings() -> dict:
    """Collect current hardware metrics."""
    if PSUTIL_AVAILABLE:
        cpu_pct   = psutil.cpu_percent(interval=1)
        mem       = psutil.virtual_memory()
        mem_pct   = mem.percent
        cpu_watts = 5 + (CPU_CORES * 3 * cpu_pct / 100)
        gpu_watts = GPU_MEM_MB / 1024 * 15 if GPU_MEM_MB else 0
        total_w   = cpu_watts + gpu_watts
        temp      = 40 + (cpu_pct * 0.4)
        gpu_pct   = min(cpu_pct * 0.8, 100) if GPU_MEM_MB else 0
    else:
        cpu_pct   = 50.0
        mem_pct   = 60.0
        cpu_watts = CPU_CORES * 5
        gpu_watts = GPU_MEM_MB / 1024 * 10 if GPU_MEM_MB else 0
        total_w   = cpu_watts + gpu_watts
        temp      = 55.0
        gpu_pct   = 40.0 if GPU_MEM_MB else 0

    return {
        "power_watts":   round(total_w, 2),
        "temperature_c": round(temp, 1),
        "cpu_usage_pct": round(cpu_pct, 1),
        "gpu_usage_pct": round(gpu_pct, 1),
    }

# ── Main ──────────────────────────────────────────────────────────────────────

def register(session: requests.Session) -> str:
    """Register device and return api_key."""
    log.info("Registering device '%s' with TRISPI node at %s...", DEVICE_ID, NODE_URL)
    resp = session.post(f"{NODE_URL}/api/energy/register", json={
        "device_id":      DEVICE_ID,
        "device_type":    DEVICE_TYPE,
        "cpu_cores":      CPU_CORES,
        "gpu_memory_mb":  GPU_MEM_MB,
        "wallet_address": WALLET,
    }, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    api_key = data.get("api_key", "")
    log.info("Registered! API key: %s...%s (store this securely)", api_key[:8], api_key[-4:])
    return api_key


def send_reading(session: requests.Session, api_key: str, stats: dict) -> None:
    payload = {
        "device_id":     DEVICE_ID,
        "api_key":       api_key,
        "timestamp":     int(time.time()),
        **stats,
    }
    resp = session.post(f"{NODE_URL}/api/energy/proxy/reading", json=payload, timeout=10)
    resp.raise_for_status()
    result = resp.json()
    reward = result.get("reward_trp", 0)
    log.info(
        "Reading sent | CPU %.1f%% | Power %.1fW | Reward: +%.6f TRP",
        stats["cpu_usage_pct"], stats["power_watts"], reward,
    )


def main() -> None:
    if WALLET == "trp1ENTER_YOUR_WALLET_ADDRESS_HERE":
        log.error("Set your wallet address: TRISPI_WALLET=trp1... python energy_provider.py")
        sys.exit(1)

    session = requests.Session()
    state   = load_state()

    # Register (or reuse saved api_key)
    api_key = state.get("api_key", "")
    if not api_key:
        api_key = register(session)
        state["api_key"] = api_key
        state["device_id"] = DEVICE_ID
        state["wallet"] = WALLET
        save_state(state)
    else:
        log.info("Resuming with saved api_key for device '%s'", DEVICE_ID)

    total_rewards = state.get("total_rewards", 0.0)
    readings_sent = state.get("readings_sent", 0)

    # Graceful shutdown
    running = {"ok": True}
    def _stop(sig, frame):
        log.info("Shutting down (total earned: %.6f TRP over %d readings)", total_rewards, readings_sent)
        running["ok"] = False
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    log.info("Energy provider started. Sending readings every %ds. Press Ctrl+C to stop.", INTERVAL_SEC)
    while running["ok"]:
        try:
            stats = get_readings()
            send_reading(session, api_key, stats)
            readings_sent += 1
        except requests.exceptions.RequestException as exc:
            log.warning("Network error: %s — retrying next interval", exc)
        except Exception as exc:
            log.error("Unexpected error: %s", exc)

        # Persist state periodically
        if readings_sent % 10 == 0:
            state["total_rewards"] = total_rewards
            state["readings_sent"] = readings_sent
            save_state(state)

        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
