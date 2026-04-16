# Security Policy

## Supported versions

| Version | Supported |
|---------|-----------|
| Latest (`main`) | ✅ |
| Older releases | ❌ |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues privately to: **security@trispi.org**

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- (Optional) Suggested fix

We will acknowledge receipt within 48 hours and aim to resolve critical issues within 7 days.

## Cryptography

TRISPI uses:
- **Ed25519** — classical digital signatures (all transactions)
- **Dilithium3 (NIST FIPS 204)** — post-quantum signature commitment
- **Kyber1024** — post-quantum key exchange (roadmap)
- **SHA-256 / SHA3-256** — hash functions

## Scope

In scope:
- Python API (`python-ai-service/`)
- Go consensus (`go-consensus/`)
- Rust P2P bridge (`rust-p2p-bridge/`)
- WASM contracts (`contracts/`)
- Node examples (`examples/build-a-node/`)

Out of scope:
- Frontend UI XSS (report but lower priority)
- Third-party dependencies (report upstream)
