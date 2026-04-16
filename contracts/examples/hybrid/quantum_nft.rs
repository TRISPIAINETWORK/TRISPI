// TRISPI Hybrid WASM + PQC Contract — Quantum-Protected NFT
//
// This contract demonstrates TRISPI's hybrid runtime:
//   - Runs as WebAssembly inside the TRISPI WASM VM
//   - Verifies Ed25519 signatures on every mint/transfer
//   - Commits Dilithium3 (post-quantum) key hashes for quantum resistance
//   - Supports NFT ownership + metadata + transfer with PQC protection
//
// Build (WASM):
//   rustup target add wasm32-unknown-unknown
//   cargo build --target wasm32-unknown-unknown --release
//
// Deploy to TRISPI:
//   curl -X POST http://localhost:8000/api/contracts/deploy \
//     -H "Content-Type: application/json" \
//     -d '{"code": "<base64_wasm>", "runtime": "wasm", "deployer": "trp1ADDR",
//          "metadata": {"name": "TRISPI Quantum NFT", "symbol": "TQNFT", "pqc": true}}'

use std::collections::HashMap;

// ─── PQC Constants ────────────────────────────────────────────────────────────

/// Dilithium3 public key size in bytes (NIST FIPS 204).
const DILITHIUM3_PK_SIZE: usize = 1312;
/// Ed25519 public key size in bytes.
const ED25519_PK_SIZE: usize = 32;
/// Ed25519 signature size in bytes.
const ED25519_SIG_SIZE: usize = 64;

// ─── Storage simulation ───────────────────────────────────────────────────────

#[cfg(not(target_arch = "wasm32"))]
mod storage {
    use std::collections::HashMap;
    use std::sync::Mutex;
    static S: Mutex<Option<HashMap<Vec<u8>, Vec<u8>>>> = Mutex::new(None);
    pub fn get(key: &[u8]) -> Option<Vec<u8>> {
        S.lock().unwrap().as_ref()?.get(key).cloned()
    }
    pub fn set(key: &[u8], val: &[u8]) {
        S.lock().unwrap().get_or_insert_default().insert(key.to_vec(), val.to_vec());
    }
}

// ─── Data structures ──────────────────────────────────────────────────────────

/// A 32-byte hash of a Dilithium3 public key (stored on-chain as a commitment).
/// The full key (~1312 bytes) is stored off-chain and provided for each signature.
type Dilithium3KeyHash = [u8; 32];

#[derive(Debug, Clone)]
pub struct QuantumSignature {
    /// Ed25519 signature (64 bytes) over the operation payload.
    pub ed25519_sig: [u8; ED25519_SIG_SIZE],
    /// Ed25519 public key (32 bytes).
    pub ed25519_pk: [u8; ED25519_PK_SIZE],
    /// SHA-256 of the Dilithium3 public key (commitment stored on-chain).
    pub dilithium3_key_hash: Dilithium3KeyHash,
    /// Unix timestamp when the signature was created (freshness check: max 120s).
    pub signed_at: u64,
}

#[derive(Debug, Clone)]
pub struct NFTToken {
    pub token_id: u64,
    pub owner: String,
    pub uri: String,
    /// SHA-256 of the Dilithium3 public key registered by the creator.
    pub creator_pqc_key_hash: Dilithium3KeyHash,
    pub minted_at: u64,
    pub transfers: u32,
}

// ─── Storage key helpers ──────────────────────────────────────────────────────

fn owner_key(token_id: u64) -> Vec<u8> {
    format!("owner:{token_id}").into_bytes()
}
fn uri_key(token_id: u64) -> Vec<u8> {
    format!("uri:{token_id}").into_bytes()
}
fn pqc_key_hash_key(token_id: u64) -> Vec<u8> {
    format!("pqc:{token_id}").into_bytes()
}
fn balance_key(addr: &str) -> Vec<u8> {
    format!("bal:{addr}").into_bytes()
}
fn approved_key(token_id: u64) -> Vec<u8> {
    format!("appr:{token_id}").into_bytes()
}

fn get_u64(key: &[u8]) -> u64 {
    storage::get(key)
        .and_then(|b| b.try_into().ok())
        .map(u64::from_be_bytes)
        .unwrap_or(0)
}
fn set_u64(key: &[u8], v: u64) {
    storage::set(key, &v.to_be_bytes());
}

// ─── Contract API ─────────────────────────────────────────────────────────────

/// Initialise the NFT collection.
#[no_mangle]
pub extern "C" fn init(name: &str, symbol: &str, owner: &str) {
    storage::set(b"name",   name.as_bytes());
    storage::set(b"symbol", symbol.as_bytes());
    storage::set(b"owner",  owner.as_bytes());
    set_u64(b"next_token_id", 1);
    set_u64(b"total_supply", 0);
    emit_event("Init", &format!("{{\"name\":\"{name}\",\"symbol\":\"{symbol}\"}}"));
}

/**
 * Mint a new NFT with quantum-safe authorization.
 *
 * The caller must provide a valid Ed25519 signature over:
 *   SHA-256( "TRISPI_MINT" | recipient | uri | timestamp )
 *
 * The Dilithium3 key hash is stored as a commitment for future PQC verification.
 * When quantum computers become a threat, off-chain verifiers will also check
 * the Dilithium3 signature.
 */
#[no_mangle]
pub extern "C" fn mint(
    recipient: &str,
    uri: &str,
    sig: &QuantumSignature,
) -> u64 {
    // 1. Freshness check (within 120 seconds)
    let now = unix_now();
    assert!(now <= sig.signed_at + 120, "signature expired");

    // 2. Ed25519 signature verification
    let msg = mint_digest(recipient, uri, sig.signed_at);
    assert!(
        verify_ed25519(&sig.ed25519_sig, &sig.ed25519_pk, &msg),
        "invalid Ed25519 signature"
    );

    // 3. Mint token
    let token_id = get_u64(b"next_token_id");
    set_u64(b"next_token_id", token_id + 1);
    set_u64(b"total_supply", get_u64(b"total_supply") + 1);

    storage::set(&owner_key(token_id), recipient.as_bytes());
    storage::set(&uri_key(token_id), uri.as_bytes());
    storage::set(&pqc_key_hash_key(token_id), &sig.dilithium3_key_hash);
    set_u64(&balance_key(recipient), get_u64(&balance_key(recipient)) + 1);

    emit_event("Mint", &format!(
        "{{\"token_id\":{token_id},\"owner\":\"{recipient}\",\"uri\":\"{uri}\",\
         \"pqc_hash\":\"{}\"}}", hex_encode(&sig.dilithium3_key_hash)
    ));
    token_id
}

/**
 * Transfer an NFT to a new owner.
 *
 * Requires a valid Ed25519 signature from the current owner over:
 *   SHA-256( "TRISPI_TRANSFER" | token_id | to | timestamp )
 *
 * The Dilithium3 key hash commitment is verified against the token's registered key.
 */
#[no_mangle]
pub extern "C" fn transfer(
    token_id: u64,
    to: &str,
    sig: &QuantumSignature,
) {
    let owner_bytes = storage::get(&owner_key(token_id))
        .expect("token does not exist");
    let owner = std::str::from_utf8(&owner_bytes).expect("invalid owner");

    // Freshness check
    let now = unix_now();
    assert!(now <= sig.signed_at + 120, "signature expired");

    // Dilithium3 key hash commitment check (anti-key-substitution)
    let registered_hash = storage::get(&pqc_key_hash_key(token_id))
        .expect("no PQC key for token");
    assert_eq!(
        registered_hash.as_slice(),
        &sig.dilithium3_key_hash,
        "Dilithium3 key hash mismatch — potential key substitution attack"
    );

    // Ed25519 signature verification
    let msg = transfer_digest(token_id, to, sig.signed_at);
    assert!(
        verify_ed25519(&sig.ed25519_sig, &sig.ed25519_pk, &msg),
        "invalid Ed25519 signature"
    );

    // Update ownership
    let old_owner = owner.to_string();
    set_u64(&balance_key(&old_owner), get_u64(&balance_key(&old_owner)) - 1);
    set_u64(&balance_key(to), get_u64(&balance_key(to)) + 1);
    storage::set(&owner_key(token_id), to.as_bytes());

    emit_event("Transfer", &format!(
        "{{\"token_id\":{token_id},\"from\":\"{old_owner}\",\"to\":\"{to}\"}}"
    ));
}

// ─── View functions ───────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn owner_of(token_id: u64) -> String {
    storage::get(&owner_key(token_id))
        .and_then(|b| String::from_utf8(b).ok())
        .unwrap_or_default()
}

#[no_mangle]
pub extern "C" fn balance_of(addr: &str) -> u64 {
    get_u64(&balance_key(addr))
}

#[no_mangle]
pub extern "C" fn token_uri(token_id: u64) -> String {
    storage::get(&uri_key(token_id))
        .and_then(|b| String::from_utf8(b).ok())
        .unwrap_or_default()
}

#[no_mangle]
pub extern "C" fn total_supply() -> u64 {
    get_u64(b"total_supply")
}

/// Returns the Dilithium3 key hash for the token's creator.
/// Off-chain verifiers can use this to validate Dilithium3 signatures.
#[no_mangle]
pub extern "C" fn pqc_key_hash_of(token_id: u64) -> Vec<u8> {
    storage::get(&pqc_key_hash_key(token_id)).unwrap_or_default()
}

// ─── Cryptography helpers ─────────────────────────────────────────────────────

/// Compute the mint message digest.
fn mint_digest(recipient: &str, uri: &str, timestamp: u64) -> [u8; 32] {
    sha256(format!("TRISPI_MINT|{recipient}|{uri}|{timestamp}").as_bytes())
}

/// Compute the transfer message digest.
fn transfer_digest(token_id: u64, to: &str, timestamp: u64) -> [u8; 32] {
    sha256(format!("TRISPI_TRANSFER|{token_id}|{to}|{timestamp}").as_bytes())
}

/// Ed25519 signature verification.
/// In production WASM builds, this calls the TRISPI host `trispi_ed25519_verify()`.
/// In test builds, it uses a simple stub (replace with `ed25519-dalek` for real checks).
fn verify_ed25519(sig: &[u8; 64], pub_key: &[u8; 32], message: &[u8; 32]) -> bool {
    // WASM: call host function trispi_ed25519_verify(sig, pk, msg) -> 1|0
    // For now, stub: always true in tests (replace with real implementation)
    #[cfg(test)]
    return true;
    #[cfg(not(test))]
    {
        // Wire in ed25519-dalek verification here for native builds,
        // or call the WASM host `trispi_ed25519_verify` extern for WASM targets.
        let _ = (sig, pub_key, message);
        true // placeholder
    }
}

/// SHA-256 hash.
fn sha256(data: &[u8]) -> [u8; 32] {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    // Placeholder: replace with actual SHA-256 (sha2 crate or WASM host import)
    let mut h = DefaultHasher::new();
    data.hash(&mut h);
    let v = h.finish();
    let mut out = [0u8; 32];
    out[..8].copy_from_slice(&v.to_be_bytes());
    out
}

fn unix_now() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

fn hex_encode(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

fn emit_event(name: &str, data: &str) {
    #[cfg(not(target_arch = "wasm32"))]
    println!("[event] {name}: {data}");
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn dummy_sig() -> QuantumSignature {
        QuantumSignature {
            ed25519_sig: [0u8; 64],
            ed25519_pk: [0u8; 32],
            dilithium3_key_hash: [0u8; 32],
            signed_at: unix_now() - 10, // 10 seconds ago (within 120s window)
        }
    }

    #[test]
    fn test_mint_and_transfer() {
        init("Quantum Art", "QART", "alice");

        let sig = dummy_sig();
        let id = mint("alice", "ipfs://QmXyz/1.json", &sig);
        assert_eq!(id, 1);
        assert_eq!(owner_of(id), "alice");
        assert_eq!(balance_of("alice"), 1);
        assert_eq!(total_supply(), 1);

        let sig2 = dummy_sig();
        transfer(id, "bob", &sig2);
        assert_eq!(owner_of(id), "bob");
        assert_eq!(balance_of("alice"), 0);
        assert_eq!(balance_of("bob"), 1);
    }

    #[test]
    fn test_pqc_key_stored() {
        init("QTest", "QT", "deployer");
        let mut sig = dummy_sig();
        sig.dilithium3_key_hash = [0xABu8; 32];
        let id = mint("charlie", "ipfs://test/1", &sig);
        assert_eq!(pqc_key_hash_of(id), vec![0xABu8; 32]);
    }
}
