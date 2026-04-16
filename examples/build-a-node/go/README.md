# TRISPI Node — Go Example

A complete, runnable TRISPI-compatible node implemented in Go.

## What it demonstrates

- Ed25519 key generation and block signing
- PBFT consensus (prepare / commit phases)
- libp2p P2P: TCP + QUIC-v1 transports, Noise encryption, Yamux muxer
- mDNS (LAN) + DHT Kademlia (internet) peer discovery
- **Peer scoring and Sybil protection** — rate limiting, ban mechanism
- HTTP API compatible with the TRISPI Python gateway

## Run

```bash
# Install Go 1.21+
go version

# Download dependencies
go mod tidy

# Start node 1
go run main.go -id node1 -http 8081 -p2p 50052

# Start node 2 (different terminal)
go run main.go -id node2 -http 8082 -p2p 50053
# Nodes discover each other via mDNS on the same LAN automatically
```

## API

```bash
# Health
curl http://localhost:8081/health

# Chain
curl http://localhost:8081/chain | python3 -m json.tool

# Mine a block
curl -X POST http://localhost:8081/mine

# Validators
curl http://localhost:8081/validators

# Peer scores (Sybil protection status)
curl http://localhost:8081/peers/scores
```

## Key security features

| Feature | Implementation |
|---------|----------------|
| Sybil protection | Only staked validators (`Stake >= 1.0 TRP`) count in PBFT quorum |
| Peer scoring | Each peer gets a score; bad messages → penalty; good messages → reward |
| Rate limiting | Max 60 messages/minute per peer |
| Auto-ban | Score < -10 → 30-minute ban |
| Block validation | Ed25519 signature + hash + prev_hash verified on every received block |
| Quantum-ready | `DilithiumSig` field in `QuantumSignature` struct — wire in real Dilithium3 here |

## Extending to production

1. **Add Dilithium3**: replace the `// DilithiumSig: ...` comment with the real PQC library
2. **Add staking API**: endpoint to register validators with a stake deposit
3. **Add slashing**: penalize validators who double-sign or go offline
4. **Persistent chain**: write `chain` to a JSON file on every new block
