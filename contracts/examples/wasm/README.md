# TRISPI WASM Smart Contracts

TRISPI supports WebAssembly (WASM) as a first-class contract runtime alongside EVM.
This directory contains example WASM contracts written in Rust.

## Why WASM?

| Feature | EVM (Solidity) | WASM (Rust/TinyGo) |
|---------|---------------|---------------------|
| Language | Solidity only | Rust, Go, C/C++, AssemblyScript |
| Performance | ~10–100x slower than native | Near-native speed |
| Memory model | Stack-based 256-bit | Linear memory (standard) |
| Post-quantum crypto | Via precompiles only | Native library support |
| Binary size | Bytecode (small) | WASM (~50–500 KB) |

## Examples

### `counter/` — Counter Contract
The simplest possible WASM contract. Stores a counter in persistent storage.
Operations: `init`, `get_count`, `increment`, `decrement`, `reset`.

```bash
cd counter
cargo test                              # run unit tests (native)
cargo build --target wasm32-unknown-unknown --release  # build WASM
```

### `token/` — TRP20 Fungible Token
A full TRP20 (ERC-20 equivalent) token contract in WASM.
Operations: `init`, `total_supply`, `balance_of`, `transfer`, `approve`, `transfer_from`, `burn`.

```bash
cd token
cargo test
cargo build --target wasm32-unknown-unknown --release
```

## Build requirements

```bash
# Install Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Add WASM target
rustup target add wasm32-unknown-unknown

# Optional: optimize binary size
cargo install wasm-opt  # from binaryen

# Build (from any contract directory)
cargo build --target wasm32-unknown-unknown --release

# Optimize size (recommended before deploy)
wasm-opt -Oz \
  target/wasm32-unknown-unknown/release/contract.wasm \
  -o contract_opt.wasm
```

## Deploy a WASM contract

```bash
# Encode the WASM binary to base64
WASM_B64=$(base64 -w0 target/wasm32-unknown-unknown/release/counter.wasm)

# Deploy via TRISPI API
curl -X POST http://localhost:8000/api/contracts/deploy \
  -H "Content-Type: application/json" \
  -d "{
    \"code\": \"$WASM_B64\",
    \"runtime\": \"wasm\",
    \"deployer\": \"trp1YOUR_ADDRESS\"
  }"
```

Response:
```json
{
  "contract_address": "trp1abc...xyz",
  "runtime": "wasm",
  "tx_hash": "0xabc...",
  "gas_used": 150000
}
```

## Call a WASM contract

```bash
# Call a function (read-only)
curl -X POST http://localhost:8000/api/contracts/call \
  -H "Content-Type: application/json" \
  -d '{
    "contract": "trp1abc...xyz",
    "function": "get_count",
    "args": [],
    "caller": "trp1YOUR_ADDRESS",
    "read_only": true
  }'

# Call a state-changing function (requires signature)
curl -X POST http://localhost:8000/api/contracts/call \
  -H "Content-Type: application/json" \
  -d '{
    "contract": "trp1abc...xyz",
    "function": "increment",
    "args": [],
    "caller": "trp1YOUR_ADDRESS",
    "signature": "ed25519:HEX_SIG"
  }'
```

## WASM Host API

TRISPI's WASM VM injects these host functions into every contract:

```rust
extern "C" {
    // Persistent storage
    fn trispi_storage_get(key_ptr: *const u8, key_len: u32, out_ptr: *mut u8) -> u32;
    fn trispi_storage_set(key_ptr: *const u8, key_len: u32, val_ptr: *const u8, val_len: u32);

    // Events
    fn trispi_emit_event(name_ptr: *const u8, name_len: u32, data_ptr: *const u8, data_len: u32);

    // Caller identity
    fn trispi_caller(out_ptr: *mut u8) -> u32;

    // Ed25519 signature verification (quantum-safe ready)
    fn trispi_ed25519_verify(
        sig_ptr: *const u8, sig_len: u32,
        pk_ptr: *const u8, pk_len: u32,
        msg_ptr: *const u8, msg_len: u32,
    ) -> u32; // 1 = valid, 0 = invalid

    // Abort / revert
    fn trispi_revert(msg_ptr: *const u8, msg_len: u32) -> !;
}
```

## TinyGo example (coming soon)

WASM contracts can also be written in TinyGo:

```go
//go:build js && wasm

package main

import "fmt"

var counter uint64

//export init
func contractInit() { counter = 0 }

//export increment
func increment() uint64 { counter++; return counter }

func main() { fmt.Println("TRISPI WASM contract") }
```

Build:
```bash
tinygo build -o counter.wasm -target wasm ./main.go
```
