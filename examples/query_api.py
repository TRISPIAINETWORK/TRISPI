#!/usr/bin/env python3
"""
TRISPI API Query Examples — read network data without a wallet.
"""
import requests

API = "https://trispi.org"  # or http://localhost:8000


def health_check():
    r = requests.get(f"{API}/health")
    d = r.json()
    print(f"Status: {d.get('status')} | Block: #{d.get('block_height')} | "
          f"Services: {d.get('services', {})}")


def get_network_status():
    r = requests.get(f"{API}/api/network/status")
    d = r.json()
    print(f"Peers: {d.get('connected_peers')} | "
          f"Chain height: {d.get('chain_height')} | "
          f"Consensus: {d.get('consensus_type')}")


def get_tokenomics():
    r = requests.get(f"{API}/api/tokenomics")
    d = r.json()
    print(f"Total supply: {d.get('total_supply'):,} TRP")
    print(f"Circulating: {d.get('circulating_supply'):,.2f} TRP")
    print(f"Burned: {d.get('burned'):,.2f} TRP")
    print(f"Block subsidy: {d.get('block_subsidy')} TRP")


def get_validators():
    r = requests.get(f"{API}/api/validators")
    validators = r.json().get("validators", [])
    print(f"Active validators: {len(validators)}")
    for v in validators[:5]:
        print(f"  - {v.get('id')} | Stake: {v.get('stake', 0):,} TRP | "
              f"Blocks: {v.get('blocks_produced', 0)}")


def get_energy_providers():
    r = requests.get(f"{API}/api/ai-energy/providers")
    providers = r.json().get("providers", [])
    print(f"Active energy providers: {len(providers)}")
    for p in providers[:5]:
        print(f"  - {p.get('contributor_id')} | Earned: {p.get('total_earned', 0):.2f} TRP | "
              f"Tasks: {p.get('tasks_completed', 0)}")


def search_blockchain(query: str):
    r = requests.get(f"{API}/api/explorer/search?q={query}")
    d = r.json()
    print(f"Search '{query}': {d.get('type')} found")
    return d


if __name__ == "__main__":
    print("=== TRISPI Network Status ===\n")

    print("Health:")
    health_check()

    print("\nNetwork:")
    get_network_status()

    print("\nTokenomics:")
    get_tokenomics()

    print("\nValidators:")
    get_validators()

    print("\nEnergy Providers:")
    get_energy_providers()
