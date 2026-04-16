"""
TRISPI Miner Fleet — tracks REAL registered energy providers only.

NO fake miners are created here. The fleet_size starts at 0 and grows
as real users run the energy provider client and register via the API.
Stats reflect only real, active, registered providers.
"""
import time
import threading
import os
from typing import Dict, List, Any
from dataclasses import dataclass, field

try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

FLEET_VERSION = "2.0.0"
# Real provider count starts at zero — grows as users join
TOTAL_MINERS = 0


@dataclass
class RealProviderNode:
    """
    A real energy provider node registered via the API.
    Created only when a user actually runs trispi_energy_provider.py.
    """
    provider_id: str
    address: str
    region: str
    cpu_cores: int
    gpu_memory_mb: int
    is_active: bool = True
    tasks_completed: int = 0
    blocks_validated: int = 0
    trp_earned: float = 0.0
    energy_watts: float = 0.0
    uptime_seconds: int = 0
    last_heartbeat: int = 0
    intelligence_score: float = 0.60   # starts at baseline, grows with training
    role: str = "compute"
    registered_at: int = field(default_factory=lambda: int(time.time()))


class MinerFleet:
    """
    Tracks real energy providers that registered via trispi_energy_provider.py.
    Does NOT pre-populate with fake miners.
    """

    def __init__(self, blockchain=None):
        self.miners: Dict[str, RealProviderNode] = {}   # address → node
        self.blockchain = blockchain
        self._running = False
        self._thread = None
        self._started_at = int(time.time())
        self._total_energy_wh = 0.0
        self._total_tasks = 0
        self._total_blocks = 0
        self._lock = threading.Lock()

    def initialize_fleet(self):
        """
        No fake miners created.
        Only real providers (registered via API) populate this fleet.
        """
        print("[FLEET] Real provider fleet ready — 0 registered providers (waiting for real nodes)")
        print("[FLEET] Run trispi_energy_provider.py to join the network and earn TRP")

    def register_real_provider(
        self,
        provider_id: str,
        address: str,
        cpu_cores: int,
        gpu_memory_mb: int,
        region: str = "Unknown",
    ) -> RealProviderNode:
        """Register a real energy provider that connected via the API."""
        with self._lock:
            if address not in self.miners:
                energy_w = 5.0 + cpu_cores * 2.5 + gpu_memory_mb * 0.002
                role = (
                    "full_node" if cpu_cores >= 32 else
                    "ai_node"   if gpu_memory_mb >= 4096 else
                    "validator" if cpu_cores >= 8 else
                    "compute"
                )
                node = RealProviderNode(
                    provider_id=provider_id,
                    address=address,
                    region=region,
                    cpu_cores=cpu_cores,
                    gpu_memory_mb=gpu_memory_mb,
                    energy_watts=energy_w,
                    role=role,
                    last_heartbeat=int(time.time()),
                )
                self.miners[address] = node
                if self.blockchain:
                    self.blockchain.balances.setdefault(address, 0.0)
                print(f"[FLEET] Real provider joined: {address[:24]}... | {cpu_cores} CPU | {gpu_memory_mb} GPU MB")
            return self.miners[address]

    def update_heartbeat(self, address: str, cpu_usage: float = 0.0):
        """Update last-seen time for a real provider."""
        with self._lock:
            if address in self.miners:
                node = self.miners[address]
                node.last_heartbeat = int(time.time())
                # Real energy based on actual CPU usage reported by provider
                node.energy_watts = 5.0 + node.cpu_cores * 2.5 * max(0.1, cpu_usage / 100.0)

    def start(self):
        """Start background tracking loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._thread.start()
        print(f"[FLEET] Provider tracker started — real providers only")

    def stop(self):
        self._running = False

    def _tracking_loop(self):
        """Background loop: mark providers inactive if heartbeat missing >120s."""
        while self._running:
            try:
                now = int(time.time())
                with self._lock:
                    for node in self.miners.values():
                        stale = (now - node.last_heartbeat) > 120
                        if node.is_active and stale:
                            node.is_active = False
                        elif not node.is_active and not stale:
                            node.is_active = True
                        if node.is_active:
                            node.uptime_seconds = now - node.registered_at
                            total_watts = sum(
                                n.energy_watts for n in self.miners.values() if n.is_active
                            )
                            self._total_energy_wh += total_watts * (30.0 / 3600.0)
                time.sleep(30)
            except Exception as e:
                print(f"[FLEET] Tracker error: {e}")
                time.sleep(5)

    def get_stats(self) -> Dict[str, Any]:
        """Return honest fleet statistics — only real registered providers."""
        with self._lock:
            all_nodes = list(self.miners.values())
            active = [n for n in all_nodes if n.is_active]
            total_cpu = sum(n.cpu_cores for n in active)
            total_gpu = sum(n.gpu_memory_mb for n in active)
            total_watts = sum(n.energy_watts for n in active)
            total_tasks = sum(n.tasks_completed for n in active)
            total_earned = sum(n.trp_earned for n in active)
            total_validated = sum(n.blocks_validated for n in active)

            regions: Dict[str, int] = {}
            roles: Dict[str, int] = {}
            for n in active:
                regions[n.region] = regions.get(n.region, 0) + 1
                roles[n.role] = roles.get(n.role, 0) + 1

            avg_score = (
                sum(n.intelligence_score for n in active) / len(active)
                if active else 0.0
            )

            return {
                "fleet_version": FLEET_VERSION,
                "total_miners": len(all_nodes),        # real providers registered
                "active_miners": len(active),          # online right now
                "total_cpu_cores": total_cpu,
                "total_gpu_memory_mb": total_gpu,
                "total_gpu_memory_gb": round(total_gpu / 1024, 1),
                "total_energy_watts": round(total_watts, 1),
                "total_energy_kwh": round(self._total_energy_wh / 1000, 3),
                "total_tasks_completed": total_tasks,
                "total_blocks_validated": total_validated,
                "total_trp_earned": round(total_earned, 4),
                "uptime_seconds": int(time.time()) - self._started_at,
                "regions": regions,
                "roles": roles,
                "network_hashrate_thps": round(total_cpu * 0.001, 2),
                "avg_intelligence_score": round(avg_score, 4),
                "real_providers_only": True,
            }

    def get_top_miners(self, limit: int = 20) -> List[Dict]:
        """Get top real providers by TRP earned."""
        with self._lock:
            sorted_nodes = sorted(
                self.miners.values(), key=lambda n: n.trp_earned, reverse=True
            )
            return [
                {
                    "address": n.address,
                    "region": n.region,
                    "role": n.role,
                    "cpu_cores": n.cpu_cores,
                    "gpu_mb": n.gpu_memory_mb,
                    "tasks": n.tasks_completed,
                    "blocks_validated": n.blocks_validated,
                    "trp_earned": round(n.trp_earned, 6),
                    "energy_watts": round(n.energy_watts, 1),
                    "intelligence_score": round(n.intelligence_score, 4),
                    "active": n.is_active,
                    "last_heartbeat": n.last_heartbeat,
                }
                for n in sorted_nodes[:limit]
            ]

    def get_miner(self, address: str) -> Dict:
        """Get single provider info."""
        with self._lock:
            n = self.miners.get(address)
            if not n:
                return {"error": "provider not found"}
            return {
                "address": n.address,
                "region": n.region,
                "role": n.role,
                "cpu_cores": n.cpu_cores,
                "gpu_mb": n.gpu_memory_mb,
                "tasks": n.tasks_completed,
                "blocks_validated": n.blocks_validated,
                "trp_earned": round(n.trp_earned, 6),
                "energy_watts": round(n.energy_watts, 1),
                "intelligence_score": round(n.intelligence_score, 4),
                "uptime_seconds": n.uptime_seconds,
                "last_heartbeat": n.last_heartbeat,
                "active": n.is_active,
            }


# ── Module-level singleton ─────────────────────────────────────────────────────

miner_fleet: MinerFleet = None


def init_fleet(blockchain=None) -> MinerFleet:
    """Initialize the real-provider fleet (starts empty — grows as users join)."""
    global miner_fleet
    miner_fleet = MinerFleet(blockchain)
    miner_fleet.initialize_fleet()
    miner_fleet.start()
    return miner_fleet
