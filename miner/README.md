# TRISPI Miner / Energy Provider

The TRISPI "miner" is an **Energy Provider** — you earn TRP by contributing compute power to the AI network, not by burning electricity on hash puzzles.

---

## Run Locally (5 minutes)

### Step 1 — Download

```bash
# Clone the full repo:
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI/miner

# Or download just this file:
curl -O https://raw.githubusercontent.com/TRISPIAINETWORK/TRISPI/main/miner/trispi_energy_provider.py
```

### Step 2 — Install dependencies

```bash
pip install requests psutil
```

That's all. No blockchain sync, no 100GB download.

### Step 3 — Run

```bash
# Connect to mainnet and start earning:
python3 trispi_energy_provider.py

# With your wallet address (to track earnings):
python3 trispi_energy_provider.py --wallet trp1YOUR_ADDRESS

# With a custom node name:
python3 trispi_energy_provider.py --id my_gaming_pc
```

### Step 4 — Check earnings

```bash
# Check your balance (replace with your wallet address):
curl https://trispi.org/api/balance/trp1YOUR_ADDRESS

# Or view on the web dashboard:
# Open https://trispi.org → Wallet tab → paste your address
```

---

## Options

```
python3 trispi_energy_provider.py [OPTIONS]

Options:
  --wallet ADDR    Your TRP wallet address (optional, auto-generated if not set)
  --id NAME        Your node identifier (default: trispi_<random>)
  --api URL        API endpoint (default: https://trispi.org)
  --interval N     Heartbeat interval in seconds (default: 10)
```

---

## How It Works

```
1. Register your node on the network
2. Start session (get session ID)
3. Every 10 seconds:
   a. Send heartbeat → earn base TRP reward
   b. Check for AI task (matrix ops, model inference, etc.)
   c. Compute task → earn bonus TRP reward
4. Repeat forever
```

**Reward formula:**
- Heartbeat: `block_subsidy / active_providers × compute_multiplier`
- Task: `task_weight × quality_score`

---

## Keep Running 24/7 (Linux server)

```bash
# Option A — screen/tmux
screen -S trispi
python3 trispi_energy_provider.py --wallet trp1YOUR
# Ctrl+A, D to detach

# Option B — systemd service (auto-start on reboot)
sudo tee /etc/systemd/system/trispi.service << SVCEOF
[Unit]
Description=TRISPI Energy Provider
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$(pwd)
ExecStart=/usr/bin/python3 $(pwd)/trispi_energy_provider.py --wallet trp1YOUR
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable --now trispi
sudo journalctl -u trispi -f
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError` | `pip install requests psutil` |
| `ConnectionError` | Check internet; try `ping trispi.org` |
| Reward is 0 | Wait 1-2 minutes; may be in low-provider window |
| Session expired | Script auto-reconnects in ~30 seconds |

---

## Minimum Requirements

- Python 3.7+
- 1 CPU core, 512 MB RAM
- Internet connection (100 KB/s is enough)
- Any OS: Linux, macOS, Windows, Raspberry Pi

No GPU required (bonus rewards with GPU in future updates).
