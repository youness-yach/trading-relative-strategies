import csv
import os
from datetime import datetime
from typing import Dict, Any

class CSVTradeLogger:
    def __init__(self, csv_dir: str = 'trade_logs'):
        self.csv_dir = csv_dir
        if not os.path.exists(csv_dir):
            os.makedirs(csv_dir)
        
        self.csv_file = os.path.join(csv_dir, f'trades_{datetime.now().strftime("%Y%m%d")}.csv')
        self._initialize_csv()

    def _initialize_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            headers = [
                'timestamp',
                'wallet_id',
                'wallet_name',
                'trade_direction',
                'token_in',
                'token_out',
                'amount_in',
                'amount_out',
                'tx_hash',
                'gas_used',
                'gas_price',
                'status',
                'error_message'
            ]
            with open(self.csv_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()

    def log_trade(self, trade_details: Dict[str, Any]):
        """Log trade details to CSV file"""
        try:
            with open(self.csv_file, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'timestamp',
                    'wallet_id',
                    'wallet_name',
                    'trade_direction',
                    'token_in',
                    'token_out',
                    'amount_in',
                    'amount_out',
                    'tx_hash',
                    'gas_used',
                    'gas_price',
                    'status',
                    'error_message'
                ])
                
                # Format the trade details
                formatted_trade = {
                    'timestamp': datetime.now().isoformat(),
                    'wallet_id': trade_details.get('wallet_id', ''),
                    'wallet_name': trade_details.get('wallet_name', ''),
                    'trade_direction': trade_details.get('direction', ''),
                    'token_in': trade_details.get('token_in', ''),
                    'token_out': trade_details.get('token_out', ''),
                    'amount_in': trade_details.get('amount_in', ''),
                    'amount_out': trade_details.get('amount_out', ''),
                    'tx_hash': trade_details.get('tx_hash', ''),
                    'gas_used': trade_details.get('gas_used', ''),
                    'gas_price': trade_details.get('gas_price', ''),
                    'status': 'success' if trade_details.get('success', False) else 'failed',
                    'error_message': trade_details.get('error', '')
                }
                
                writer.writerow(formatted_trade)
                
        except Exception as e:
            print(f"Error logging trade to CSV: {str(e)}") 