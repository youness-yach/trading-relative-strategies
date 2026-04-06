import requests
import json
from typing import Dict
from configs.wallets_config import SLACK_WEBHOOK_URL
from configs.logger_config import setup_logger

logger = setup_logger('slack_notifier')

class SlackNotifier:
    def __init__(self, webhook_url: str = SLACK_WEBHOOK_URL):
        self.webhook_url = webhook_url

    def send_trade_notification(self, trade_details: Dict):
        """Send trade notification to Slack"""
        try:
            message = self._format_trade_message(trade_details)
            response = requests.post(
                self.webhook_url,
                json=message,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                logger.info(f"Successfully sent Slack notification for trade")
            else:
                logger.error(f"Failed to send Slack notification. Status code: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending Slack notification: {str(e)}", exc_info=True)

    def _format_trade_message(self, trade_details: Dict) -> Dict:
        """Format trade details into a Slack message"""
        wallet_name = trade_details.get('wallet_name', 'Unknown Wallet')
        direction = trade_details.get('direction', 'UNKNOWN')
        status = "SUCCESS" if trade_details.get('success', False) else "FAILED"
        
        # Format amounts with appropriate decimals
        amount_in = float(trade_details.get('amount_in', 0))
        amount_out = float(trade_details.get('amount_out', 0))
        price = float(trade_details.get('price', 0))
        
        # Format gas details
        gas_used = trade_details.get('gas_used', 0)
        gas_price = float(trade_details.get('gas_price', 0))
        gas_cost = float(trade_details.get('gas_cost', 0))
        
        # Create message blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Trade Alert: {wallet_name} - {direction} {status}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Wallet:*\n{wallet_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Direction:*\n{direction}"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount In:*\n{amount_in:.6f} OP"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount Out:*\n{amount_out:.6f} USDT"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Price:*\n{price:.6f} USDT/OP"
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
                        "text": f"*Gas Used:*\n{gas_used:,} units"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Gas Price:*\n{gas_price:.2f} Gwei"
                    }
                ]
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Gas Cost:*\n{gas_cost:.6f} ETH"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Time:*\n{trade_details.get('timestamp', 'N/A')}"
                    }
                ]
            }
        ]
        
        # Add transaction hash link if available
        tx_hash = trade_details.get('tx_hash')
        if tx_hash:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Transaction:*\n<https://optimistic.etherscan.io/tx/{trade_details['tx_hash']}|View on Etherscan>"
                }
            })
        
        # Add error message if trade failed
        if not trade_details.get('success', False):
            error_msg = trade_details.get('error', 'Unknown error')
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error:*\n{error_msg}"
                }
            })
        
        return {
            "blocks": blocks
        } 