from web3 import Web3
from utils.Ctypes import TradeDirection
import random

def get_checksum_address(address):
    return Web3.to_checksum_address(address.lower())

# Token addresses for Optimism Mainnet
base_token = get_checksum_address('0x4200000000000000000000000000000000000042')  # OP (Optimism)
quote_token = get_checksum_address('0x94b008aA00579c1307B0EF2c499aD98a8ce58e58')  # USDT on Optimism

# TWAP configuration
trade_delay = random.uniform(15, 45) # seconds delay between wallets used to make it untracable and random no paternistic behavior
total_quantity = 2  # Total amount of Base asset to spend (selling its quantity of base asset in buy its quantity of quote asset)
duration_hours = 2/60  # Execute over 5 minutes
interval_minutes = 0.5  # Execute every 30 minutes
min_quantity_per_trade = 0.1  # Minimum amount per trade
max_quantity_per_trade = 1  # Maximum amount per trade
trade_direction = TradeDirection.BUY  # Trade direction (BUY or SELL)