// TRISPI WASM Smart Contract — TRP20 Fungible Token
//
// Implements the TRP20 token standard on TRISPI's WASM runtime.
// Equivalent to ERC-20 but runs natively in WebAssembly.
//
// Build:
//   rustup target add wasm32-unknown-unknown
//   cargo build --target wasm32-unknown-unknown --release
//
// Deploy:
//   curl -X POST http://localhost:8000/api/contracts/deploy \
//     -H "Content-Type: application/json" \
//     -d '{"code": "<base64_wasm>", "runtime": "wasm", "deployer": "trp1ADDR",
//          "metadata": {"name": "MyToken", "symbol": "MTK", "supply": 1000000}}'

use std::collections::HashMap;

// ─── Storage simulation (replaced by WASM host imports in production) ─────────
#[cfg(not(target_arch = "wasm32"))]
mod storage {
    use std::collections::HashMap;
    use std::sync::Mutex;

    static S: Mutex<Option<HashMap<Vec<u8>, Vec<u8>>>> = Mutex::new(None);

    pub fn get(key: &[u8]) -> Option<Vec<u8>> {
        let guard = S.lock().unwrap();
        guard.as_ref()?.get(key).cloned()
    }

    pub fn set(key: &[u8], val: &[u8]) {
        let mut guard = S.lock().unwrap();
        guard.get_or_insert_default().insert(key.to_vec(), val.to_vec());
    }
}

// ─── Storage keys ─────────────────────────────────────────────────────────────

fn balance_key(addr: &str) -> Vec<u8> {
    [b"bal:".as_ref(), addr.as_bytes()].concat()
}

fn allowance_key(owner: &str, spender: &str) -> Vec<u8> {
    format!("alw:{owner}:{spender}").into_bytes()
}

const KEY_TOTAL_SUPPLY: &[u8] = b"total_supply";
const KEY_NAME:         &[u8] = b"name";
const KEY_SYMBOL:       &[u8] = b"symbol";
const KEY_DECIMALS:     &[u8] = b"decimals";

// ─── Serialization helpers ────────────────────────────────────────────────────

fn u128_to_bytes(v: u128) -> Vec<u8> { v.to_be_bytes().to_vec() }
fn u128_from_bytes(b: &[u8]) -> u128 {
    if b.len() < 16 { return 0; }
    u128::from_be_bytes(b[..16].try_into().unwrap_or([0u8; 16]))
}

fn get_u128(key: &[u8]) -> u128 {
    storage::get(key).map(|b| u128_from_bytes(&b)).unwrap_or(0)
}
fn set_u128(key: &[u8], v: u128) {
    storage::set(key, &u128_to_bytes(v));
}

// ─── Contract initialisation ──────────────────────────────────────────────────

/// Deploy: mint `initial_supply` tokens to the deployer.
#[no_mangle]
pub extern "C" fn init(
    name: &str,
    symbol: &str,
    decimals: u8,
    initial_supply: u128,
    deployer: &str,
) {
    storage::set(KEY_NAME,     name.as_bytes());
    storage::set(KEY_SYMBOL,   symbol.as_bytes());
    storage::set(KEY_DECIMALS, &[decimals]);
    set_u128(KEY_TOTAL_SUPPLY, initial_supply);
    set_u128(&balance_key(deployer), initial_supply);

    emit_event("Transfer", &format!(
        "{{\"from\":\"0x0\",\"to\":\"{deployer}\",\"amount\":{initial_supply}}}"
    ));
}

// ─── Read functions ───────────────────────────────────────────────────────────

#[no_mangle]
pub extern "C" fn total_supply() -> u128 {
    get_u128(KEY_TOTAL_SUPPLY)
}

#[no_mangle]
pub extern "C" fn balance_of(addr: &str) -> u128 {
    get_u128(&balance_key(addr))
}

#[no_mangle]
pub extern "C" fn allowance(owner: &str, spender: &str) -> u128 {
    get_u128(&allowance_key(owner, spender))
}

// ─── Write functions ──────────────────────────────────────────────────────────

/// Transfer `amount` tokens from `from` to `to`.
#[no_mangle]
pub extern "C" fn transfer(from: &str, to: &str, amount: u128) -> bool {
    let from_bal = balance_of(from);
    assert!(from_bal >= amount, "insufficient balance");

    set_u128(&balance_key(from), from_bal - amount);
    set_u128(&balance_key(to), balance_of(to) + amount);

    emit_event("Transfer", &format!(
        "{{\"from\":\"{from}\",\"to\":\"{to}\",\"amount\":{amount}}}"
    ));
    true
}

/// Approve `spender` to spend up to `amount` tokens on behalf of `owner`.
#[no_mangle]
pub extern "C" fn approve(owner: &str, spender: &str, amount: u128) -> bool {
    set_u128(&allowance_key(owner, spender), amount);
    emit_event("Approval", &format!(
        "{{\"owner\":\"{owner}\",\"spender\":\"{spender}\",\"amount\":{amount}}}"
    ));
    true
}

/// Transfer tokens using a pre-approved allowance.
#[no_mangle]
pub extern "C" fn transfer_from(caller: &str, from: &str, to: &str, amount: u128) -> bool {
    let allowed = allowance(from, caller);
    assert!(allowed >= amount, "allowance exceeded");

    let from_bal = balance_of(from);
    assert!(from_bal >= amount, "insufficient balance");

    set_u128(&allowance_key(from, caller), allowed - amount);
    set_u128(&balance_key(from), from_bal - amount);
    set_u128(&balance_key(to), balance_of(to) + amount);

    emit_event("Transfer", &format!(
        "{{\"from\":\"{from}\",\"to\":\"{to}\",\"amount\":{amount},\"by\":\"{caller}\"}}"
    ));
    true
}

/// Burn `amount` tokens from `from` — reduces total supply.
#[no_mangle]
pub extern "C" fn burn(from: &str, amount: u128) {
    let bal = balance_of(from);
    assert!(bal >= amount, "insufficient balance");
    set_u128(&balance_key(from), bal - amount);
    set_u128(KEY_TOTAL_SUPPLY, total_supply() - amount);
    emit_event("Burn", &format!("{{\"from\":\"{from}\",\"amount\":{amount}}}"));
}

// ─── Event helper ─────────────────────────────────────────────────────────────

fn emit_event(name: &str, data: &str) {
    #[cfg(not(target_arch = "wasm32"))]
    println!("[event] {name}: {data}");
}

// ─── Tests ────────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_token_lifecycle() {
        init("MyToken", "MTK", 18, 1_000_000, "alice");

        assert_eq!(total_supply(), 1_000_000);
        assert_eq!(balance_of("alice"), 1_000_000);
        assert_eq!(balance_of("bob"), 0);

        transfer("alice", "bob", 100);
        assert_eq!(balance_of("alice"), 999_900);
        assert_eq!(balance_of("bob"), 100);

        approve("alice", "charlie", 500);
        assert_eq!(allowance("alice", "charlie"), 500);

        transfer_from("charlie", "alice", "bob", 200);
        assert_eq!(balance_of("bob"), 300);
        assert_eq!(allowance("alice", "charlie"), 300);

        burn("bob", 50);
        assert_eq!(total_supply(), 999_950);
    }
}
