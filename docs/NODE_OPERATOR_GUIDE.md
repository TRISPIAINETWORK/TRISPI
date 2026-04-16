# TRISPI Node Operator Guide

## Running a TRISPI Node

### Prerequisites

- Docker and Docker Compose
- 4+ CPU cores, 8GB+ RAM, 100GB+ disk
- Stable internet connection

### Quick Start

```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI-network-

# Start the node
docker-compose -f docker-compose.trispi.yml up -d

# Check health
curl http://localhost:8001/api/health
curl http://localhost:8001/api/network/status
```

### Node Types

| Type | Description | Extra Requirements |
|------|-------------|-------------------|
| Full Node | Stores entire chain, validates blocks | Default config |
| Validator | Participates in PBFT+PoI consensus | TRP stake required |
| Energy Provider | Provides CPU/GPU for AI tasks | Run miner script |
| RPC Node | Public API for dApp developers | Additional bandwidth |

### Configuration

Environment variables for the node:

| Variable | Default | Description |
|----------|---------|-------------|
| `TRISPI_PORT` | `8001` | API port |
| `TRISPI_P2P_PORT` | `30303` | P2P network port |
| `TRISPI_RPC_PORT` | `8545` | JSON-RPC port |
| `TRISPI_WS_PORT` | `8546` | WebSocket port |
| `TRISPI_DATA_DIR` | `./chain_data` | Blockchain data directory |

### Monitoring

The node exposes Prometheus metrics on `/metrics`.

### API Endpoints

```bash
# Network status
curl http://localhost:8001/api/network/status

# Latest blocks
curl http://localhost:8001/api/chain

# AI status
curl http://localhost:8001/api/ai/full-status

# P2P network info
curl http://localhost:8001/api/network/p2p/status

# Consensus status
curl http://localhost:8001/api/network/consensus
```

### Troubleshooting

**Node won't start:**
- Check Docker logs: `docker-compose logs -f`
- Ensure ports 8001, 30303 are not in use

**Not syncing:**
- Check internet connectivity
- Verify bootstrap node is reachable
- Check disk space

**Low rewards:**
- Ensure CPU/GPU is not throttled
- Check that `psutil` is installed for accurate metrics
