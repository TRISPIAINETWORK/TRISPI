# TRISPI Python SDK

Official Python client for the TRISPI AI Blockchain.

## Installation

```bash
pip install requests
```

Then copy `trispi.py` to your project.

## Quick Start

```python
from trispi import TRISPIClient

# Create client
client = TRISPIClient("https://trispi.network")

# Get network status
status = client.get_network_status()
print(f"Block Height: {status['block_height']}")
print(f"Accounts: {status['total_accounts']}")

# Check balance
balance = client.get_balance("trp1your_address_here")
print(f"Balance: {balance['balance']} TRP")
```

## API Reference

### Network

```python
# Get network status
client.get_network_status()

# Get AI engine status
client.get_ai_status()

# Get post-quantum cryptography status  
client.get_pqc_status()

# Get blockchain (list of blocks)
client.get_chain()
```

### Wallet

```python
# Get balance
client.get_balance("trp1address")

# Transfer TRP
client.transfer("trp1from", "trp1to", 100.0)
```

### Smart Contracts

```python
# Deploy EVM (Solidity) contract
result = client.deploy_evm_contract(
    deployer="0xYourAddress",
    bytecode="0x606060...",
    constructor_args=[]
)
print(f"Contract: {result['contract_address']}")

# Deploy WASM (Rust/Go) contract
result = client.deploy_wasm_contract(
    deployer="trp1YourAddress",
    bytecode="0061736d...",
    init_args={}
)

# Call contract method
result = client.call_contract(
    contract_address="0xContractAddress",
    method="balanceOf",
    args=["0xOwnerAddress"]
)
```

### Energy Provider

```python
import uuid

# Register as energy provider
contributor_id = str(uuid.uuid4())
reg = client.register_energy_provider(
    contributor_id=contributor_id,
    cpu_cores=4,
    gpu_memory_mb=4096
)

# Start session
session = client.start_energy_session(contributor_id)
session_id = session['session_id']

# Send heartbeat (returns reward)
result = client.energy_heartbeat(
    contributor_id=contributor_id,
    session_id=session_id,
    cpu_usage=50.0,
    tasks_completed=1
)
print(f"Reward: {result['reward_earned']} TRP")

# Get statistics
stats = client.get_energy_stats()
```

### Cryptography

```python
# Generate hybrid Ed25519 + Dilithium3 keypair
keypair = client.generate_keypair()

# Get cryptographic scheme info
info = client.get_crypto_info()
```

## Examples

### Complete Energy Provider

```python
from trispi import TRISPIClient
import uuid
import time

client = TRISPIClient("https://trispi.network")

# Register
contributor_id = str(uuid.uuid4())
client.register_energy_provider(contributor_id, cpu_cores=4)

# Start session  
session = client.start_energy_session(contributor_id)
session_id = session['session_id']

# Main loop
total_rewards = 0.0
while True:
    result = client.energy_heartbeat(contributor_id, session_id)
    reward = result.get('reward_earned', 0)
    total_rewards += reward
    print(f"Earned: {reward:.6f} TRP (Total: {total_rewards:.6f})")
    time.sleep(10)
```

## Error Handling

```python
from trispi import TRISPIClient, TRISPIError

client = TRISPIClient("https://trispi.network")

try:
    balance = client.get_balance("invalid_address")
except TRISPIError as e:
    print(f"API Error: {e}")
```

## License

MIT License
