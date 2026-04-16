# Contributing to TRISPI

Thank you for your interest in TRISPI — the AI-powered Web4 blockchain platform.

## How to contribute

### 1. Fork & clone
```bash
git clone https://github.com/TRISPIAINETWORK/TRISPI.git
cd TRISPI
```

### 2. Set up development environment

**Backend (Python)**
```bash
cd python-ai-service
pip install -r requirements.txt
uvicorn app.main_simplified:app --reload --port 8000
```

**Go consensus**
```bash
cd go-consensus
go build ./...
./go-consensus
```

**Rust TCP bridge**
```bash
cd rust-p2p-bridge
cargo build --release
```

**Frontend**
```bash
cd frontend
npm install
npm start
```

### 3. Smart contracts (Rust / WASM)
All contracts are in `contracts/examples/`. They run on the TRISPI WASM runtime — no Solidity.

```bash
cd contracts/examples/wasm/counter
cargo test
cargo build --release --target wasm32-unknown-unknown
```

### 4. Building a node
See `examples/build-a-node/` for complete Go and Rust node examples with:
- libp2p P2P networking (TCP + QUIC)
- PBFT consensus
- Peer scoring & Sybil protection
- Ed25519 + Dilithium3 PQC

### 5. Commit style
Follow [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add Kyber1024 key exchange
fix: correct peer score ban threshold
docs: update WASM contract examples
```

### 6. Security
- Never commit private keys or mnemonics
- PQC signatures use Dilithium3 (NIST FIPS 204)
- Classical signatures use Ed25519

## Community
- GitHub Discussions: use the Discussions tab for questions and ideas
- Issues: use issue templates for bugs and features
- Discord: [Coming soon at trispi.org]

## Code of conduct
Be respectful, constructive, and inclusive. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
