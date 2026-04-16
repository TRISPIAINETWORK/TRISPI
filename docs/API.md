# TRISPI REST API Reference

**Base URL:** `https://trispi.org`  
**Local node:** `http://localhost:8000`  
**Swagger UI:** `https://trispi.org/api/docs`

All endpoints return JSON. POST endpoints accept `Content-Type: application/json`.

---

## Network & Health

### `GET /health`
Network health and service status.

```bash
curl https://trispi.org/health
```
```json
{
  "status": "healthy",
  "block_height": 3650,
  "chain_id": 7878,
  "services": {
    "python_ai": "running",
    "go_consensus": "running",
    "rust_core": "running"
  }
}
```

### `GET /api/network/status`
Full network status including peer count and consensus state.

### `GET /api/network/peers`
List connected P2P peers.

### `POST /api/network/peers/register`
Register your node as a peer.
```json
{
  "node_id":      "my_node_01",
  "address":      "1.2.3.4:50051",
  "node_type":    "full_node",
  "chain_height": 3650
}
```

### `GET /api/tokenomics`
Current supply, burn rate, block subsidy, halving schedule.

---

## Blockchain Explorer

### `GET /api/explorer/blocks?limit=10&offset=0`
Latest blocks with transactions.

### `GET /api/explorer/blocks/{hash}`
Single block by hash.

### `GET /api/explorer/tx/{tx_id}`
Transaction details.

### `GET /api/explorer/search?q=QUERY`
Search by address, block hash, or transaction ID.

### `GET /api/explorer/stats`
Overall chain statistics.

---

## Wallet & Tokens

### `GET /api/balance/{address}`
Get TRP balance for any address.
```bash
curl https://trispi.org/api/balance/trp1abc123
```
```json
{ "address": "trp1abc123", "balance": 1250.75, "token": "TRP" }
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

---

## Smart Contracts

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
  "runtime": "evm",
  "gas_used": 215000,
  "tx_hash": "0xdef456..."
}
```

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
List all deployed contracts.

### `POST /api/contract/audit`
AI-powered contract security audit.

---

## Energy Provider

### `POST /api/ai-energy/register`
Register as an Energy Provider.
```json
{ "contributor_id": "my_node", "cpu_cores": 8, "gpu_memory_mb": 0 }
```

### `POST /api/ai-energy/start-session`
Start a provider session (get `session_id`).
```json
{ "contributor_id": "my_node" }
```

### `POST /api/ai-energy/heartbeat`
Send heartbeat — earns TRP automatically.
```json
{
  "contributor_id": "my_node",
  "session_id":     "uuid-...",
  "cpu_usage":      45.0,
  "tasks_completed": 1
}
```
**Response:**
```json
{ "reward_earned": 0.5, "total_earned": 12.5, "next_task_available": true }
```

### `GET /api/ai-energy/task/{node_id}`
Get an AI task to compute.

### `POST /api/ai-energy/submit`
Submit completed task result.
```json
{
  "task_id":        "task_abc",
  "contributor_id": "my_node",
  "result": { "accuracy": 0.94, "result_hash": "sha256..." }
}
```

### `GET /api/ai-energy/providers`
List all active Energy Providers and their earnings.

---

## Validators

### `GET /api/validators`
List active validators with stake and block production stats.

### `POST /api/validators/stake`
Stake TRP to become a validator (minimum 10,000 TRP).
```json
{ "validator": "my_validator", "amount": 10000 }
```

---

## MetaMask JSON-RPC

**Endpoint:** `POST /rpc`

Compatible with MetaMask, ethers.js, web3.js.

```bash
# Get Chain ID (returns 0x1EC6 = 7878):
curl -X POST https://trispi.org/rpc \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# Get balance (EVM address format):
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xYOUR_ADDRESS","latest"],"id":1}'

# Get latest block:
curl -X POST https://trispi.org/rpc \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

**Supported methods:** `eth_chainId`, `eth_blockNumber`, `eth_getBalance`, `eth_getTransactionCount`, `eth_sendRawTransaction`, `eth_call`, `eth_estimateGas`, `net_version`

---

## GraphQL

**Endpoint:** `POST /api/graphql`

```bash
curl -X POST https://trispi.org/api/graphql \
  -H "Content-Type: application/json" \
  -d '{
    "query": "{ blocks(limit: 5) { index hash timestamp transactions { tx_id amount } } }"
  }'
```

---

## AI / Proof of Intelligence

### `GET /api/ai/full-status`
Status of all AI modules (fraud detection, anomaly detection, gas optimizer).

### `POST /api/ai/poi/generate`
Generate a Proof of Intelligence for a block.

### `POST /api/ai/network-protector/check`
Check a transaction for fraud or anomalies.
```json
{ "from": "trp1...", "to": "trp1...", "amount": 1000.0 }
```

### `GET /api/gas/recommend`
AI-recommended gas price based on network load.

---

## Governance

### `GET /api/governance/proposals`
Active governance proposals.

### `POST /api/governance/propose`
Create a governance proposal.

### `POST /api/governance/vote`
Vote on a proposal.

---

## Rate Limits

Public mainnet endpoints: **60 requests/minute** per IP.  
No rate limit on your own local node.

---

## Error Responses

```json
{ "detail": "Error message here" }
```

| HTTP Code | Meaning |
|-----------|---------|
| 200 | Success |
| 400 | Bad request — check your JSON body |
| 404 | Not found |
| 422 | Validation error — check field types |
| 429 | Rate limit exceeded |
| 500 | Server error |
