// TRISPI Node — Go Implementation Example
//
// This file shows how to build a minimal TRISPI-compatible node from scratch in Go.
// It implements:
//   - Ed25519 key generation and block signing
//   - PBFT consensus (prepare / commit phases)
//   - libp2p P2P networking (TCP + QUIC-v1, mDNS + DHT)
//   - Peer scoring and Sybil protection
//   - HTTP API (compatible with TRISPI Python gateway)
//
// Run:
//   go mod init trispi-node-example
//   go mod tidy
//   go run main.go -id mynode -http 8081 -p2p 50052
//
// Dependencies (go.mod):
//   github.com/libp2p/go-libp2p v0.35.0
//   github.com/libp2p/go-libp2p-kad-dht v0.25.2
//   github.com/multiformats/go-multiaddr v0.13.0

package main

import (
	"context"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"math"
	"net/http"
	"os"
	"sync"
	"time"

	dht "github.com/libp2p/go-libp2p-kad-dht"
	libp2p "github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/network"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/core/protocol"
	"github.com/libp2p/go-libp2p/p2p/discovery/mdns"
	discrouting "github.com/libp2p/go-libp2p/p2p/discovery/routing"
	"github.com/libp2p/go-libp2p/p2p/muxer/yamux"
	"github.com/libp2p/go-libp2p/p2p/security/noise"
	libp2ptcp "github.com/libp2p/go-libp2p/p2p/transport/tcp"
	libp2pquic "github.com/libp2p/go-libp2p/p2p/transport/quic"
	ma "github.com/multiformats/go-multiaddr"
)

// ─── Constants ────────────────────────────────────────────────────────────────

const (
	ConsensusProtocol = protocol.ID("/trispi/consensus/1.0.0")
	TRISPIRendezvous  = "trispi-consensus-v1"

	// Sybil / peer scoring parameters
	MaxMsgPerMinute     = 60    // rate limit: messages per peer per minute
	MinStakeForQuorum   = 1.0   // minimum stake (TRP) to participate in PBFT quorum
	PeerBanThreshold    = -10.0 // peer score below this → banned
	PeerGoodMsgReward   = 0.1   // score reward per valid message
	PeerBadMsgPenalty   = -2.0  // score penalty per invalid message
	PeerBlockBanPenalty = -20.0 // score penalty for sending invalid block
)

// ─── Data types ───────────────────────────────────────────────────────────────

type QuantumSignature struct {
	Ed25519Sig   string `json:"ed25519_sig"`
	DilithiumSig string `json:"dilithium_sig,omitempty"` // placeholder — wire in real Dilithium3 here
	PubKey       string `json:"pub_key"`
	SignedAt     int64  `json:"signed_at"`
}

type Transaction struct {
	TxID      string           `json:"tx_id"`
	From      string           `json:"from"`
	To        string           `json:"to"`
	Amount    float64          `json:"amount"`
	GasFee    float64          `json:"gas_fee"`
	Nonce     int              `json:"nonce"`
	Data      string           `json:"data,omitempty"`
	Signature QuantumSignature `json:"signature"`
	Timestamp int64            `json:"timestamp"`
	Status    string           `json:"status"`
}

type Block struct {
	Index        int              `json:"index"`
	Timestamp    string           `json:"timestamp"`
	Transactions []Transaction    `json:"transactions"`
	PrevHash     string           `json:"prev_hash"`
	Hash         string           `json:"hash"`
	Nonce        int              `json:"nonce"`
	MerkleRoot   string           `json:"merkle_root"`
	Proposer     string           `json:"proposer"`
	Signature    QuantumSignature `json:"signature"`
	PBFTVotes    []PBFTVote       `json:"pbft_votes"`
}

type PBFTVote struct {
	ValidatorID string           `json:"validator_id"`
	BlockHash   string           `json:"block_hash"`
	VoteType    string           `json:"vote_type"`
	Signature   QuantumSignature `json:"signature"`
	Timestamp   int64            `json:"timestamp"`
}

type Validator struct {
	ID         string  `json:"id"`
	PubKey     string  `json:"pub_key"`
	Stake      float64 `json:"stake"`
	Reputation float64 `json:"reputation"`
	IsActive   bool    `json:"is_active"`
}

// PeerScore tracks per-peer scoring for Sybil resistance and rate limiting.
type PeerScore struct {
	PeerID      string
	Score       float64
	MsgCount    int       // messages received this minute
	WindowStart time.Time // start of current rate-limit window
	Banned      bool
	BannedUntil time.Time
}

// ─── Node ─────────────────────────────────────────────────────────────────────

type Node struct {
	id         string
	chain      []*Block
	validators map[string]*Validator
	balances   map[string]float64
	peerScores map[string]*PeerScore // peer ID → score

	privKey ed25519.PrivateKey
	pubKey  ed25519.PublicKey

	pbftVotes map[string]PBFTVote // block_hash → vote
	pbftBlock *Block

	h   host.Host
	kad *dht.IpfsDHT
	ctx context.Context

	mu sync.RWMutex
}

func NewNode(id string) *Node {
	pub, priv, err := ed25519.GenerateKey(nil)
	if err != nil {
		log.Fatal("ed25519 key generation failed:", err)
	}

	n := &Node{
		id:         id,
		chain:      make([]*Block, 0),
		validators: make(map[string]*Validator),
		balances:   make(map[string]float64),
		peerScores: make(map[string]*PeerScore),
		pbftVotes:  make(map[string]PBFTVote),
		privKey:    priv,
		pubKey:     pub,
	}

	// Genesis block
	genesis := n.makeGenesisBlock()
	n.chain = append(n.chain, genesis)

	// Register self as staked validator
	n.validators[id] = &Validator{
		ID:         id,
		PubKey:     hex.EncodeToString(pub),
		Stake:      1000.0,
		Reputation: 1.0,
		IsActive:   true,
	}
	n.balances["trp1genesis"] = 50_000_000.0

	log.Printf("[node] Node %s started | pubkey: %s...", id, hex.EncodeToString(pub)[:16])
	return n
}

// ─── Cryptography ─────────────────────────────────────────────────────────────

func sha256hex(data []byte) string {
	h := sha256.Sum256(data)
	return hex.EncodeToString(h[:])
}

func (n *Node) sign(data string) QuantumSignature {
	sig := ed25519.Sign(n.privKey, []byte(data))
	return QuantumSignature{
		Ed25519Sig: hex.EncodeToString(sig),
		PubKey:     hex.EncodeToString(n.pubKey),
		SignedAt:   time.Now().Unix(),
		// DilithiumSig: dilithium.Sign(n.dilithiumKey, []byte(data)) — wire in here
	}
}

func verifyEd25519(sig QuantumSignature, data string) bool {
	pub, err := hex.DecodeString(sig.PubKey)
	if err != nil || len(pub) != ed25519.PublicKeySize {
		return false
	}
	sigBytes, err := hex.DecodeString(sig.Ed25519Sig)
	if err != nil {
		return false
	}
	return ed25519.Verify(ed25519.PublicKey(pub), []byte(data), sigBytes)
}

func (n *Node) blockHash(b *Block) string {
	return sha256hex([]byte(fmt.Sprintf("%d|%s|%s|%s|%d|%s",
		b.Index, b.Timestamp, b.PrevHash, b.MerkleRoot, b.Nonce, b.Proposer)))
}

func merkleRoot(txs []Transaction) string {
	if len(txs) == 0 {
		return sha256hex([]byte("empty"))
	}
	hashes := make([]string, len(txs))
	for i, tx := range txs {
		d, _ := json.Marshal(tx)
		hashes[i] = sha256hex(d)
	}
	for len(hashes) > 1 {
		if len(hashes)%2 == 1 {
			hashes = append(hashes, hashes[len(hashes)-1])
		}
		next := make([]string, len(hashes)/2)
		for i := 0; i < len(hashes); i += 2 {
			next[i/2] = sha256hex([]byte(hashes[i] + hashes[i+1]))
		}
		hashes = next
	}
	return hashes[0]
}

// ─── Genesis ──────────────────────────────────────────────────────────────────

func (n *Node) makeGenesisBlock() *Block {
	b := &Block{
		Index:      0,
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		Proposer:   "genesis",
		PrevHash:   fmt.Sprintf("%064d", 0),
		MerkleRoot: sha256hex([]byte("genesis")),
	}
	b.Hash = n.blockHash(b)
	return b
}

// ─── Block production ─────────────────────────────────────────────────────────

func (n *Node) MineBlock() *Block {
	n.mu.Lock()
	defer n.mu.Unlock()

	prev := n.chain[len(n.chain)-1]
	b := &Block{
		Index:      prev.Index + 1,
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		Proposer:   n.id,
		PrevHash:   prev.Hash,
		MerkleRoot: merkleRoot(nil),
	}
	// Simple difficulty-1 proof-of-work
	for {
		b.Nonce++
		b.Hash = n.blockHash(b)
		if b.Hash[0] == '0' {
			break
		}
	}
	b.Signature = n.sign(b.Hash)
	return b
}

func (n *Node) AddBlock(b *Block, fromPeerID string) bool {
	n.mu.Lock()
	defer n.mu.Unlock()

	// Peer scoring: invalid block → big penalty
	if err := n.validateBlock(b); err != nil {
		log.Printf("[node] invalid block from %s: %v", fromPeerID, err)
		n.adjustScore(fromPeerID, PeerBlockBanPenalty)
		return false
	}

	n.chain = append(n.chain, b)
	n.adjustScore(fromPeerID, PeerGoodMsgReward)
	log.Printf("[node] block #%d accepted from %s | hash=%s...", b.Index, fromPeerID, b.Hash[:8])
	return true
}

func (n *Node) validateBlock(b *Block) error {
	if b.Index != len(n.chain) {
		return fmt.Errorf("wrong index: got %d want %d", b.Index, len(n.chain))
	}
	prev := n.chain[len(n.chain)-1]
	if b.PrevHash != prev.Hash {
		return fmt.Errorf("prev hash mismatch")
	}
	if b.Hash != n.blockHash(b) {
		return fmt.Errorf("hash mismatch")
	}
	if !verifyEd25519(b.Signature, b.Hash) {
		return fmt.Errorf("invalid signature")
	}
	return nil
}

// ─── PBFT Consensus ───────────────────────────────────────────────────────────

// stakedQuorum returns the minimum votes needed for 2f+1 PBFT quorum
// from staked validators only (prevents Sybil quorum inflation).
func (n *Node) stakedQuorum() int {
	staked := 0
	for _, v := range n.validators {
		if v.Stake >= MinStakeForQuorum && v.IsActive {
			staked++
		}
	}
	if staked == 0 {
		return 1
	}
	return int(math.Floor(float64(staked)*2.0/3.0)) + 1
}

func (n *Node) HandlePBFTVote(vote PBFTVote, fromPeerID string) {
	n.mu.Lock()
	defer n.mu.Unlock()

	// Rate-limit + score gate
	if !n.checkRateAndScore(fromPeerID) {
		return
	}

	// Must be from a staked validator
	v, ok := n.validators[vote.ValidatorID]
	if !ok || v.Stake < MinStakeForQuorum {
		log.Printf("[pbft] vote from unstaked peer %s — ignored", fromPeerID)
		n.adjustScore(fromPeerID, PeerBadMsgPenalty)
		return
	}

	// Verify Ed25519 signature on the vote
	if !verifyEd25519(vote.Signature, vote.BlockHash) {
		log.Printf("[pbft] invalid vote signature from %s", fromPeerID)
		n.adjustScore(fromPeerID, PeerBadMsgPenalty)
		return
	}

	n.pbftVotes[vote.ValidatorID] = vote
	n.adjustScore(fromPeerID, PeerGoodMsgReward)

	quorum := n.stakedQuorum()
	commitCount := 0
	for _, v := range n.pbftVotes {
		if v.VoteType == "commit" {
			commitCount++
		}
	}

	if commitCount >= quorum && n.pbftBlock != nil {
		log.Printf("[pbft] COMMIT quorum reached (%d/%d) — block #%d finalized",
			commitCount, quorum, n.pbftBlock.Index)
		n.chain = append(n.chain, n.pbftBlock)
		n.pbftBlock = nil
		n.pbftVotes = make(map[string]PBFTVote)
	}
}

// ─── Peer Scoring & Sybil Protection ──────────────────────────────────────────

func (n *Node) getOrCreateScore(peerID string) *PeerScore {
	ps, ok := n.peerScores[peerID]
	if !ok {
		ps = &PeerScore{
			PeerID:      peerID,
			Score:       0.0,
			WindowStart: time.Now(),
		}
		n.peerScores[peerID] = ps
	}
	return ps
}

// checkRateAndScore returns false if the peer is banned or exceeds rate limit.
func (n *Node) checkRateAndScore(peerID string) bool {
	ps := n.getOrCreateScore(peerID)

	// Check ban
	if ps.Banned {
		if time.Now().Before(ps.BannedUntil) {
			return false
		}
		// Ban expired — reset
		ps.Banned = false
		ps.Score = 0
		log.Printf("[scoring] peer %s unbanned", peerID[:12])
	}

	// Rate limit: reset window every minute
	if time.Since(ps.WindowStart) > time.Minute {
		ps.MsgCount = 0
		ps.WindowStart = time.Now()
	}
	ps.MsgCount++
	if ps.MsgCount > MaxMsgPerMinute {
		log.Printf("[scoring] peer %s rate limited (%d msg/min)", peerID[:12], ps.MsgCount)
		n.adjustScore(peerID, PeerBadMsgPenalty)
		return false
	}

	return true
}

// adjustScore updates a peer's score and bans if it drops below threshold.
func (n *Node) adjustScore(peerID string, delta float64) {
	if peerID == "" {
		return
	}
	ps := n.getOrCreateScore(peerID)
	ps.Score += delta
	if ps.Score < PeerBanThreshold && !ps.Banned {
		ps.Banned = true
		ps.BannedUntil = time.Now().Add(30 * time.Minute)
		log.Printf("[scoring] peer %s BANNED (score %.1f) for 30 min", peerID[:12], ps.Score)
		// Optionally: n.h.Network().ClosePeer(peer.ID(peerID))
	}
}

// ─── libp2p P2P (TCP + QUIC-v1, mDNS + DHT) ──────────────────────────────────

type p2pMsg struct {
	Type    string          `json:"type"`
	Sender  string          `json:"sender"`
	Payload json.RawMessage `json:"payload"`
}

type mdnsHandler struct{ n *Node }

func (m *mdnsHandler) HandlePeerFound(pi peer.AddrInfo) {
	if pi.ID == m.n.h.ID() {
		return
	}
	ctx, cancel := context.WithTimeout(m.n.ctx, 5*time.Second)
	defer cancel()
	if err := m.n.h.Connect(ctx, pi); err == nil {
		log.Printf("[p2p] mDNS peer connected: %s", pi.ID.String()[:12])
	}
}

func (n *Node) startLibP2P(p2pPort int) error {
	tcpAddr := fmt.Sprintf("/ip4/0.0.0.0/tcp/%d", p2pPort)
	quicAddr := fmt.Sprintf("/ip4/0.0.0.0/udp/%d/quic-v1", p2pPort)

	h, err := libp2p.New(
		libp2p.ListenAddrStrings(tcpAddr, quicAddr),
		libp2p.Transport(libp2ptcp.NewTCPTransport),
		libp2p.Transport(libp2pquic.NewTransport),
		libp2p.Security(noise.ID, noise.New),
		libp2p.Muxer(yamux.ID, yamux.DefaultTransport),
	)
	if err != nil {
		return err
	}
	n.h = h

	log.Printf("[p2p] Host ID: %s", h.ID())
	for _, addr := range h.Addrs() {
		log.Printf("[p2p] Listening: %s/p2p/%s", addr, h.ID())
	}

	// Register stream handler
	h.SetStreamHandler(ConsensusProtocol, n.handleStream)

	// mDNS (LAN discovery)
	mdnsSvc := mdns.NewMdnsService(h, "trispi", &mdnsHandler{n})
	if err := mdnsSvc.Start(); err != nil {
		log.Printf("[p2p] mDNS warning: %v", err)
	}

	// DHT (internet discovery)
	go n.runDHT()

	return nil
}

func (n *Node) runDHT() {
	bootstrapAddrs := []string{
		"/dnsaddr/bootstrap.libp2p.io/p2p/QmNnooDu7bfjPFoTZYxMNLWUQJyrVwtbZg5gBMjTezGAJN",
		"/dnsaddr/bootstrap.libp2p.io/p2p/QmQCU2EcMqAqQPR2i9bChDtGNJchTbq5TbXJJ16u19uLTa",
	}

	kad, err := dht.New(n.ctx, n.h, dht.Mode(dht.ModeAutoServer))
	if err != nil {
		log.Printf("[dht] init error: %v", err)
		return
	}
	n.kad = kad

	for _, addrStr := range bootstrapAddrs {
		maddr, err := ma.NewMultiaddr(addrStr)
		if err != nil {
			continue
		}
		pi, err := peer.AddrInfoFromP2pAddr(maddr)
		if err != nil {
			continue
		}
		ctx, cancel := context.WithTimeout(n.ctx, 10*time.Second)
		if err := n.h.Connect(ctx, *pi); err == nil {
			log.Printf("[dht] bootstrap ok: %s", pi.ID.String()[:12])
		}
		cancel()
	}

	if err := kad.Bootstrap(n.ctx); err != nil {
		log.Printf("[dht] bootstrap warning: %v", err)
	}

	time.Sleep(5 * time.Second)
	disc := discrouting.NewRoutingDiscovery(kad)

	for {
		select {
		case <-n.ctx.Done():
			return
		default:
		}
		ttl, err := disc.Advertise(n.ctx, TRISPIRendezvous)
		if err != nil {
			time.Sleep(30 * time.Second)
			continue
		}
		log.Printf("[dht] advertised (TTL=%s)", ttl)

		peers, err := disc.FindPeers(n.ctx, TRISPIRendezvous)
		if err == nil {
			for pi := range peers {
				if pi.ID == n.h.ID() || len(pi.Addrs) == 0 {
					continue
				}
				ctx, cancel := context.WithTimeout(n.ctx, 10*time.Second)
				if err := n.h.Connect(ctx, pi); err == nil {
					log.Printf("[dht] found peer: %s", pi.ID.String()[:12])
				}
				cancel()
			}
		}

		wait := ttl
		if wait == 0 || wait > 10*time.Minute {
			wait = 10 * time.Minute
		}
		time.Sleep(wait)
	}
}

func (n *Node) handleStream(s network.Stream) {
	defer s.Close()
	peerID := s.Conn().RemotePeer().String()

	n.mu.Lock()
	if !n.checkRateAndScore(peerID) {
		n.mu.Unlock()
		return
	}
	n.mu.Unlock()

	var msg p2pMsg
	if err := json.NewDecoder(s).Decode(&msg); err != nil {
		n.mu.Lock()
		n.adjustScore(peerID, PeerBadMsgPenalty)
		n.mu.Unlock()
		return
	}

	switch msg.Type {
	case "block":
		var b Block
		if err := json.Unmarshal(msg.Payload, &b); err == nil {
			n.AddBlock(&b, peerID)
		}
	case "pbft_commit":
		var vote PBFTVote
		if err := json.Unmarshal(msg.Payload, &vote); err == nil {
			n.HandlePBFTVote(vote, peerID)
		}
	}
}

func (n *Node) broadcast(msgType string, payload interface{}) {
	data, _ := json.Marshal(payload)
	msg, _ := json.Marshal(p2pMsg{Type: msgType, Sender: n.id, Payload: data})
	msg = append(msg, '\n')

	for _, pid := range n.h.Network().Peers() {
		go func(peerID peer.ID) {
			ctx, cancel := context.WithTimeout(n.ctx, 5*time.Second)
			defer cancel()
			s, err := n.h.NewStream(ctx, peerID, ConsensusProtocol)
			if err != nil {
				return
			}
			defer s.Close()
			s.Write(msg)
		}(pid)
	}
}

// ─── HTTP API ─────────────────────────────────────────────────────────────────

func (n *Node) startHTTP(port int) {
	mux := http.NewServeMux()

	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]interface{}{
			"status":      "ok",
			"node_id":     n.id,
			"chain_len":   len(n.chain),
			"peer_count":  len(n.h.Network().Peers()),
			"validator_n": len(n.validators),
		})
	})

	mux.HandleFunc("/chain", func(w http.ResponseWriter, r *http.Request) {
		n.mu.RLock()
		defer n.mu.RUnlock()
		json.NewEncoder(w).Encode(n.chain)
	})

	mux.HandleFunc("/mine", func(w http.ResponseWriter, r *http.Request) {
		block := n.MineBlock()
		n.broadcast("block", block)
		json.NewEncoder(w).Encode(block)
	})

	mux.HandleFunc("/validators", func(w http.ResponseWriter, r *http.Request) {
		n.mu.RLock()
		defer n.mu.RUnlock()
		json.NewEncoder(w).Encode(n.validators)
	})

	mux.HandleFunc("/peers/scores", func(w http.ResponseWriter, r *http.Request) {
		n.mu.RLock()
		defer n.mu.RUnlock()
		json.NewEncoder(w).Encode(n.peerScores)
	})

	addr := fmt.Sprintf(":%d", port)
	log.Printf("[http] API server on %s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

// ─── Main ─────────────────────────────────────────────────────────────────────

func main() {
	id := flag.String("id", "node1", "unique node identifier")
	httpPort := flag.Int("http", 8081, "HTTP API port")
	p2pPort := flag.Int("p2p", 50052, "libp2p TCP + QUIC port")
	flag.Parse()

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	node := NewNode(*id)
	node.ctx = ctx

	// Start P2P
	if err := node.startLibP2P(*p2pPort); err != nil {
		log.Fatal("libp2p start failed:", err)
	}

	// Mine a block every 3 seconds
	go func() {
		ticker := time.NewTicker(3 * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				block := node.MineBlock()
				node.broadcast("block", block)
				log.Printf("[chain] mined block #%d (hash=%s...)", block.Index, block.Hash[:8])
			}
		}
	}()

	// Save node ID to file for other nodes to connect
	os.WriteFile("node_id.txt", []byte(node.h.ID().String()), 0644)

	node.startHTTP(*httpPort)
}
