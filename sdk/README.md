# TRISPI SDK Examples

## Python SDK

```python
import requests

class TRISPIClient:
    def __init__(self, rpc_url="http://localhost:8001"):
        self.url = rpc_url

    def get_status(self):
        """Get network status"""
        return requests.get(f"{self.url}/api/network/status").json()

    def get_balance(self, address):
        """Get wallet balance"""
        return requests.get(f"{self.url}/api/wallet/balances/{address}").json()

    def send_transaction(self, sender, recipient, amount, private_key):
        """Send TRP tokens"""
        return requests.post(f"{self.url}/api/transaction/send", json={
            "from": sender,
            "to": recipient,
            "amount": amount,
            "private_key": private_key
        }).json()

    def deploy_evm_contract(self, deployer, bytecode, args=None):
        """Deploy an EVM smart contract"""
        return requests.post(f"{self.url}/api/contracts/deploy", json={
            "type": "evm",
            "deployer": deployer,
            "bytecode": bytecode,
            "constructor_args": args or []
        }).json()

    def deploy_wasm_contract(self, deployer, wasm_binary, init_params=None):
        """Deploy a WASM smart contract"""
        return requests.post(f"{self.url}/api/contracts/deploy", json={
            "type": "wasm",
            "deployer": deployer,
            "wasm_binary": wasm_binary,
            "init_params": init_params or {}
        }).json()

    def search(self, query):
        """Search blocks and transactions"""
        return requests.get(f"{self.url}/api/explorer/search", params={"q": query}).json()


# Usage example
if __name__ == "__main__":
    client = TRISPIClient()
    
    # Get network status
    status = client.get_status()
    print(f"Network: {status['network']}")
    print(f"Block Height: {status['block_height']}")
    print(f"Active Miners: {status['active_miners']}")
    
    # Check balance
    balance = client.get_balance("trp1your_address_here")
    print(f"Balance: {balance}")
```

## JavaScript SDK

```javascript
class TRISPIClient {
  constructor(rpcUrl = 'http://localhost:8001') {
    this.url = rpcUrl;
  }

  async getStatus() {
    const res = await fetch(`${this.url}/api/network/status`);
    return res.json();
  }

  async getBalance(address) {
    const res = await fetch(`${this.url}/api/wallet/balances/${address}`);
    return res.json();
  }

  async sendTransaction(from, to, amount, privateKey) {
    const res = await fetch(`${this.url}/api/transaction/send`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, amount, private_key: privateKey })
    });
    return res.json();
  }

  async deployContract(type, deployer, code, args = {}) {
    const res = await fetch(`${this.url}/api/contracts/deploy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ type, deployer, bytecode: code, ...args })
    });
    return res.json();
  }
}

// Usage
const client = new TRISPIClient();
const status = await client.getStatus();
console.log(`Block Height: ${status.block_height}`);
```

## cURL Examples

```bash
# Get network status
curl http://localhost:8001/api/network/status

# Get wallet balance
curl http://localhost:8001/api/wallet/balances/trp1your_address

# Send transaction
curl -X POST http://localhost:8001/api/transaction/send \
  -H "Content-Type: application/json" \
  -d '{"from": "trp1sender", "to": "trp1recipient", "amount": 10}'

# Deploy EVM contract
curl -X POST http://localhost:8001/api/contracts/deploy \
  -H "Content-Type: application/json" \
  -d '{"type": "evm", "deployer": "trp1deployer", "bytecode": "0x608060..."}'

# Search explorer
curl "http://localhost:8001/api/explorer/search?q=block_hash_or_tx"
```
