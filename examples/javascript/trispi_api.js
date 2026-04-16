/**
 * TRISPI API — JavaScript / Node.js examples
 * Works in browser or Node.js
 */

const API = "https://trispi.org"; // or http://localhost:8000

// ─── Health check ──────────────────────────────────────────
async function healthCheck() {
  const res = await fetch(`${API}/health`);
  const data = await res.json();
  console.log("Network status:", data.status);
  console.log("Block height:", data.block_height);
  return data;
}

// ─── Get wallet balance ─────────────────────────────────────
async function getBalance(address) {
  const res = await fetch(`${API}/api/balance/${address}`);
  const data = await res.json();
  console.log(`Balance of ${address}: ${data.balance} TRP`);
  return data.balance;
}

// ─── Get latest blocks ──────────────────────────────────────
async function getBlocks(limit = 10) {
  const res = await fetch(`${API}/api/explorer/blocks?limit=${limit}`);
  const data = await res.json();
  data.blocks.forEach(b => {
    console.log(`Block #${b.index} | ${b.hash?.slice(0, 16)}... | ${b.transactions?.length || 0} txs`);
  });
  return data.blocks;
}

// ─── Transfer TRP ───────────────────────────────────────────
async function transferTRP(fromAddress, toAddress, amount) {
  const res = await fetch(`${API}/api/tokens/transfer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ from_address: fromAddress, to_address: toAddress, amount }),
  });
  const data = await res.json();
  console.log("Transfer status:", data.status, "| TX:", data.tx_hash);
  return data;
}

// ─── Deploy EVM contract ─────────────────────────────────────
async function deployContract(creatorAddress, bytecode, runtime = "evm") {
  const res = await fetch(`${API}/api/engine/deploy`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      creator: creatorAddress,
      bytecode,
      runtime,
      gas_limit: 3000000,
    }),
  });
  const data = await res.json();
  console.log("Contract address:", data.contract_address);
  console.log("Gas used:", data.gas_used);
  return data;
}

// ─── MetaMask-compatible JSON-RPC ────────────────────────────
async function rpcCall(method, params = []) {
  const res = await fetch(`${API}/rpc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", method, params, id: 1 }),
  });
  const data = await res.json();
  return data.result;
}

// ─── Usage examples ──────────────────────────────────────────
async function main() {
  console.log("=== TRISPI JavaScript SDK Example ===\n");

  await healthCheck();

  const chainId = await rpcCall("eth_chainId");
  console.log("Chain ID:", parseInt(chainId, 16)); // 7878

  await getBlocks(3);

  // Uncomment to use:
  // await getBalance("trp1YOUR_ADDRESS");
  // await transferTRP("trp1from", "trp1to", 100);
  // await deployContract("trp1creator", "0x6080604052...");
}

main().catch(console.error);
