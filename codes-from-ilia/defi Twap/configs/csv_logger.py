import csv
import os
from datetime import datetime
from web3 import Web3
from configs.trade_config import base_token, quote_token
from utils.Ctypes import get_token_decimals
from configs.wallets_config import Network
from configs.logger_config import setup_logger

# Setup logger
logger = setup_logger('csv_logger')

class CSVTradeLogger:
    def __init__(self):
        # Create logs directory if it doesn't exist
        if not os.path.exists('trade_logs'):
            os.makedirs('trade_logs')
        
        # Initialize token decimals
        self.base_decimals = get_token_decimals(base_token)
        self.quote_decimals = get_token_decimals(quote_token)

    def _format_amount(self, amount: float, decimals: int) -> float:
        """Format amount with proper decimals"""
        return float(amount) * (10 ** decimals)

    def _calculate_gas_cost_eth(self, gas_used: int, gas_price: int) -> float:
        """Calculate gas cost in ETH"""
        return (gas_used * gas_price) / 1e18

    def _calculate_price(self, amount_in: float, amount_out: float, direction: str) -> float:
        """Calculate price based on trade direction"""
        if not amount_in or not amount_out:
            return 0
        
        if direction.lower() == 'buy':
            return amount_out / amount_in
        else:
            return amount_in / amount_out

    def log_trade(self, trade_details: dict):
        """Log trade details to CSV file"""
        try:
            # Get current date for filename
            current_date = datetime.now().strftime('%Y%m%d')
            filename = f'trade_logs/trades_{current_date}.csv'

            # Format amounts with proper decimals
            amount_in = self._format_amount(
                trade_details.get('amount_in', 0),
                self.base_decimals if trade_details.get('token_in') == base_token else self.quote_decimals
            )
            amount_out = self._format_amount(
                trade_details.get('amount_out', 0),
                self.quote_decimals if trade_details.get('token_in') == base_token else self.base_decimals
            )
            
            # Calculate price
            price = self._calculate_price(
                trade_details.get('amount_in', 0),
                trade_details.get('amount_out', 0),
                trade_details.get('direction', '')
            )
            
            # Format gas details
            gas_price_gwei = self._format_amount(trade_details.get('gas_price', 0),
                                                  self.quote_decimals if trade_details.get('token_in') == base_token else self.base_decimals
            )
            gas_cost_eth = self._calculate_gas_cost_eth(
                trade_details.get('gas_used', 0),
                trade_details.get('gas_price', 0)
            )
            
            # Prepare row data with formatted values
            row = [
                datetime.now().isoformat(),
                trade_details.get('direction', '').upper(),
                trade_details.get('token_in', ''),
                trade_details.get('token_out', ''),
                f"{amount_in}",  # Formatted amount in
                f"{amount_out}",  # Formatted amount out
                f"{price}",      # Formatted price
                trade_details.get('tx_hash', ''),
                f"{trade_details.get('gas_used', 0):,}",  # Formatted gas used
                f"{gas_price_gwei}",  # Formatted gas price in gwei
                f"{gas_cost_eth}",    # Formatted gas cost in ETH
                'SUCCESS' if trade_details.get('success', False) else 'FAILED',
                trade_details.get('error', '')
            ]
            
            # Check if file exists to determine if we need to write headers
            file_exists = os.path.isfile(filename)
            
            # Write to CSV
            with open(filename, 'a', newline='') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow([
                        'timestamp',
                        'direction',
                        'token_in',
                        'token_out',
                        'amount_in',
                        'amount_out',
                        'price',
                        'tx_hash',
                        'gas_used',
                        'gas_price_gwei',
                        'gas_cost_eth',
                        'status',
                        'error'
                    ])
                writer.writerow(row)
                
            logger.info(f"Trade logged to {filename}")
            
        except Exception as e:
            logger.error(f"Error logging trade to CSV: {str(e)}", exc_info=True) 











            