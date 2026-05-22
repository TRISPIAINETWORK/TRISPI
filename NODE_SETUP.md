# TRISPI Node Setup Guide

This guide covers running every type of TRISPI node — from a simple Energy Provider to a full validator, RPC node, and custom blockchain.

---

## Table of Contents

1. [Quick Start — Energy Provider (5 min)](#1-quick-start--energy-provider-5-min)
2. [Full Node Setup](#2-full-node-setup)
3. [Run an RPC Node](#3-run-an-rpc-node)
4. [Docker Setup (Recommended for Servers)](#4-docker-setup-recommended-for-servers)
5. [Join the Mainnet](#5-join-the-mainnet)
6. [Run as a Validator](#6-run-as-a-validator)
7. [Create a Custom Blockchain](#7-create-a-custom-blockchain)
8. [Connect Your Blockchain to TRISPI](#8-connect-your-blockchain-to-trispi)
9. [Systemd Service (Auto-Start)](#9-systemd-service-auto-start)
10. [Troubleshooting](#10-troubleshooting)

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

# The pre-built binary is included:
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
pip install requests
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP

# Monitor sync:
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP --monitor
```

---

## 3. Run an RPC Node

An RPC node exposes a JSON-RPC endpoint compatible with MetaMask, ethers.js, web3.js, and Hardhat — so dApp developers can connect to your node instead of the mainnet.

### What you need

- A running Full Node (Section 2 above)
- A public IP or domain name
- Ports **8000** (REST API) and **8545** (JSON-RPC) open in your firewall

### Step 1 — Enable the RPC endpoint

The Python AI service already includes a JSON-RPC server at `/rpc`. Start the node with public binding:

```bash
uvicorn app.main_simplified:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2
```

Your RPC endpoint is now at:
```
http://YOUR_IP:8000/rpc
```

### Step 2 — (Optional) Dedicated port 8545 with nginx

Use nginx to expose the RPC on the standard Ethereum RPC port:

```nginx
# /etc/nginx/sites-available/trispi-rpc
server {
    listen 8545;
    server_name _;

    location / {
        proxy_pass         http://127.0.0.1:8000/rpc;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        add_header         Access-Control-Allow-Origin *;
        add_header         Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header         Access-Control-Allow-Headers "Content-Type";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/trispi-rpc /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### Step 3 — Verify the RPC

```bash
# Get Chain ID (should return 0x1EC6 = 7878):
curl -X POST http://YOUR_IP:8000/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Get latest block number:
curl -X POST http://YOUR_IP:8000/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Get balance:
curl -X POST http://YOUR_IP:8000/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xYOUR_ADDRESS","latest"],"id":1}'
```

### Step 4 — Add your RPC to MetaMask

1. MetaMask → **Add Network** → **Add manually**
2. Fill in:

| Field | Value |
|-------|-------|
| Network Name | `TRISPI — My Node` |
| New RPC URL | `http://YOUR_IP:8000/rpc` |
| Chain ID | `7878` |
| Currency Symbol | `TRP` |

### Step 5 — Connect with ethers.js

```javascript
const { ethers } = require("ethers");

const provider = new ethers.JsonRpcProvider("http://YOUR_IP:8000/rpc");

// Get chain ID:
const network = await provider.getNetwork();
console.log(network.chainId); // 7878n

// Get balance:
const balance = await provider.getBalance("0xYOUR_ADDRESS");
console.log(ethers.formatEther(balance));
```

### Step 6 — Register your RPC node with mainnet

```bash
curl -X POST https://trispi.org/api/network/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id":      "my_rpc_node_01",
    "address":      "YOUR_IP:50051",
    "node_type":    "rpc_node",
    "rpc_endpoint": "http://YOUR_IP:8000/rpc"
  }'
```

### Supported JSON-RPC methods

| Method | Description |
|--------|-------------|
| `eth_chainId` | Returns `0x1EC6` (7878) |
| `eth_blockNumber` | Latest block number |
| `eth_getBalance` | Address balance |
| `eth_getTransactionCount` | Nonce for address |
| `eth_sendRawTransaction` | Broadcast signed transaction |
| `eth_call` | Call a contract (read-only) |
| `eth_estimateGas` | Estimate gas for a transaction |
| `eth_getTransactionReceipt` | Transaction receipt by hash |
| `net_version` | Network ID (`7878`) |

---

## 4. Docker Setup (Recommended for Servers)

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

### Health check

```bash
curl http://localhost:8000/health
curl http://localhost:8081/health
```

---

## 5. Join the Mainnet

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
| 8000 | TCP | REST API (expose if running public RPC) |
| 8081 | TCP | Go consensus HTTP |

---

## 6. Run as a Validator

Validators participate in PoI + PBFT consensus and earn additional block rewards.

**Minimum stake:** 10,000 TRP

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

# Stake TRP:
curl -X POST https://trispi.org/api/validators/stake \
  -H "Content-Type: application/json" \
  -d '{"validator":"validator_01","amount":10000}'

# Check validator status:
curl https://trispi.org/api/validators

# Check your PoI score:
curl https://trispi.org/api/poi/scores
```

**Validator rewards:**
- Base block reward: `block_subsidy × stake_weight`
- PoI bonus: up to +50% for high AI accuracy
- Uptime bonus: +10% for >99% availability

---

## 7. Create a Custom Blockchain

TRISPI lets you scaffold a full parachain project in Go, Rust, or Solidity and connect it as a TRISPI subnet.

### Step 1 — Scaffold the project

```bash
export NODE=https://trispi.org

# Go chain (same stack as TRISPI core):
curl -X POST $NODE/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name":   "my-chain",
    "language":     "go",
    "block_time":   15,
    "token_name":   "MYTOKEN",
    "token_symbol": "MYT"
  }' -o my-chain.zip

# Rust / CosmWasm:
curl -X POST $NODE/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name": "my-chain",
    "language":   "rust",
    "block_time": 10
  }' -o my-chain.zip

# Solidity / EVM (Hardhat):
curl -X POST $NODE/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name": "my-chain",
    "language":   "solidity",
    "block_time": 12
  }' -o my-chain.zip
```

### Step 2 — Extract and run locally

```bash
unzip my-chain.zip -d my-chain
cd my-chain

# Go:
go mod tidy && go run main.go

# Rust:
cargo build --target wasm32-unknown-unknown --release && bash build.sh

# Solidity:
npm install && npx hardhat node
```

### Step 3 — What's in the ZIP

**Go scaffold:**
```
main.go               — Entry point
consensus/node.go     — PBFT consensus
p2p/node.go           — libp2p P2P layer
go.mod
Dockerfile
connect-to-trispi.sh  — Auto-register with TRISPI
README.md
```

**Rust scaffold:**
```
Cargo.toml
src/contract.rs       — CosmWasm contract
src/state.rs          — On-chain state
src/msg.rs            — Message types
build.sh              — WASM compile script
Dockerfile
connect-to-trispi.sh
README.md
```

**Solidity scaffold:**
```
contracts/
  ChainRegistry.sol   — On-chain registry
  BridgeVault.sol     — Token bridge vault
hardhat.config.js
scripts/deploy.js
package.json
connect-to-trispi.sh
README.md
```

---

## 8. Connect Your Blockchain to TRISPI

### Option A — Automatic (recommended)

Each scaffold includes `connect-to-trispi.sh`:

```bash
# Connect to TRISPI mainnet:
bash connect-to-trispi.sh

# Or point at your own TRISPI node:
TRISPI_NODE_URL=http://YOUR_TRISPI_NODE:8000 bash connect-to-trispi.sh
```

The script:
1. Registers your chain in the TRISPI parachain registry
2. Submits your genesis hash and validator set
3. Opens an IBC channel for cross-chain transfers
4. Starts syncing block headers with the TRISPI hub

### Option B — Manual registration

```bash
curl -X POST https://trispi.org/api/chains/register \
  -H "Content-Type: application/json" \
  -d '{
    "name":         "my-chain",
    "genesis_hash": "0xYOUR_GENESIS_HASH",
    "validators":   ["trp1val1", "trp1val2"],
    "ibc_endpoint": "http://YOUR_CHAIN_IP:8000/api"
  }'
```

**Response:**
```json
{
  "chain_id":     "uuid-...",
  "name":         "my-chain",
  "admin_secret": "one-time-secret-SAVE-THIS",
  "status":       "registered"
}
```

> ⚠️ Copy `admin_secret` immediately — shown **once only**.  
> Save it: `echo "SECRET" > .trispi-admin-secret && chmod 600 .trispi-admin-secret`  
> Use it as `X-Admin-Token` header for admin operations.

### Keep your chain alive — submit headers

```bash
# Submit block headers every ~60 seconds:
curl -X POST https://trispi.org/api/chain/sync-block \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: YOUR_ADMIN_SECRET" \
  -d '{
    "chain_id":     "your-chain-uuid",
    "block_hash":   "0xABC...",
    "block_height": 1234,
    "timestamp":    1700000000
  }'
```

### Cross-chain TRP transfers (IBC)

```bash
curl -X POST https://trispi.org/api/ibc/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "from_chain": "trispi-mainnet-1",
    "to_chain":   "your-chain-uuid",
    "sender":     "trp1sender",
    "recipient":  "trp1recipient",
    "token":      "TRP",
    "amount":     100.0
  }'
```

### Architecture

```
┌──────────────────────────────┐
│   TRISPI mainnet (hub)       │
│   /api/chains  /api/rpc      │
└──────────────▲───────────────┘
               │  register / submitHeader / IBC
 ┌─────────────┼─────────────┐
 │             │             │
┌──┴───────┐  ┌──┴───────┐  ┌──┴───────┐
│  chainA  │  │  chainB  │  │  chainN  │
│  (Go)    │◀▶│  (Rust)  │◀▶│  (EVM)   │
└──────────┘  └──────────┘  └──────────┘
        ▲
        └── trispi-relayer handles IBC routing
```

---

## 9. Systemd Service (Auto-Start)

### Energy Provider

```bash
sudo tee /etc/systemd/system/trispi-provider.service > /dev/null << 'EOF'
[Unit]
Description=TRISPI Energy Provider
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/TRISPI
ExecStart=/usr/bin/python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trispi-provider
sudo systemctl start trispi-provider
sudo journalctl -u trispi-provider -f
```

### Full Node (Python AI service)

```bash
sudo tee /etc/systemd/system/trispi-node.service > /dev/null << 'EOF'
[Unit]
Description=TRISPI AI Node
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/TRISPI/python-ai-service
ExecStart=/usr/bin/python3 -m uvicorn app.main_simplified:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trispi-node
sudo systemctl start trispi-node
```

### Go Consensus Node

```bash
sudo tee /etc/systemd/system/trispi-consensus.service > /dev/null << 'EOF'
[Unit]
Description=TRISPI Go Consensus
After=network.target trispi-node.service

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/TRISPI/go-consensus
ExecStart=/path/to/TRISPI/go-consensus/trispi-consensus -id node1 -http 8081 -port 50051
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable trispi-consensus
sudo systemctl start trispi-consensus
```

---

## 10. Troubleshooting

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
| Chain shows as revoked | Submit a header within 24h to keep it active |
| RPC 403 / CORS error | Add `Access-Control-Allow-Origin *` to nginx config |
| `admin_secret` lost | Re-register the chain — a new secret will be issued |

### Useful commands

```bash
# Check all TRISPI services:
curl http://localhost:8000/health
curl http://localhost:8081/health

# Network status:
curl http://localhost:8000/api/network/status

# Your node's peers:
curl http://localhost:8000/api/network/peers

# Latest blocks:
curl http://localhost:8000/api/chain

# AI engine status:
curl http://localhost:8000/api/ai/full-status
```

---

## Architecture Overview

```
Your Server
├── Python AI Service   :8000  ← REST API, JSON-RPC (/rpc), AI/PoI, Energy
├── Go Consensus Node   :8081  ← PBFT consensus + libp2p P2P (:50051/:50052)
└── Rust Core Bridge    :6000  ← EVM + WASM execution, PQC signatures (TCP)
         │
         ▼ P2P (port 50051)
   TRISPI Mainnet (trispi.org)
         │
         ▼ IBC
   Your Custom Chains (parachains)
```

For the full API reference see [docs/API.md](docs/API.md).  
For blockchain creation details see [docs/BLOCKCHAIN_CREATION.md](docs/BLOCKCHAIN_CREATION.md).
