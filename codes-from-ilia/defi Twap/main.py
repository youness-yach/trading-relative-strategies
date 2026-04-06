from dotenv import load_dotenv
from w3 import UniswapV3
from twap import TWAPExecutor, TradeDirection
from configs.wallets_config import *
from configs.trade_config import *
from configs.logger_config import setup_logger
from typing import Dict, List
import asyncio
import random
import time
from dashboard_logger import add_dashboard_log

# Setup logger
logger = setup_logger('main')

async def execute_wallet_trades(wallet_id: str, wallet_info: Dict) -> List[dict]:
    """Execute trades for a single wallet"""
    try:
        # Add random delay between 0 and 30 seconds before starting
        delay = trade_delay
        add_dashboard_log('INFO', f"Starting {wallet_info['name']} with {delay:.2f}s delay")
        await asyncio.sleep(delay)
        
        add_dashboard_log('INFO', f"Initializing trading for {wallet_info['name']}")
        
        # Initialize Uniswap V3 with wallet
        uniswap = UniswapV3(
            Network,
            wallet_info['address'],
            wallet_info['private_key'],
            Factory_address,
            Position_manager_address,
            wallet_id=wallet_id,
            wallet_name=wallet_info['name']
        )
        
        if not uniswap.w3.is_connected():
            add_dashboard_log('ERROR', f"Failed to connect to network for {wallet_info['name']}")
            return []

        # Get token symbols
        base_token_contract = uniswap.w3.eth.contract(address=base_token, abi=[{
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }])
        quote_token_contract = uniswap.w3.eth.contract(address=quote_token, abi=[{
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }])

        try:
            base_symbol = base_token_contract.functions.symbol().call()
            quote_symbol = quote_token_contract.functions.symbol().call()
            add_dashboard_log('INFO', f"Token symbols for {wallet_info['name']} - Base: {base_symbol}, Quote: {quote_symbol}")
        except Exception as e:
            add_dashboard_log('WARNING', f"Could not get token symbols for {wallet_info['name']}: {e}")
            base_symbol = "BASE"
            quote_symbol = "QUOTE"

        # Create TWAP executor
        twap = TWAPExecutor(
            uniswap=uniswap,
            base_token=base_token,
            quote_token=quote_token,
            total_quantity=total_quantity,
            duration_hours=duration_hours,
            interval_minutes=interval_minutes,
            min_quantity_per_trade=min_quantity_per_trade,
            max_quantity_per_trade=max_quantity_per_trade,
            trade_direction=trade_direction,
            wallet_id=wallet_id,
            wallet_name=wallet_info['name']
        )

        # Print trade setup information
        direction_str = "Buying" if trade_direction == TradeDirection.BUY else "Selling"
        add_dashboard_log('INFO', f"TWAP Setup for {wallet_info['name']}: {direction_str} {base_symbol} for {quote_symbol}")
        add_dashboard_log('INFO', f"Total {quote_symbol} to spend: {total_quantity}")
        add_dashboard_log('INFO', f"Min {quote_symbol} per trade: {min_quantity_per_trade}")
        add_dashboard_log('INFO', f"Max {quote_symbol} per trade: {max_quantity_per_trade}")
        add_dashboard_log('INFO', f"Duration: {duration_hours} hours")
        add_dashboard_log('INFO', f"Interval: {interval_minutes} minutes")

        # Execute TWAP strategy
        add_dashboard_log('INFO', f"Starting TWAP execution for {wallet_info['name']}")
        results = await twap.execute_twap_async()

        # Print summary
        successful_trades = [trade for trade in results if trade['success']]
        failed_trades = [trade for trade in results if not trade['success']]
        
        add_dashboard_log('INFO', f"TWAP Execution Summary for {wallet_info['name']}:")
        add_dashboard_log('INFO', f"Operation: {direction_str} {base_symbol}" + 
              f" {'with' if trade_direction == TradeDirection.BUY else 'for'} {quote_symbol}")
        add_dashboard_log('INFO', f"Total trades executed: {len(results)}")
        add_dashboard_log('INFO', f"Successful trades: {len(successful_trades)}")
        add_dashboard_log('INFO', f"Failed trades: {len(failed_trades)}")
        
        total_executed = sum(trade['quantity'] for trade in successful_trades)
        if trade_direction == TradeDirection.BUY:
            add_dashboard_log('INFO', f"Total {quote_symbol} spent: {total_executed}")
        else:
            add_dashboard_log('INFO', f"Total {base_symbol} sold: {total_executed}")

        return results

    except Exception as e:
        add_dashboard_log('ERROR', f"Error executing trades for {wallet_info['name']}: {str(e)}", exc_info=True)
        return []

async def main():
    try:
        # Load environment variables
        load_dotenv()
        add_dashboard_log('INFO', "Environment variables loaded")

        # Create tasks for each wallet
        tasks = []
        for wallet_id, wallet_info in WALLETS.items():
            add_dashboard_log('INFO', f"Creating task for wallet: {wallet_info['name']}")
            task = asyncio.create_task(execute_wallet_trades(wallet_id, wallet_info))
            tasks.append(task)

        # Execute all wallet tasks concurrently
        add_dashboard_log('INFO', "Starting concurrent execution of all wallets")
        results = await asyncio.gather(*tasks)

        # Process results
        all_results = dict(zip(WALLETS.keys(), results))

        # Print overall summary
        add_dashboard_log('INFO', "\nOverall Trading Summary:")
        for wallet_id, results in all_results.items():
            wallet_name = WALLETS[wallet_id]['name']
            successful_trades = [trade for trade in results if trade['success']]
            failed_trades = [trade for trade in results if not trade['success']]
            
            add_dashboard_log('INFO', f"\n{wallet_name}:")
            add_dashboard_log('INFO', f"Total trades: {len(results)}")
            add_dashboard_log('INFO', f"Successful trades: {len(successful_trades)}")
            add_dashboard_log('INFO', f"Failed trades: {len(failed_trades)}")
            
            if successful_trades:
                total_executed = sum(trade['quantity'] for trade in successful_trades)
                add_dashboard_log('INFO', f"Total executed quantity: {total_executed}")

    except Exception as e:
        add_dashboard_log('ERROR', f"Error in main execution: {str(e)}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())

