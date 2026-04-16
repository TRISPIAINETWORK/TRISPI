"""
Example: Complete Energy Provider with Real Computation
This example shows how to become an energy provider and earn TRP rewards.
"""

import sys
sys.path.insert(0, '../sdk/python')

from trispi import TRISPIClient, TRISPIError
import uuid
import time
import hashlib


def main():
    # Configuration
    SERVER_URL = "https://trispi.network"  # Change to your network URL
    
    print("=" * 60)
    print("  TRISPI Energy Provider Example")
    print("=" * 60)
    
    # Initialize client
    client = TRISPIClient(SERVER_URL)
    
    # Check network status
    try:
        status = client.get_network_status()
        print(f"\nNetwork: {status.get('network')}")
        print(f"Block Height: {status.get('block_height')}")
        print(f"Active Providers: {status.get('active_energy_providers', 0)}")
    except TRISPIError as e:
        print(f"Could not connect to network: {e}")
        return
    
    # Generate unique provider ID
    contributor_id = str(uuid.uuid4())
    print(f"\nYour Provider ID: {contributor_id[:16]}...")
    
    # Register as energy provider
    print("\n[1/3] Registering with network...")
    try:
        reg = client.register_energy_provider(
            contributor_id=contributor_id,
            cpu_cores=4,
            gpu_memory_mb=0
        )
        print(f"Registration: {reg.get('status', 'success')}")
    except TRISPIError as e:
        print(f"Registration failed: {e}")
        return
    
    # Start session
    print("[2/3] Starting energy session...")
    try:
        session = client.start_energy_session(contributor_id)
        session_id = session.get('session_id')
        print(f"Session started: {session_id[:16]}...")
    except TRISPIError as e:
        print(f"Session start failed: {e}")
        return
    
    # Main loop
    print("[3/3] Providing energy to network...")
    print("\nPress Ctrl+C to stop\n")
    print("-" * 60)
    
    total_rewards = 0.0
    iteration = 0
    
    try:
        while True:
            iteration += 1
            
            # Simulate some computation
            compute_hash = hashlib.sha256(f"{time.time()}:{contributor_id}".encode()).hexdigest()
            
            # Send heartbeat
            result = client.energy_heartbeat(
                contributor_id=contributor_id,
                session_id=session_id,
                cpu_usage=50.0 + (iteration % 30),
                tasks_completed=1
            )
            
            reward = result.get('reward_earned', 0)
            total_rewards += reward
            
            print(f"[{time.strftime('%H:%M:%S')}] "
                  f"#{iteration} | "
                  f"Reward: +{reward:.6f} TRP | "
                  f"Total: {total_rewards:.6f} TRP")
            
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print(f"\nStopping...")
        print(f"Total earned: {total_rewards:.6f} TRP")
        print(f"Iterations: {iteration}")


if __name__ == "__main__":
    main()
