# Creating a Blockchain on TRISPI

This guide walks you through scaffolding a custom parachain and connecting it to the TRISPI network as a subnet.

---

## Overview

TRISPI supports three runtimes for custom chains:

| Runtime | Language | Use Case |
|---------|----------|----------|
| **Go** | Go + libp2p + PBFT | Same stack as TRISPI core — best for full nodes |
| **Rust / CosmWasm** | Rust + WASM | Smart-contract-heavy chains |
| **Solidity / EVM** | Hardhat + EVM | Ethereum-compatible chains |

---

## Step 1 — Scaffold the Project

Use the TRISPI scaffold API to generate a complete ready-to-run project ZIP.

### Via curl

```bash
export TRISPI_NODE_URL=https://trispi.org

# Go chain:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name":   "my-chain",
    "language":     "go",
    "block_time":   15,
    "token_name":   "MYTOKEN",
    "token_symbol": "MYT"
  }' -o my-chain.zip

# Rust / CosmWasm:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name":   "my-chain",
    "language":     "rust",
    "block_time":   10
  }' -o my-chain.zip

# Solidity / EVM:
curl -X POST $TRISPI_NODE_URL/api/chains/scaffold \
  -H "Content-Type: application/json" \
  -d '{
    "chain_name":   "my-chain",
    "language":     "solidity",
    "block_time":   12
  }' -o my-chain.zip
```

### Scaffold API parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `chain_name` | string | ✅ | Letters, digits, hyphens, underscores only |
| `language` | string | ✅ | `go`, `rust`, or `solidity` |
| `block_time` | integer | — | Target block time in seconds (default: 15) |
| `token_name` | string | — | Native token name (default: `MYTOKEN`) |
| `token_symbol` | string | — | Token ticker (default: `MYT`) |
| `chain_id` | string | — | Custom chain ID (auto-generated if omitted) |
| `rpc_url` | string | — | TRISPI hub RPC (defaults to `https://trispi.org`) |
| `validators` | array | — | Initial validator addresses |

---

## Step 2 — Extract and Explore the ZIP

```bash
unzip my-chain.zip -d my-chain
cd my-chain
ls
```

### Go scaffold contents
```
main.go                 — Entry point
consensus/node.go       — PBFT consensus engine
p2p/node.go             — libp2p peer-to-peer layer
go.mod                  — Go module file
Dockerfile              — Container build
connect-to-trispi.sh    — Auto-register with TRISPI mainnet
README.md               — Chain-specific instructions
```

### Rust scaffold contents
```
Cargo.toml              — Rust manifest
src/contract.rs         — CosmWasm contract logic
src/state.rs            — On-chain state definitions
src/msg.rs              — Message types
src/error.rs            — Error handling
build.sh                — WASM compile script
Dockerfile
connect-to-trispi.sh
README.md
```

### Solidity scaffold contents
```
contracts/
  ChainRegistry.sol     — On-chain registry
  BridgeVault.sol       — Token bridge vault
hardhat.config.js       — Hardhat configuration
scripts/deploy.js       — Deployment script
package.json
connect-to-trispi.sh
README.md
```

---

## Step 3 — Run Your Chain Locally

### Go
```bash
cd my-chain
go mod tidy
go run main.go
```

### Rust / CosmWasm
```bash
cd my-chain
cargo build --target wasm32-unknown-unknown --release
bash build.sh
```

### Solidity / EVM
```bash
cd my-chain
npm install
npx hardhat node       # local EVM
npx hardhat run scripts/deploy.js --network localhost
```

---

## Step 4 — Connect to TRISPI Mainnet

Each scaffold includes `connect-to-trispi.sh`. Run it once your chain is up:

```bash
# Connect to TRISPI mainnet:
bash connect-to-trispi.sh

# Or connect to a specific node:
TRISPI_NODE_URL=http://YOUR_NODE_IP:8000 bash connect-to-trispi.sh
```

The script:
1. Registers your chain in the TRISPI parachain registry
2. Submits your genesis hash and validator set
3. Opens an IBC channel for cross-chain transfers
4. Starts syncing your chain with the TRISPI hub

---

## Step 5 — Register Manually (Optional)

If you prefer to register without the script:

```bash
curl -X POST https://trispi.org/api/chains/register \
  -H "Content-Type: application/json" \
  -d '{
    "name":          "my-chain",
    "genesis_hash":  "0xYOUR_GENESIS_HASH",
    "validators":    ["trp1val1", "trp1val2"],
    "ibc_endpoint":  "http://YOUR_CHAIN_IP:8000/api"
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

> ⚠️ Copy `admin_secret` immediately — it is shown **once only**. Save it to `.trispi-admin-secret` (chmod 600). Use it as the `X-Admin-Token` header for future admin operations.

---

## Step 6 — Submit Block Headers (Keep Chain Live)

Your chain must submit headers to TRISPI regularly to stay active:

```bash
# Submit a block header:
curl -X POST https://trispi.org/api/chain/sync-block \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: YOUR_ADMIN_SECRET" \
  -d '{
    "chain_id":    "your-chain-uuid",
    "block_hash":  "0xABC...",
    "block_height": 1234,
    "timestamp":   1700000000
  }'

# Bootstrap your chain from a peer:
curl https://trispi.org/api/network/bootstrap
```

---

## Cross-Chain Transfers (IBC)

Once your chain is registered and an IBC channel is open, you can transfer TRP between chains:

```bash
# Transfer TRP from TRISPI mainnet to your chain:
curl -X POST https://trispi.org/api/ibc/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "from_chain": "trispi-mainnet-1",
    "to_chain":   "my-chain-uuid",
    "sender":     "trp1sender",
    "recipient":  "trp1recipient",
    "token":      "TRP",
    "amount":     100.0
  }'
```

---

## Architecture Overview

```
┌──────────────────────────────┐
│   TRISPI mainnet (hub)       │
│   • ChainRegistry            │
│   • /api/chains              │
└──────────────▲───────────────┘
               │  registerChain / submitHeader
 ┌─────────────┼─────────────┐
 │             │             │
┌──┴───────┐  ┌──┴───────┐  ┌──┴───────┐
│  chainA  │  │  chainB  │  │  chainN  │
│  Bridge  │◀▶│  Bridge  │◀▶│  Bridge  │
└──────────┘  └──────────┘  └──────────┘
                    ▲
                    │  trispi-relayer (Go)
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `chain_name` rejected | Use only letters, digits, hyphens, underscores |
| Registration 401 | Wrong or missing `X-Admin-Token` header |
| Chain shows as revoked | Submit a header within 24h to keep it active |
| IBC transfer fails | Ensure an open channel exists between both chains |
| Scaffold ZIP empty | Check API response for validation errors |

---

## Related

- [docs/API.md](API.md) — Full API reference including `/api/chains/*` endpoints
- [docs/NODE_OPERATOR_GUIDE.md](NODE_OPERATOR_GUIDE.md) — Running a TRISPI node
- [examples/](../examples/) — Code examples in Python, JavaScript, Go
