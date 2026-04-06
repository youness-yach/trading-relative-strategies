import os

from web3 import Web3
from typing import Dict

def get_checksum_address(address):
    return Web3.to_checksum_address(address.lower())

# Contract Addresses for Optimism Mainnet
Factory_address = '0x1F98431c8aD98523631AE4a59f267346ea31F984'  # Uniswap V3 Factory on Optimism
Position_manager_address = '0xC36442b4a4522E871399CD717aBDD847Ab11FE88'  # Uniswap V3 NonfungiblePositionManager on Optimism
Quoter_address = '0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6'  # Uniswap V3 Quoter on Optimism
Router_address = '0xE592427A0AEce92De3Edee1F18E0157C05861564'  # Uniswap V3 SwapRouter on Optimism

# Chain ID for Optimism
Chain_ID = 10  # Optimism Mainnet Chain ID

# Network configuration
Network = 'https://optimism-mainnet.infura.io/v3/your_key'

# Multiple wallet configuration

# Multiple wallet configuration
WALLETS: Dict[str, Dict] = {
    'wallet1': {
        'address': get_checksum_address(''),
        'private_key': '',
        'name': 'Wallet 1'
    }
}

# Slack webhook: set locally, never commit real URLs (see README).
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")














