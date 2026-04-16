"""
TRISPI Python SDK
Official Python SDK for the TRISPI AI Blockchain Network
"""

import requests
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


class TRISPIError(Exception):
    """TRISPI API Error"""
    pass


class TRISPIClient:
    """
    TRISPI Network Client
    
    Usage:
        client = TRISPIClient("https://trispi.network")
        status = client.get_network_status()
        balance = client.get_balance("trp1your_address")
    """
    
    def __init__(self, server_url: str, timeout: int = 30):
        """
        Initialize TRISPI client
        
        Args:
            server_url: TRISPI network URL
            timeout: Request timeout in seconds
        """
        self.server_url = server_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'TRISPI-Python-SDK/1.0'
        })
    
    def _request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make API request"""
        url = f"{self.server_url}{endpoint}"
        
        try:
            if method == "GET":
                response = self.session.get(url, timeout=self.timeout)
            elif method == "POST":
                response = self.session.post(url, json=data, timeout=self.timeout)
            else:
                raise TRISPIError(f"Unsupported method: {method}")
            
            result = response.json()
            
            if response.status_code >= 400:
                raise TRISPIError(result.get("error", "Unknown error"))
            
            return result
            
        except requests.exceptions.RequestException as e:
            raise TRISPIError(f"Request failed: {str(e)}")
    
    # ========== Network ==========
    
    def get_network_status(self) -> Dict:
        """Get network status"""
        return self._request("GET", "/api/network/status")
    
    def get_ai_status(self) -> Dict:
        """Get AI engine status"""
        return self._request("GET", "/api/ai/status")
    
    def get_pqc_status(self) -> Dict:
        """Get post-quantum cryptography status"""
        return self._request("GET", "/api/pqc/status")
    
    def get_chain(self) -> List[Dict]:
        """Get blockchain"""
        return self._request("GET", "/api/chain")
    
    # ========== Wallet ==========
    
    def get_balance(self, address: str) -> Dict:
        """
        Get address balance
        
        Args:
            address: Wallet address (trp1... or 0x...)
        """
        return self._request("GET", f"/api/balance/{address}")
    
    def transfer(self, from_address: str, to_address: str, amount: float) -> Dict:
        """
        Transfer TRP tokens
        
        Args:
            from_address: Sender address
            to_address: Recipient address
            amount: Amount to transfer
        """
        return self._request("POST", "/api/transfer", {
            "from": from_address,
            "to": to_address,
            "amount": amount
        })
    
    # ========== Contracts ==========
    
    def deploy_evm_contract(
        self,
        deployer: str,
        bytecode: str,
        constructor_args: List = None,
        gas_limit: int = 3000000
    ) -> Dict:
        """
        Deploy EVM (Solidity) smart contract
        
        Args:
            deployer: Deployer address (0x...)
            bytecode: Compiled contract bytecode
            constructor_args: Constructor arguments
            gas_limit: Maximum gas for deployment
        """
        return self._request("POST", "/api/contract/deploy/evm", {
            "deployer": deployer,
            "bytecode": bytecode,
            "constructor_args": constructor_args or [],
            "gas_limit": gas_limit
        })
    
    def deploy_wasm_contract(
        self,
        deployer: str,
        bytecode: str,
        init_args: Dict = None,
        gas_limit: int = 5000000
    ) -> Dict:
        """
        Deploy WASM (Rust/Go) smart contract
        
        Args:
            deployer: Deployer address (trp1...)
            bytecode: Compiled WASM bytecode
            init_args: Initialization arguments
            gas_limit: Maximum gas for deployment
        """
        return self._request("POST", "/api/contract/deploy/wasm", {
            "deployer": deployer,
            "bytecode": bytecode,
            "init_args": init_args or {},
            "gas_limit": gas_limit
        })
    
    def call_contract(
        self,
        contract_address: str,
        method: str,
        args: List = None,
        caller: str = "",
        value: float = 0
    ) -> Dict:
        """
        Call smart contract method
        
        Args:
            contract_address: Contract address
            method: Method name to call
            args: Method arguments
            caller: Caller address
            value: TRP value to send
        """
        return self._request("POST", "/api/contract/call", {
            "contract_address": contract_address,
            "method": method,
            "args": args or [],
            "caller": caller,
            "value": value
        })
    
    def get_contract(self, address: str) -> Dict:
        """Get contract details"""
        return self._request("GET", f"/api/contract/{address}")
    
    def get_contracts(self) -> Dict:
        """Get all deployed contracts"""
        return self._request("GET", "/api/contracts")
    
    # ========== Energy Provider ==========
    
    def register_energy_provider(
        self,
        contributor_id: str,
        cpu_cores: int,
        gpu_memory_mb: int = 0
    ) -> Dict:
        """
        Register as energy provider
        
        Args:
            contributor_id: Unique provider ID
            cpu_cores: Number of CPU cores
            gpu_memory_mb: GPU memory in MB (0 if no GPU)
        """
        return self._request("POST", "/api/ai-energy/register", {
            "contributor_id": contributor_id,
            "cpu_cores": cpu_cores,
            "gpu_memory_mb": gpu_memory_mb
        })
    
    def start_energy_session(self, contributor_id: str) -> Dict:
        """Start energy provision session"""
        return self._request("POST", "/api/ai-energy/start-session", {
            "contributor_id": contributor_id
        })
    
    def energy_heartbeat(
        self,
        contributor_id: str,
        session_id: str,
        cpu_usage: float = 50.0,
        tasks_completed: int = 1
    ) -> Dict:
        """
        Send energy provider heartbeat
        
        Args:
            contributor_id: Provider ID
            session_id: Session ID from start_energy_session
            cpu_usage: Current CPU usage percentage
            tasks_completed: Number of tasks completed
        """
        return self._request("POST", "/api/ai-energy/heartbeat", {
            "contributor_id": contributor_id,
            "session_id": session_id,
            "cpu_usage": cpu_usage,
            "tasks_completed": tasks_completed
        })
    
    def get_energy_stats(self) -> Dict:
        """Get energy provider statistics"""
        return self._request("GET", "/api/ai-energy/stats")
    
    # ========== Crypto ==========
    
    def generate_keypair(self) -> Dict:
        """Generate hybrid Ed25519 + Dilithium3 keypair"""
        return self._request("POST", "/api/crypto/generate-keypair")
    
    def get_crypto_info(self) -> Dict:
        """Get cryptographic scheme information"""
        return self._request("GET", "/api/crypto/info")


# Example usage
if __name__ == "__main__":
    # Create client
    client = TRISPIClient("https://trispi.network")
    
    # Get network status
    status = client.get_network_status()
    print(f"Network: {status.get('network')}")
    print(f"Block Height: {status.get('block_height')}")
    
    # Check balance
    balance = client.get_balance("trp1example")
    print(f"Balance: {balance.get('balance', 0)} TRP")
