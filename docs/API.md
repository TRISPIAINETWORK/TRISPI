# TRISPI REST API Reference

**Base URL:** `https://trispi.org`  
**Local node:** `http://localhost:8000`  
**Swagger UI:** `https://trispi.org/api/docs`  
**GraphQL:** `https://trispi.org/api/graphql`

All endpoints return JSON. POST endpoints accept `Content-Type: application/json`.

---

## Table of Contents

1. [Network & Health](#1-network--health)
2. [Blockchain Explorer](#2-blockchain-explorer)
3. [Wallet & Tokens](#3-wallet--tokens)
4. [Smart Contracts (EVM + WASM)](#4-smart-contracts-evm--wasm)
5. [Energy Provider](#5-energy-provider)
6. [Validators & Staking](#6-validators--staking)
7. [Blockchain Scaffolding](#7-blockchain-scaffolding)
8. [MetaMask JSON-RPC](#8-metamask-json-rpc)
9. [GraphQL](#9-graphql)
10. [AI / Proof of Intelligence](#10-ai--proof-of-intelligence)
11. [Governance](#11-governance)
12. [Rate Limits & Errors](#12-rate-limits--errors)

---

## 1. Network & Health

### `GET /health`
Network health and service status.

```bash
curl https://trispi.org/health
```
```json
{
  "status": "healthy",
  "block_height": 12345,
  "chain_id": 7878,
  "services": {
    "python_ai": "running",
    "go_consensus": "running",
    "rust_core": "running"
  }
}
```

### `GET /api/network/status`
Full network status including peer count, consensus state and token stats.

### `GET /api/network/peers`
List all connected P2P peers.

### `POST /api/network/peers/register`
Register your node as a mainnet peer.
```json
{
  "node_id":      "my_node_01",
  "address":      "1.2.3.4:50051",
  "node_type":    "full_node",
  "chain_height": 12345
}
```

### `GET /api/network/bootstrap`
Bootstrap data: current chain head, peer list, genesis hash.

### `GET /api/tokenomics`
Current supply, burn rate, block subsidy, halving schedule.

### `GET /api/network/overview`
Combined overview: block height, TPS, node count, AI accuracy.

---

## 2. Blockchain Explorer

### `GET /api/explorer/blocks?limit=10&offset=0`
Latest blocks with transactions.

```bash
curl "https://trispi.org/api/explorer/blocks?limit=5"
```

### `GET /api/explorer/blocks/{hash}`
Single block by hash.

### `GET /api/explorer/tx/{tx_id}`
Transaction details by ID.

### `GET /api/explorer/search?q=QUERY`
Search by address, block hash, or transaction ID.

### `GET /api/explorer/stats`
Overall chain statistics (TPS, total transactions, avg block time).

### `GET /api/chain`
Full blockchain (all blocks). Use pagination for large chains.

---

## 3. Wallet & Tokens

### `GET /api/balance/{address}`
Get TRP balance for any address.
```bash
curl https://trispi.org/api/balance/trp1abc123
```
```json
{ "address": "trp1abc123", "balance": 1250.75, "token": "TRP" }
```

### `POST /api/wallet/create`
Create a new TRISPI DUO wallet (Ed25519 + Dilithium3 + BIP39).
```json
{}
```
**Response:**
```json
{
  "trp_address":   "trp1...",
  "evm_address":   "0x...",
  "public_key":    "hex...",
  "mnemonic":      "word1 word2 ... word24",
  "quantum_public_key": "hex..."
}
```

### `POST /api/tokens/transfer`
Transfer TRP between addresses.
```json
{
  "from_address": "trp1sender",
  "to_address":   "trp1receiver",
  "amount":       100.0,
  "memo":         "payment"
}
```

### `GET /api/transactions?address={addr}&limit=50`
Transaction history for an address.

---

## 4. Smart Contracts (EVM + WASM)

### `POST /api/engine/deploy`
Deploy an EVM or WASM contract.
```json
{
  "creator":   "trp1address",
  "bytecode":  "0x6080604052...",
  "runtime":   "evm",
  "gas_limit": 3000000
}
```
**Response:**
```json
{
  "contract_address": "trp1contract_abc123",
  "runtime":   "evm",
  "gas_used":  215000,
  "tx_hash":   "0xdef456..."
}
```
> Set `"runtime": "wasm"` for WASM contracts.

### `POST /api/engine/call`
Call a contract method.
```json
{
  "caller":           "trp1caller",
  "contract_address": "trp1contract_abc123",
  "method":           "transfer",
  "args":             ["trp1recipient", 1000],
  "gas_limit":        100000
}
```

### `GET /api/engine/contracts`
List all deployed contracts with metadata.

### `POST /api/contract/audit`
AI-powered security audit of a smart contract.
```json
{
  "source_code": "pragma solidity ^0.8.0; contract MyToken { ... }",
  "runtime":     "evm"
}
```

---

## 5. Energy Provider

### `POST /api/ai-energy/register`
Register as an Energy Provider.
```json
{
  "contributor_id": "my_node_01",
  "cpu_cores":      8,
  "gpu_memory_mb":  0
}
```

### `POST /api/ai-energy/start-session`
Start a provider session and receive a `session_id`.
```json
{ "contributor_id": "my_node_01" }
```

### `POST /api/ai-energy/heartbeat`
Send a heartbeat — earns TRP automatically every 15 seconds.
```json
{
  "contributor_id":  "my_node_01",
  "session_id":      "uuid-...",
  "cpu_usage":       45.0,
  "tasks_completed": 1
}
```
**Response:**
```json
{
  "reward_earned":        0.5,
  "total_earned":         12.5,
  "next_task_available":  true
}
```

### `GET /api/ai-energy/task/{node_id}`
Get the next AI task to compute (gradient batch or fraud check).

### `POST /api/ai-energy/submit`
Submit a completed task result.
```json
{
  "task_id":        "task_abc",
  "contributor_id": "my_node_01",
  "result": {
    "accuracy":    0.94,
    "result_hash": "sha256..."
  }
}
```

### `GET /api/ai-energy/providers`
List all active Energy Providers with earnings and compute scores.

---

## 6. Validators & Staking

### `GET /api/validators`
List active validators with stake, PoI score, and block stats.

### `POST /api/validators/stake`
Stake TRP to become a validator (minimum 10,000 TRP).
```json
{
  "validator": "my_validator_id",
  "amount":    10000
}
```

### `GET /api/poi/scores`
Current Proof of Intelligence scores for all validators.

### `GET /api/poi/next-proposer`
Address of the next block proposer.

### `GET /api/staking/slashing-events`
Recent slashing events (validator penalties).

---

## 7. Blockchain Scaffolding

See [docs/BLOCKCHAIN_CREATION.md](BLOCKCHAIN_CREATION.md) for the full guide.

### `POST /api/chains/scaffold`
Generate a complete parachain project ZIP.
```json
{
  "chain_name":   "my-chain",
  "language":     "go",
  "block_time":   15,
  "token_name":   "MYTOKEN",
  "token_symbol": "MYT"
}
```
> **Response:** ZIP file download.  
> `language` options: `go`, `rust`, `solidity`

### `POST /api/chains/register`
Register a running chain as a TRISPI subnet.
```json
{
  "name":         "my-chain",
  "genesis_hash": "0xYOUR_GENESIS_HASH",
  "validators":   ["trp1val1", "trp1val2"],
  "ibc_endpoint": "http://YOUR_CHAIN_IP:8000/api"
}
```
**Response:**
```json
{
  "chain_id":     "uuid-...",
  "admin_secret": "one-time-secret",
  "status":       "registered"
}
```

### `POST /api/chain/sync-block`
Submit a block header from your chain to TRISPI.
```json
{
  "chain_id":     "your-chain-uuid",
  "block_hash":   "0xABC...",
  "block_height": 1234,
  "timestamp":    1700000000
}
```
> Requires `X-Admin-Token: YOUR_ADMIN_SECRET` header.

---

## 8. MetaMask JSON-RPC

**Endpoint:** `POST /rpc`

Compatible with MetaMask, ethers.js, web3.js, Hardhat.

```bash
# Get Chain ID (returns 0x1EC6 = 7878):
curl -X POST https://trispi.org/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Get block number:
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Get balance:
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xYOUR_ADDRESS","latest"],"id":1}'

# Send raw transaction:
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":["0xSIGNED_TX"],"id":1}'
```

**Supported methods:**
`eth_chainId` · `eth_blockNumber` · `eth_getBalance` · `eth_getTransactionCount` · `eth_sendRawTransaction` · `eth_call` · `eth_estimateGas` · `eth_getTransactionReceipt` · `net_version`

---

## 9. GraphQL

**Endpoint:** `POST /api/graphql`

```bash
curl -X POST https://trispi.org/api/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ blocks(limit: 5) { index hash timestamp transactions { tx_id amount } } }"
  }'
```

**Example queries:**

```graphql
# Latest blocks with transactions:
{
  blocks(limit: 10) {
    index
    hash
    timestamp
    transactions {
      tx_id
      from_address
      to_address
      amount
    }
  }
}

# Address balance:
{
  balance(address: "trp1abc123") {
    balance
    token
  }
}

# Validator scores:
{
  validators {
    node_id
    stake
    poi_score
    blocks_produced
  }
}
```

---

## 10. AI / Proof of Intelligence

### `GET /api/ai/full-status`
Status of all AI modules (fraud detection, anomaly detection, gas optimizer, federated learning).

### `POST /api/ai/poi/generate`
Generate a Proof of Intelligence certificate for a block.

### `POST /api/ai/network-protector/check`
Check a transaction for fraud or anomalies.
```json
{
  "from":   "trp1sender",
  "to":     "trp1recipient",
  "amount": 1000.0
}
```

### `GET /api/gas/recommend`
AI-recommended gas price based on current network load.

### `GET /api/ai/federated/status`
Current federated learning round, accuracy, participant count.

---

## 11. Governance

### `GET /api/governance/proposals`
Active governance proposals.

### `POST /api/governance/propose`
Create a governance proposal.
```json
{
  "proposer":    "trp1address",
  "title":       "Increase block size",
  "description": "Proposal to double the max block size",
  "type":        "parameter_change"
}
```

### `POST /api/governance/vote`
Vote on a proposal.
```json
{
  "voter":       "trp1address",
  "proposal_id": "prop_001",
  "vote":        "yes"
}
```

---

## 12. Rate Limits & Errors

### Rate limits

| Environment | Limit |
|-------------|-------|
| Public mainnet | 60 requests/minute per IP |
| Your own node | Unlimited |

### Error format

```json
{ "detail": "Error message here" }
```

### HTTP status codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 400 | Bad request — check JSON body |
| 401 | Unauthorized — check X-Admin-Token |
| 404 | Not found |
| 422 | Validation error — check field types |
| 429 | Rate limit exceeded |
| 500 | Server error |

---

## Quick Reference Card

```bash
BASE=https://trispi.org

# Health
curl $BASE/health

# Balance
curl $BASE/api/balance/trp1ADDRESS

# Transfer
curl -X POST $BASE/api/tokens/transfer \
  -d '{"from_address":"trp1...","to_address":"trp1...","amount":100}'

# Latest blocks
curl "$BASE/api/explorer/blocks?limit=10"

# Network status
curl $BASE/api/network/status

# Register node
curl -X POST $BASE/api/network/peers/register \
  -d '{"node_id":"node1","address":"IP:50051","node_type":"full_node"}'

# Deploy contract
curl -X POST $BASE/api/engine/deploy \
  -d '{"creator":"trp1...","bytecode":"0x...","runtime":"evm"}'

# Scaffold blockchain
curl -X POST $BASE/api/chains/scaffold \
  -d '{"chain_name":"my-chain","language":"go"}' -o my-chain.zip
```
