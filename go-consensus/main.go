// TRISPI Go Consensus - Main Entry Point
// Enhanced P2P Network with PBFT, AI Validation, and Energy Providers
package main

import (
        "bytes"
        "encoding/json"
        "flag"
        "fmt"
        "log"
        "net/http"
        "os"
        "os/signal"
        "strings"
        "syscall"
        "time"
)

func main() {
        // Parse flags
        nodeID := flag.String("id", "node1", "Node ID")
        port := flag.String("port", "50051", "P2P listen port (legacy TCP)")
        httpPort := flag.String("http", "8081", "HTTP API port")
        libp2pPort := flag.Int("libp2p-port", 50052, "libp2p P2P listen port")
        peers := flag.String("peers", "", "Comma-separated peer addresses (legacy)")
        chainFile := flag.String("chain", "trispi_chain.json", "Chain storage file")
        flag.Parse()

        log.Println("╔══════════════════════════════════════════════════════════╗")
        log.Println("║         TRISPI Go Consensus Node Starting                ║")
        log.Println("║         AI-Powered Web4 Blockchain Network              ║")
        log.Println("╚══════════════════════════════════════════════════════════╝")
        log.Printf("Node ID: %s", *nodeID)
        log.Printf("Legacy TCP P2P Port: %s", *port)
        log.Printf("libp2p P2P Port: %d", *libp2pPort)
        log.Printf("HTTP API Port: %s", *httpPort)

        // Create enhanced node
        node := NewEnhancedNode(*nodeID, 50051)

        // Load persisted chain
        if err := node.LoadChain(*chainFile); err != nil {
                log.Printf("No persisted chain loaded: %v (starting fresh)", err)
        } else {
                log.Printf("Loaded chain with %d blocks", len(node.Chain))
        }

        // Fetch the trusted service Ed25519 pubkey from Python at startup.
        // Go will reject any /tx whose ed25519_pub doesn't match this registered key.
        // Retries up to 10 times (Python may still be starting up).
        go func() {
                pythonBase := os.Getenv("PYTHON_AI_URL")
                if pythonBase == "" {
                        pythonBase = "http://127.0.0.1:8000"
                }
                url := strings.TrimRight(pythonBase, "/") + "/api/crypto/info"
                client := &http.Client{Timeout: 3 * time.Second}
                for attempt := 1; attempt <= 10; attempt++ {
                        time.Sleep(time.Duration(attempt) * 2 * time.Second)
                        resp, err := client.Get(url)
                        if err != nil {
                                log.Printf("[trust] Python not ready (attempt %d/10): %v", attempt, err)
                                continue
                        }
                        var info struct {
                                ServiceEd25519Pub string `json:"service_ed25519_pub"`
                        }
                        if err := json.NewDecoder(resp.Body).Decode(&info); err != nil || info.ServiceEd25519Pub == "" {
                                resp.Body.Close()
                                log.Printf("[trust] Waiting for service_ed25519_pub (attempt %d/10)", attempt)
                                continue
                        }
                        resp.Body.Close()
                        node.mu.Lock()
                        node.TrustedServiceEd25519Pub = info.ServiceEd25519Pub
                        node.mu.Unlock()
                        log.Printf("[trust] Registered service Ed25519 pub: %s…", info.ServiceEd25519Pub[:16])
                        return
                }
                log.Printf("[trust] WARNING: could not fetch service pubkey from Python — identity binding disabled")
        }()

        // Legacy peers flag (unused now that libp2p handles discovery)
        _ = peers

        // ── Start libp2p Host (real P2P discovery) ─────────────────────────
        go func() {
                mgr, err := StartLibP2PHost(node, *libp2pPort)
                if err != nil {
                        log.Printf("[libp2p] Failed to start host: %v — continuing without libp2p", err)
                        return
                }
                log.Printf("[libp2p] Host running on port %d, peer ID: %s",
                        *libp2pPort, mgr.Host.ID())
        }()

        // ── Start HTTP API server ──────────────────────────────────────────
        go func() {
                mux := http.NewServeMux()

                // Chain endpoints
                mux.HandleFunc("/chain", node.HandleGetChain)
                mux.HandleFunc("/tx", node.HandlePostTx)
                mux.HandleFunc("/block/", node.HandleGetBlock)

                // Network status
                mux.HandleFunc("/network/status", node.HandleNetworkStatus)
                mux.HandleFunc("/network/stats", node.HandleGetStats)
                mux.HandleFunc("/network/consensus", node.HandleConsensusStatus)

                // Peers — enhanced to include libp2p peers
                mux.HandleFunc("/peers", handlePeers(node))
                mux.HandleFunc("/peers/register", node.HandleRegisterPeer)
                mux.HandleFunc("/validators", node.HandleGetValidators)
                mux.HandleFunc("/balance/", node.HandleGetBalance)

                // Energy providers
                mux.HandleFunc("/energy/register", node.HandleRegisterProvider)
                mux.HandleFunc("/energy/heartbeat", node.HandleHeartbeat)
                mux.HandleFunc("/energy/providers", node.HandleGetProviders)

                // PBFT consensus
                mux.HandleFunc("/pbft/prepare", node.HandlePBFTPrepare)
                mux.HandleFunc("/pbft/commit", node.HandlePBFTCommit)

                // Validator staking & slashing (Sybil protection, stake-weighted PBFT)
                mux.HandleFunc("/validators/stake", node.HandleStake)
                mux.HandleFunc("/validators/unstake", node.HandleUnstake)
                mux.HandleFunc("/validators/whitelist", node.HandleWhitelist)
                mux.HandleFunc("/validators/stakes", node.HandleGetStakes)

                // Block sync from peers (push new block)
                mux.HandleFunc("/blocks/sync", node.HandleSyncBlock)

                // libp2p info
                mux.HandleFunc("/p2p/info", handleLibP2PInfo())

                // Health check
                mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
                        w.Header().Set("Content-Type", "application/json")
                        w.Write([]byte(`{"status":"ok","service":"TRISPI Go Consensus","node_id":"` + *nodeID + `"}`))
                })

                log.Printf("HTTP API listening on :%s", *httpPort)
                if err := http.ListenAndServe(":"+*httpPort, corsMiddleware(mux)); err != nil {
                        log.Fatal("HTTP server error:", err)
                }
        }()

        // ── Block production loop — mines every 15s ────────────────────────
        go func() {
                ticker := time.NewTicker(15 * time.Second)
                defer ticker.Stop()

                for range ticker.C {
                        block := node.CreateBlockAlways()
                        if block != nil {
                                if node.AddBlock(block) {
                                        // Propagate mined block to libp2p peers.
                                        if GlobalLibP2P != nil {
                                                go GlobalLibP2P.BroadcastConsensus("block", block)
                                        }
                                        // Include real libp2p peer count in log
                                        peerCount := 0
                                        if GlobalLibP2P != nil {
                                                peerCount = GlobalLibP2P.PeerCount()
                                        }
                                        log.Printf("✓ Block #%d | txns=%d | ai_score=%.2f | peers=%d | hash=%s...",
                                                block.Index, len(block.Transactions),
                                                block.AIProof.Accuracy, peerCount, block.Hash[:16])

                                        // Save #1: chain with Ed25519 sig (no Dilithium yet)
                                        if err := node.SaveChain(*chainFile); err != nil {
                                                log.Printf("Warning: Failed to save chain: %v", err)
                                        }

                                        // Non-blocking goroutine: fetch Dilithium3 PQC sig from
                                        // Rust bridge, then re-save chain so it is persisted.
                                        // node.mu is acquired before writing to block.Signature to
                                        // avoid races with SaveChain (which reads under RLock).
                                        savedChainFile := *chainFile
                                        go func(b *EnhancedBlock) {
                                                sig := fetchDilithiumSig(b.Hash)
                                                if sig != "" {
                                                        node.mu.Lock()
                                                        b.Signature.DilithiumSig = sig
                                                        node.mu.Unlock()
                                                        if err := node.SaveChain(savedChainFile); err != nil {
                                                                log.Printf("[dilithium] Re-save after PQC sig failed: %v", err)
                                                        }
                                                }
                                        }(block)

                                        // Notify Python AI service (non-blocking)
                                        pythonURL := os.Getenv("PYTHON_AI_URL")
                                        if pythonURL == "" {
                                                pythonURL = "http://127.0.0.1:8000"
                                        }
                                        go notifyPython(pythonURL, block)
                                }
                        }
                }
        }()

        // ── Graceful shutdown ──────────────────────────────────────────────
        sigCh := make(chan os.Signal, 1)
        signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

        log.Println("TRISPI Go Consensus node is running. Press Ctrl+C to stop.")

        <-sigCh
        log.Println("Shutting down...")

        // Stop libp2p
        if GlobalLibP2P != nil {
                GlobalLibP2P.cancel()
                if err := GlobalLibP2P.Host.Close(); err != nil {
                        log.Printf("libp2p host close: %v", err)
                }
        }

        // Save chain before exit
        if err := node.SaveChain(*chainFile); err != nil {
                log.Printf("Failed to save chain: %v", err)
        } else {
                log.Printf("Chain saved to %s", *chainFile)
        }

        log.Println("Goodbye!")
}

// corsMiddleware adds CORS headers to all responses.
func corsMiddleware(next http.Handler) http.Handler {
        return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
                w.Header().Set("Access-Control-Allow-Origin", "*")
                w.Header().Set("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
                if r.Method == http.MethodOptions {
                        w.WriteHeader(http.StatusNoContent)
                        return
                }
                next.ServeHTTP(w, r)
        })
}

// handlePeers returns combined peers: EnhancedNode peers + real libp2p peers.
func handlePeers(node *EnhancedNode) http.HandlerFunc {
        return func(w http.ResponseWriter, r *http.Request) {
                node.mu.RLock()
                nodePeers := make([]map[string]interface{}, 0, len(node.Peers))
                for id, p := range node.Peers {
                        nodePeers = append(nodePeers, map[string]interface{}{
                                "id":           id,
                                "address":      p.Address,
                                "last_seen":    p.LastSeen,
                                "is_validator": p.IsValidator,
                                "reputation":   p.Reputation,
                                "source":       "node",
                        })
                }
                node.mu.RUnlock()

                // Merge in libp2p-connected peers (with multiaddr format)
                libp2pPeers := make([]map[string]interface{}, 0)
                if GlobalLibP2P != nil {
                        libp2pPeers = GlobalLibP2P.ConnectedPeers()
                        for i := range libp2pPeers {
                                libp2pPeers[i]["source"] = "libp2p"
                        }
                }

                totalPeers := len(nodePeers) + len(libp2pPeers)

                w.Header().Set("Content-Type", "application/json")
                json.NewEncoder(w).Encode(map[string]interface{}{
                        "peers":        append(nodePeers, libp2pPeers...),
                        "count":        totalPeers,
                        "libp2p_peers": len(libp2pPeers),
                        "node_peers":   len(nodePeers),
                })
        }
}

// handleLibP2PInfo returns libp2p host info (peer ID, multiaddrs, etc.).
// Optional query param: ?limit=N (default 50) to cap the peer list size.
func handleLibP2PInfo() http.HandlerFunc {
        return func(w http.ResponseWriter, r *http.Request) {
                w.Header().Set("Content-Type", "application/json")

                if GlobalLibP2P == nil {
                        json.NewEncoder(w).Encode(map[string]interface{}{
                                "status":  "not_started",
                                "message": "libp2p host not yet initialised",
                        })
                        return
                }

                limit := 50
                if l := r.URL.Query().Get("limit"); l != "" {
                        var n int
                        if _, err := fmt.Sscanf(l, "%d", &n); err == nil && n > 0 {
                                limit = n
                        }
                }

                allPeers := GlobalLibP2P.ConnectedPeers()
                if len(allPeers) > limit {
                        allPeers = allPeers[:limit]
                }

                json.NewEncoder(w).Encode(map[string]interface{}{
                        "status":          "running",
                        "peer_id":         GlobalLibP2P.Host.ID().String(),
                        "self_multiaddrs": GlobalLibP2P.SelfMultiaddrs(),
                        "connected_peers": GlobalLibP2P.PeerCount(),
                        "peers":           allPeers,
                        "peers_shown":     len(allPeers),
                })
        }
}

// notifyPython sends a block-mined notification to the Python AI service.
// Called non-blocking from a goroutine after each successful block add.
func notifyPython(pythonURL string, block *EnhancedBlock) {
        payload := map[string]interface{}{
                "index":     block.Index,
                "hash":      block.Hash,
                "tx_count":  len(block.Transactions),
                "proposer":  block.Proposer,
                "timestamp": block.Timestamp,
                "ai_score":  block.AIProof.Accuracy,
        }
        body, err := json.Marshal(payload)
        if err != nil {
                return
        }
        url := strings.TrimRight(pythonURL, "/") + "/api/internal/go/block-mined"
        secret := os.Getenv("BLOCK_MINED_SECRET")
        if secret == "" {
                log.Printf("[notify] BLOCK_MINED_SECRET env var not set — skipping Python callback for block %d", block.Index)
                return
        }
        req, err := http.NewRequest("POST", url, bytes.NewBuffer(body))
        if err != nil {
                return
        }
        req.Header.Set("Content-Type", "application/json")
        req.Header.Set("Authorization", "Bearer "+secret)
        client := &http.Client{Timeout: 3 * time.Second}
        resp, err := client.Do(req)
        if err != nil {
                log.Printf("[notify] Python callback failed: %v", err)
                return
        }
        defer resp.Body.Close()
        log.Printf("[notify] Python block-mined callback: status=%d block=%d", resp.StatusCode, block.Index)
}
