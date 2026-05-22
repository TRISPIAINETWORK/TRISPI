# TRISPI Node Operator Guide

A complete guide to running every type of TRISPI node.

---

## Table of Contents

1. [Node Types](#1-node-types)
2. [Requirements](#2-requirements)
3. [Quick Start — Docker](#3-quick-start--docker)
4. [Manual Setup](#4-manual-setup)
5. [Join the Mainnet](#5-join-the-mainnet)
6. [Run as a Validator](#6-run-as-a-validator)
7. [Configuration Reference](#7-configuration-reference)
8. [Monitoring](#8-monitoring)
9. [Systemd Service](#9-systemd-service)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Node Types

| Type | Description | Minimum Stake |
|------|-------------|---------------|
| **Full Node** | Stores the entire chain, validates blocks | None |
| **Validator Node** | Participates in PoI + PBFT consensus | 10,000 TRP |
| **Energy Provider** | Provides CPU/GPU for AI tasks, earns TRP | None |
| **RPC Node** | Public JSON-RPC endpoint for dApp developers | None |
| **Archive Node** | Full node + complete historical state | None |

---

## 2. Requirements

### Minimum (Full Node)
- **CPU:** 4 cores
- **RAM:** 8 GB
- **Disk:** 100 GB SSD
- **Network:** 100 Mbps, stable
- **OS:** Ubuntu 22.04 / Debian 12 / any Linux with Docker

### Recommended (Validator)
- **CPU:** 8+ cores
- **RAM:** 16 GB
- **Disk:** 500 GB NVMe SSD
- **Network:** 1 Gbps with static public IP
- **Uptime:** 99.9%+

### Software
- Docker 24+ and Docker Compose v2
- Python 3.8+ (for non-Docker setup)
- Go 1.21+ (optional, for building from source)

---

## 3. Quick Start — Docker

The fastest way to run a TRISPI node.

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

# Full stack (Python AI service + Go consensus):
docker-compose -f docker-compose.trispi.yml up -d

# Check status:
docker-compose -f docker-compose.trispi.yml ps
docker-compose -f docker-compose.trispi.yml logs -f

# Health check:
curl http://localhost:8000/health
curl http://localhost:8081/health
```

### Expected health response:
```json
{
  "status": "healthy",
  "block_height": 12345,
  "chain_id": 7878,
  "services": {
    "python_ai": "running",
    "go_consensus": "running"
  }
}
```

---

## 4. Manual Setup

### 4.1 Python AI Service (port 8000)

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI

pip install fastapi uvicorn numpy requests psutil python-multipart websockets

# Start the AI service:
cd python-ai-service
uvicorn app.main_simplified:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 1

# Verify:
curl http://localhost:8000/health
```

### 4.2 Go Consensus Node (port 8081)

```bash
# The pre-built binary is included:
chmod +x go-consensus/trispi-consensus

./go-consensus/trispi-consensus \
  -id   node1 \
  -http 8081 \
  -port 50051

# Verify:
curl http://localhost:8081/health
```

### 4.3 (Optional) Rust Core Bridge (port 6000)

The Rust core provides the EVM + WASM execution bridge over TCP:

```bash
# Build from source (requires Rust 1.75+):
cd contracts/wasm
cargo build --release
./target/release/trispi-core --port 6000
```

---

## 5. Join the Mainnet

### Auto-join with the script

```bash
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP

# With monitoring (keeps connection alive):
python3 scripts/join-network.py --public-ip YOUR_PUBLIC_IP --monitor
```

### Manual peer registration

```bash
curl -X POST https://trispi.org/api/network/peers/register \
  -H "Content-Type: application/json" \
  -d '{
    "node_id":      "my_node_01",
    "address":      "YOUR_PUBLIC_IP:50051",
    "node_type":    "full_node",
    "chain_height": 0
  }'
```

### Sync from the network

```bash
# Bootstrap: get current chain head + peer list
curl https://trispi.org/api/network/bootstrap

# Sync blocks from a peer:
curl -X POST https://trispi.org/api/chain/sync-block \
  -H "Content-Type: application/json" \
  -d '{"peer_url": "https://trispi.org"}'
```

---

## 6. Run as a Validator

Validators participate in PoI + PBFT consensus and earn block rewards.

**Minimum stake:** 10,000 TRP

```bash
# 1. Stake TRP to activate your validator:
curl -X POST https://trispi.org/api/validators/stake \
  -H "Content-Type: application/json" \
  -d '{
    "validator": "my_node_01",
    "amount":    10000
  }'

# 2. Check your validator status:
curl https://trispi.org/api/validators

# 3. Check PoI scores:
curl https://trispi.org/api/poi/scores
```

**Validator rewards:**
- Base block reward: `block_subsidy × stake_weight`
- PoI bonus: up to +50% for high AI accuracy score
- Uptime bonus: +10% for >99% availability

---

## 7. Configuration Reference

Set via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8000` | Python AI service API port |
| `TRISPI_P2P_PORT` | `50051` | Go consensus P2P port |
| `TRISPI_HTTP_PORT` | `8081` | Go consensus HTTP port |
| `TRISPI_RUST_PORT` | `6000` | Rust core bridge TCP port |
| `TRISPI_NODE_ID` | auto | Unique node identifier |
| `TRISPI_DATA_DIR` | `./chain_data` | Blockchain data directory |
| `TRISPI_LOG_LEVEL` | `info` | Logging level: debug/info/warn/error |
| `TRISPI_MAX_PEERS` | `50` | Maximum P2P peer connections |
| `TRISPI_BLOCK_TIME` | `10` | Target block time in seconds |

### `.env` example

```env
PORT=8000
TRISPI_P2P_PORT=50051
TRISPI_HTTP_PORT=8081
TRISPI_NODE_ID=my_node_01
TRISPI_DATA_DIR=/var/trispi/chain_data
TRISPI_LOG_LEVEL=info
```

---

## 8. Monitoring

### API endpoints

```bash
# Network status:
curl http://localhost:8000/api/network/status

# Latest blocks:
curl http://localhost:8000/api/chain

# AI service status:
curl http://localhost:8000/api/ai/full-status

# P2P peer info:
curl http://localhost:8000/api/network/p2p/status

# Consensus state:
curl http://localhost:8081/api/network/consensus

# Prometheus metrics:
curl http://localhost:8000/metrics
```

### Key metrics to watch

| Metric | Healthy Value |
|--------|---------------|
| `block_height` | Increasing ~every 10s |
| `peer_count` | > 3 |
| `ai_accuracy` | > 0.80 |
| `consensus_status` | `active` |
| `disk_usage` | < 90% |

---

## 9. Systemd Service

Run TRISPI as a system service that auto-starts on boot.

```bash
# /etc/systemd/system/trispi.service
[Unit]
Description=TRISPI AI Blockchain Node
After=network.target

[Service]
Type=simple
User=trispi
WorkingDirectory=/opt/trispi
ExecStart=/usr/bin/python3 -m uvicorn app.main_simplified:app \
    --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable trispi
sudo systemctl start trispi
sudo systemctl status trispi

# View logs:
journalctl -u trispi -f
```

---

## 10. Troubleshooting

### Node won't start

```bash
# Check for port conflicts:
ss -tlnp | grep -E '8000|8081|50051|6000'

# View Docker logs:
docker-compose -f docker-compose.trispi.yml logs -f

# Check Python dependencies:
pip install -r requirements.txt --upgrade
```

### Not syncing with mainnet

```bash
# Verify internet connectivity to mainnet:
curl https://trispi.org/health

# Re-register your node:
python3 scripts/join-network.py --public-ip YOUR_IP --force

# Check your firewall allows:
# TCP inbound 50051 (P2P)
# TCP inbound 8081 (HTTP consensus)
ufw allow 50051/tcp
ufw allow 8081/tcp
```

### Low validator rewards

- Ensure `psutil` is installed for accurate CPU metrics: `pip install psutil`
- Check AI accuracy score: `curl http://localhost:8000/api/poi/scores`
- Verify uptime — the node must be online for >95% of blocks

### High memory usage

```bash
# Limit AI model memory:
export TRISPI_AI_MAX_MEMORY_MB=2048

# Reduce peers:
export TRISPI_MAX_PEERS=20
```

---

## Related

- [NODE_SETUP.md](../NODE_SETUP.md) — Quick setup reference
- [docs/API.md](API.md) — Full REST API reference
- [docs/BLOCKCHAIN_CREATION.md](BLOCKCHAIN_CREATION.md) — Create a custom chain
- [CONTRIBUTING.md](../CONTRIBUTING.md) — How to contribute
