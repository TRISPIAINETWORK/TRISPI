# TRISPI — The Autonomous AI Blockchain Network

> **Web4 · AI-Powered · Post-Quantum Secure · EVM + WASM**

[![Website](https://img.shields.io/badge/Website-trispi.org-blue)](https://trispi.org)


---

## What is TRISPI?

TRISPI is a next-generation **Web4 blockchain** where AI agents act as validators, smart contracts self-heal, and your compute power fuels an autonomous intelligence network.

| Feature | Description |
|---------|-------------|
| **Proof of Intelligence (PoI)** | AI-based consensus — models validate transactions |
| **Post-Quantum Security** | Ed25519 + Dilithium3 (NIST PQC) hybrid signatures |
| **EVM + WASM** | Run Solidity and WebAssembly contracts on the same chain |
| **Energy Provider System** | Earn TRP by contributing compute to the network |
| **PBFT Consensus** | Byzantine-fault-tolerant, ~3 second block time |
| **Chain ID 7878** | MetaMask / EVM wallet compatible |

---

## Quick Start

### Option 1 — Energy Provider (earn TRP in 5 minutes)

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI
pip install requests psutil numpy
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# With GPU (NVIDIA):
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS --gpu
```

### Option 2 — Run a Full Node

```bash
# Join mainnet automatically
python3 scripts/join-network.py --public-ip YOUR_IP

# With continuous sync monitoring
python3 scripts/join-network.py --public-ip YOUR_IP --monitor
```

### Option 3 — Docker

```bash
# Full TRISPI stack:
docker-compose -f docker-compose.trispi.yml up -d

# Single node only:
docker-compose -f docker-compose.node.yml up -d
```

---

## Repository Structure

```
TRISPI/
├── .github/                  # GitHub templates (issues, PRs, security)
├── contracts/                # Smart contract examples
│   ├── examples/             #   Solidity (EVM) + WASM + Hybrid
│   └── templates/            #   Starter templates
├── docs/                     # Developer documentation
│   ├── API.md                #   Full REST API reference
│   ├── ARCHITECTURE.md       #   System architecture
│   └── NODE_OPERATOR_GUIDE.md#   Node operator guide
├── energy-provider/          # Energy Provider scripts (earn TRP)
│   ├── trispi_energy_provider.py
│   └── README.md
├── examples/                 # API usage examples (Python, Go, curl)
│   ├── deploy_contract.py
│   └── build-a-node/
├── miner/                    # Mining client
│   └── trispi_energy_provider.py
├── scripts/                  # Utility scripts
│   ├── join-network.py       #   Connect your node to mainnet
│   └── trispi_energy_provider.py
├── sdk/                      # TypeScript & Python SDK
├── docker-compose.trispi.yml # Full stack Docker
├── docker-compose.node.yml   # Single node Docker
├── genesis.json              # Network genesis block
├── .env.example              # Environment variables template
├── NODE_SETUP.md             # Node setup guide
├── WHITEPAPER.md             # TRISPI Whitepaper
└── CONTRIBUTING.md           # How to contribute
```

---

## Network Details

| Parameter | Value |
|-----------|-------|
| Chain ID | `7878` |
| Token Symbol | `TRP` |
| Total Supply | `50,000,000 TRP` |
| Block Time | `~10 seconds` |
| Blocks Produced | `5,000+` |
| Consensus | `PoI + PBFT` |
| AI Engine | `NumPy Federated Learning (real)` |
| Post-Quantum | `Ed25519 + Dilithium3 (NIST PQC)` |
| RPC Endpoint | `https://trispi.org/rpc` |
| Explorer | `https://trispi.org` (Explorer tab) |
| AI Accuracy | grows from 60% → 99% via training |

### Add to MetaMask

1. MetaMask → **Add Network** → **Add manually**
2. **Network Name**: `TRISPI Mainnet`
3. **RPC URL**: `https://trispi.org/rpc`
4. **Chain ID**: `7878`
5. **Currency Symbol**: `TRP`

---

## Energy Provider — Earn TRP

Earn TRP tokens by contributing your **real** CPU/GPU compute to the TRISPI AI network.

The client downloads a neural network, runs **real NumPy gradient descent** on your hardware,
and submits the gradients back — this is genuine federated learning.

```bash
# Install:
pip install requests psutil numpy

# Run (CPU):
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# Run (GPU — NVIDIA):
python3 energy-provider/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS --gpu

# Run on local node:
python3 energy-provider/trispi_energy_provider.py --server http://localhost:8000 --wallet trp1YOUR_ADDRESS
```

**What your device does:**
1. Downloads AI model weights + training mini-batch from TRISPI node
2. Runs 5 gradient descent steps (real NumPy operations on your CPU/GPU)
3. Sends back the computed gradients (federated averaging)
4. Earns TRP rewards based on compute quality

**Reward formula:**
- **Heartbeat** (every 15s): `block_subsidy / active_providers × compute_multiplier`
- **AI Training Task**: `0.05 TRP × quality_score` (real federated gradient)
- **Fraud Check Task**: `0.001 TRP × accuracy`

**Requirements:** Python 3.8+, `pip install requests psutil numpy`

---

## Smart Contracts

TRISPI supports **Solidity (EVM)** and **WebAssembly (WASM)** contracts natively:

```bash
# Deploy a Solidity contract:
curl -X POST https://trispi.org/api/engine/deploy \
  -H "Content-Type: application/json" \
  -d '{"creator":"trp1...","bytecode":"0x6080...","runtime":"evm"}'

# Deploy a WASM contract:
curl -X POST https://trispi.org/api/engine/deploy \
  -H "Content-Type: application/json" \
  -d '{"creator":"trp1...","bytecode":"AGFzbQE...","runtime":"wasm"}'
```

See [contracts/examples/](contracts/examples/) for templates.

---

## API Quick Reference

Base URL: `https://trispi.org`

```bash
# Health:
curl https://trispi.org/health

# Latest blocks:
curl https://trispi.org/api/explorer/blocks?limit=10

# Wallet balance:
curl https://trispi.org/api/balance/trp1YOUR_ADDRESS

# Transfer TRP:
curl -X POST https://trispi.org/api/tokens/transfer \
  -d '{"from_address":"trp1...","to_address":"trp1...","amount":100}'

# Register your node:
curl -X POST https://trispi.org/api/network/peers/register \
  -d '{"node_id":"my_node","address":"IP:50051","node_type":"full_node"}'

# MetaMask RPC:
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
```

---

## Contributing

We welcome all contributions!

- 🐛 **Bug reports** → [.github/ISSUE_TEMPLATE/bug_report.md](.github/ISSUE_TEMPLATE/bug_report.md)
- 💡 **Feature requests** → [.github/ISSUE_TEMPLATE/feature_request.md](.github/ISSUE_TEMPLATE/feature_request.md)
- 🔒 **Security** → [.github/SECURITY.md](.github/SECURITY.md)
- 📖 **Contributing guide** → [CONTRIBUTING.md](CONTRIBUTING.md)

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

## License

MIT License — see [LICENSE](LICENSE).
