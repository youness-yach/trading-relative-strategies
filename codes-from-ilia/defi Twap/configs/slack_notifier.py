import requests
import json
from typing import Dict, Any
from datetime import datetime
from configs.logger_config import setup_logger
from configs.trade_config import base_token, quote_token
from web3 import Web3
from utils.Ctypes import get_token_decimals
from configs.wallets_config import Network

logger = setup_logger('slack')

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.logger = logger
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(Network))
        
        # Get token decimals
        try:
            self.base_decimals = get_token_decimals(self.w3, base_token)
            self.quote_decimals = get_token_decimals(self.w3, quote_token)
        except Exception as e:
            logger.error(f"Failed to get token decimals: {str(e)}")
            # Use default decimals as fallback
            self.base_decimals = 18  # OP default
            self.quote_decimals = 6  # USDT default
            logger.info(f"Using default decimals - base: {self.base_decimals}, quote: {self.quote_decimals}")

    def _format_amount(self, amount: int, decimals: int) -> float:
        """Convert raw token amount to human-readable format"""
        return float(amount) / (10 ** decimals)

    def _format_gas_price(self, gas_price: int) -> float:
        """Convert gas price from wei to gwei"""
        return float(gas_price) / 1e9

    def _calculate_gas_cost_eth(self, gas_used: int, gas_price: int) -> float:
        """Calculate gas cost in ETH"""
        return float(gas_used * gas_price) / 1e18

    def _calculate_price(self, amount_in: int, amount_out: int, direction: str) -> float:
        """Calculate the price of the trade"""
        if direction == 'buy':
            return self._format_amount(amount_out, self.quote_decimals) / self._format_amount(amount_in, self.base_decimals)
        else:
            return self._format_amount(amount_in, self.base_decimals) / self._format_amount(amount_out, self.quote_decimals)

    def _get_token_symbol(self, token_address: str) -> str:
        """Get token symbol from address"""
        if token_address.lower() == base_token.lower():
            return "OP"
        elif token_address.lower() == quote_token.lower():
            return "USDT"
        return token_address[:6] + "..."

    def _format_trade_message(self, trade_details: Dict[str, Any]) -> Dict[str, Any]:
        """Format trade details into a Slack message"""
        direction = trade_details.get('direction', '').upper()
        status = "SUCCESS" if trade_details.get('success', False) else "FAILED"
        
        # Format amounts with proper decimals
        amount_in = self._format_amount(trade_details.get('amount_in', 0), self.base_decimals if trade_details.get('token_in') == base_token else self.quote_decimals)
        amount_out = self._format_amount(trade_details.get('amount_out', 0), self.quote_decimals if trade_details.get('token_in') == base_token else self.base_decimals)
        
        # Calculate price
        price = self._calculate_price(trade_details.get('amount_in', 0), trade_details.get('amount_out', 0), direction)
        
        # Format gas details
        gas_price_gwei = self._format_gas_price(trade_details.get('gas_price', 0))
        gas_cost_eth = self._calculate_gas_cost_eth(trade_details.get('gas_used', 0), trade_details.get('gas_price', 0))

        # Get token symbols
        token_in_symbol = self._get_token_symbol(trade_details.get('token_in', ''))
        token_out_symbol = self._get_token_symbol(trade_details.get('token_out', ''))

        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{'Buy' if direction == 'buy' else 'Sell'} {token_in_symbol}/{token_out_symbol}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount In:*\n{amount_in:.6f} {token_in_symbol}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount Out:*\n{amount_out:.6f} {token_out_symbol}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Price:*\n{price:.6f} {token_out_symbol}/{token_in_symbol}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Status:*\n{status}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Gas Used:*\n{trade_details.get('gas_used', 0):,} units"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Gas Price:*\n{gas_price_gwei:.2f} Gwei"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Gas Cost:*\n{gas_cost_eth:.6f} ETH"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                ]
            }
        ]

        # Add transaction hash if available
        if trade_details.get('tx_hash'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Transaction:*\n<https://optimistic.etherscan.io/tx/{trade_details['tx_hash']}|View on Etherscan>"
                }
            })

        # Add error message if trade failed
        if not trade_details.get('success') and trade_details.get('error'):
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n{trade_details['error']}"
                }
            })

        # Add timestamp
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                }
            ]
        })

        return {
            "blocks": blocks
        }

    def send_trade_notification(self, trade_details: Dict[str, Any]) -> bool:
        """Send trade notification to Slack"""
        try:
            message = self._format_trade_message(trade_details)
            response = requests.post(
                self.webhook_url,
                data=json.dumps(message),
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                self.logger.info("Successfully sent trade notification to Slack")
                return True
            else:
                self.logger.error(f"Failed to send Slack notification. Status code: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending Slack notification: {str(e)}", exc_info=True)
            return False 