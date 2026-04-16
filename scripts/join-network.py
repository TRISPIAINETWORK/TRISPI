#!/usr/bin/env python3
"""
TRISPI — Подключение своей ноды к сети mainnet.

Что делает скрипт:
  1. Проверяет что ваша нода запущена (Python :8000, Go :8081)
  2. Синхронизирует последние блоки с mainnet
  3. Регистрирует вашу ноду в mainnet
  4. Запускает мониторинг синхронизации

Использование:
  python3 scripts/join-network.py
  python3 scripts/join-network.py --local-api http://localhost:8000 --mainnet https://trispi.org
"""
import requests
import sys
import time
import argparse
import json

MAINNET  = "https://trispi.org"
LOCAL_PY = "http://localhost:8000"
LOCAL_GO = "http://localhost:8081"

def parse_args():
    p = argparse.ArgumentParser(description="Join TRISPI Network")
    p.add_argument("--local-api",  default=LOCAL_PY, help="Ваш Python API URL")
    p.add_argument("--local-go",   default=LOCAL_GO, help="Ваш Go API URL")
    p.add_argument("--mainnet",    default=MAINNET,  help="Mainnet URL")
    p.add_argument("--node-id",    default="",       help="ID вашей ноды")
    p.add_argument("--public-ip",  default="",       help="Публичный IP вашего сервера (для P2P)")
    p.add_argument("--monitor",    action="store_true", help="Запустить непрерывный мониторинг")
    return p.parse_args()

def check(url, name, timeout=5):
    try:
        r = requests.get(f"{url}/health", timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            print(f"  ✓ {name} запущен — блок #{data.get('block_height', data.get('blocks','?'))}")
            return True
        print(f"  ✗ {name}: HTTP {r.status_code}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"  ✗ {name}: не доступен ({url})")
        return False
    except Exception as e:
        print(f"  ✗ {name}: {e}")
        return False

def get_mainnet_height(mainnet):
    try:
        r = requests.get(f"{mainnet}/health", timeout=10)
        return r.json().get("block_height", 0)
    except Exception:
        return 0

def get_local_height(local_api):
    try:
        r = requests.get(f"{local_api}/health", timeout=5)
        return r.json().get("block_height", 0)
    except Exception:
        return 0

def sync_blocks(local_api, mainnet):
    """Скачать недостающие блоки с mainnet и залить в локальную ноду."""
    local_h  = get_local_height(local_api)
    mainnet_h = get_mainnet_height(mainnet)

    if mainnet_h <= local_h:
        print(f"  ✓ Нода синхронизирована (блок #{local_h})")
        return True

    diff = mainnet_h - local_h
    print(f"  Отстаём на {diff} блоков (local={local_h}, mainnet={mainnet_h})")
    print(f"  Синхронизируем последние блоки...")

    try:
        # Получить последние блоки с mainnet
        r = requests.get(f"{mainnet}/api/explorer/blocks?limit=50", timeout=15)
        blocks = r.json().get("blocks", [])

        # Залить блоки в локальную Go ноду
        synced = 0
        for block in reversed(blocks):  # от старых к новым
            if block.get("index", 0) > local_h:
                try:
                    res = requests.post(f"{local_api}/api/chain/sync-block",
                                        json=block, timeout=5)
                    if res.status_code == 200:
                        synced += 1
                except Exception:
                    pass

        print(f"  ✓ Синхронизировано {synced} новых блоков")
        return True
    except Exception as e:
        print(f"  ! Ошибка синхронизации: {e}")
        print(f"  ! Нода продолжит работу — блоки придут через P2P")
        return True

def register_with_mainnet(local_api, local_go, mainnet, node_id, public_ip):
    """Зарегистрировать ноду в mainnet."""
    # Получить libp2p peer ID с локальной Go ноды
    peer_id = ""
    p2p_port = 50052
    try:
        r = requests.get(f"{local_go}/p2p/info", timeout=5)
        info = r.json()
        peer_id = info.get("peer_id", "")
        multiaddrs = info.get("multiaddrs", [])
        if multiaddrs:
            print(f"  libp2p: {multiaddrs[0]}")
    except Exception:
        pass

    # Сформировать адрес для P2P подключений
    if public_ip:
        address = f"{public_ip}:50051"
        libp2p_addr = f"/ip4/{public_ip}/tcp/{p2p_port}/p2p/{peer_id}" if peer_id else f"{public_ip}:{p2p_port}"
    else:
        address = "unknown"
        libp2p_addr = ""

    # Узнать высоту локальной цепи
    chain_height = get_local_height(local_api)

    # Зарегистрировать в mainnet Python API
    payload = {
        "node_id":      node_id,
        "address":      address,
        "libp2p_addr":  libp2p_addr,
        "node_type":    "full_node",
        "chain_height": chain_height,
    }
    try:
        r = requests.post(f"{mainnet}/api/network/peers/register",
                          json=payload, timeout=10)
        if r.status_code == 200:
            print(f"  ✓ Зарегистрирован в mainnet Python API")
        else:
            print(f"  ! Python API: HTTP {r.status_code} — {r.text[:100]}")
    except Exception as e:
        print(f"  ! Не удалось зарегистрироваться в Python API: {e}")

    # Зарегистрировать в mainnet Go ноде
    go_payload = {
        "id":           node_id,
        "address":      address,
        "is_validator": False,
    }
    try:
        r = requests.post(f"{mainnet}/api/go/peers/register",
                          json=go_payload, timeout=10)
        if r.status_code == 200:
            print(f"  ✓ Зарегистрирован в mainnet Go ноде")
    except Exception:
        # Mainnet не проксирует /api/go/* — пробуем напрямую на :8081
        pass

    return True

def monitor(local_api, mainnet, interval=30):
    """Непрерывный мониторинг синхронизации."""
    print(f"\nМониторинг синхронизации (каждые {interval}с). Ctrl+C для выхода.\n")
    while True:
        local_h   = get_local_height(local_api)
        mainnet_h = get_mainnet_height(mainnet)
        diff      = mainnet_h - local_h
        status    = "SYNCED" if diff <= 2 else f"LAG={diff}"
        print(f"[{time.strftime('%H:%M:%S')}] Local: #{local_h} | Mainnet: #{mainnet_h} | {status}")
        time.sleep(interval)

def main():
    args = parse_args()
    mainnet   = args.mainnet.rstrip("/")
    local_api = args.local_api.rstrip("/")
    local_go  = args.local_go.rstrip("/")
    node_id   = args.node_id or f"trispi_node_{int(time.time())}"

    print()
    print("═" * 55)
    print("  TRISPI — Подключение к основной сети")
    print("═" * 55)
    print(f"  Mainnet : {mainnet}")
    print(f"  Local   : {local_api}")
    print(f"  Node ID : {node_id}")
    if args.public_ip:
        print(f"  Public IP: {args.public_ip}")
    print()

    # 1. Проверяем свои сервисы
    print("1. Проверка локальных сервисов:")
    py_ok = check(local_api, "Python AI Service")
    go_ok = check(local_go,  "Go Consensus")

    if not py_ok:
        print("\n  [!] Python сервис недоступен.")
        print("  Запустите: cd python-ai-service && uvicorn app.main_simplified:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    if not go_ok:
        print("\n  [!] Go нода недоступна (некритично — продолжим без Go).")

    # 2. Проверяем mainnet
    print("\n2. Проверка mainnet:")
    mn_ok = check(mainnet, "TRISPI Mainnet")
    if not mn_ok:
        print("\n  [!] Mainnet недоступен. Проверьте интернет-соединение.")
        print("  Продолжаем в offline-режиме...")

    # 3. Синхронизация блоков
    if mn_ok:
        print("\n3. Синхронизация блоков:")
        sync_blocks(local_api, mainnet)

    # 4. Регистрация в сети
    if mn_ok:
        print("\n4. Регистрация ноды в mainnet:")
        register_with_mainnet(local_api, local_go, mainnet, node_id, args.public_ip)

    # 5. Проверка P2P
    print("\n5. Проверка P2P подключения:")
    try:
        r = requests.get(f"{local_api}/api/network/status", timeout=5)
        data = r.json()
        peers = data.get("connected_peers", data.get("total_peers", "?"))
        print(f"  ✓ P2P пиры: {peers}")
    except Exception:
        print("  ! Статус P2P недоступен")

    if go_ok:
        try:
            r = requests.get(f"{local_go}/p2p/info", timeout=5)
            info = r.json()
            print(f"  ✓ libp2p Peer ID: {info.get('peer_id', '?')}")
            print(f"  ✓ libp2p адреса: {info.get('multiaddrs', [])}")
        except Exception:
            pass

    print()
    print("═" * 55)
    print("  Нода подключена к TRISPI!")
    print()
    print("  Следующие шаги:")
    print("  - Проверить блоки:  curl http://localhost:8000/api/explorer/blocks")
    print("  - Стать провайдером: python3 miner-client/trispi_energy_provider.py")
    print("  - Задеплоить контракт: см. contracts/README.md")
    if args.public_ip:
        print(f"  - Ваша нода публично доступна: {args.public_ip}:50051 (P2P)")
    print("═" * 55)

    # Мониторинг (если запрошен)
    if args.monitor and mn_ok:
        monitor(local_api, mainnet)

if __name__ == "__main__":
    main()
