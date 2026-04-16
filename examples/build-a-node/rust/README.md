# TRISPI Node — Rust Example

A complete TRISPI-compatible node implemented in Rust.

## What it demonstrates

- Ed25519 block signing (`ed25519-dalek`)
- Dilithium3 PQC stub ready to wire in (`pqcrypto-dilithium`)
- SHA-256 Merkle tree and block hashing
- Peer scoring and Sybil protection (rate limiting + ban)
- PBFT commit vote handling (staked quorum only)
- Axum HTTP API (health, chain, mine)
- Tokio async TCP P2P listener

## Run

```bash
# Requires Rust 1.80+
cargo run -- --id node1 --http 8081 --p2p 6001

# Different terminal
cargo run -- --id node2 --http 8082 --p2p 6002
```

## API

```bash
curl http://localhost:8081/health
curl http://localhost:8081/chain
curl http://localhost:8081/mine
```

## Adding real Dilithium3 PQC

1. Uncomment `pqcrypto-dilithium` in `Cargo.toml`
2. In `src/main.rs`, replace the `dilithium_sig: String::new()` line with:

```rust
use pqcrypto_dilithium::dilithium3;
// Generate keypair once:
let (pk, sk) = dilithium3::keypair();
// Sign:
let sig = dilithium3::sign(data.as_bytes(), &sk);
let dilithium_sig = hex::encode(sig.as_bytes());
// Verify:
let open = dilithium3::open(&sig, &pk);
```

## Security model

| Feature | Details |
|---------|---------|
| Sybil protection | PBFT quorum counts only validators with `stake >= 1.0 TRP` |
| Peer scoring | Valid messages: +0.1 score; invalid blocks: -20 score |
| Rate limiting | Max 60 messages/minute per peer IP |
| Auto-ban | Score < -10 → 30-minute connection ban |
| Signature check | Ed25519 verified on every received block |
| PQC-ready | `dilithium_sig` field in wire format — plug in real Dilithium3 |
