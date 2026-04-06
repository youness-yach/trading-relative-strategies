import json
import time
import uuid
from typing import Dict, Optional
import requests
from fireblocks_sdk import FireblocksSDK, TRANSACTION_STATUS_COMPLETED
from configs.fireblocks_config import (
    FIREBLOCKS_API_KEY,
    FIREBLOCKS_SECRET_KEY,
    FIREBLOCKS_BASE_URL,
    GAS_STATION_SETTINGS,
    TRANSACTION_SETTINGS
)
from configs.logger_config import setup_logger

logger = setup_logger('fireblocks')

class FireblocksClient:
    def __init__(self, vault_account_id: str, wallet_name: str):
        """Initialize Fireblocks client with vault account ID"""
        self.vault_account_id = vault_account_id
        self.wallet_name = wallet_name
        self.fb_client = FireblocksSDK(FIREBLOCKS_API_KEY, FIREBLOCKS_SECRET_KEY)
        
    async def create_transaction(
        self,
        destination_address: str,
        amount: str,
        asset_id: str = "ETH_TEST",  # Default to Ethereum, change as needed
        note: Optional[str] = None
    ) -> Dict:
        """Create and submit a transaction through Fireblocks"""
        try:
            # Generate a unique external transaction ID
            external_tx_id = str(uuid.uuid4())
            
            # Prepare transaction parameters
            tx_params = {
                "assetId": asset_id,
                "source": {
                    "type": "VAULT_ACCOUNT",
                    "id": self.vault_account_id
                },
                "destination": {
                    "type": "EXTERNAL",
                    "id": destination_address
                },
                "amount": amount,
                "note": note or TRANSACTION_SETTINGS["note"],
                "externalTxId": external_tx_id,
                "gasPrice": GAS_STATION_SETTINGS["max_fee"],
                "priorityFee": GAS_STATION_SETTINGS["priority_fee"]
            }
            
            # Create transaction
            tx = self.fb_client.create_transaction(tx_params)
            logger.info(f"Created Fireblocks transaction for {self.wallet_name}: {tx['id']}")
            
            return tx
            
        except Exception as e:
            logger.error(f"Error creating Fireblocks transaction for {self.wallet_name}: {str(e)}")
            raise
            
    async def wait_for_transaction_completion(self, tx_id: str, timeout: int = 300) -> Dict:
        """Wait for a transaction to complete"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                tx = self.fb_client.get_transaction_by_id(tx_id)
                status = tx.get("status")
                
                if status == TRANSACTION_STATUS_COMPLETED:
                    logger.info(f"Transaction {tx_id} completed for {self.wallet_name}")
                    return tx
                    
                elif status in ["FAILED", "REJECTED", "CANCELLED"]:
                    error_msg = f"Transaction {tx_id} failed with status {status}"
                    logger.error(f"{error_msg} for {self.wallet_name}")
                    raise Exception(error_msg)
                    
                await asyncio.sleep(5)  # Wait 5 seconds before checking again
                
            except Exception as e:
                logger.error(f"Error checking transaction {tx_id} status for {self.wallet_name}: {str(e)}")
                raise
                
        raise TimeoutError(f"Transaction {tx_id} timed out after {timeout} seconds")
        
    async def get_gas_price(self) -> Dict:
        """Get current gas price from Fireblocks Gas Station"""
        try:
            response = requests.get(f"{FIREBLOCKS_BASE_URL}/v1/gas_station")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error fetching gas price for {self.wallet_name}: {str(e)}")
            raise
            
    def get_vault_balance(self, asset_id: str = "ETH_TEST") -> Dict:
        """Get vault account balance for specific asset"""
        try:
            balance = self.fb_client.get_vault_account_asset(self.vault_account_id, asset_id)
            logger.info(f"Retrieved balance for {self.wallet_name}: {balance}")
            return balance
        except Exception as e:
            logger.error(f"Error fetching vault balance for {self.wallet_name}: {str(e)}")
            raise 