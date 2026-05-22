# TRISPI — The Autonomous AI Blockchain Network

> **Web4 · AI-Powered · Post-Quantum Secure · EVM + WASM**

[![Website](https://img.shields.io/badge/Website-trispi.org-blue)](https://trispi.org)
[![Telegram](https://img.shields.io/badge/Telegram-@trispiainetwork-26A5E4)](https://t.me/trispiainetwork)
[![Chain ID](https://img.shields.io/badge/Chain%20ID-7878-green)](https://trispi.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What is TRISPI?

TRISPI is a next-generation **Web4 blockchain** where AI agents act as validators, smart contracts self-heal, and your compute power fuels an autonomous intelligence network. The network is secured by post-quantum cryptography and supports both EVM (Solidity) and WASM (CosmWasm) smart contracts.

| Feature | Description |
|---------|-------------|
| **Proof of Intelligence (PoI)** | AI-based consensus — models validate every transaction |
| **Post-Quantum Security** | Ed25519 + Dilithium3 (NIST PQC) + Kyber1024 hybrid |
| **EVM + WASM** | Run Solidity and WebAssembly contracts on the same chain |
| **Energy Provider System** | Earn TRP by contributing CPU/GPU compute to AI training |
| **PBFT Consensus** | Byzantine-fault-tolerant, ~10 second block time |
| **Chain ID 7878** | MetaMask / ethers.js / web3.js compatible |
| **EIP-1559 Tokenomics** | Dynamic gas fees, 70% burn, Bitcoin-style halving |

---

## Table of Contents

1. [Network Details](#network-details)
2. [Quick Start](#quick-start)
3. [Add to MetaMask](#add-to-metamask)
4. [Energy Provider — Earn TRP](#energy-provider--earn-trp)
5. [Run a Full Node](#run-a-full-node)
6. [Create a Blockchain on TRISPI](#create-a-blockchain-on-trispi)
7. [Smart Contracts](#smart-contracts)
8. [SDK & API](#sdk--api)
9. [Repository Structure](#repository-structure)
10. [Community](#community)

---

## Network Details

| Parameter | Value |
|-----------|-------|
| Chain ID | `7878` |
| Token Symbol | `TRP` |
| Total Supply | `50,000,000 TRP` |
| Block Time | `~10 seconds` |
| Consensus | `PoI + PBFT` |
| Post-Quantum | `Ed25519 + Dilithium3 + Kyber1024` |
| RPC Endpoint | `https://trispi.org/rpc` |
| REST API | `https://trispi.org/api` |
| Explorer | `https://trispi.org` |
| Swagger Docs | `https://trispi.org/api/docs` |

---

## Quick Start

### Option 1 — Energy Provider (earn TRP in 5 minutes)

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI
pip install requests psutil numpy

# Run on CPU:
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# Run with GPU (NVIDIA CUDA):
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS --gpu
```

### Option 2 — Run a Full Node

```bash
# Auto-join mainnet:
python3 scripts/join-network.py --public-ip YOUR_SERVER_IP

# With sync monitoring:
python3 scripts/join-network.py --public-ip YOUR_SERVER_IP --monitor
```

### Option 3 — Docker (Recommended for Servers)

```bash
# Full TRISPI stack (Python AI + Go Consensus):
docker-compose -f docker-compose.trispi.yml up -d

# Single node only:
docker-compose -f docker-compose.node.yml up -d

# Check health:
curl http://localhost:8000/health
```

---

## Add to MetaMask

1. Open MetaMask → **Add Network** → **Add a network manually**
2. Fill in:

| Field | Value |
|-------|-------|
| Network Name | `TRISPI Mainnet` |
| New RPC URL | `https://trispi.org/rpc` |
| Chain ID | `7878` |
| Currency Symbol | `TRP` |
| Block Explorer URL | `https://trispi.org` |

3. Click **Save** — TRISPI is now in your MetaMask.

---

## Energy Provider — Earn TRP

Earn TRP tokens by contributing your **real** CPU/GPU compute to the TRISPI AI network.

The client downloads a neural network, runs **real NumPy gradient descent** on your hardware, and submits gradients back — genuine federated learning.

```bash
pip install requests psutil numpy

# CPU (basic):
python3 energy-provider/trispi_energy_provider.py \
  --wallet trp1YOUR_ADDRESS \
  --id my_server_01

# GPU (NVIDIA):
python3 energy-provider/trispi_energy_provider.py \
  --wallet trp1YOUR_ADDRESS \
  --gpu \
  --id my_server_01

# Connect to your own local node:
python3 energy-provider/trispi_energy_provider.py \
  --server http://localhost:8000 \
  --wallet trp1YOUR_ADDRESS
```

**What your device does:**
1. Downloads AI model weights + training mini-batch from TRISPI node
2. Runs 5 gradient descent steps (real NumPy ops on your CPU/GPU)
3. Sends back computed gradients (federated averaging)
4. Earns TRP rewards based on compute quality

**Reward Formula:**
- **Heartbeat** (every 15 s): `block_subsidy / active_providers × compute_multiplier`
- **AI Training Task**: `0.05 TRP × quality_score`
- **Fraud Check Task**: `0.001 TRP × accuracy`

**Requirements:** Python 3.8+, `pip install requests psutil numpy`

---

## Run a Full Node

See [NODE_SETUP.md](NODE_SETUP.md) for the complete guide. Quick reference:

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

# 1. Install Python dependencies
pip install -r requirements.txt

# 2. Start Python AI service (port 8000)
cd python-ai-service
uvicorn app.main_simplified:app --host 0.0.0.0 --port 8000

# 3. Start Go consensus node (port 8081) in another terminal
./go-consensus/trispi-consensus -id node1 -http 8081 -port 50051

# 4. Register your node with mainnet
curl -X POST https://trispi.org/api/network/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id":   "my_node_01",
    "address":   "YOUR_PUBLIC_IP:50051",
    "node_type": "full_node"
  }'
```

### Become a Validator (requires 10,000 TRP stake)

```bash
curl -X POST https://trispi.org/api/validators/stake \
  -H "Content-Type: application/json" \
  -d '{
    "validator": "my_node_01",
    "amount":    10000
  }'
```

---

## Create a Blockchain on TRISPI

TRISPI lets you scaffold a full parachain project and connect it as a subnet. See [docs/BLOCKCHAIN_CREATION.md](docs/BLOCKCHAIN_CREATION.md) for the full guide.

### Scaffold in one command

```bash
# Go parachain:
curl -X POST https://trispi.org/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name":   "my-chain",
    "language":     "go",
    "block_time":   15,
    "token_name":   "MYTOKEN",
    "token_symbol": "MYT"
  }' -o my-chain.zip

# Rust / CosmWasm:
curl -X POST https://trispi.org/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{"chain_name":"my-chain","language":"rust","block_time":10}' \
  -o my-chain.zip

# Solidity / EVM (Hardhat):
curl -X POST https://trispi.org/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{"chain_name":"my-chain","language":"solidity","block_time":12}' \
  -o my-chain.zip
```

### Connect to TRISPI mainnet

```bash
unzip my-chain.zip -d my-chain
cd my-chain

# The included script registers your chain and starts syncing:
bash connect-to-trispi.sh

# Or point at a specific node:
TRISPI_NODE_URL=http://YOUR_NODE:8000 bash connect-to-trispi.sh
```

---

## Smart Contracts

TRISPI supports **Solidity (EVM)** and **WebAssembly (WASM)** contracts natively.

```bash
# Deploy a Solidity contract:
curl -X POST https://trispi.org/api/engine/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "creator":   "trp1YOUR_ADDRESS",
    "bytecode":  "0x6080604052...",
    "runtime":   "evm",
    "gas_limit": 3000000
  }'

# Deploy a WASM contract:
curl -X POST https://trispi.org/api/engine/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "creator":  "trp1YOUR_ADDRESS",
    "bytecode": "AGFzbQE...",
    "runtime":  "wasm"
  }'

# Call a contract:
curl -X POST https://trispi.org/api/engine/call \
  -H "Content-Type: application/json" \
  -d '{
    "caller":           "trp1YOUR_ADDRESS",
    "contract_address": "trp1CONTRACT",
    "method":           "transfer",
    "args":             ["trp1RECIPIENT", 1000],
    "gas_limit":        100000
  }'
```

See [contracts/examples/](contracts/examples/) for full templates.

---

## SDK & API

### TypeScript SDK

```typescript
import { TrispiClient } from './sdk/typescript';

const client = new TrispiClient('https://trispi.org');

// Get balance
const balance = await client.getBalance('trp1YOUR_ADDRESS');

// Transfer TRP
await client.transfer({
  from:   'trp1sender',
  to:     'trp1recipient',
  amount: 100
});

// Get network overview
const network = await client.getNetworkOverview();
```

### Python SDK

```python
import requests

NODE = "https://trispi.org"

# Balance
r = requests.get(f"{NODE}/api/balance/trp1YOUR_ADDRESS")
print(r.json())  # {"address": "trp1...", "balance": 1250.75}

# Transfer
r = requests.post(f"{NODE}/api/tokens/transfer", json={
    "from_address": "trp1sender",
    "to_address":   "trp1recipient",
    "amount":       100.0
})

# Deploy contract
r = requests.post(f"{NODE}/api/engine/deploy", json={
    "creator":  "trp1YOUR_ADDRESS",
    "bytecode": "0x6080...",
    "runtime":  "evm"
})
```

**Full API reference:** [docs/API.md](docs/API.md)

---

## Repository Structure

```
TRISPI/
├── contracts/                # Smart contract examples & templates
│   ├── examples/             #   Solidity (EVM) + WASM + Hybrid
│   └── templates/            #   Starter templates
├── docs/                     # Developer documentation
│   ├── API.md                #   Full REST API reference
│   ├── BLOCKCHAIN_CREATION.md#   Create & connect a blockchain
│   ├── NODE_OPERATOR_GUIDE.md#   Node operator guide
│   └── WHITEPAPER.md         #   Technical whitepaper
├── energy-provider/          # Energy Provider scripts (earn TRP)
│   ├── trispi_energy_provider.py
│   └── README.md
├── examples/                 # API usage examples (Python, JS, curl)
│   ├── deploy_contract.py
│   ├── energy_provider.py
│   ├── query_api.py
│   └── build-a-node/
├── miner/                    # Mining client
├── scripts/                  # Utility scripts
│   └── join-network.py       #   Auto-connect your node to mainnet
├── sdk/                      # TypeScript & Python SDK
│   ├── typescript/
│   └── python/
├── docker-compose.trispi.yml # Full stack Docker
├── docker-compose.node.yml   # Single node Docker
├── genesis.json              # Network genesis block
├── NODE_SETUP.md             # Complete node setup guide
├── WHITEPAPER.md             # TRISPI Whitepaper
└── CONTRIBUTING.md           # How to contribute
```

---

## Community

| Platform | Link |
|----------|------|
| 🌐 Website | [trispi.org](https://trispi.org) |
| 💬 Telegram | [@trispiainetwork](https://t.me/trispiainetwork) |
| 🐦 X / Twitter | [@trispinetwork](https://x.com/trispinetwork) |
| 💼 LinkedIn | [TRISPI AI Network](https://linkedin.com/company/trispi-ai-network) |
| 🐙 GitHub | [TRISPIAINETWORK](https://github.com/TRISPIAINETWORK) |

---

## Contributing

We welcome all contributions!

- 🐛 **Bug reports** → [GitHub Issues](https://github.com/TRISPIAINETWORK/TRISPI/issues)
- 💡 **Feature requests** → [GitHub Discussions](https://github.com/TRISPIAINETWORK/TRISPI/discussions)
- 🔒 **Security** → see [CONTRIBUTING.md](CONTRIBUTING.md)
- 📖 **Docs / code** → open a Pull Request to `main`

---

## License

MIT License — see [LICENSE](LICENSE).
