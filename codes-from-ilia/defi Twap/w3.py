from web3 import Web3
from typing import Optional, Tuple
from configs.abi_config import *
from configs.wallets_config import *
from configs.trade_config import *
from configs.logger_config import setup_logger
from csv_logger import CSVTradeLogger
from configs.slack_notifier import SlackNotifier
from dashboard_logger import add_dashboard_log

# Setup logger
logger = setup_logger('uniswap')

class UniswapV3:
    def __init__(
        self,
        provider_url: str,
        wallet_address: Optional[str] = None,
        private_key: Optional[str] = None,
        factory_address: Optional[str] = None,
        position_manager_address: Optional[str] = None,
        wallet_id: Optional[str] = None,
        wallet_name: Optional[str] = None
    ):
        add_dashboard_log('INFO', f"Initializing UniswapV3 instance for {wallet_name or 'Unknown Wallet'}")
        self.w3 = Web3(Web3.HTTPProvider(provider_url))
        self.wallet_address = wallet_address
        self.private_key = private_key
        self.wallet_id = wallet_id
        self.wallet_name = wallet_name
        
        # Contract Addresses
        self.factory_address = factory_address or Factory_address
        self.position_manager_address = position_manager_address or Position_manager_address
        
        # Initialize contracts
        add_dashboard_log('DEBUG', "Initializing contract instances")
        self.factory = self.w3.eth.contract(
            address=self.factory_address,
            abi=UNISWAP_V3_FACTORY_ABI
        )
        self.position_manager = self.w3.eth.contract(
            address=self.position_manager_address,
            abi=POSITION_MANAGER_ABI
        )
        self.router = self.w3.eth.contract(
            address=Router_address,
            abi=ROUTER_ABI
        )
        
        # Initialize CSV logger
        self.csv_logger = CSVTradeLogger()
        
        # Initialize Slack notifier
        self.slack_notifier = SlackNotifier(SLACK_WEBHOOK_URL)

    def get_pool(self, token_a: str, token_b: str, fee: int = 3000) -> Optional[str]:
        """Get the pool address for a token pair."""
        try:
            add_dashboard_log('DEBUG', f"Getting pool for tokens {token_a} and {token_b} with fee {fee}")
            pool_address = self.factory.functions.getPool(token_a, token_b, fee).call()
            if pool_address == "0x0000000000000000000000000000000000000000":
                add_dashboard_log('WARNING', f"No pool found for tokens with fee {fee}")
                return None
            add_dashboard_log('DEBUG', f"Found pool at address: {pool_address}")
            return pool_address
        except Exception as e:
            add_dashboard_log('ERROR', f"Error getting pool: {str(e)}", exc_info=True)
            return None

    def get_price(self, token_a: str, token_b: str, amount_in: int = 1000000, fee: int = 3000) -> Optional[float]:
        """Get the price for a token pair."""
        try:
            # Get pool address
            pool_address = self.get_pool(token_a, token_b, fee)
            if not pool_address:
                add_dashboard_log('WARNING', f"No pool found for tokens with fee {fee}")
                return None

            # Create pool contract
            add_dashboard_log('DEBUG', f"Creating pool contract for address: {pool_address}")
            pool = self.w3.eth.contract(
                address=pool_address,
                abi=UNISWAP_V3_POOL_ABI
            )

            # Get current price from slot0
            add_dashboard_log('DEBUG', "Getting current price from slot0")
            slot0 = pool.functions.slot0().call()
            sqrt_price_x96 = slot0[0]
            
            # Calculate price from sqrtPriceX96
            price = (sqrt_price_x96 ** 2) / (2 ** 192)
            add_dashboard_log('INFO', f"Current price: {price}")
            
            return price
        except Exception as e:
            add_dashboard_log('ERROR', f"Error getting price: {str(e)}", exc_info=True)
            return None

    def get_token_balance(self, token_address: str) -> int:
        """Get token balance for the wallet"""
        try:
            add_dashboard_log('DEBUG', f"Getting token balance for {token_address}")
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            balance = token_contract.functions.balanceOf(self.wallet_address).call()
            add_dashboard_log('INFO', f"Token balance: {balance}")
            return balance
        except Exception as e:
            add_dashboard_log('ERROR', f"Error getting token balance: {str(e)}", exc_info=True)
            return 0

    def get_token_allowance(self, token_address: str) -> int:
        """Get current allowance for the router"""
        try:
            add_dashboard_log('DEBUG', f"Getting token allowance for {token_address}")
            token_contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address(token_address),
                abi=ERC20_ABI
            )
            allowance = token_contract.functions.allowance(
                self.wallet_address,
                Router_address
            ).call()
            add_dashboard_log('INFO', f"Current allowance: {allowance}")
            return allowance
        except Exception as e:
            add_dashboard_log('ERROR', f"Error getting allowance: {str(e)}", exc_info=True)
            return 0

    def approve_tokens(self, token_address: str, amount: int) -> bool:
        """Approve tokens for trading"""
        try:
            token_address = self.w3.to_checksum_address(token_address)
            add_dashboard_log('INFO', f"Approving {amount} tokens for {token_address}")
            
            # Check current balance
            balance = self.get_token_balance(token_address)
            if balance < amount:
                add_dashboard_log('ERROR', f"Insufficient balance. Have: {balance}, Need: {amount}")
                return False

            # Check current allowance
            current_allowance = self.get_token_allowance(token_address)
            if current_allowance >= amount:
                add_dashboard_log('INFO', f"Already approved sufficient amount: {current_allowance}")
                return True

            # Create token contract
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )

            # If previous allowance exists but is insufficient, first reset it to 0
            if current_allowance > 0:
                add_dashboard_log('INFO', "Resetting previous allowance...")
                reset_txn = token_contract.functions.approve(
                    Router_address,
                    0
                ).build_transaction({
                    'from': self.wallet_address,
                    'gas': 100000,
                    'gasPrice': self.w3.eth.gas_price,
                    'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                    'chainId': Chain_ID
                })
                
                signed_txn = self.w3.eth.account.sign_transaction(reset_txn, self.private_key)
                tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
                
                if receipt['status'] != 1:
                    add_dashboard_log('ERROR', "Failed to reset allowance")
                    return False

            # Approve new amount
            add_dashboard_log('INFO', f"Approving {amount} tokens...")
            approve_txn = token_contract.functions.approve(
                Router_address,
                amount
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 100000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': self.w3.eth.get_transaction_count(self.wallet_address),
                'chainId': Chain_ID
            })
            
            signed_txn = self.w3.eth.account.sign_transaction(approve_txn, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)
            
            if receipt['status'] == 1:
                # Verify the approval was successful
                new_allowance = self.get_token_allowance(token_address)
                if new_allowance >= amount:
                    add_dashboard_log('INFO', "Approval successful")
                    return True
                else:
                    add_dashboard_log('ERROR', f"Approval failed. New allowance: {new_allowance}, Required: {amount}")
                    return False
            else:
                add_dashboard_log('ERROR', "Approval transaction failed")
                return False

        except Exception as e:
            add_dashboard_log('ERROR', f"Error in approve_tokens: {str(e)}", exc_info=True)
            return False

    def add_liquidity(
        self,
        token0: str,
        token1: str,
        amount0: int,
        amount1: int,
        fee: int = 3000,
        tick_lower: int = -887272,
        tick_upper: int = 887272
    ) -> Optional[dict]:
        """Add liquidity to a Uniswap V3 pool."""
        if not self.wallet_address or not self.private_key:
            raise Exception("Wallet address and private key required for adding liquidity")

        try:
            # Approve tokens first
            if not self.approve_tokens(token0, amount0):
                raise Exception("Failed to approve token0")
            if not self.approve_tokens(token1, amount1):
                raise Exception("Failed to approve token1")

            # Prepare mint parameters
            deadline = self.w3.eth.get_block('latest').timestamp + 1200  # 20 minutes from now
            mint_params = {
                'token0': token0,
                'token1': token1,
                'fee': fee,
                'tickLower': tick_lower,
                'tickUpper': tick_upper,
                'amount0Desired': amount0,
                'amount1Desired': amount1,
                'amount0Min': 0,  # Set minimum amounts as needed
                'amount1Min': 0,
                'recipient': self.wallet_address,
                'deadline': deadline
            }

            # Build mint transaction
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            mint_txn = self.position_manager.functions.mint(mint_params).build_transaction({
                'from': self.wallet_address,
                'gas': 500000,
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(mint_txn, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if tx_receipt.status == 1:
                # Parse the mint event to get position details
                mint_event = self.position_manager.events.IncreaseLiquidity().process_receipt(tx_receipt)[0]
                return {
                    'tokenId': mint_event.args.tokenId,
                    'liquidity': mint_event.args.liquidity,
                    'amount0': mint_event.args.amount0,
                    'amount1': mint_event.args.amount1
                }
            else:
                raise Exception("Transaction failed")

        except Exception as e:
            add_dashboard_log('ERROR', f"Error adding liquidity: {e}")
            return None

    def find_best_pool(self, token_in: str, token_out: str, amount_in: int) -> Tuple[int, str]:
        """
        Find the best pool (fee tier) for a given token pair by checking liquidity and prices.
        Returns the best fee tier and pool address.
        """
        # Standard Uniswap V3 fee tiers
        fee_tiers = [100, 500, 3000, 10000]  # 0.01%, 0.05%, 0.3%, 1%
        best_fee = None
        best_pool = None
        best_amount_out = 0

        for fee in fee_tiers:
            try:
                pool_address = self.get_pool(token_in, token_out, fee)
                if not pool_address:
                    continue

                # Create quoter contract
                quoter = self.w3.eth.contract(
                    address=Quoter_address,  # QuoterV2 contract on Sepolia
                    abi=QUOTER_V2_ABI
                )

                # Get quote for this pool
                quote_params = {
                    'tokenIn': token_in,
                    'tokenOut': token_out,
                    'fee': fee,
                    'amountIn': amount_in,
                    'sqrtPriceLimitX96': 0
                }

                try:
                    quote = quoter.functions.quoteExactInputSingle(quote_params).call()
                    amount_out = quote[0]

                    # Update best pool if this one offers better output
                    if amount_out > best_amount_out:
                        best_amount_out = amount_out
                        best_fee = fee
                        best_pool = pool_address
                except Exception:
                    continue

            except Exception as e:
                add_dashboard_log('ERROR', f"Error checking fee tier {fee}: {e}")
                continue

        if best_fee is None:
            raise Exception("No viable pool found for token pair")

        return best_fee, best_pool

    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        slippage_tolerance: float = 0.005
    ) -> Optional[dict]:
        """Execute a swap on Uniswap V3 using SwapRouter."""
        if not self.wallet_address or not self.private_key:
            add_dashboard_log('ERROR', "Wallet address and private key required for swapping")
            raise Exception("Wallet address and private key required for swapping")

        try:
            # Check balance first
            balance = self.get_token_balance(token_in)
            if balance < amount_in:
                add_dashboard_log('ERROR', f"Insufficient balance for swap. Have: {balance}, Need: {amount_in}")
                return None

            # Convert addresses to checksum format
            token_in = self.w3.to_checksum_address(token_in)
            token_out = self.w3.to_checksum_address(token_out)

            # Verify and update approval if needed
            if not self.approve_tokens(token_in, amount_in):
                add_dashboard_log('ERROR', "Failed to approve tokens for swap")
                return None

            # Use known working fee tier
            fee = 3000  # 0.3% fee tier
            
            # Verify pool exists
            pool_address = self.get_pool(token_in, token_out, fee)
            if not pool_address:
                add_dashboard_log('ERROR', f"Pool does not exist for token pair with {fee/10000}% fee")
                raise Exception(f"Pool does not exist for token pair with {fee/10000}% fee")
            add_dashboard_log('INFO', f"Found pool at address: {pool_address}")

            # Get current block for deadline
            current_block = self.w3.eth.get_block('latest')
            deadline = current_block.timestamp + 1200  # 20 minutes
            add_dashboard_log('DEBUG', f"Setting deadline to: {deadline} (current: {current_block.timestamp})")

            # Create the exact input single params
            swap_params = {
                'tokenIn': token_in,
                'tokenOut': token_out,
                'fee': fee,
                'recipient': self.wallet_address,
                'deadline': deadline,
                'amountIn': amount_in,
                'amountOutMinimum': 0,  # We'll set this after getting a quote
                'sqrtPriceLimitX96': 0
            }

            # First get a quote for the swap
            try:
                add_dashboard_log('DEBUG', "Getting swap quote")
                quote = self.router.functions.exactInputSingle(swap_params).call({
                    'from': self.wallet_address,
                    'chainId': Chain_ID
                })
                add_dashboard_log('INFO', f"Quoted output amount: {quote}")
                
                # Calculate minimum output with slippage tolerance
                min_amount_out = int(quote * (1 - slippage_tolerance))
                add_dashboard_log('DEBUG', f"Amount in: {amount_in}, Min amount out: {min_amount_out}")
                
                # Update the swap params with the calculated minimum output
                swap_params['amountOutMinimum'] = min_amount_out
            except Exception as e:
                add_dashboard_log('ERROR', f"Error getting quote: {str(e)}", exc_info=True)
                # If quote fails, use a conservative minimum output
                min_amount_out = int(amount_in * 0.1)  # Expect at least 10% of input value
                swap_params['amountOutMinimum'] = min_amount_out
                add_dashboard_log('WARNING', f"Using fallback min amount out: {min_amount_out}")

            # Estimate gas
            try:
                add_dashboard_log('DEBUG', "Estimating gas for swap")
                estimated_gas = self.router.functions.exactInputSingle(swap_params).estimate_gas({
                    'from': self.wallet_address,
                    'chainId': Chain_ID
                })
                add_dashboard_log('INFO', f"Estimated gas: {estimated_gas}")
                gas_limit = int(estimated_gas * 1.5)  # Add 50% buffer
            except Exception as e:
                add_dashboard_log('ERROR', f"Gas estimation failed: {str(e)}", exc_info=True)
                return None

            # Get current gas price with buffer
            gas_price = int(self.w3.eth.gas_price * 1.1)  # Add 10% to gas price
            add_dashboard_log('INFO', f"Current gas price: {gas_price}")

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)
            tx_params = {
                'from': self.wallet_address,
                'gas': gas_limit,
                'gasPrice': gas_price,
                'nonce': nonce,
                'chainId': Chain_ID
            }

            add_dashboard_log('INFO', "Building swap transaction...")
            swap_txn = self.router.functions.exactInputSingle(swap_params).build_transaction(tx_params)

            add_dashboard_log('INFO', "Signing transaction...")
            signed_txn = self.w3.eth.account.sign_transaction(swap_txn, self.private_key)
            
            add_dashboard_log('INFO', "Sending transaction...")
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            add_dashboard_log('INFO', f"Transaction sent: {tx_hash.hex()}")
            add_dashboard_log('INFO', "Waiting for transaction confirmation...")
            
            # Wait for transaction receipt with timeout
            try:
                receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)  # 3 minutes timeout
                add_dashboard_log('INFO', f"Transaction status: {'Success' if receipt['status'] == 1 else 'Failed'}")
                add_dashboard_log('INFO', f"Gas used: {receipt['gasUsed']}")
                
                if receipt['status'] == 1:
                    # Prepare trade details for logging
                    trade_details = {
                        'wallet_id': self.wallet_id,
                        'wallet_name': self.wallet_name,
                        'direction': 'buy' if token_in == quote_token else 'sell',
                        'token_in': token_in,
                        'token_out': token_out,
                        'amount_in': amount_in,
                        'amount_out': quote,
                        'tx_hash': tx_hash.hex(),
                        'gas_used': receipt['gasUsed'],
                        'gas_price': receipt['effectiveGasPrice'],
                        'success': True
                    }
                    
                    # Log to CSV
                    self.csv_logger.log_trade(trade_details)
                    
                    # Send Slack notification
                    self.slack_notifier.send_trade_notification(trade_details)
                    
                    return {
                        'success': True,
                        'tx_hash': tx_hash.hex(),
                        'gas_used': receipt['gasUsed'],
                        'effective_gas_price': receipt['effectiveGasPrice']
                    }
                else:
                    # Prepare trade details for failed trade
                    trade_details = {
                        'wallet_id': self.wallet_id,
                        'wallet_name': self.wallet_name,
                        'direction': 'buy' if token_in == quote_token else 'sell',
                        'token_in': token_in,
                        'token_out': token_out,
                        'amount_in': amount_in,
                        'amount_out': 0,
                        'tx_hash': tx_hash.hex(),
                        'gas_used': receipt['gasUsed'],
                        'gas_price': receipt['effectiveGasPrice'],
                        'success': False,
                        'error': 'Transaction failed'
                    }
                    
                    # Log to CSV
                    self.csv_logger.log_trade(trade_details)
                    
                    # Send Slack notification
                    self.slack_notifier.send_trade_notification(trade_details)
                    
                    # Get transaction to check failure reason
                    tx = self.w3.eth.get_transaction(tx_hash)
                    try:
                        # Try to replay the failed transaction to get more info
                        self.w3.eth.call({
                            'from': tx['from'],
                            'to': tx['to'],
                            'data': tx['input'],
                            'value': tx['value'],
                            'gas': tx['gas'],
                            'gasPrice': tx['gasPrice'],
                            'nonce': tx['nonce']
                        }, receipt.blockNumber - 1)
                    except Exception as e:
                        add_dashboard_log('ERROR', f"Transaction failed with reason: {str(e)}")
                    return None
                    
            except Exception as e:
                # Prepare trade details for failed trade
                trade_details = {
                    'wallet_id': self.wallet_id,
                    'wallet_name': self.wallet_name,
                    'direction': 'buy' if token_in == quote_token else 'sell',
                    'token_in': token_in,
                    'token_out': token_out,
                    'amount_in': amount_in,
                    'amount_out': 0,
                    'tx_hash': tx_hash.hex(),
                    'gas_used': 0,
                    'gas_price': gas_price,
                    'success': False,
                    'error': str(e)
                }
                
                # Log to CSV
                self.csv_logger.log_trade(trade_details)
                
                # Send Slack notification
                self.slack_notifier.send_trade_notification(trade_details)
                
                add_dashboard_log('ERROR', f"Error waiting for transaction: {str(e)}", exc_info=True)
                return None

        except Exception as e:
            # Prepare trade details for failed trade
            trade_details = {
                'wallet_id': self.wallet_id,
                'wallet_name': self.wallet_name,
                'direction': 'buy' if token_in == quote_token else 'sell',
                'token_in': token_in,
                'token_out': token_out,
                'amount_in': amount_in,
                'amount_out': 0,
                'tx_hash': '',
                'gas_used': 0,
                'gas_price': 0,
                'success': False,
                'error': str(e)
            }
            
            # Log to CSV
            self.csv_logger.log_trade(trade_details)
            
            # Send Slack notification
            self.slack_notifier.send_trade_notification(trade_details)
            
            add_dashboard_log('ERROR', f"Error executing swap: {str(e)}", exc_info=True)
            if hasattr(e, 'args') and len(e.args) > 0:
                add_dashboard_log('ERROR', f"Detailed error: {e.args[0]}")
            return None

    def transfer_token(self, token_address: str, to_address: str, amount: int) -> Optional[dict]:
        """
        Direct token transfer without using Uniswap pools
        :param token_address: The token contract address
        :param to_address: Recipient address
        :param amount: Amount to transfer (in token's smallest unit)
        :return: Transaction details if successful, None if failed
        """
        if not self.wallet_address or not self.private_key:
            raise Exception("Wallet address and private key required for transfer")

        try:
            # Create token contract instance
            token_contract = self.w3.eth.contract(
                address=token_address,
                abi=ERC20_ABI
            )

            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)

            # Build transfer transaction
            transfer_txn = token_contract.functions.transfer(
                to_address,
                amount
            ).build_transaction({
                'from': self.wallet_address,
                'gas': 100000,  # Lower gas limit for simple transfers
                'gasPrice': self.w3.eth.gas_price,
                'nonce': nonce,
                'chainId': Chain_ID  # Optimism chain ID
            })

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transfer_txn, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if tx_receipt.status == 1:
                return {
                    'success': True,
                    'amount': amount,
                    'tx_hash': tx_hash.hex(),
                    'from': self.wallet_address,
                    'to': to_address
                }
            else:
                raise Exception("Transfer transaction failed")

        except Exception as e:
            add_dashboard_log('ERROR', f"Error executing transfer: {e}")
            return None

    def transfer_eth(self, to_address: str, amount_wei: int) -> Optional[dict]:
        """
        Direct ETH transfer
        :param to_address: Recipient address
        :param amount_wei: Amount in Wei to send
        :return: Transaction details if successful, None if failed
        """
        if not self.wallet_address or not self.private_key:
            raise Exception("Wallet address and private key required for transfer")

        try:
            # Get nonce
            nonce = self.w3.eth.get_transaction_count(self.wallet_address)

            # Build transaction
            transaction = {
                'nonce': nonce,
                'to': to_address,
                'value': amount_wei,
                'gas': 21000,  # Standard ETH transfer gas limit
                'gasPrice': self.w3.eth.gas_price,
                'chainId': Chain_ID  # Optimism chain ID
            }

            # Sign and send transaction
            signed_txn = self.w3.eth.account.sign_transaction(transaction, self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash)

            if tx_receipt.status == 1:
                return {
                    'success': True,
                    'amount_wei': amount_wei,
                    'tx_hash': tx_hash.hex(),
                    'from': self.wallet_address,
                    'to': to_address
                }
            else:
                raise Exception("ETH transfer failed")

        except Exception as e:
            add_dashboard_log('ERROR', f"Error sending ETH: {e}")
            return None

   
       