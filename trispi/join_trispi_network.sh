#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
#  TRISPI Network — Full Node Join Script
#  Автоматически скачивает цепочку, настраивает и запускает полный нод.
#
#  Использование:
#    bash join_trispi_network.sh
#
#  Или с указанием bootstrap нода:
#    TRISPI_BOOTSTRAP=https://trispi-mainnet.replit.app bash join_trispi_network.sh
#
#  Требования: Docker 24+, docker compose v2, curl, python3
# ═══════════════════════════════════════════════════════════════════════════════
set -euo pipefail

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

BOOTSTRAP="${TRISPI_BOOTSTRAP:-https://trispi-mainnet.replit.app}"
NODE_ID="${NODE_ID:-node-$(hostname | tr -d '.-' | head -c12)}"
DATA_DIR="${DATA_DIR:-$HOME/.trispi}"
TRISPI_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

banner() {
  echo -e "${CYAN}"
  echo "  ████████╗██████╗ ██╗███████╗██████╗ ██╗"
  echo "     ██╔══╝██╔══██╗██║██╔════╝██╔══██╗██║"
  echo "     ██║   ██████╔╝██║███████╗██████╔╝██║"
  echo "     ██║   ██╔══██╗██║╚════██║██╔═══╝ ██║"
  echo "     ██║   ██║  ██║██║███████║██║     ██║"
  echo "     ╚═╝   ╚═╝  ╚═╝╚═╝╚══════╝╚═╝     ╚═╝"
  echo -e "${NC}"
  echo -e "${BOLD}  TRISPI Network — Full Node Setup v3.0${NC}"
  echo "  ─────────────────────────────────────────"
}

log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*" >&2; }
step() { echo -e "\n${BOLD}${CYAN}▶ $*${NC}"; }

# ── 1. Проверка зависимостей ──────────────────────────────────────────────────
banner

step "Checking prerequisites"

check_cmd() {
  if ! command -v "$1" &>/dev/null; then
    err "$1 is required but not installed."
    echo "  Install: $2"
    exit 1
  fi
  log "$1 found"
}

check_cmd docker  "https://docs.docker.com/get-docker/"
check_cmd curl    "apt install curl / brew install curl"
check_cmd python3 "apt install python3 / brew install python3"

# Check docker compose v2
if ! docker compose version &>/dev/null; then
  err "docker compose v2 required. Install: https://docs.docker.com/compose/install/"
  exit 1
fi
log "docker compose v2 found"

DOCKER_VERSION=$(docker --version | grep -oP '\d+' | head -1)
if [[ "$DOCKER_VERSION" -lt 24 ]]; then
  warn "Docker $DOCKER_VERSION detected — recommend Docker 24+"
fi

# ── 2. Проверка доступности bootstrap нода ───────────────────────────────────
step "Connecting to bootstrap node: $BOOTSTRAP"

SNAPSHOT_URL="$BOOTSTRAP/api/chain/snapshot"
if ! curl -sf --max-time 15 "$SNAPSHOT_URL" -o /tmp/trispi_snapshot.json; then
  err "Cannot reach bootstrap node at $BOOTSTRAP"
  err "Check: curl $SNAPSHOT_URL"
  exit 1
fi

BLOCK_HEIGHT=$(python3 -c "import json; d=json.load(open('/tmp/trispi_snapshot.json')); print(d.get('block_height',0))")
TOTAL_ACCOUNTS=$(python3 -c "import json; d=json.load(open('/tmp/trispi_snapshot.json')); print(d.get('total_accounts',0))")
BOOTSTRAP_PEER=$(python3 -c "
import json
d=json.load(open('/tmp/trispi_snapshot.json'))
peers = d.get('bootstrap_peers', [])
print(peers[0].get('p2p_addr','') if peers else '')
")

log "Bootstrap node OK"
log "  Chain height: $BLOCK_HEIGHT blocks"
log "  Total accounts: $TOTAL_ACCOUNTS"
log "  P2P addr: $BOOTSTRAP_PEER"

# ── 3. Создание директорий ────────────────────────────────────────────────────
step "Creating data directories"

mkdir -p "$DATA_DIR"/{chain,state,secrets,logs}
log "Data dir: $DATA_DIR"

# ── 4. Скачивание genesis state ───────────────────────────────────────────────
step "Downloading genesis state (${TOTAL_ACCOUNTS} accounts)"

GENESIS_URL="$BOOTSTRAP/api/chain/genesis-state"
if curl -sf --max-time 60 "$GENESIS_URL" -o "$DATA_DIR/state/genesis_state.json"; then
  SAVED_ACCOUNTS=$(python3 -c "
import json
d=json.load(open('$DATA_DIR/state/genesis_state.json'))
print(len(d.get('balances',{})))
")
  log "Genesis state saved: $SAVED_ACCOUNTS accounts"
else
  warn "Could not download genesis state — node will sync from scratch"
fi

# ── 5. Скачивание блоков (первичная синхронизация) ────────────────────────────
step "Syncing blocks (height=$BLOCK_HEIGHT)"

BLOCK_SYNC_URL="$BOOTSTRAP/api/chain/blocks?from=0&limit=500"
if curl -sf --max-time 120 "$BLOCK_SYNC_URL" -o "$DATA_DIR/chain/chain_snapshot.json"; then
  SAVED_BLOCKS=$(python3 -c "
import json
d=json.load(open('$DATA_DIR/chain/chain_snapshot.json'))
print(d.get('count', len(d.get('blocks',[]))))
")
  log "Downloaded $SAVED_BLOCKS blocks"
else
  warn "Block download failed — node will sync via P2P"
fi

# ── 6. Генерация конфигурации ─────────────────────────────────────────────────
step "Generating node configuration"

DB_PASSWORD="$(python3 -c "import secrets; print(secrets.token_hex(16))")"
NODE_SECRET="$(python3 -c "import secrets; print(secrets.token_hex(24))")"

cat > "$TRISPI_DIR/.env.node" <<EOF
# TRISPI Node — сгенерировано join_trispi_network.sh $(date -Iseconds)
NODE_ID=$NODE_ID
DB_PASSWORD=$DB_PASSWORD
BLOCK_MINED_SECRET=$NODE_SECRET
GOVERNANCE_SECRET=
TRISPI_BOOTSTRAP=$BOOTSTRAP
TRISPI_BOOTSTRAP_PEER=$BOOTSTRAP_PEER
DATA_DIR=$DATA_DIR
EOF

log "Config written to .env.node"
log "Node ID: $NODE_ID"

# ── 7. Запуск стека ───────────────────────────────────────────────────────────
step "Starting TRISPI node (docker compose)"

cd "$TRISPI_DIR"

echo ""
echo -e "${BOLD}Building Docker images (first run takes 3-5 min)...${NC}"
docker compose --env-file .env.node build --parallel 2>&1 | tail -5

echo ""
echo -e "${BOLD}Starting services...${NC}"
docker compose --env-file .env.node up -d

# ── 8. Health check ───────────────────────────────────────────────────────────
step "Waiting for services to start"

echo -n "  Python AI: "
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health &>/dev/null; then
    echo -e "${GREEN}OK${NC} (${i}×2s)"
    break
  fi
  echo -n "."
  sleep 2
  if [[ $i -eq 30 ]]; then echo -e " ${YELLOW}timeout — check: docker compose logs trispi-python${NC}"; fi
done

echo -n "  Go Consensus: "
for i in $(seq 1 15); do
  if curl -sf http://localhost:8181/health &>/dev/null; then
    echo -e "${GREEN}OK${NC} (${i}×2s)"
    break
  fi
  echo -n "."
  sleep 2
  if [[ $i -eq 15 ]]; then echo -e " ${YELLOW}timeout — check: docker compose logs trispi-go${NC}"; fi
done

# ── 9. Итог ──────────────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}════════════════════════════════════════════════${NC}"
echo -e "${BOLD}${GREEN}  ✓ TRISPI Node is running!${NC}"
echo -e "${CYAN}════════════════════════════════════════════════${NC}"
echo ""
echo "  Frontend:      http://localhost:5000"
echo "  Python API:    http://localhost:8000/api/health"
echo "  Go Consensus:  http://localhost:8181/health"
echo "  Chain Snapshot: http://localhost:8000/api/chain/snapshot"
echo ""
echo "  Useful commands:"
echo "    docker compose logs -f          — show all logs"
echo "    docker compose logs trispi-go   — Go consensus logs"
echo "    docker compose ps               — service status"
echo "    docker compose down             — stop node"
echo ""
echo "  Open port 50052 on your firewall for P2P peering:"
echo "    sudo ufw allow 50052/tcp"
echo ""
echo -e "${BOLD}  Your P2P address (share with other nodes):${NC}"
echo "    /ip4/$(curl -sf ifconfig.me 2>/dev/null || echo '<your-public-ip>')/tcp/50052/p2p/$(cat /tmp/trispi_snapshot.json | python3 -c "import json,sys; d=json.load(sys.stdin); peers=d.get('bootstrap_peers',[]); print(peers[0].get('p2p_addr','').split('/')[-1] if peers else '<peer-id>')" 2>/dev/null || echo '<peer-id>')"
echo ""
