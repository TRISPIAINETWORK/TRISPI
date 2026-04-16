// TRISPI Node — Rust Implementation Example
//
// Demonstrates how to build a TRISPI-compatible node in Rust with:
//   - Ed25519 signing (via the `ed25519-dalek` crate)
//   - Post-quantum Dilithium3 stub (wire in `pqcrypto-dilithium` here)
//   - SHA-256 block hashing
//   - Peer scoring & rate limiting (Sybil protection)
//   - TCP listener for P2P block propagation
//   - HTTP API server (health, chain, mine)
//
// Run:
//   cargo run -- --id mynode --http 8081 --p2p 6001
//
// Cargo.toml dependencies (add to your project):
//   ed25519-dalek = { version = "2", features = ["rand_core"] }
//   sha2 = "0.10"
//   serde = { version = "1", features = ["derive"] }
//   serde_json = "1"
//   rand = "0.8"
//   clap = { version = "4", features = ["derive"] }
//   tokio = { version = "1", features = ["full"] }
//   axum = "0.7"

use std::{
    collections::HashMap,
    net::SocketAddr,
    sync::{Arc, RwLock},
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};

use clap::Parser;
use ed25519_dalek::{Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tokio::io::AsyncWriteExt;
use axum::{extract::State, response::Json, routing::get, Router};

// ─── CLI ──────────────────────────────────────────────────────────────────────

#[derive(Parser)]
#[command(name = "trispi-node", about = "TRISPI Node — Rust example")]
struct Cli {
    #[arg(long, default_value = "node1")]
    id: String,
    #[arg(long, default_value_t = 8081)]
    http: u16,
    #[arg(long, default_value_t = 6001)]
    p2p: u16,
}

// ─── Peer scoring constants ───────────────────────────────────────────────────

const MAX_MSG_PER_MINUTE: u32 = 60;
const MIN_STAKE_FOR_QUORUM: f64 = 1.0;
const PEER_BAN_THRESHOLD: f64 = -10.0;
const PEER_GOOD_MSG_REWARD: f64 = 0.1;
const PEER_BAD_MSG_PENALTY: f64 = -2.0;
const PEER_INVALID_BLOCK_PENALTY: f64 = -20.0;

// ─── Data types ───────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumSignature {
    pub ed25519_sig: String,
    /// Dilithium3 placeholder — replace with real PQC signature
    /// using the `pqcrypto-dilithium` crate:
    ///   let sig = pqcrypto_dilithium::dilithium3::sign(msg, &sk);
    pub dilithium_sig: String,
    pub pub_key: String,
    pub signed_at: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub tx_id: String,
    pub from: String,
    pub to: String,
    pub amount: f64,
    pub gas_fee: f64,
    pub nonce: u64,
    pub data: Option<String>,
    pub signature: QuantumSignature,
    pub timestamp: u64,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    pub index: u64,
    pub timestamp: String,
    pub transactions: Vec<Transaction>,
    pub prev_hash: String,
    pub hash: String,
    pub nonce: u64,
    pub merkle_root: String,
    pub proposer: String,
    pub signature: QuantumSignature,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PBFTVote {
    pub validator_id: String,
    pub block_hash: String,
    pub vote_type: String,
    pub signature: QuantumSignature,
    pub timestamp: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Validator {
    pub id: String,
    pub pub_key: String,
    pub stake: f64,
    pub reputation: f64,
    pub is_active: bool,
}

/// Per-peer scoring entry for Sybil resistance and rate limiting.
#[derive(Debug, Clone)]
pub struct PeerScore {
    pub score: f64,
    pub msg_count: u32,
    pub window_start: Instant,
    pub banned: bool,
    pub banned_until: Instant,
}

impl Default for PeerScore {
    fn default() -> Self {
        PeerScore {
            score: 0.0,
            msg_count: 0,
            window_start: Instant::now(),
            banned: false,
            banned_until: Instant::now(),
        }
    }
}

// ─── Node ─────────────────────────────────────────────────────────────────────

pub struct Node {
    pub id: String,
    pub chain: Vec<Block>,
    pub validators: HashMap<String, Validator>,
    pub balances: HashMap<String, f64>,
    pub peer_scores: HashMap<String, PeerScore>,
    pub pbft_votes: HashMap<String, PBFTVote>,

    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl Node {
    pub fn new(id: &str) -> Self {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let verifying_key = signing_key.verifying_key();

        let mut node = Node {
            id: id.to_string(),
            chain: Vec::new(),
            validators: HashMap::new(),
            balances: HashMap::new(),
            peer_scores: HashMap::new(),
            pbft_votes: HashMap::new(),
            signing_key,
            verifying_key,
        };

        // Genesis block
        let genesis = node.make_genesis();
        node.chain.push(genesis);

        // Register self as staked validator
        node.validators.insert(id.to_string(), Validator {
            id: id.to_string(),
            pub_key: hex::encode(verifying_key.as_bytes()),
            stake: 1000.0,
            reputation: 1.0,
            is_active: true,
        });
        node.balances.insert("trp1genesis".into(), 50_000_000.0);

        eprintln!("[node] {} started | pubkey={}...",
            id, &hex::encode(verifying_key.as_bytes())[..16]);
        node
    }

    // ── Crypto ────────────────────────────────────────────────────────────────

    fn sha256hex(data: &[u8]) -> String {
        let mut h = Sha256::new();
        h.update(data);
        hex::encode(h.finalize())
    }

    fn block_hash(b: &Block) -> String {
        let data = format!("{}|{}|{}|{}|{}|{}",
            b.index, b.timestamp, b.prev_hash, b.merkle_root, b.nonce, b.proposer);
        Self::sha256hex(data.as_bytes())
    }

    fn merkle_root(txs: &[Transaction]) -> String {
        if txs.is_empty() {
            return Self::sha256hex(b"empty");
        }
        let mut hashes: Vec<String> = txs.iter()
            .map(|tx| Self::sha256hex(serde_json::to_string(tx).unwrap_or_default().as_bytes()))
            .collect();
        while hashes.len() > 1 {
            if hashes.len() % 2 == 1 {
                let last = hashes.last().unwrap().clone();
                hashes.push(last);
            }
            hashes = hashes.chunks(2)
                .map(|pair| Self::sha256hex(format!("{}{}", pair[0], pair[1]).as_bytes()))
                .collect();
        }
        hashes[0].clone()
    }

    fn sign(&self, data: &str) -> QuantumSignature {
        let sig = self.signing_key.sign(data.as_bytes());
        QuantumSignature {
            ed25519_sig: hex::encode(sig.to_bytes()),
            dilithium_sig: String::new(), // TODO: wire in pqcrypto_dilithium here
            pub_key: hex::encode(self.verifying_key.as_bytes()),
            signed_at: unix_now(),
        }
    }

    fn verify_ed25519(sig: &QuantumSignature, data: &str) -> bool {
        let Ok(pub_bytes) = hex::decode(&sig.pub_key) else { return false };
        let Ok(vk) = VerifyingKey::from_bytes(pub_bytes.as_slice().try_into().unwrap_or(&[0u8; 32])) else { return false };
        let Ok(sig_bytes) = hex::decode(&sig.ed25519_sig) else { return false };
        let Ok(sig) = ed25519_dalek::Signature::from_slice(&sig_bytes) else { return false };
        vk.verify(data.as_bytes(), &sig).is_ok()
    }

    // ── Genesis ───────────────────────────────────────────────────────────────

    fn make_genesis(&self) -> Block {
        let mut b = Block {
            index: 0,
            timestamp: iso_now(),
            transactions: vec![],
            prev_hash: "0".repeat(64),
            hash: String::new(),
            nonce: 0,
            merkle_root: Self::sha256hex(b"genesis"),
            proposer: "genesis".into(),
            signature: QuantumSignature {
                ed25519_sig: String::new(),
                dilithium_sig: String::new(),
                pub_key: String::new(),
                signed_at: 0,
            },
        };
        b.hash = Self::block_hash(&b);
        b
    }

    // ── Mining ────────────────────────────────────────────────────────────────

    pub fn mine_block(&self) -> Block {
        let prev = self.chain.last().unwrap();
        let mut b = Block {
            index: prev.index + 1,
            timestamp: iso_now(),
            transactions: vec![],
            prev_hash: prev.hash.clone(),
            hash: String::new(),
            nonce: 0,
            merkle_root: Self::merkle_root(&[]),
            proposer: self.id.clone(),
            signature: QuantumSignature {
                ed25519_sig: String::new(),
                dilithium_sig: String::new(),
                pub_key: String::new(),
                signed_at: 0,
            },
        };
        // Difficulty-1 proof of work
        loop {
            b.nonce += 1;
            b.hash = Self::block_hash(&b);
            if b.hash.starts_with('0') {
                break;
            }
        }
        b.signature = self.sign(&b.hash);
        b
    }

    pub fn add_block(&mut self, b: Block, from_peer: &str) -> Result<(), String> {
        // Validate
        let prev = self.chain.last().ok_or("empty chain")?;
        if b.index != prev.index + 1 {
            self.adjust_score(from_peer, PEER_INVALID_BLOCK_PENALTY);
            return Err(format!("wrong index: got {} want {}", b.index, prev.index + 1));
        }
        if b.prev_hash != prev.hash {
            self.adjust_score(from_peer, PEER_INVALID_BLOCK_PENALTY);
            return Err("prev_hash mismatch".into());
        }
        if Self::block_hash(&b) != b.hash {
            self.adjust_score(from_peer, PEER_INVALID_BLOCK_PENALTY);
            return Err("hash mismatch".into());
        }
        if !Self::verify_ed25519(&b.signature, &b.hash) {
            self.adjust_score(from_peer, PEER_INVALID_BLOCK_PENALTY);
            return Err("invalid signature".into());
        }
        self.adjust_score(from_peer, PEER_GOOD_MSG_REWARD);
        self.chain.push(b);
        Ok(())
    }

    // ── PBFT ─────────────────────────────────────────────────────────────────

    fn staked_quorum(&self) -> usize {
        let staked = self.validators.values()
            .filter(|v| v.stake >= MIN_STAKE_FOR_QUORUM && v.is_active)
            .count();
        (staked.max(1) * 2 / 3) + 1
    }

    pub fn handle_pbft_vote(&mut self, vote: PBFTVote, from_peer: &str) {
        if !self.check_rate_and_score(from_peer) {
            return;
        }
        // Only staked validators can vote
        if self.validators.get(&vote.validator_id)
            .map(|v| v.stake < MIN_STAKE_FOR_QUORUM)
            .unwrap_or(true)
        {
            self.adjust_score(from_peer, PEER_BAD_MSG_PENALTY);
            return;
        }
        if !Self::verify_ed25519(&vote.signature, &vote.block_hash) {
            self.adjust_score(from_peer, PEER_BAD_MSG_PENALTY);
            return;
        }

        self.pbft_votes.insert(vote.validator_id.clone(), vote);
        self.adjust_score(from_peer, PEER_GOOD_MSG_REWARD);

        let commit_count = self.pbft_votes.values()
            .filter(|v| v.vote_type == "commit")
            .count();

        if commit_count >= self.staked_quorum() {
            eprintln!("[pbft] COMMIT quorum reached ({commit_count}) — ready to finalize");
            self.pbft_votes.clear();
        }
    }

    // ── Peer Scoring & Sybil Protection ───────────────────────────────────────

    fn check_rate_and_score(&mut self, peer_id: &str) -> bool {
        let ps = self.peer_scores.entry(peer_id.to_string()).or_default();

        // Check ban
        if ps.banned {
            if Instant::now() < ps.banned_until {
                return false;
            }
            ps.banned = false;
            ps.score = 0.0;
            eprintln!("[scoring] peer {peer_id:.12} unbanned");
        }

        // Rate limit window reset
        if ps.window_start.elapsed() > Duration::from_secs(60) {
            ps.msg_count = 0;
            ps.window_start = Instant::now();
        }
        ps.msg_count += 1;
        if ps.msg_count > MAX_MSG_PER_MINUTE {
            eprintln!("[scoring] peer {peer_id:.12} rate limited");
            self.adjust_score(peer_id, PEER_BAD_MSG_PENALTY);
            return false;
        }

        true
    }

    fn adjust_score(&mut self, peer_id: &str, delta: f64) {
        let ps = self.peer_scores.entry(peer_id.to_string()).or_default();
        ps.score += delta;
        if ps.score < PEER_BAN_THRESHOLD && !ps.banned {
            ps.banned = true;
            ps.banned_until = Instant::now() + Duration::from_secs(1800);
            eprintln!("[scoring] peer {peer_id:.12} BANNED (score={:.1})", ps.score);
        }
    }
}

// ─── HTTP API ─────────────────────────────────────────────────────────────────

type SharedNode = Arc<RwLock<Node>>;

async fn health_handler(State(node): State<SharedNode>) -> Json<serde_json::Value> {
    let n = node.read().unwrap();
    Json(serde_json::json!({
        "status": "ok",
        "node_id": n.id,
        "chain_len": n.chain.len(),
        "validators": n.validators.len(),
    }))
}

async fn chain_handler(State(node): State<SharedNode>) -> Json<serde_json::Value> {
    let n = node.read().unwrap();
    Json(serde_json::json!(n.chain))
}

async fn mine_handler(State(node): State<SharedNode>) -> Json<serde_json::Value> {
    let block = {
        let n = node.read().unwrap();
        n.mine_block()
    };
    let mut n = node.write().unwrap();
    n.chain.push(block.clone());
    Json(serde_json::json!(block))
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

fn unix_now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_secs()
}

fn iso_now() -> String {
    let d = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    format!("{}", d.as_secs())
}

// ─── Main ─────────────────────────────────────────────────────────────────────

#[tokio::main]
async fn main() {
    let cli = Cli::parse();

    let node = Arc::new(RwLock::new(Node::new(&cli.id)));

    // HTTP API
    let app = Router::new()
        .route("/health", get(health_handler))
        .route("/chain", get(chain_handler))
        .route("/mine", get(mine_handler))
        .with_state(Arc::clone(&node));

    let addr = SocketAddr::from(([0, 0, 0, 0], cli.http));
    eprintln!("[http] listening on {addr}");

    // Block mining loop
    let node_mine = Arc::clone(&node);
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_secs(3));
        loop {
            interval.tick().await;
            let block = {
                let n = node_mine.read().unwrap();
                n.mine_block()
            };
            let mut n = node_mine.write().unwrap();
            n.chain.push(block.clone());
            eprintln!("[chain] block #{} mined | hash={}...", block.index, &block.hash[..8]);
        }
    });

    // Minimal TCP P2P listener (receives JSON blocks from peers)
    let node_p2p = Arc::clone(&node);
    let p2p_addr = format!("0.0.0.0:{}", cli.p2p);
    tokio::spawn(async move {
        let listener = tokio::net::TcpListener::bind(&p2p_addr).await.unwrap();
        eprintln!("[p2p] TCP listening on {p2p_addr}");
        loop {
            if let Ok((mut stream, peer_addr)) = listener.accept().await {
                let node_ref = Arc::clone(&node_p2p);
                tokio::spawn(async move {
                    let mut buf = Vec::new();
                    use tokio::io::AsyncReadExt;
                    let _ = stream.read_to_end(&mut buf).await;
                    if let Ok(block) = serde_json::from_slice::<Block>(&buf) {
                        let peer = peer_addr.to_string();
                        let mut n = node_ref.write().unwrap();
                        match n.add_block(block.clone(), &peer) {
                            Ok(_) => eprintln!("[p2p] accepted block #{} from {peer}", block.index),
                            Err(e) => eprintln!("[p2p] rejected block from {peer}: {e}"),
                        }
                    }
                    let _ = stream.shutdown().await;
                });
            }
        }
    });

    axum::serve(
        tokio::net::TcpListener::bind(addr).await.unwrap(),
        app
    ).await.unwrap();
}
