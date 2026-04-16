# TRISPI Node Setup Guide

This guide covers running every type of TRISPI node — from a simple Energy Provider to a full validator node.

---

## Table of Contents

1. [Quick Start — Energy Provider (5 min)](#1-quick-start--energy-provider-5-min)
2. [Full Node Setup](#2-full-node-setup)
3. [Docker Setup (Recommended for Servers)](#3-docker-setup-recommended-for-servers)
4. [Join the Mainnet](#4-join-the-mainnet)
5. [Run as a Validator](#5-run-as-a-validator)
6. [Systemd Service (Auto-Start)](#6-systemd-service-auto-start)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Quick Start — Energy Provider (5 min)

Earn TRP tokens by contributing your compute. No blockchain experience required.

**Requirements:** Python 3.8+, internet connection

```bash
# 1. Clone the repository
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

# 2. Install dependencies (minimal)
pip install requests psutil

# 3. Start the Energy Provider
python3 energy-provider/trispi_energy_provider.py

# With a custom wallet address:
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# With a custom node ID:
python3 energy-provider/trispi_energy_provider.py --id my_server_01
```

The script connects to `https://trispi.org`, registers your node, and starts earning TRP automatically.

**Expected output:**
```
[TRISPI] Registering node: my_node_abc123
[TRISPI] Session started: uuid-...
[TRISPI] Heartbeat #1 | Reward: +0.5 TRP | Total: 0.5 TRP
[TRISPI] Task received: matrix_multiplication_4x4
[TRISPI] Task completed | Quality: 0.94 | Reward: +2.3 TRP
```

---

## 2. Full Node Setup

Run a complete TRISPI node with all three services: Python AI, Go Consensus, Rust Bridge.

### Requirements

| Minimum | Recommended |
|---------|-------------|
| 2 CPU cores | 4+ CPU cores |
| 4 GB RAM | 8+ GB RAM |
| 20 GB disk | 100+ GB SSD |
| Ubuntu 20.04+ / macOS / Windows WSL2 | Ubuntu 22.04 |
| Python 3.10+ | Python 3.11 |
| Go 1.21+ | Go 1.22 |
| Rust 1.75+ | Rust 1.78 (stable) |

### Step 1 — Clone

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI
```

### Step 2 — Python AI Service (Port 8000)

```bash
cd python-ai-service

# Install all dependencies:
pip install -r requirements.txt

# If errors, install minimal set:
pip install fastapi uvicorn pydantic requests httpx cryptography dilithium-py numpy

# Optional (for EVM + WASM contract execution):
pip install py-evm wasmtime

# Start the service:
uvicorn app.main_simplified:app --host 0.0.0.0 --port 8000

# Verify:
curl http://localhost:8000/health
```

### Step 3 — Go Consensus Node (Port 8081)

```bash
cd go-consensus

# Download the pre-built binary for Linux x64:
# (already included in the repo as trispi-consensus)
chmod +x trispi-consensus

# Or build from source (requires Go 1.21+):
go build -o trispi-consensus .

# Start:
./trispi-consensus -id my_node_01 -http 8081 -port 50051 -libp2p-port 50052

# Verify:
curl http://localhost:8081/health
```

### Step 4 — Rust Core Bridge (Port 6000)

```bash
cd rust-core

# Build (requires Rust stable):
# Linux dependencies:
sudo apt install pkg-config libssl-dev build-essential
# macOS:
brew install pkg-config openssl

cargo build --release

# Start:
./target/release/trispi_core

# Verify (TCP connection):
echo '{"cmd":"get_chain"}' | nc 127.0.0.1 6000
```

### Step 5 — Join Mainnet

```bash
# From the repo root:
pip install requests
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP

# Monitor sync:
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP --monitor
```

---

## 3. Docker Setup (Recommended for Servers)

### Full Stack (Python + Go + Rust + Nginx)

```bash
# Copy and configure environment:
cp .env.example .env
nano .env   # set FOUNDER_WALLET and other options

# Start everything:
docker-compose -f docker-compose.trispi.yml up -d

# Check status:
docker-compose -f docker-compose.trispi.yml ps

# View logs:
docker-compose -f docker-compose.trispi.yml logs -f

# Stop:
docker-compose -f docker-compose.trispi.yml down
```

### Single Node Only

```bash
docker-compose -f docker-compose.node.yml up -d
```

---

## 4. Join the Mainnet

After your node is running locally:

```bash
# Auto-join script (checks health, syncs blocks, registers):
python3 scripts/join-network.py

# With your public IP (required for P2P discovery):
python3 scripts/join-network.py --public-ip 1.2.3.4

# With continuous monitoring:
python3 scripts/join-network.py --public-ip 1.2.3.4 --monitor

# Manual registration:
curl -X POST https://trispi.org/api/network/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id":      "my_node_01",
    "address":      "1.2.3.4:50051",
    "node_type":    "full_node",
    "chain_height": 0
  }'
```

**Required open ports:**
| Port | Protocol | Purpose |
|------|----------|---------|
| 50051 | TCP | P2P peer connections |
| 50052 | TCP | libp2p DHT |
| 8000 | TCP | REST API (optional, if you want to expose it) |

---

## 5. Run as a Validator

Validators participate in PBFT consensus and earn additional block rewards.

```bash
# Register as validator:
curl -X POST https://trispi.org/api/network/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id":        "validator_01",
    "address":        "YOUR_IP:50051",
    "node_type":      "validator",
    "wallet_address": "trp1YOUR_WALLET"
  }'

# Stake TRP (minimum 10,000 TRP to become validator):
curl -X POST https://trispi.org/api/validators/stake \
  -d '{"validator":"validator_01","amount":10000}'

# Check validator status:
curl https://trispi.org/api/validators
```

---

## 6. Systemd Service (Auto-Start on Server)

Run the Energy Provider automatically on Linux server boot:

```bash
# Create the service file:
sudo tee /etc/systemd/system/trispi-provider.service > /dev/null << SVCEOF
[Unit]
Description=TRISPI Energy Provider
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=/path/to/TRISPI
ExecStart=/usr/bin/python3 energy-provider/trispi_energy_provider.py
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

# Enable and start:
sudo systemctl daemon-reload
sudo systemctl enable trispi-provider
sudo systemctl start trispi-provider

# Check status:
sudo systemctl status trispi-provider
sudo journalctl -u trispi-provider -f
```

---

## 7. Troubleshooting

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: fastapi` | `pip install -r python-ai-service/requirements.txt` |
| `ModuleNotFoundError: dilithium` | `pip install dilithium-py` |
| `Address already in use :8000` | `pkill -f uvicorn` then retry |
| `go: command not found` | Install Go: https://golang.org/dl/ |
| `cargo: command not found` | `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs \| sh` |
| `linker 'cc' not found` | `sudo apt install build-essential` |
| `openssl not found` | `sudo apt install pkg-config libssl-dev` |
| `Connection refused :8081` | Go node not running — Python works standalone |
| `Connection refused :6000` | Rust bridge not running — Python works standalone |
| Node not syncing | Check firewall, ensure port 50051 is open |
| Balance not showing | Wait 1-2 minutes for first block reward |

---

## Architecture Overview

```
Your Node
├── Python AI Service   :8000  (REST API, AI/PoI, Energy Provider)
├── Go Consensus Node   :8081  (PBFT, P2P via libp2p port :50052)
└── Rust Core Bridge    :6000  (EVM, WASM, PQC signatures — TCP)
         │
         ▼
   TRISPI Mainnet (trispi.org)
```

For more details see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
