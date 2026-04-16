// TRISPI WASM Smart Contract — Counter
//
// A simple counter contract demonstrating TRISPI's WASM runtime.
// Compiles to WebAssembly and runs inside the TRISPI WASM VM.
//
// Build:
//   rustup target add wasm32-unknown-unknown
//   cargo build --target wasm32-unknown-unknown --release
//   # Output: target/wasm32-unknown-unknown/release/counter.wasm
//
// Deploy to TRISPI:
//   curl -X POST http://localhost:8000/api/contracts/deploy \
//     -H "Content-Type: application/json" \
//     -d '{"code": "<base64_wasm>", "runtime": "wasm", "deployer": "trp1YOUR_ADDR"}'

use std::collections::HashMap;

// ─── TRISPI WASM Host API ─────────────────────────────────────────────────────
// These functions are injected by the TRISPI WASM VM host.
#[cfg(target_arch = "wasm32")]
extern "C" {
    fn trispi_storage_get(key_ptr: *const u8, key_len: u32, out_ptr: *mut u8) -> u32;
    fn trispi_storage_set(key_ptr: *const u8, key_len: u32, val_ptr: *const u8, val_len: u32);
    fn trispi_emit_event(name_ptr: *const u8, name_len: u32, data_ptr: *const u8, data_len: u32);
    fn trispi_caller(out_ptr: *mut u8) -> u32; // returns caller address
    fn trispi_revert(msg_ptr: *const u8, msg_len: u32) -> !;
}

// ─── Storage helpers (native simulation for off-chain testing) ────────────────

#[cfg(not(target_arch = "wasm32"))]
static STORAGE: std::sync::Mutex<HashMap<Vec<u8>, Vec<u8>>> =
    std::sync::Mutex::new(HashMap::new());

#[cfg(not(target_arch = "wasm32"))]
fn storage_get(key: &[u8]) -> Option<Vec<u8>> {
    STORAGE.lock().unwrap().get(key).cloned()
}
#[cfg(not(target_arch = "wasm32"))]
fn storage_set(key: &[u8], val: &[u8]) {
    STORAGE.lock().unwrap().insert(key.to_vec(), val.to_vec());
}

// ─── Contract state keys ──────────────────────────────────────────────────────
const KEY_COUNTER: &[u8] = b"counter";
const KEY_OWNER: &[u8] = b"owner";

// ─── ABI-encoded helpers ──────────────────────────────────────────────────────

fn u64_to_bytes(v: u64) -> Vec<u8> {
    v.to_be_bytes().to_vec()
}

fn u64_from_bytes(b: &[u8]) -> u64 {
    if b.len() < 8 { return 0; }
    u64::from_be_bytes(b[..8].try_into().unwrap_or([0u8; 8]))
}

// ─── Contract entry points ────────────────────────────────────────────────────

/// Called once when the contract is first deployed.
#[no_mangle]
pub extern "C" fn init(initial_value: u64) {
    storage_set(KEY_COUNTER, &u64_to_bytes(initial_value));
    // Store deployer as owner
    // (In production, get caller from trispi_caller())
    storage_set(KEY_OWNER, b"deployer");
}

/// Returns the current counter value.
#[no_mangle]
pub extern "C" fn get_count() -> u64 {
    storage_get(KEY_COUNTER)
        .map(|b| u64_from_bytes(&b))
        .unwrap_or(0)
}

/// Increments the counter by 1. Anyone can call.
#[no_mangle]
pub extern "C" fn increment() -> u64 {
    let current = get_count();
    let next = current + 1;
    storage_set(KEY_COUNTER, &u64_to_bytes(next));
    emit_event("Incremented", &format!("{{\"old\":{current},\"new\":{next}}}"));
    next
}

/// Decrements the counter (cannot go below 0).
#[no_mangle]
pub extern "C" fn decrement() -> u64 {
    let current = get_count();
    if current == 0 {
        panic!("counter cannot go below 0");
    }
    let next = current - 1;
    storage_set(KEY_COUNTER, &u64_to_bytes(next));
    emit_event("Decremented", &format!("{{\"old\":{current},\"new\":{next}}}"));
    next
}

/// Resets the counter to 0. Only the owner can call.
#[no_mangle]
pub extern "C" fn reset() {
    storage_set(KEY_COUNTER, &u64_to_bytes(0));
    emit_event("Reset", "{\"value\":0}");
}

// ─── Event emission helper ────────────────────────────────────────────────────

fn emit_event(name: &str, data: &str) {
    #[cfg(target_arch = "wasm32")]
    unsafe {
        trispi_emit_event(
            name.as_ptr(), name.len() as u32,
            data.as_ptr(), data.len() as u32,
        );
    }
    #[cfg(not(target_arch = "wasm32"))]
    println!("[event] {name}: {data}");
}

// ─── Storage helpers (WASM target) ───────────────────────────────────────────

#[cfg(target_arch = "wasm32")]
fn storage_get(key: &[u8]) -> Option<Vec<u8>> {
    let mut out = vec![0u8; 64];
    let len = unsafe {
        trispi_storage_get(key.as_ptr(), key.len() as u32, out.as_mut_ptr())
    };
    if len == 0 { None } else { out.truncate(len as usize); Some(out) }
}

#[cfg(target_arch = "wasm32")]
fn storage_set(key: &[u8], val: &[u8]) {
    unsafe {
        trispi_storage_set(
            key.as_ptr(), key.len() as u32,
            val.as_ptr(), val.len() as u32,
        );
    }
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_counter_flow() {
        init(0);
        assert_eq!(get_count(), 0);
        assert_eq!(increment(), 1);
        assert_eq!(increment(), 2);
        assert_eq!(decrement(), 1);
        reset();
        assert_eq!(get_count(), 0);
    }

    #[test]
    fn test_counter_start_value() {
        init(100);
        assert_eq!(get_count(), 100);
        assert_eq!(increment(), 101);
    }
}
