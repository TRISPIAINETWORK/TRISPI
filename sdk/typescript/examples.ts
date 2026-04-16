/**
 * TRISPI TypeScript SDK — Usage Examples
 * Run: npx ts-node examples.ts
 */
import TrispiSDK from './index';

const sdk = new TrispiSDK('http://localhost:8000');

async function main() {

  // 1. Health check
  const health = await sdk.health();
  console.log('Health:', health.status);

  // 2. Network stats
  const network = await sdk.getNetworkOverview();
  console.log(`Block height: ${network.block_height} | Peers: ${network.peer_count}`);

  // 3. Create a wallet
  const wallet = await sdk.createWallet();
  console.log('Wallet:', wallet.address);

  // 4. Check balance
  const balance = await sdk.getBalance(wallet.address);
  console.log('Balance:', balance.balances);

  // 5. Send a transaction
  const tx = await sdk.sendTransaction(wallet.address, 'trp1recipient000', 10);
  console.log('TX hash:', tx.tx_hash);

  // 6. Tokenomics
  const tokenomics = await sdk.getTokenomics();
  console.log(`Supply: ${tokenomics.current_supply} TRP | Burned: ${tokenomics.total_burned} TRP`);

  // 7. Register as an energy provider
  const reg = await sdk.registerEnergyDevice({
    device_id: 'my-gpu-server-1',
    device_type: 'gpu',
    cpu_cores: 16,
    gpu_memory_mb: 24576,
    wallet_address: wallet.address,
  });
  console.log('Energy API key:', reg.api_key);

  // 8. Submit a power reading (sends every 30s in production)
  const reading = await sdk.submitEnergyReading({
    device_id: 'my-gpu-server-1',
    api_key: reg.api_key,
    power_watts: 450,
    temperature_c: 72,
    cpu_usage_pct: 85,
    gpu_usage_pct: 90,
    timestamp: Math.floor(Date.now() / 1000),
  });
  console.log(`Energy reward: ${reading.reward_trp} TRP`);

  // 9. Deploy a smart contract
  const contract = await sdk.deployContract(
    '// SPDX-License-Identifier: MIT\npragma solidity ^0.8.0;\ncontract Hello { string public msg = "Hello from TRISPI!"; }',
    'evm',
    wallet.address,
    { name: 'HelloWorld', version: '1.0' }
  );
  console.log('Contract:', contract);

  // 10. Recent blocks
  const { blocks } = await sdk.getRecentBlocks(5);
  console.log('Recent blocks:', blocks.length);
}

main().catch(console.error);
