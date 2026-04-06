from enum import Enum
from typing import Protocol, Optional, Dict
from web3 import Web3
from configs.abi_config import ERC20_ABI
from configs.logger_config import setup_logger

# Setup logger
logger = setup_logger('token_utils')

class TradeDirection(Enum):
    BUY = "buy"   # Buy OP with USDT
    SELL = "sell" # Sell OP for USDT

class UniswapInterface(Protocol):
    """Protocol defining the interface for Uniswap interactions"""
    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_tolerance: float = 0.005
    ) -> Optional[Dict]:
        ... 

def get_token_decimals(w3: Web3, token_address: str) -> int:
    """
    Get the number of decimals for a token
    
    Args:
        w3: Web3 instance
        token_address: Token contract address
        
    Returns:
        int: Number of decimals for the token
    """
    try:
        logger.debug(f"Getting decimals for token: {token_address}")
        token_contract = w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=ERC20_ABI
        )
        decimals = token_contract.functions.decimals().call()
        logger.info(f"Retrieved decimals for token {token_address}: {decimals}")
        return decimals
    except Exception as e:
        logger.error(f"Error getting token decimals for {token_address}: {str(e)}")
        raise  # Re-raise the exception to handle it in the calling code
        