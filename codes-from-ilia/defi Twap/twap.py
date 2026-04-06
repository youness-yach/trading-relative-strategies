from web3 import Web3
from typing import List, Optional, Dict
import random
import asyncio
from datetime import datetime, timedelta
from configs.wallets_config import *
from utils.Ctypes import TradeDirection, UniswapInterface
from configs.abi_config import *
from configs.logger_config import setup_logger
from configs.trade_config import total_quantity
from dashboard_logger import add_dashboard_log, dashboard_log_handler

# Setup logger
logger = setup_logger('twap')

# Global variable to track total executed quantity across all wallets
total_executed_quantity: Dict[str, float] = {
    'total': 0.0,
    'wallets': {}
}

class TWAPExecutor:
    def __init__(
        self,
        uniswap: UniswapInterface,
        base_token: str,      # OP token
        quote_token: str,     # USDT
        total_quantity: float,
        duration_hours: float,
        interval_minutes: float,
        min_quantity_per_trade: float,
        max_quantity_per_trade: float,
        trade_direction: TradeDirection,
        wallet_id: Optional[str] = None,
        wallet_name: Optional[str] = None
    ):
        self.w3 = Web3(Web3.HTTPProvider(Network))
        self.uniswap = uniswap
        self.base_token = base_token    # OP
        self.quote_token = quote_token  # USDT
        self.total_quantity = total_quantity
        self.duration = timedelta(hours=duration_hours)
        self.interval = timedelta(minutes=interval_minutes)
        self.min_quantity = min_quantity_per_trade
        self.max_quantity = max_quantity_per_trade
        self.trade_direction = trade_direction
        self.wallet_id = wallet_id
        self.wallet_name = wallet_name
        
        # Get token decimals
        self.base_decimals = self._get_token_decimals(base_token)   # OP decimals (18)
        self.quote_decimals = self._get_token_decimals(quote_token) # USDT decimals (6)
        add_dashboard_log('INFO', f"Base token decimals: {self.base_decimals}")
        add_dashboard_log('INFO', f"Quote token decimals: {self.quote_decimals}")
        
        # Calculate number of intervals
        self.total_intervals = int(self.duration.total_seconds() / self.interval.total_seconds())
        self.quantity_per_interval = self.total_quantity / self.total_intervals
        
        # Validate quantities
        if self.min_quantity > self.quantity_per_interval or self.max_quantity < self.quantity_per_interval:
            add_dashboard_log('ERROR', "Min/max quantities are incompatible with total quantity and intervals")
            raise ValueError("Min/max quantities are incompatible with total quantity and intervals")
            
        self.executed_trades: List[dict] = []
        self.total_executed_quantity = 0
        
        # Initialize wallet tracking in global dict
        if wallet_id:
            total_executed_quantity['wallets'][wallet_id] = 0.0

    async def execute_twap_async(self) -> List[dict]:
        """Execute the TWAP strategy asynchronously with randomized execution within each interval"""
        start_time = datetime.now()
        end_time = start_time + self.duration
        direction_str = "buying" if self.trade_direction == TradeDirection.BUY else "selling"
        add_dashboard_log('INFO', f"Starting TWAP execution for {self.wallet_name or 'Unknown Wallet'} - {direction_str} {self.total_quantity} OP tokens")
        add_dashboard_log('INFO', f"Time period: {start_time} to {end_time}")
        add_dashboard_log('INFO', f"Intervals: {self.total_intervals}")

        # Pre-approve total amount if selling
        if self.trade_direction == TradeDirection.SELL:
            total_amount_wei = self._convert_to_token_amount(self.total_quantity, self.base_decimals)
            add_dashboard_log('INFO', f"Pre-approving {self.total_quantity} OP tokens for selling")
            if not self.uniswap.approve_tokens(self.base_token, total_amount_wei):
                add_dashboard_log('ERROR', "Failed to approve tokens for trading")
                return self.executed_trades

        for i in range(self.total_intervals):
            # Check if stop was requested
            if dashboard_log_handler.get_stop_requested():
                add_dashboard_log('INFO', f"Stop requested, exiting TWAP execution for {self.wallet_name}")
                break
                
            # Calculate progress percentage (30% base + 60% for trading progress + 10% for completion)
            progress_percentage = 30 + (i / self.total_intervals) * 60
            
            # Update wallet status with current progress
            if self.wallet_id:
                dashboard_log_handler.update_wallet_status(self.wallet_id, {
                    'status': 'executing',
                    'progress': progress_percentage,
                    'trades_executed': len(self.executed_trades),
                    'successful_trades': len([t for t in self.executed_trades if t['success']]),
                    'failed_trades': len([t for t in self.executed_trades if not t['success']]),
                    'total_executed': self.total_executed_quantity,
                    'last_update': datetime.now().isoformat()
                })
                
            interval_start = start_time + i * self.interval
            interval_end = interval_start + self.interval
            now = datetime.now()
            # If we're already past the interval, skip
            if now > interval_end:
                continue
            # Pick a random offset within the interval (in seconds)
            random_offset = random.uniform(0, self.interval.total_seconds())
            scheduled_time = interval_start + timedelta(seconds=random_offset)
            # If scheduled_time is in the past, execute immediately
            wait_seconds = (scheduled_time - datetime.now()).total_seconds()
            if wait_seconds > 0:
                # Break the wait into smaller chunks to check for stop requests
                for _ in range(int(wait_seconds)):
                    if dashboard_log_handler.get_stop_requested():
                        add_dashboard_log('INFO', f"Stop requested during wait, exiting TWAP execution for {self.wallet_name}")
                        return self.executed_trades
                    await asyncio.sleep(1)
                # Handle any remaining fractional seconds
                remaining_wait = wait_seconds - int(wait_seconds)
                if remaining_wait > 0:
                    await asyncio.sleep(remaining_wait)

            # Check again before executing trade
            if dashboard_log_handler.get_stop_requested():
                add_dashboard_log('INFO', f"Stop requested before trade execution, exiting TWAP for {self.wallet_name}")
                break

            # Calculate quantity for this trade (in OP tokens)
            quantity = self._get_random_quantity()

            # Check if this would exceed the global total limit
            if total_executed_quantity['total'] + quantity > total_quantity:
                quantity = total_quantity - total_executed_quantity['total']
                if quantity <= 0:
                    add_dashboard_log('INFO', "Global total quantity limit reached")
                    break

            add_dashboard_log('DEBUG', f"Calculated quantity for trade: {quantity} OP")
            current_time = datetime.now()
            try:
                if self.trade_direction == TradeDirection.SELL:
                    # Selling OP tokens
                    amount_in = self._convert_to_token_amount(quantity, self.base_decimals)
                    add_dashboard_log('INFO', f"Executing sell trade - Amount: {quantity} OP")
                    result = self.uniswap.swap(
                        token_in=self.base_token,    # OP
                        token_out=self.quote_token,  # USDT
                        amount_in=amount_in
                    )
                else:  # TradeDirection.BUY
                    # Buying with USDT, use quote_decimals
                    amount_in = self._convert_to_token_amount(quantity, self.quote_decimals)
                    add_dashboard_log('INFO', f"Executing buy trade - Amount: {quantity} USDT")
                    result = self.uniswap.swap(
                        token_in=self.quote_token,   # USDT
                        token_out=self.base_token,   # OP
                        amount_in=amount_in
                    )

                if result and result.get('success'):
                    add_dashboard_log('INFO', f"Trade successful - Quantity: {quantity}, TX: {result.get('tx_hash')}")
                    trade_record = {
                        'timestamp': current_time,
                        'quantity': quantity,
                        'success': True,
                        'direction': self.trade_direction.value,
                        'tx_hash': result.get('tx_hash'),
                        'wallet_id': self.wallet_id,
                        'wallet_name': self.wallet_name
                    }
                    self.executed_trades.append(trade_record)
                    
                    # Add to live trade history immediately
                    trade_history_record = {
                        'timestamp': current_time.isoformat() if hasattr(current_time, 'isoformat') else str(current_time),
                        'wallet_name': self.wallet_name,
                        'quantity': quantity,
                        'success': True,
                        'direction': self.trade_direction.value,
                        'tx_hash': result.get('tx_hash', ''),
                        'error': ''
                    }
                    dashboard_log_handler.add_trade_to_history(trade_history_record)
                    
                    self.total_executed_quantity += quantity

                    # Update global tracking
                    if self.wallet_id:
                        total_executed_quantity['wallets'][self.wallet_id] = self.total_executed_quantity
                        total_executed_quantity['total'] += quantity

                        add_dashboard_log('INFO', f"Global total executed: {total_executed_quantity['total']:.6f} OP")
                        add_dashboard_log('INFO', f"Wallet {self.wallet_name} total: {self.total_executed_quantity:.6f} OP")
                        
                        # Update wallet status immediately after successful trade
                        current_progress = 30 + ((i + 1) / self.total_intervals) * 60
                        dashboard_log_handler.update_wallet_status(self.wallet_id, {
                            'status': 'executing',
                            'progress': current_progress,
                            'trades_executed': len(self.executed_trades),
                            'successful_trades': len([t for t in self.executed_trades if t['success']]),
                            'failed_trades': len([t for t in self.executed_trades if not t['success']]),
                            'total_executed': self.total_executed_quantity,
                            'last_update': datetime.now().isoformat()
                        })
                else:
                    add_dashboard_log('ERROR', f"Trade failed at {current_time}")
                    trade_record = {
                        'timestamp': current_time,
                        'quantity': quantity,
                        'success': False,
                        'direction': self.trade_direction.value,
                        'error': 'Transaction failed',
                        'wallet_id': self.wallet_id,
                        'wallet_name': self.wallet_name
                    }
                    self.executed_trades.append(trade_record)
                    
                    # Add failed trade to live trade history immediately
                    trade_history_record = {
                        'timestamp': current_time.isoformat() if hasattr(current_time, 'isoformat') else str(current_time),
                        'wallet_name': self.wallet_name,
                        'quantity': quantity,
                        'success': False,
                        'direction': self.trade_direction.value,
                        'tx_hash': '',
                        'error': 'Transaction failed'
                    }
                    dashboard_log_handler.add_trade_to_history(trade_history_record)
                    
                    # Update wallet status after failed trade too
                    if self.wallet_id:
                        current_progress = 30 + ((i + 1) / self.total_intervals) * 60
                        dashboard_log_handler.update_wallet_status(self.wallet_id, {
                            'status': 'executing',
                            'progress': current_progress,
                            'trades_executed': len(self.executed_trades),
                            'successful_trades': len([t for t in self.executed_trades if t['success']]),
                            'failed_trades': len([t for t in self.executed_trades if not t['success']]),
                            'total_executed': self.total_executed_quantity,
                            'last_update': datetime.now().isoformat()
                        })

            except Exception as e:
                add_dashboard_log('ERROR', f"Error executing trade: {str(e)}", exc_info=True)
                trade_record = {
                    'timestamp': current_time,
                    'quantity': quantity,
                    'success': False,
                    'direction': self.trade_direction.value,
                    'error': str(e),
                    'wallet_id': self.wallet_id,
                    'wallet_name': self.wallet_name
                }
                self.executed_trades.append(trade_record)
                
                # Add error trade to live trade history immediately
                trade_history_record = {
                    'timestamp': current_time.isoformat() if hasattr(current_time, 'isoformat') else str(current_time),
                    'wallet_name': self.wallet_name,
                    'quantity': quantity,
                    'success': False,
                    'direction': self.trade_direction.value,
                    'tx_hash': '',
                    'error': str(e)
                }
                dashboard_log_handler.add_trade_to_history(trade_history_record)
                
                # Update wallet status after error too
                if self.wallet_id:
                    current_progress = 30 + ((i + 1) / self.total_intervals) * 60
                    dashboard_log_handler.update_wallet_status(self.wallet_id, {
                        'status': 'executing',
                        'progress': current_progress,
                        'trades_executed': len(self.executed_trades),
                        'successful_trades': len([t for t in self.executed_trades if t['success']]),
                        'failed_trades': len([t for t in self.executed_trades if not t['success']]),
                        'total_executed': self.total_executed_quantity,
                        'last_update': datetime.now().isoformat()
                    })

            # Check if stop was requested after trade
            if dashboard_log_handler.get_stop_requested():
                add_dashboard_log('INFO', f"Stop requested after trade, exiting TWAP execution for {self.wallet_name}")
                break

            # After trade, if any time remains in the interval, wait until next interval
            now = datetime.now()
            if now < interval_end:
                remaining_time = (interval_end - now).total_seconds()
                # Break the remaining wait into chunks to check for stop requests
                for _ in range(int(remaining_time)):
                    if dashboard_log_handler.get_stop_requested():
                        add_dashboard_log('INFO', f"Stop requested during interval wait, exiting TWAP for {self.wallet_name}")
                        return self.executed_trades
                    await asyncio.sleep(1)
                # Handle any remaining fractional seconds
                remaining_fractional = remaining_time - int(remaining_time)
                if remaining_fractional > 0:
                    await asyncio.sleep(remaining_fractional)

            # If we've reached the total quantity, break
            if self.total_executed_quantity >= self.total_quantity:
                break

        return self.executed_trades

    def _get_token_decimals(self, token_address: str) -> int:
        """Get the number of decimals for a token"""
        try:
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=[{
                    "constant": True,
                    "inputs": [],
                    "name": "decimals",
                    "outputs": [{"name": "", "type": "uint8"}],
                    "payable": False,
                    "stateMutability": "view",
                    "type": "function"
                }]
            )
            decimals = token_contract.functions.decimals().call()
            add_dashboard_log('DEBUG', f"Retrieved decimals for token {token_address}: {decimals}")
            return decimals
        except Exception as e:
            add_dashboard_log('ERROR', f"Error getting decimals for token {token_address}: {str(e)}", exc_info=True)
            # Return default decimals (18 for most tokens)
            return 18

    def _convert_to_token_amount(self, amount: float, decimals: int) -> int:
        """Convert a float amount to token amount with proper decimals"""
        return int(amount * (10 ** decimals))

    def _get_random_quantity(self) -> float:
        """Generate a random quantity within bounds that doesn't exceed remaining quantity"""
        remaining = self.total_quantity - self.total_executed_quantity
        max_possible = min(self.max_quantity, remaining)
        
        if max_possible <= self.min_quantity:
            return max_possible
            
        return random.uniform(self.min_quantity, max_possible)