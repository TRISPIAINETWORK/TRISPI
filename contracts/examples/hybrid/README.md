# TRISPI Hybrid Contracts — Rust / WASM + Post-Quantum Cryptography

All contracts in this directory are written in **Rust** and compile to the **WASM runtime**.  
TRISPI does not use Solidity or EVM — every contract runs in the TRISPI WASM execution environment with built-in post-quantum cryptography.

## Why Rust / WASM?

| Property | TRISPI WASM (Rust) |
|----------|--------------------|
| Language | Rust |
| Runtime | WASM (wasm32-unknown-unknown) |
| PQC | Dilithium3 hash commitment on-chain |
| Classical | Ed25519 (runtime-verified) |
| Binary size | ~30–80 kB (release + opt-level=z) |
| Testing | `cargo test` — no node required |
| Determinism | Guaranteed (`#![no_std]`, `panic = "abort"`) |

---

## Contracts

### 1. QuantumVault (`quantum_vault/`)

Multi-signature withdrawal vault with dual PQC protection.

**Security model:**

| Layer | Algorithm | Verification |
|-------|-----------|--------------|
| Classical | Ed25519 | TRISPI runtime (tx envelope) |
| Post-Quantum | Dilithium3 | On-chain hash commitment + freshness |

**Flow:**

```
Owner         Signers (M of N)        WASM Runtime
 │                  │                      │
 ├─ init()──────────►                      │
 │  (signers, keys, threshold)             │
 │                  │                      │
 ├─ propose(to, amount)                    │
 │                  │                      │
 │            approve(msg_hash,            │
 │              dil_hash, timestamp)       │
 │            × M signers, ≤120s           │
 │                                         │
 ├─ execute()──────────────────────────────►
 │  (transfers TRP if M approvals met)     │
```

**Build & test:**

```bash
cd quantum_vault
cargo test

# Build WASM
rustup target add wasm32-unknown-unknown
cargo build --release --target wasm32-unknown-unknown --features wasm
```

**Deploy:**

```bash
trispi contract deploy \
  --wasm target/wasm32-unknown-unknown/release/quantum_vault.wasm \
  --init-args <signers_hex> <ed_keys_hex> <dil_keys_hex> <threshold>
```

**Exported functions:**

| Function | Description |
|----------|-------------|
| `init(signers, ed_keys, dil_keys, threshold)` | Initialize vault with M-of-N signers |
| `deposit(amount_utrp)` | Deposit micro-TRP into vault |
| `propose(to, amount)` | Owner proposes a withdrawal |
| `approve(msg_hash, dil_hash, timestamp_signed)` | Signer approves (Ed25519 + Dilithium3) |
| `execute()` | Execute if threshold met |
| `cancel()` | Owner cancels active proposal |
| `get_balance()` | Read vault balance |
| `approval_count()` | Count approvals on current proposal |

**Freshness proof (anti-replay):**

```rust
// Each signer computes:
let dil_hash = sha256(sha256(dilithium3_pubkey) || timestamp_signed_le64);
// On-chain check: now - timestamp_signed <= 120s AND now - prop_ts <= 120s
```

---

### 2. QuantumNFT (`quantum_nft.rs`)

NFT collection where each token stores a per-owner dual-key hash commitment.

- Every mint and transfer requires a fresh **Ed25519** signature
- Each token stores `sha256(ed25519_pubkey)` and `sha256(dilithium3_pubkey)` on-chain
- Signatures older than 120 seconds are rejected

**Deploy:**

```bash
# Build
rustup target add wasm32-unknown-unknown
cargo build --target wasm32-unknown-unknown --release

# Deploy
trispi contract deploy \
  --wasm target/wasm32-unknown-unknown/release/quantum_nft.wasm \
  --metadata '{"name":"Quantum Art","symbol":"QART","pqc":true}'
```

**Mint with quantum-safe signature (Python):**

```python
from trispi_client import TRISPIClient
import ed25519, time, hashlib

client = TRISPIClient()
priv, pub = ed25519.create_keypair()

timestamp = int(time.time())
msg = f"TRISPI_MINT|alice|ipfs://QmXyz/1.json|{timestamp}".encode()
digest = hashlib.sha256(msg).digest()
signature = priv.sign(digest)

result = client.call_contract(contract_addr, 'mint', {
    'recipient': 'alice',
    'uri': 'ipfs://QmXyz/1.json',
    'ed25519_sig': signature.hex(),
    'ed25519_pk': pub.to_bytes().hex(),
    'dilithium3_key_hash': dilithium3_key_hash_hex,
    'signed_at': timestamp,
})
```

---

## Host API

Both contracts use the TRISPI WASM host imports:

| Import | Signature | Description |
|--------|-----------|-------------|
| `trispi_storage_get` | `(key_ptr, key_len, out_ptr) → i32` | Read storage slot |
| `trispi_storage_set` | `(key_ptr, key_len, val_ptr, val_len)` | Write storage slot |
| `trispi_caller` | `(out_ptr)` | 32-byte sender address |
| `trispi_timestamp` | `() → i64` | Block timestamp (unix s) |
| `trispi_transfer` | `(to_ptr, to_len, amount) → i32` | Transfer TRP |
| `trispi_emit` | `(event_ptr, event_len)` | Emit event log |

---

## Dilithium3 (NIST FIPS 204)

| Property | Value |
|----------|-------|
| Security level | NIST Level 3 (≈ AES-192) |
| Public key size | 1,312 bytes |
| Signature size | ~2,420 bytes |
| Based on | Module-LWE lattice |
| Standard | NIST FIPS 204 (2024) |

Because storing 1,312 bytes on-chain is expensive, TRISPI uses a **hash commitment pattern**:
only `sha256(dilithium3_pubkey)` (32 bytes) is stored on-chain; full signature verification happens off-chain by the AI validator network.

## Roadmap

- [ ] Native Dilithium3 WASM precompile in the TRISPI WASM VM  
- [ ] CRYSTALS-Kyber for post-quantum key encapsulation (encrypted contract state)  
- [ ] FALCON-512 as alternative PQC signature  
- [ ] Batch Ed25519 verification via TRISPI host API  
