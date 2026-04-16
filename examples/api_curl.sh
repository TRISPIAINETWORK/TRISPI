#!/bin/bash
# TRISPI API — curl examples
# Works against mainnet (https://trispi.org) or your local node (http://localhost:8000)

API="https://trispi.org"
YOUR_ADDRESS="trp1YOUR_WALLET_ADDRESS"

echo "=== Network Health ==="
curl -s "$API/health" | python3 -m json.tool

echo -e "\n=== Latest 5 Blocks ==="
curl -s "$API/api/explorer/blocks?limit=5" | python3 -m json.tool

echo -e "\n=== Wallet Balance ==="
curl -s "$API/api/balance/$YOUR_ADDRESS" | python3 -m json.tool

echo -e "\n=== Tokenomics ==="
curl -s "$API/api/tokenomics" | python3 -m json.tool

echo -e "\n=== Active Validators ==="
curl -s "$API/api/validators" | python3 -m json.tool

echo -e "\n=== Energy Providers ==="
curl -s "$API/api/ai-energy/providers" | python3 -m json.tool

echo -e "\n=== Network Peers ==="
curl -s "$API/api/network/peers" | python3 -m json.tool

echo -e "\n=== Transfer TRP ==="
# curl -X POST "$API/api/tokens/transfer" \
#   -H "Content-Type: application/json" \
#   -d "{\"from_address\":\"$YOUR_ADDRESS\",\"to_address\":\"trp1RECIPIENT\",\"amount\":10.0}"

echo -e "\n=== Deploy EVM Contract ==="
# curl -X POST "$API/api/engine/deploy" \
#   -H "Content-Type: application/json" \
#   -d "{\"creator\":\"$YOUR_ADDRESS\",\"bytecode\":\"0x6080...\",\"runtime\":\"evm\"}"

echo -e "\n=== MetaMask JSON-RPC ==="
curl -s -X POST "$API/rpc" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'
echo ""

curl -s -X POST "$API/rpc" \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"$YOUR_ADDRESS\",\"latest\"],\"id\":2}"
echo ""

echo -e "\n=== Register Node ==="
# curl -X POST "$API/api/network/peers/register" \
#   -H "Content-Type: application/json" \
#   -d '{"node_id":"my_node","address":"YOUR_IP:50051","node_type":"full_node","chain_height":0}'
