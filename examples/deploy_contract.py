#!/usr/bin/env python3
"""
TRISPI Smart Contract Deployment Example

Deploy an EVM (Solidity) or WASM contract to the TRISPI network.
"""
import requests
import json

API = "https://trispi.org"  # or http://localhost:8000 for local node

# ============================================================
# Example 1: Deploy a simple EVM (Solidity) contract
# ============================================================

def deploy_evm_contract(creator_address: str, bytecode: str, gas_limit: int = 3000000):
    """Deploy a Solidity EVM contract."""
    response = requests.post(f"{API}/api/engine/deploy", json={
        "creator":   creator_address,
        "bytecode":  bytecode,       # hex bytecode from Remix/Hardhat/Foundry
        "runtime":   "evm",
        "gas_limit": gas_limit,
    })
    result = response.json()
    print(f"[EVM] Contract deployed at: {result.get('contract_address')}")
    print(f"[EVM] Gas used: {result.get('gas_used')}")
    print(f"[EVM] TX hash: {result.get('tx_hash')}")
    return result


# ============================================================
# Example 2: Deploy a WASM contract
# ============================================================

def deploy_wasm_contract(creator_address: str, wasm_bytecode: str):
    """Deploy a WebAssembly contract."""
    response = requests.post(f"{API}/api/engine/deploy", json={
        "creator":  creator_address,
        "bytecode": wasm_bytecode,   # base64-encoded .wasm file
        "runtime":  "wasm",
        "gas_limit": 1000000,
    })
    result = response.json()
    print(f"[WASM] Contract deployed at: {result.get('contract_address')}")
    return result


# ============================================================
# Example 3: Call a deployed contract
# ============================================================

def call_contract(caller: str, contract_address: str, method: str, args: list):
    """Call a method on a deployed contract."""
    response = requests.post(f"{API}/api/engine/call", json={
        "caller":           caller,
        "contract_address": contract_address,
        "method":           method,
        "args":             args,
        "gas_limit":        100000,
    })
    result = response.json()
    print(f"[CALL] Result: {result.get('return_value')}")
    print(f"[CALL] Gas used: {result.get('gas_used')}")
    return result


# ============================================================
# Example 4: Transfer TRP tokens
# ============================================================

def transfer_trp(from_address: str, to_address: str, amount: float):
    """Transfer TRP tokens between addresses."""
    response = requests.post(f"{API}/api/tokens/transfer", json={
        "from_address": from_address,
        "to_address":   to_address,
        "amount":       amount,
        "memo":         "transfer via example script",
    })
    result = response.json()
    print(f"[TX] Transfer result: {result.get('status')}")
    print(f"[TX] TX hash: {result.get('tx_hash')}")
    return result


# ============================================================
# Example 5: Check wallet balance
# ============================================================

def get_balance(address: str):
    """Get TRP balance for an address."""
    response = requests.get(f"{API}/api/balance/{address}")
    data = response.json()
    balance = data.get("balance", 0)
    print(f"[BALANCE] {address}: {balance} TRP")
    return balance


# ============================================================
# Example 6: Read latest blocks
# ============================================================

def get_latest_blocks(limit: int = 5):
    """Get the latest blocks from the chain."""
    response = requests.get(f"{API}/api/explorer/blocks?limit={limit}")
    data = response.json()
    blocks = data.get("blocks", [])
    for block in blocks:
        print(f"  Block #{block.get('index')} | Hash: {block.get('hash','')[:16]}... | "
              f"TXs: {len(block.get('transactions', []))} | AI Score: {block.get('ai_score', 0):.2f}")
    return blocks


# ============================================================
# Example 7: Register your node in the network
# ============================================================

def register_node(node_id: str, public_ip: str, chain_height: int = 0):
    """Register your node as a peer in the TRISPI network."""
    response = requests.post(f"{API}/api/network/peers/register", json={
        "node_id":      node_id,
        "address":      f"{public_ip}:50051",
        "node_type":    "full_node",
        "chain_height": chain_height,
    })
    result = response.json()
    print(f"[P2P] Node registered: {result.get('registered')}")
    return result


if __name__ == "__main__":
    # Run examples (replace addresses with your own)
    MY_ADDRESS = "trp1your_address_here"

    print("=== TRISPI API Examples ===\n")

    # Check balance
    print("1. Balance:")
    get_balance(MY_ADDRESS)
    print()

    # Latest blocks
    print("2. Latest blocks:")
    get_latest_blocks(3)
    print()

    # Example bytecode (minimal EVM contract that stores a number)
    SIMPLE_STORAGE_BYTECODE = "0x608060405234801561001057600080fd5b5060f78061001f6000396000f3"
    print("3. Deploy EVM contract:")
    # deploy_evm_contract(MY_ADDRESS, SIMPLE_STORAGE_BYTECODE)
    print("   (Commented out — add your bytecode and address)")
    print()

    print("All examples complete.")
