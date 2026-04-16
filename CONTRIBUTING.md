# Contributing to TRISPI

Thank you for your interest in contributing to the TRISPI Network!

---

## Ways to Contribute

| Contribution | Where |
|---|---|
| Bug reports | [GitHub Issues](https://github.com/TRISPIAINETWORK/TRISPI/issues) |
| Feature requests | [GitHub Discussions](https://github.com/TRISPIAINETWORK/TRISPI/discussions/categories/feature-requests) |
| Code (Go, Rust, Python) | Pull Request to `main` |
| Documentation | `docs/` directory, PR to `main` |
| Smart contracts | `contracts/` directory |
| SDK improvements | `sdk/` directory |
| Node operator feedback | [Node Setup Help Discussions](https://github.com/TRISPIAINETWORK/TRISPI/discussions/categories/node-setup-help) |

---

## Reporting Bugs

1. Search [existing issues](https://github.com/TRISPIAINETWORK/TRISPI/issues) first
2. Open a new issue with:
   - **Clear title** describing the problem
   - **Steps to reproduce** (numbered list)
   - **Expected vs actual behavior**
   - **Node version** (`curl http://localhost:8081/health`)
   - **Logs** (sanitize any private info before pasting)

---

## Development Setup

### Requirements

- Go 1.21+
- Rust 1.80+
- Python 3.11+
- Docker 24+

### Running Locally

```bash
# Start all services
bash start_backend.sh

# Python only (port 8000)
cd python-ai-service && uvicorn app.main_simplified:app --reload --port 8000

# Go only (port 8081)
cd go-consensus && go run . -id dev-node -http 8081 -port 50051

# Rust only (port 6000)
cd rust-core && cargo run --release
```

### Running Tests

```bash
# Go unit tests
cd go-consensus && go test ./...

# Python tests
cd python-ai-service && python -m pytest

# Rust tests
cd rust-core && cargo test
```

---

## Pull Request Process

1. **Fork** the repository
2. **Branch** from `main`: `git checkout -b feat/your-feature`
3. **Write tests** for new functionality
4. **Run tests** before submitting
5. **Keep PRs focused** — one feature or fix per PR
6. **Write a clear description** — what, why, and how
7. **Reference issues**: "Closes #123"

### Commit Message Format

```
<type>(<scope>): <short description>
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`

Examples:
```
feat(libp2p): add QUIC-v1 transport for faster peer connections
fix(pbft): correct quorum calculation for staked validators only
docs(node-setup): add firewall configuration section
```

---

## Architecture Overview

```
Frontend (React :5000)
    |
    v  /api/*
Python AI Service (:8000)     <- blockchain state, AI, GraphQL, API
    |
    v  Go consensus URL
Go Consensus Engine (:8081)   <- PBFT, libp2p P2P (mDNS + DHT), blocks
    |
    v  Rust core URL
Rust Core (:6000)             <- PQC signatures, EVM, WASM VM
```

---

## Code Style

- **Go**: `gofmt`, standard library preferred
- **Rust**: `rustfmt`, `clippy` warnings as errors
- **Python**: `black`, `isort`, type hints required for new functions
- **TypeScript**: `prettier`, strict mode

---

## Security Policy

Please **do not** open public GitHub Issues for security vulnerabilities.

Instead, email: **security@trispi.org**

We follow responsible disclosure and will respond within 72 hours.

---

## Areas Where We Need Help

- **SDK Development** — TypeScript/Python SDKs for dApp developers
- **Documentation** — Tutorials, guides, examples
- **Testing** — Unit tests, integration tests
- **Smart Contracts** — Example contracts and templates
- **Translations** — Documentation in other languages

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
