# TRISPI Energy Provider

Earn TRP tokens by contributing your CPU/GPU compute power to the TRISPI AI network.

---

## What is an Energy Provider?

An Energy Provider is a node that:
1. **Runs AI inference tasks** sent by the network (matrix operations, model inference, etc.)
2. **Sends heartbeats** every 10 seconds to prove it's alive
3. **Earns TRP tokens** automatically for both heartbeats and completed tasks

No blockchain knowledge required — just run the script and earn.

---

## Quick Start

```bash
# Install dependencies (just 2 packages):
pip install requests psutil

# Run with default settings (connects to trispi.org):
python3 trispi_energy_provider.py

# Run with your wallet address:
python3 trispi_energy_provider.py --wallet trp1YOUR_WALLET_ADDRESS

# Run with custom node ID:
python3 trispi_energy_provider.py --id my_server_01

# Run against a local node:
python3 trispi_energy_provider.py --api http://localhost:8000
```

---

## Command Line Options

| Option | Default | Description |
|--------|---------|-------------|
| `--api` | `https://trispi.org` | TRISPI API endpoint |
| `--wallet` | auto-generated | Your TRP wallet address |
| `--id` | `trispi_<random>` | Node identifier |
| `--interval` | `10` | Heartbeat interval in seconds |

---

## How Rewards Work

### Heartbeat Reward (every 10 seconds)
```
reward = (current_block_subsidy / active_providers) × compute_multiplier
```
- `block_subsidy` decreases with each halving epoch
- `compute_multiplier` = 1.0 to 2.0 based on your CPU cores / RAM

### Task Reward (per completed AI task)
```
reward = task_weight × quality_score
```
- `task_weight` = 0.5 to 10.0 depending on task complexity
- `quality_score` = 0.0 to 1.0 based on result accuracy

### Example earnings (approximate)
| Setup | Estimated TRP/day |
|-------|-------------------|
| 1 core, 2 GB RAM | ~50-150 TRP |
| 4 cores, 8 GB RAM | ~200-600 TRP |
| 8 cores, 16 GB RAM | ~500-1500 TRP |
| GPU (any) | ~1000-5000 TRP |

---

## Run as Background Service (Linux)

```bash
# Create systemd service:
sudo tee /etc/systemd/system/trispi-provider.service << SVCEOF
[Unit]
Description=TRISPI Energy Provider
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/trispi_energy_provider.py --wallet trp1YOUR_ADDRESS
Restart=always
RestartSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
SVCEOF

# Enable and start:
sudo systemctl daemon-reload
sudo systemctl enable --now trispi-provider

# View logs:
sudo journalctl -u trispi-provider -f

# Stop:
sudo systemctl stop trispi-provider
```

---

## Run as Background Process (any OS)

```bash
# Linux/macOS — run in background with nohup:
nohup python3 trispi_energy_provider.py --wallet trp1YOUR > provider.log 2>&1 &
echo "PID: $!"

# View logs:
tail -f provider.log

# Stop:
kill $(cat provider.pid)

# Windows — run in a new window:
start pythonw trispi_energy_provider.py --wallet trp1YOUR
```

---

## Docker

```bash
# Run in Docker:
docker run -d \
  --name trispi-provider \
  --restart always \
  -e WALLET=trp1YOUR_ADDRESS \
  python:3.11-slim \
  sh -c "pip install requests psutil && python3 trispi_energy_provider.py --wallet $WALLET"
```

---

## Check Your Balance

After running for a few minutes, check your earned TRP:

```bash
# Via the API (replace with your node ID or wallet):
curl https://trispi.org/api/balance/trp1YOUR_ADDRESS

# Or check provider stats:
curl https://trispi.org/api/ai-energy/providers | python3 -m json.tool
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ConnectionError: trispi.org` | Check internet connection |
| `ModuleNotFoundError: requests` | `pip install requests psutil` |
| Heartbeat shows 0 reward | Wait 1-2 minutes for first epoch |
| Session expired | Script auto-reconnects — wait 30s |
| Balance not visible on site | Connect wallet at trispi.org |

---

## API Flow (for developers)

The script uses these API calls in sequence:

```
POST /api/ai-energy/register        # Register as provider
POST /api/ai-energy/start-session   # Get session ID
POST /api/ai-energy/heartbeat       # Every 10s → earn TRP
GET  /api/ai-energy/task/{node_id}  # Get AI task
POST /api/ai-energy/submit          # Submit result → earn TRP
```

See [examples/energy_provider.py](../examples/energy_provider.py) for a minimal implementation example.
