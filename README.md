# TRISPI — The Autonomous AI Blockchain Network

> **Web4 · AI-Powered · Post-Quantum Secure · EVM + WASM**

[![Website](https://img.shields.io/badge/Website-fffgfggffff.replit.app-blue)](https://fffgfggffff.replit.app)
[![Telegram](https://img.shields.io/badge/Telegram-@trispiainetwork-26A5E4)](https://t.me/trispiainetwork)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What is TRISPI?

TRISPI is a next-generation **Web4 blockchain** where AI agents act as validators, smart contracts self-heal, and your compute power fuels an autonomous intelligence network. The network is secured by post-quantum cryptography and supports both EVM (Solidity) and WASM (CosmWasm) smart contracts.

| Feature | Description |
|---------|-------------|
| **Proof of Intelligence (PoI)** | AI scores every block — models validate transactions with fraud detection |
| **Post-Quantum Security** | Ed25519 + Dilithium3 (NIST PQC) + Kyber1024 hybrid |
| **EVM + WASM** | Run Solidity and WebAssembly contracts on the same chain |
| **Energy Provider System** | Earn TRP by contributing CPU/GPU compute to AI training |
| **PBFT Consensus** | Byzantine-fault-tolerant, ~15 second block time |
| **Chain ID 7878** | MetaMask / ethers.js / web3.js compatible |
| **EIP-1559 Tokenomics** | Dynamic gas fees, 70% burn, Bitcoin-style halving |

---

## Network Details

| Parameter | Value |
|-----------|-------|
| Chain ID | `7878` |
| Token Symbol | `TRP` |
| Total Supply | `50,000,000 TRP` |
| Block Time | `~15 seconds` |
| Consensus | `PoI + PBFT` |
| Post-Quantum | `Ed25519 + Dilithium3 + Kyber1024` |
| **Mainnet URL** | `https://fffgfggffff.replit.app` |
| REST API | `https://fffgfggffff.replit.app/api` |
| Explorer | `https://fffgfggffff.replit.app` |
| Swagger Docs | `https://fffgfggffff.replit.app/api/docs` |
| **Bootstrap endpoint** | `GET https://fffgfggffff.replit.app/api/p2p/bootstrap` |
| **P2P peer ID** | `12D3KooWPR3pFyevgAtZWHGiM4e1RBKQVVXLF3TRbKzT7dvHjjWH` |

---

## Node Types — Choose Your Role

### 1. Energy Provider (Easiest — 2 minutes)
> Python script only. No Docker, no Go. Earn TRP by scoring blocks and submitting FL gradients.

**Requirements:** Python 3.9+, 1 GB RAM  
**Earns:** TRP per block scored + FL gradient round reward

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
pip install requests numpy cryptography psutil

# Connect to mainnet:
python3 trispi/trispi_energy_provider.py \
  --node https://fffgfggffff.replit.app \
  --wallet trp1YOUR_ADDRESS

# Or connect to your own full node:
python3 trispi/trispi_energy_provider.py \
  --node http://YOUR_SERVER:8000 \
  --wallet trp1YOUR_ADDRESS
```

**How data reaches this node:**
```
Every 20s: GET /api/explorer/blocks  → get latest block hash
           POST /api/poi/score-block → submit AI score → earn 0.1 TRP
Every 30s: GET /api/federated/round-status → check FL round
           POST /api/federated/submit-gradient → submit gradient → earn 1.0 TRP
```

---

### 2. Validator Node (Full Stack — 10 minutes)
> Python + Go + Rust. Participates in PBFT consensus, receives real-time P2P blocks, earns block rewards.

**Requirements:** 4 CPU cores, 8 GB RAM, port 50052 open  
**Earns:** 10 TRP block reward + priority fees

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI/trispi

# 1. Start Python AI Service (port 8000):
cd python-ai-service
pip install -r requirements.txt
export TRISPI_BOOTSTRAP=https://fffgfggffff.replit.app
uvicorn app.main_fast:app --host 0.0.0.0 --port 8000 &

# 2. Start Go Consensus Node (port 8181, P2P 50052):
cd ../go-consensus
./trispi-consensus \
  -id my-validator-001 \
  -http 8181 \
  -libp2p-port 50052 \
  -bootstrap https://fffgfggffff.replit.app &

# 3. Register as validator:
curl -X POST http://localhost:8000/api/validators/register \
  -H "Content-Type: application/json" \
  -d '{"validator_id":"my-validator-001","public_key":"YOUR_ED25519_PUBKEY_HEX","stake":1000.0}'
```

**How data reaches this node:**
```
Go startup:
  GET  https://fffgfggffff.replit.app/api/p2p/bootstrap       → chain height, peer ID
  GET  https://fffgfggffff.replit.app/api/p2p/blocks/range    → download 100 blocks/batch
  ...repeat until synced to chain_height

After sync (real-time P2P):
  libp2p connects to 12D3KooWPR3pFyevgAtZWHGiM4e... (mainnet peer)
  → receives new blocks every ~15 seconds via gossip protocol
  → Go calls Python /api/poi/score-block for each block
  → Python calls Rust /pqc/sign for Dilithium3 signature
```

**Open port 50052** so other nodes can peer with you:
```bash
sudo ufw allow 50052/tcp
```

---

### 3. Full Node / Observer (No consensus — 5 minutes)
> Full chain history in PostgreSQL. Serves API to wallets and dApps. No consensus participation.

**Requirements:** 2 CPU cores, 4 GB RAM, 20 GB disk  
**Role:** Serves /api/* to dApps, stores full chain history

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI/trispi

# Start Python AI Service with bootstrap sync:
cd python-ai-service
pip install -r requirements.txt
export TRISPI_BOOTSTRAP=https://fffgfggffff.replit.app
export DATABASE_URL=postgresql://user:pass@localhost:5432/trispi

# Python auto-syncs blocks from mainnet on startup:
uvicorn app.main_fast:app --host 0.0.0.0 --port 8000

# Your node now exposes the full TRISPI API:
curl http://localhost:8000/api/network/status
curl http://localhost:8000/api/explorer/blocks
```

**How data reaches this node:**
```
Python startup:
  GET  https://fffgfggffff.replit.app/api/p2p/blocks/range  → sync blocks to PG
  Stores all block data in postgresql → blocks, balances, proofs

After sync:
  Serves GET /api/explorer/blocks, /api/balance/*, /api/tokenomics
  Energy providers and wallets connect to YOUR node
  YOUR node is now part of the decentralized API layer
```

---

## How Network Data Flows to Your Node

```
MAINNET (fffgfggffff.replit.app)
│
├─ GET /api/p2p/bootstrap          ← Any node calls this first
│    returns: chain_height=9823, peer_id, libp2p_addrs[6]
│
├─ GET /api/p2p/blocks/range?from=X&to=Y   ← Bulk sync (100 blocks/batch)
│    returns: {blocks:[...], head:9823}
│
├─ GET /api/chain/genesis-state    ← Account state snapshot
│    returns: 1055 accounts with TRP balances
│
├─ GET /api/p2p/peers              ← Other nodes to connect to
│    returns: connected Go peer IDs
│
└─ libp2p P2P :50052               ← Real-time block propagation
     Go nodes receive new blocks instantly via gossip
```

### Verify bootstrap is working:
```bash
# Check mainnet is alive:
curl https://fffgfggffff.replit.app/api/p2p/bootstrap | python3 -m json.tool

# Sync first 100 blocks:
curl "https://fffgfggffff.replit.app/api/p2p/blocks/range?from=0&to=100" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'blocks: {len(d[\"blocks\"])}, head: {d[\"head\"]}')"

# Check network live stats:
curl https://fffgfggffff.replit.app/api/network/status | python3 -m json.tool
```

---

## Quick Start — One Command (Docker)

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

export TRISPI_BOOTSTRAP=https://fffgfggffff.replit.app

# Full node with Docker:
bash join_trispi_network.sh

# After start, verify your node:
curl http://localhost:8000/api/network/status
curl http://localhost:8000/api/p2p/bootstrap
```

---

## Add to MetaMask

| Field | Value |
|-------|-------|
| Network Name | TRISPI Mainnet |
| RPC URL | `https://fffgfggffff.replit.app/rpc` |
| Chain ID | `7878` |
| Currency Symbol | `TRP` |
| Explorer | `https://fffgfggffff.replit.app` |

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/network/status` | GET | Block height, nodes, AI accuracy, energy sensors |
| `/api/p2p/bootstrap` | GET | Bootstrap data: chain height, peer ID, libp2p addrs |
| `/api/p2p/blocks/range?from=X&to=Y` | GET | Download blocks in batches (100/request) |
| `/api/p2p/peers` | GET | Connected P2P peer IDs |
| `/api/chain/genesis-state` | GET | All 1055 account balances (live state) |
| `/api/explorer/blocks` | GET | Recent blocks with AI scores |
| `/api/poi/score-block` | POST | Submit PoI score for a block |
| `/api/federated/register` | POST | Register as FL gradient provider |
| `/api/federated/submit-gradient` | POST | Submit encrypted FL gradient |
| `/api/federated/round-status` | GET | Current FL round status |
| `/api/federated/verify-round/{id}` | GET | Verify FL aggregation vs on-chain hash |
| `/api/validators/register` | POST | Register as PoI validator |
| `/api/validators/submit-score` | POST | Submit block validation score |
| `/api/balance/{address}` | GET | TRP balance |
| `/api/tokens/transfer` | POST | Transfer TRP |
| `/api/gas/estimate` | GET | Dynamic EIP-1559 base fee |
| `/api/docs` | GET | Full Swagger UI |

---

## Architecture

```
Energy Providers ──► Python AI Service  :8000  (FastAPI · PoI · FL · Fraud model)
                              │ /api/* serves wallets + dApps
                              │ syncs blocks ↔ Go
                              ▼
                    Go Consensus Node   :8181  (PBFT · libp2p P2P)
                              │ P2P :50052  (block propagation)
                              ▼
                    Rust Core Bridge    :6000  (EVM · WASM · PQC signing)
                              │
                    PostgreSQL          :5432  (full chain history)
```

---

## Repository Structure

```
TRISPI/
├── trispi/
│   ├── python-ai-service/app/
│   │   ├── main_fast.py          # Fast gateway + all API endpoints
│   │   ├── autonomous_agents.py  # ValidatorAgent + ComputeProviderAgent
│   │   ├── federated_learning_v2.py  # FL aggregation + on-chain commitment
│   │   └── pg_persist.py         # PostgreSQL persistence
│   ├── go-consensus/
│   │   ├── trispi-consensus      # Pre-built Go binary (Linux x64)
│   │   └── p2p_api.go            # P2P sync protocol implementation
│   ├── trispi_energy_provider.py # Standalone energy provider script
│   └── start_backend.sh          # Start all services
├── README.md
└── LICENSE
```

---

## Community

| Platform | Link |
|----------|------|
| 🌐 Website | [fffgfggffff.replit.app](https://fffgfggffff.replit.app) |
| 💬 Telegram | [@trispiainetwork](https://t.me/trispiainetwork) |
| 🐙 GitHub | [TRISPIAINETWORK/TRISPI](https://github.com/TRISPIAINETWORK/TRISPI) |

---

## License

MIT License — see [LICENSE](LICENSE).
