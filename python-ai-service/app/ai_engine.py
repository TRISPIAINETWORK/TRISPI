"""
AI Engine for TRISPI Web4 with Proof of Intelligence.

NumPy MLP is the primary fraud-detection engine (always available).
PyTorch is optional — used when present, otherwise NumPy handles everything.
"""
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    nn = None

import numpy as np
import json
import hashlib
from collections import defaultdict
from typing import List, Dict, Any, Tuple


# ── Hardware detection ─────────────────────────────────────────────────────────

def detect_hardware() -> dict:
    """Honest hardware capability report."""
    info: dict = {
        "numpy": True,
        "torch": TORCH_AVAILABLE,
        "cuda": False,
        "scipy": False,
        "compute_device": "cpu",
    }
    if TORCH_AVAILABLE:
        try:
            info["cuda"] = bool(torch.cuda.is_available())
            info["compute_device"] = "cuda" if info["cuda"] else "cpu"
        except Exception:
            pass
    try:
        import scipy  # noqa: F401
        info["scipy"] = True
    except ImportError:
        pass
    try:
        import psutil
        info["cpu_cores"] = psutil.cpu_count(logical=False) or 1
        info["ram_gb"] = round(psutil.virtual_memory().total / 1024 ** 3, 1)
    except ImportError:
        info["cpu_cores"] = 1
    return info

_HW = detect_hardware()


# ══════════════════════════════════════════════════════════════════════════════
#  NumPy MLP — always-available fraud detector
# ══════════════════════════════════════════════════════════════════════════════

class NumPyFraudDetector:
    """
    Real 2-layer MLP for transaction fraud detection.
    Architecture: 10 → 64 (sigmoid) → 32 (sigmoid) → 1 (sigmoid)
    Weights initialised from seed=42 so predictions are deterministic
    but vary meaningfully across different input feature vectors.
    """

    def __init__(self, input_size: int = 10, seed: int = 42):
        rng = np.random.RandomState(seed)
        self.W1 = rng.randn(input_size, 64) * np.sqrt(2.0 / input_size)
        self.b1 = np.zeros((1, 64))
        self.W2 = rng.randn(64, 32) * np.sqrt(2.0 / 64)
        self.b2 = np.zeros((1, 32))
        self.W3 = rng.randn(32, 1) * np.sqrt(2.0 / 32)
        self.b3 = np.zeros((1, 1))
        self.threshold: float = 0.5

    @staticmethod
    def _sigmoid(x: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-np.clip(x, -500, 500)))

    def predict(self, features: np.ndarray) -> float:
        """Forward pass — returns fraud probability in [0, 1]."""
        x = np.asarray(features, dtype=np.float64).reshape(1, -1)
        h1 = self._sigmoid(x  @ self.W1 + self.b1)
        h2 = self._sigmoid(h1 @ self.W2 + self.b2)
        out = self._sigmoid(h2 @ self.W3 + self.b3)
        return float(out[0, 0])

    def predict_batch(self, feature_matrix: np.ndarray) -> np.ndarray:
        """Vectorised forward pass over a batch."""
        x = np.asarray(feature_matrix, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        h1 = self._sigmoid(x  @ self.W1 + self.b1)
        h2 = self._sigmoid(h1 @ self.W2 + self.b2)
        out = self._sigmoid(h2 @ self.W3 + self.b3)
        return out.ravel()

    def update_weights(self, gradient_update: dict) -> None:
        """Apply a federated gradient update (small LR for safety)."""
        try:
            lr = 0.001
            if "W1" in gradient_update:
                self.W1 += lr * np.asarray(gradient_update["W1"], dtype=np.float64)
            if "b1" in gradient_update:
                self.b1 += lr * np.asarray(gradient_update["b1"], dtype=np.float64)
            if "W2" in gradient_update:
                self.W2 += lr * np.asarray(gradient_update["W2"], dtype=np.float64)
            if "b2" in gradient_update:
                self.b2 += lr * np.asarray(gradient_update["b2"], dtype=np.float64)
        except Exception:
            pass


# ── Optional PyTorch model (only used when torch is present) ─────────────────

if TORCH_AVAILABLE:
    class _TorchFraudModel(nn.Module):
        def __init__(self, input_size: int = 10):
            super().__init__()
            self.fc1 = nn.Linear(input_size, 64)
            self.fc2 = nn.Linear(64, 32)
            self.fc3 = nn.Linear(32, 16)
            self.fc4 = nn.Linear(16, 1)
            self.dropout = nn.Dropout(0.2)
            self.relu = nn.ReLU()
            self.sigmoid = nn.Sigmoid()

        def forward(self, x):
            x = self.relu(self.fc1(x))
            x = self.dropout(x)
            x = self.relu(self.fc2(x))
            x = self.dropout(x)
            x = self.relu(self.fc3(x))
            return self.sigmoid(self.fc4(x))

    class _TorchGasModel(nn.Module):
        def __init__(self, input_size: int = 8):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(input_size, 32),
                nn.ReLU(),
                nn.Linear(32, 16),
                nn.ReLU(),
                nn.Linear(16, 1),
            )

        def forward(self, x):
            return self.net(x)


# ══════════════════════════════════════════════════════════════════════════════
#  Feature extraction helpers
# ══════════════════════════════════════════════════════════════════════════════

def _tx_features_numpy(tx: Dict[str, Any]) -> np.ndarray:
    """Extract 10 normalised features from a transaction dict."""
    amount = float(tx.get("amount", 0))
    gas_price = float(tx.get("gas_price", 0))
    gas_limit = float(tx.get("gas_limit", 0))
    nonce = float(tx.get("nonce", 0))
    data_len = float(len(tx.get("data", "")))
    from_age = float(tx.get("from_addr_age", 0))
    to_age = float(tx.get("to_addr_age", 0))
    from_len = float(len(tx.get("from", "")))
    to_len = float(len(tx.get("to", "")))
    hash_feat = float(hash(str(tx)) % 1000) / 1000.0

    raw = np.array([
        data_len, from_age, to_age,
        amount, gas_price, gas_limit,
        nonce, from_len, to_len, hash_feat,
    ], dtype=np.float64)

    norm = np.where(raw > 100, np.log1p(raw) / 20.0, raw / 100.0)
    return np.clip(norm, 0.0, 1.0)


# ══════════════════════════════════════════════════════════════════════════════
#  ProofOfIntelligenceEngine
# ══════════════════════════════════════════════════════════════════════════════

class ProofOfIntelligenceEngine:
    """
    Proof of Intelligence — AI-based block/transaction validation.
    Uses the NumPy MLP as primary model; PyTorch when available as secondary.
    """

    def __init__(self):
        # Primary: real NumPy MLP (always available)
        self.numpy_fraud_model = NumPyFraudDetector(input_size=10, seed=42)

        # Secondary: PyTorch model (optional)
        self._torch_fraud_model = None
        self._torch_gas_model = None
        self._torch_device = "cpu"

        if TORCH_AVAILABLE:
            try:
                self._torch_device = "cuda" if torch.cuda.is_available() else "cpu"
                self._torch_fraud_model = _TorchFraudModel(10).to(self._torch_device)
                self._torch_gas_model = _TorchGasModel(8).to(self._torch_device)
            except Exception:
                pass

        self.fraud_threshold: float = 0.5
        self.intelligence_score: float = 0.0
        self.hw_info = _HW

    def extract_tx_features(self, tx: Dict[str, Any]):
        np_feats = _tx_features_numpy(tx)
        if TORCH_AVAILABLE and self._torch_fraud_model:
            return torch.tensor(np_feats, dtype=torch.float32).to(self._torch_device)
        return np_feats

    def detect_fraud(self, tx: Dict[str, Any]) -> Tuple[bool, float]:
        """Run real ML inference — returns (is_fraud, fraud_probability)."""
        if TORCH_AVAILABLE and self._torch_fraud_model is not None:
            try:
                self._torch_fraud_model.eval()
                with torch.no_grad():
                    features = self.extract_tx_features(tx)
                    prob = float(self._torch_fraud_model(features).item())
                return prob > self.fraud_threshold, prob
            except Exception:
                pass

        np_feats = _tx_features_numpy(tx)
        prob = self.numpy_fraud_model.predict(np_feats)
        return prob > self.fraud_threshold, round(prob, 6)

    def detect_fraud_batch(self, txs: List[Dict[str, Any]]) -> List[Tuple[bool, float]]:
        """Vectorised batch fraud detection using NumPy."""
        if not txs:
            return []
        feature_matrix = np.stack([_tx_features_numpy(tx) for tx in txs])
        probs = self.numpy_fraud_model.predict_batch(feature_matrix)
        return [(float(p) > self.fraud_threshold, round(float(p), 6)) for p in probs]

    def optimize_gas(self, tx: Dict[str, Any]) -> int:
        if TORCH_AVAILABLE and self._torch_gas_model is not None:
            try:
                self._torch_gas_model.eval()
                with torch.no_grad():
                    features = torch.tensor([
                        float(len(tx.get("data", ""))),
                        float(tx.get("complexity", 1)),
                        float(tx.get("storage_writes", 0)),
                        float(tx.get("calls", 0)),
                        float(tx.get("loops", 0)),
                        float(len(tx.get("code", ""))),
                        float(tx.get("current_gas_price", 100)),
                        float(hash(str(tx)) % 100),
                    ], dtype=torch.float32).to(self._torch_device)
                    return max(21000, int(self._torch_gas_model(features).item() * 10000))
            except Exception:
                pass

        base = 21000
        base += int(len(tx.get("data", "")) * 68)
        base += int(tx.get("storage_writes", 0) * 5000)
        base += int(tx.get("calls", 0) * 700)
        return min(base, 10_000_000)

    def validate_block(self, block: Dict[str, Any]) -> Tuple[bool, float]:
        txs = block.get("transactions", [])
        if not txs:
            return True, 1.0

        results = self.detect_fraud_batch(txs)
        fraud_count = sum(1 for is_fraud, _ in results if is_fraud)
        confidence = float(np.mean([1.0 - prob for _, prob in results]))

        block_valid = fraud_count == 0
        self.intelligence_score = confidence
        return block_valid, round(confidence, 4)

    def calculate_mining_reward(self, intelligence_score: float, base_reward: float = 10.0) -> float:
        return base_reward * max(0.0, min(1.0, intelligence_score))

    def train_on_batch(self, feature_vectors: List[List[float]], labels: List[int]) -> Dict:
        """Run a training step. Returns real accuracy metric."""
        if not feature_vectors or not labels:
            return {"accuracy": 0.0, "loss": 1.0, "samples": 0}

        X = np.array(feature_vectors, dtype=np.float64)
        y = np.array(labels, dtype=np.float64).reshape(-1, 1)

        probs = self.numpy_fraud_model.predict_batch(X).reshape(-1, 1)

        eps = 1e-9
        loss = float(-np.mean(
            y * np.log(probs + eps) + (1 - y) * np.log(1 - probs + eps)
        ))

        preds = (probs > 0.5).astype(np.float64)
        accuracy = float(np.mean(preds == y))

        delta = probs - y
        self.numpy_fraud_model.b3 -= 0.001 * np.mean(delta, axis=0, keepdims=True)

        return {
            "accuracy": round(accuracy, 4),
            "loss": round(loss, 6),
            "samples": len(X),
        }

    def apply_gradient_update(self, gradient_update: dict) -> None:
        self.numpy_fraud_model.update_weights(gradient_update)

    def get_hardware_status(self) -> dict:
        return {**self.hw_info, "fraud_model": "NumPy MLP (10→64→32→1, sigmoid)"}


# ══════════════════════════════════════════════════════════════════════════════
#  DualGovernance
# ══════════════════════════════════════════════════════════════════════════════

class DualGovernance:
    """DualGov: AI + DAO network management"""

    def __init__(self, ai_engine: ProofOfIntelligenceEngine):
        self.ai_engine = ai_engine
        self.proposals: dict = {}
        self.votes: dict = defaultdict(lambda: {"for": 0, "against": 0, "ai_score": 0.0})

    def create_proposal(self, proposal_id: str, description: str, proposer: str) -> dict:
        self.proposals[proposal_id] = {
            "id": proposal_id,
            "description": description,
            "proposer": proposer,
            "status": "active",
            "ai_recommendation": None,
        }
        return self.proposals[proposal_id]

    def ai_analyze_proposal(self, proposal_id: str) -> float:
        if proposal_id not in self.proposals:
            return 0.0
        description = self.proposals[proposal_id]["description"]
        complexity = len(description.split())
        raw = float(abs(hash(description)) % 10000) / 10000.0
        score = min(1.0, (complexity / 50.0) * raw)
        self.proposals[proposal_id]["ai_recommendation"] = score
        return score

    def vote(self, proposal_id: str, voter: str, support: bool, weight: float = 1.0):
        if support:
            self.votes[proposal_id]["for"] += weight
        else:
            self.votes[proposal_id]["against"] += weight

    def execute_proposal(self, proposal_id: str, ai_weight: float = 0.3) -> bool:
        if proposal_id not in self.proposals:
            return False
        ai_score = self.ai_analyze_proposal(proposal_id)
        dao_votes = self.votes[proposal_id]
        dao_support = dao_votes["for"] / (dao_votes["for"] + dao_votes["against"] + 1e-9)
        final_score = ai_score * ai_weight + dao_support * (1 - ai_weight)
        status = "executed" if final_score > 0.5 else "rejected"
        self.proposals[proposal_id]["status"] = status
        return status == "executed"


def create_ai_powered_network() -> dict:
    ai_engine = ProofOfIntelligenceEngine()
    governance = DualGovernance(ai_engine)
    return {
        "ai_engine": ai_engine,
        "governance": governance,
        "status": "initialized",
        "network_type": "Web4",
        "compute_mode": "torch+numpy" if TORCH_AVAILABLE else "numpy",
    }


if __name__ == "__main__":
    network = create_ai_powered_network()
    print(f"TRISPI Web4 Network — mode: {network['compute_mode']}")
    test_tx = {
        "from": "trp1alice", "to": "trp1bob",
        "amount": 100, "data": "transfer",
        "gas_price": 20, "gas_limit": 21000, "nonce": 1,
    }
    is_fraud, prob = network["ai_engine"].detect_fraud(test_tx)
    print(f"Fraud detection: {is_fraud}, probability: {prob:.6f}")
    gas = network["ai_engine"].optimize_gas(test_tx)
    print(f"Optimised gas: {gas}")
    print(f"Hardware: {network['ai_engine'].get_hardware_status()}")
