# @trispi/sdk — TypeScript SDK

Official TypeScript/JavaScript client for the TRISPI AI Blockchain.

## Installation

```bash
npm install @trispi/sdk axios
```

## Quick Start

```typescript
import TrispiSDK from '@trispi/sdk';

const sdk = new TrispiSDK('http://localhost:8000'); // or https://trispi.org

// Create a wallet
const wallet = await sdk.createWallet();
console.log(wallet.address); // trp1abc...

// Send TRP
const tx = await sdk.sendTransaction(wallet.address, 'trp1recipient', 100);
console.log(tx.tx_hash);

// Tokenomics
const tokenomics = await sdk.getTokenomics();
console.log(`${tokenomics.current_supply} TRP in circulation`);

// Network stats
const network = await sdk.getNetworkOverview();
console.log(`${network.peer_count} peers | block ${network.block_height}`);
```

## Become an Energy Provider

Earn TRP by contributing CPU/GPU compute:

```typescript
// Register once
const reg = await sdk.registerEnergyDevice({
  device_id: 'my-gpu-server',
  device_type: 'gpu',
  cpu_cores: 16,
  gpu_memory_mb: 24576,
  wallet_address: wallet.address,
});

// Save reg.api_key securely — cannot be recovered later

// Submit readings every 30 seconds
setInterval(async () => {
  const result = await sdk.submitEnergyReading({
    device_id: 'my-gpu-server',
    api_key: reg.api_key,
    power_watts: 450,
    temperature_c: 72,
    cpu_usage_pct: 85,
    gpu_usage_pct: 90,
    timestamp: Math.floor(Date.now() / 1000),
  });
  console.log(`+${result.reward_trp} TRP`);
}, 30_000);
```

## API Reference

| Method | Description |
|--------|-------------|
| `health()` | Node health check |
| `systemStatus()` | All service statuses |
| `createWallet()` | Generate a new TRP wallet |
| `getBalance(address)` | Wallet balance |
| `sendTransaction(from, to, amount)` | Send TRP |
| `getTokenomics()` | Supply, burn rate, issuance |
| `getNetworkOverview()` | Block height, peers, validators |
| `registerEnergyDevice(params)` | Register as energy provider |
| `submitEnergyReading(reading)` | Submit compute reading |
| `deployContract(code, runtime, deployer)` | Deploy EVM/WASM contract |
| `getRecentBlocks(limit)` | Latest blocks |
| `getRecentTransactions(limit)` | Latest transactions |
| `stake(address, amount)` | Stake TRP |
| `unstake(address, amount)` | Unstake TRP |
| `getFounderWallet()` | Founder wallet info |

## Building from Source

```bash
npm install
npm run build
# Output: dist/
```

## License

MIT — see [LICENSE](../../LICENSE)
