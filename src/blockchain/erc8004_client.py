"""ERC-8004 client — manages on-chain agent identity and reputation."""

import json
import os
from typing import Any

from utils import log

# Load settings
_settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "settings.json")
with open(_settings_path, "r") as f:
    _settings = json.load(f)["erc8004"]

CHAIN_ID = int(os.getenv("ERC8004_CHAIN_ID", _settings.get("chain_id", 84532)))
RPC_URL = os.getenv("ETH_RPC_URL", _settings.get("rpc_url", "https://sepolia.base.org"))


# ──────────────────────────────────────────────
# Registration File
# ──────────────────────────────────────────────

def generate_registration_file(
    name: str = "MoltBridgeAgent",
    description: str = "",
    web_endpoint: str = "",
    a2a_endpoint: str = "",
) -> dict:
    """
    Generate an ERC-8004 compliant agent registration JSON file.

    This file is stored off-chain (IPFS/https) and linked on-chain via tokenURI.
    """
    reg = _settings.get("registration", {}).copy()
    reg["name"] = name
    if description:
        reg["description"] = description

    services = []
    if web_endpoint:
        services.append({"name": "web", "endpoint": web_endpoint})
    if a2a_endpoint:
        services.append({"name": "A2A", "endpoint": a2a_endpoint})
    reg["services"] = services

    return reg


def save_registration_file(reg: dict, filepath: str = None) -> str:
    """Save registration file to disk."""
    if filepath is None:
        data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
        os.makedirs(data_dir, exist_ok=True)
        filepath = os.path.join(data_dir, "agent_registration.json")

    with open(filepath, "w") as f:
        json.dump(reg, f, indent=2)

    log.info(f"📋 Registration file saved to {filepath}")
    return filepath


# ──────────────────────────────────────────────
# On-Chain Registration (web3.py)
# ──────────────────────────────────────────────

# Minimal Identity Registry ABI (register + setAgentURI)
IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [
            {"name": "agentURI", "type": "string"},
        ],
        "name": "register",
        "outputs": [{"name": "agentId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "agentURI", "type": "string"},
        ],
        "name": "setAgentURI",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "agentId", "type": "uint256"},
            {"indexed": True, "name": "owner", "type": "address"},
        ],
        "name": "Registered",
        "type": "event",
    },
]


async def register_on_chain(
    agent_uri: str,
    registry_address: str = None,
    private_key: str = None,
) -> dict:
    """
    Register the agent on ERC-8004 Identity Registry.

    Args:
        agent_uri: IPFS or HTTPS URL pointing to registration JSON
        registry_address: Identity Registry contract address
        private_key: Ethereum private key for signing

    Returns:
        {"agent_id": int, "tx_hash": str} or {"error": str}
    """
    try:
        from web3 import Web3

        pk = private_key or os.getenv("ETH_PRIVATE_KEY", "")
        if not pk:
            return {"error": "ETH_PRIVATE_KEY not set. Cannot register on-chain."}

        if not registry_address:
            return {
                "error": "Registry address not provided. "
                "Check 8004.org for deployed addresses on your target chain."
            }

        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            return {"error": f"Cannot connect to RPC: {RPC_URL}"}

        account = w3.eth.account.from_key(pk)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(registry_address),
            abi=IDENTITY_REGISTRY_ABI,
        )

        # Build transaction
        tx = contract.functions.register(agent_uri).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "chainId": CHAIN_ID,
        })

        # Sign and send
        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        log.info(f"📡 Registration TX sent: {tx_hash.hex()}")

        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt.status == 1:
            log.info(f"✅ Agent registered on-chain! TX: {tx_hash.hex()}")
            # Try to extract agentId from logs
            agent_id = None
            for event_log in receipt.logs:
                if len(event_log.topics) >= 2:
                    agent_id = int(event_log.topics[1].hex(), 16)
                    break

            return {
                "agent_id": agent_id,
                "tx_hash": tx_hash.hex(),
                "chain_id": CHAIN_ID,
                "block": receipt.blockNumber,
            }
        else:
            return {"error": "Transaction reverted", "tx_hash": tx_hash.hex()}

    except ImportError:
        return {
            "error": "web3 not installed. Run: pip install web3",
            "manual_steps": [
                "1. Host your registration JSON on IPFS or HTTPS",
                "2. Call IdentityRegistry.register(agentURI) on your target chain",
                "3. Save your agentId for future interactions",
            ],
        }
    except Exception as e:
        log.error(f"On-chain registration failed: {e}")
        return {"error": str(e)}


async def update_agent_uri(
    agent_id: int,
    agent_uri: str,
    registry_address: str = None,
    private_key: str = None,
) -> dict:
    """Update agentURI for an existing ERC-8004 agent."""
    try:
        from web3 import Web3

        pk = private_key or os.getenv("ETH_PRIVATE_KEY", "")
        if not pk:
            return {"error": "ETH_PRIVATE_KEY not set. Cannot update agentURI."}

        if registry_address is None:
            return {
                "error": "Registry address not provided. "
                "Check 8004.org for deployed addresses on your target chain."
            }

        if agent_id is None:
            return {"error": "Agent ID not provided. Cannot update agentURI."}

        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.is_connected():
            return {"error": f"Cannot connect to RPC: {RPC_URL}"}

        account = w3.eth.account.from_key(pk)
        contract = w3.eth.contract(
            address=Web3.to_checksum_address(registry_address),
            abi=IDENTITY_REGISTRY_ABI,
        )

        tx = contract.functions.setAgentURI(int(agent_id), agent_uri).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
            "gas": 300000,
            "gasPrice": w3.eth.gas_price,
            "chainId": CHAIN_ID,
        })

        signed = account.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        log.info(f"📡 setAgentURI TX sent: {tx_hash.hex()}")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        if receipt.status == 1:
            log.info(f"✅ agentURI updated! TX: {tx_hash.hex()}")
            return {
                "agent_id": int(agent_id),
                "tx_hash": tx_hash.hex(),
                "chain_id": CHAIN_ID,
                "block": receipt.blockNumber,
            }

        return {"error": "Transaction reverted", "tx_hash": tx_hash.hex()}

    except ImportError:
        return {
            "error": "web3 not installed. Run: pip install web3",
        }
    except Exception as e:
        log.error(f"agentURI update failed: {e}")
        return {"error": str(e)}


# ──────────────────────────────────────────────
# Utility: Print setup guide
# ──────────────────────────────────────────────

def print_setup_guide():
    """Print a guide for setting up ERC-8004 registration."""
    guide = """
╔══════════════════════════════════════════════════════════════╗
║              ERC-8004 Registration Guide                     ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  1. Generate registration file:                              ║
║     python src/main.py --generate-8004                       ║
║                                                              ║
║  2. Host the JSON file:                                      ║
║     - IPFS via Filecoin Pin (free for ERC-8004)              ║
║     - Or HTTPS (e.g., GitHub raw URL)                        ║
║                                                              ║
║  3. Set environment variables:                               ║
║     export ETH_PRIVATE_KEY=0x...                             ║
║     export ETH_RPC_URL=https://sepolia.base.org              ║
║                                                              ║
║  4. Register on-chain:                                       ║
║     python src/main.py --register-8004 <registry_address>    ║
║                                                              ║
║  Alternative: Use agent0 SDK (TypeScript)                    ║
║     npm install @agent0/sdk                                  ║
║     See: https://github.com/agent0lab/agent0-ts              ║
║                                                              ║
║  Resources:                                                  ║
║     - EIP Spec: eips.ethereum.org/EIPS/eip-8004              ║
║     - Builder Program: 8004.org/build                        ║
║     - Community: ethereum-magicians.org                      ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(guide)
