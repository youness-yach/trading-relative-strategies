import streamlit as st
import asyncio
import time
import json
import pandas as pd
import uuid
import io
import sys
from datetime import datetime, timedelta
from typing import Dict, List
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from streamlit_autorefresh import st_autorefresh
import threading

# Import existing modules
from dotenv import load_dotenv
from w3 import UniswapV3
from twap import TWAPExecutor, TradeDirection
from configs.wallets_config import *
from configs.trade_config import *
from configs.logger_config import setup_logger
from dashboard_logger import add_dashboard_log, dashboard_log_handler

# Load environment variables
load_dotenv()

logger = setup_logger('streamlit_dashboard')

# Global execution lock to prevent multiple executions
_execution_lock = False
_current_execution_id = None

# Page configuration
st.set_page_config(
    page_title="DeFi TWAP Bot Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Global state management using Streamlit session state
if 'bot_running' not in st.session_state:
    st.session_state.bot_running = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'end_time' not in st.session_state:
    st.session_state.end_time = None
if 'wallet_status' not in st.session_state:
    st.session_state.wallet_status = {}
if 'trade_history' not in st.session_state:
    st.session_state.trade_history = []
if 'execution_results' not in st.session_state:
    st.session_state.execution_results = {}
if 'current_config' not in st.session_state:
    st.session_state.current_config = {}
if 'execution_complete' not in st.session_state:
    st.session_state.execution_complete = False
if 'duration_hours' not in st.session_state:
    st.session_state.duration_hours = 1.0  # or your default value
if 'interval_minutes' not in st.session_state:
    st.session_state.interval_minutes = 10.0  # or your default value

def get_default_config():
    """Get default trade configuration"""
    return {
        'base_token': base_token,
        'quote_token': quote_token,
        'total_quantity': total_quantity,
        'duration_hours': duration_hours,
        'interval_minutes': interval_minutes,
        'min_quantity_per_trade': min_quantity_per_trade,
        'max_quantity_per_trade': max_quantity_per_trade,
        'trade_direction': trade_direction.value,  # Use the enum value, not the enum itself
        'trade_delay': trade_delay,
        'network': Network,
        'factory_address': Factory_address,
        'position_manager_address': Position_manager_address
    }

def get_token_list():
    """Get list of common tokens for selection"""
    return {
        'Optimism (OP)': '0x4200000000000000000000000000000000000042',
        'Wrapped Ether (WETH)': '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2',
        'USDT (OP)': '0x94b008aA00579c1307B0EF2c499aD98a8ce58e58',
        'Custom Token': 'custom'
    }

def get_checksum_address_safe(address):
    """Safely get checksum address"""
    try:
        if address and address != 'custom' and address.startswith('0x'):
            return Web3.to_checksum_address(address.lower())
        return None
    except Exception:
        return None

def get_wallet_config():
    """Get wallet configuration"""
    return {
        'wallets': WALLETS,
        'chain_id': Chain_ID,
        'slack_webhook': SLACK_WEBHOOK_URL
    }

def update_wallet_status(wallet_id: str, status_data: Dict):
    """Update wallet status in session state"""
    dashboard_log_handler.update_wallet_status(wallet_id, status_data)

def add_trade_to_history(trade_data: Dict):
    """Add trade to history in session state"""
    dashboard_log_handler.add_trade_to_history(trade_data)

async def execute_wallet_trades_streamlit(wallet_id: str, wallet_info: Dict, config: Dict):
    """Execute trades for a single wallet with Streamlit integration"""
    
    try:
        # Check if stop was requested
        if dashboard_log_handler.get_stop_requested():
            add_dashboard_log('INFO', f"Stop requested, skipping {wallet_info['name']}")
            return []

        # Update wallet status
        dashboard_log_handler.update_wallet_status(wallet_id, {
            'status': 'starting',
            'progress': 0,
            'trades_executed': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_executed': 0,
            'last_update': datetime.now().isoformat()
        })

        # Add random delay
        delay = config.get('trade_delay', 15)
        add_dashboard_log('INFO', f"Starting {wallet_info['name']} with {delay:.2f}s delay")
        
        # Break delay into smaller chunks to check stop more frequently
        for _ in range(int(delay)):
            if dashboard_log_handler.get_stop_requested():
                add_dashboard_log('INFO', f"Stop requested during delay, stopping {wallet_info['name']}")
                dashboard_log_handler.update_wallet_status(wallet_id, {
                    'status': 'stopped',
                    'progress': 0,
                    'trades_executed': 0,
                    'successful_trades': 0,
                    'failed_trades': 0,
                    'total_executed': 0,
                    'last_update': datetime.now().isoformat()
                })
                return []
            await asyncio.sleep(1)

        # Check if stop was requested during delay
        if dashboard_log_handler.get_stop_requested():
            add_dashboard_log('INFO', f"Stop requested during delay, stopping {wallet_info['name']}")
            dashboard_log_handler.update_wallet_status(wallet_id, {
                'status': 'stopped',
                'progress': 0,
                'trades_executed': 0,
                'successful_trades': 0,
                'failed_trades': 0,
                'total_executed': 0,
                'last_update': datetime.now().isoformat()
            })
            return []

        # Update status
        dashboard_log_handler.update_wallet_status(wallet_id, {
            'status': 'initializing',
            'progress': 10,
            'trades_executed': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_executed': 0,
            'last_update': datetime.now().isoformat()
        })

        # Initialize Uniswap V3
        add_dashboard_log('INFO', f"Initializing UniswapV3 instance for {wallet_info['name']}")
        uniswap = UniswapV3(
            config['network'],
            wallet_info['address'],
            wallet_info['private_key'],
            config['factory_address'],
            config['position_manager_address'],
            wallet_id=wallet_id,
            wallet_name=wallet_info['name']
        )

        if not uniswap.w3.is_connected():
            add_dashboard_log('ERROR', f"Failed to connect to network for {wallet_info['name']}")
            dashboard_log_handler.update_wallet_status(wallet_id, {
                'status': 'failed',
                'error': 'Network connection failed',
                'last_update': datetime.now().isoformat()
            })
            return []

        # Get token symbols
        base_token_contract = uniswap.w3.eth.contract(address=config['base_token'], abi=[{
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function"
        }])
        quote_token_contract = uniswap.w3.eth.contract(address=config['quote_token'], abi=[{
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
            add_dashboard_log('INFO', f"Trading {base_symbol} vs {quote_symbol} for {wallet_info['name']}")
        except Exception as e:
            add_dashboard_log('WARNING', f"Could not get token symbols for {wallet_info['name']}: {e}")
            base_symbol = "BASE"
            quote_symbol = "QUOTE"

        # Create TWAP executor
        # Convert string trade direction to enum
        trade_direction_enum = TradeDirection.BUY if config['trade_direction'].upper() == 'BUY' else TradeDirection.SELL
        
        twap = TWAPExecutor(
            uniswap=uniswap,
            base_token=config['base_token'],
            quote_token=config['quote_token'],
            total_quantity=config['total_quantity'],
            duration_hours=config['duration_hours'],
            interval_minutes=config['interval_minutes'],
            min_quantity_per_trade=config['min_quantity_per_trade'],
            max_quantity_per_trade=config['max_quantity_per_trade'],
            trade_direction=trade_direction_enum,
            wallet_id=wallet_id,
            wallet_name=wallet_info['name']
        )

        # Update status
        dashboard_log_handler.update_wallet_status(wallet_id, {
            'status': 'executing',
            'progress': 30,
            'trades_executed': 0,
            'successful_trades': 0,
            'failed_trades': 0,
            'total_executed': 0,
            'last_update': datetime.now().isoformat()
        })

        # Execute TWAP strategy
        add_dashboard_log('INFO', f"Starting TWAP execution for {wallet_info['name']}")
        results = await twap.execute_twap_async()

        # Check if stop was requested during execution
        if dashboard_log_handler.get_stop_requested():
            add_dashboard_log('INFO', f"Stop requested during execution, stopping {wallet_info['name']}")
            dashboard_log_handler.update_wallet_status(wallet_id, {
                'status': 'stopped',
                'progress': 50,
                'trades_executed': len(results),
                'successful_trades': len([r for r in results if r['success']]),
                'failed_trades': len([r for r in results if not r['success']]),
                'total_executed': sum(r['quantity'] for r in results if r['success']),
                'last_update': datetime.now().isoformat()
            })
            return results

        # Process results
        successful_trades = [trade for trade in results if trade['success']]
        failed_trades = [trade for trade in results if not trade['success']]
        total_executed = sum(trade['quantity'] for trade in successful_trades)

        add_dashboard_log('INFO', f"{wallet_info['name']} completed: {len(successful_trades)} successful, {len(failed_trades)} failed trades")

        # Update wallet status
        dashboard_log_handler.update_wallet_status(wallet_id, {
            'status': 'completed',
            'progress': 100,
            'trades_executed': len(results),
            'successful_trades': len(successful_trades),
            'failed_trades': len(failed_trades),
            'total_executed': total_executed,
            'last_update': datetime.now().isoformat()
        })

        # Trade history is now added live during execution in twap.py
        # No need to add duplicate entries here

        return results

    except Exception as e:
        add_dashboard_log('ERROR', f"Error executing trades for {wallet_info['name']}: {str(e)}")
        dashboard_log_handler.update_wallet_status(wallet_id, {
            'status': 'failed',
            'error': str(e),
            'last_update': datetime.now().isoformat()
        })
        return []

async def run_bot_execution(config: Dict):
    """Run the bot execution with the given configuration"""
    global _execution_lock, _current_execution_id
    
    if _execution_lock:
        add_dashboard_log('WARNING', "Bot execution already in progress")
        return
    
    execution_id = str(uuid.uuid4())
    _execution_lock = True
    _current_execution_id = execution_id
    add_dashboard_log('INFO', f"Starting new execution with ID: {execution_id}")
    
    try:
        st.session_state.start_time = datetime.now()
        st.session_state.end_time = st.session_state.start_time + timedelta(hours=config['duration_hours'])
        st.session_state.current_config = config
        st.session_state.execution_results = {}
        st.session_state.execution_complete = False
        
        # Track configured wallets

        # Create tasks for each wallet
        tasks = []
        configured_wallets = []
        for wallet_id, wallet_info in WALLETS.items():
            if wallet_info['address'] and wallet_info['private_key'] != 'your_private_key':
                if dashboard_log_handler.get_stop_requested():
                    break
                add_dashboard_log('INFO', f"Creating task for wallet: {wallet_info['name']}")
                task = asyncio.create_task(execute_wallet_trades_streamlit(wallet_id, wallet_info, config))
                tasks.append(task)
                configured_wallets.append(wallet_id)

        if not tasks:
            add_dashboard_log('ERROR', "No configured wallets found!")
            return

        # Execute all wallet tasks concurrently
        add_dashboard_log('INFO', "Starting concurrent execution of all wallets")
        results = await asyncio.gather(*tasks)

        # Process results
        all_results = dict(zip(configured_wallets, results))
        st.session_state.execution_results = all_results
        st.session_state.execution_complete = True
        
        if dashboard_log_handler.get_stop_requested():
            add_dashboard_log('INFO', f"Execution stopped by user: {execution_id}")
        else:
            add_dashboard_log('INFO', f"Execution completed successfully: {execution_id}")

    except Exception as e:
        add_dashboard_log('ERROR', f"Error in bot execution: {str(e)}")
        st.session_state.bot_running = False
    finally:
        _execution_lock = False
        _current_execution_id = None
        st.session_state.bot_running = False
        add_dashboard_log('INFO', f"Execution finished: {execution_id}")

def start_bot(config: Dict):
    """Start the bot"""
    
    if not st.session_state.bot_running:
        # Check if wallets are properly configured
        configured_wallets = []
        for wallet_id, wallet_info in WALLETS.items():
            if wallet_info['address'] and wallet_info['private_key'] != 'your_private_key':
                configured_wallets.append(wallet_info['name'])
        
        if not configured_wallets:
            add_dashboard_log('ERROR', "No wallets configured! Please set up wallet addresses and private keys.")
            return False
        
        st.session_state.bot_running = True
        dashboard_log_handler.clear_stop()
        add_dashboard_log('INFO', "Bot started successfully")
        return True
    return False

def stop_bot():
    """Stop the bot"""
    
    if st.session_state.bot_running:
        st.session_state.bot_running = False
        dashboard_log_handler.request_stop()
        add_dashboard_log('INFO', "Stop requested by user")
        return True
    return False

def create_progress_chart():
    """Create a progress chart for all wallets"""
    wallet_status = dashboard_log_handler.get_wallet_status()
    if not wallet_status:
        return None
    
    fig = go.Figure()
    
    # Add individual wallet progress only
    for wallet_id, status in wallet_status.items():
        if wallet_id in WALLETS:
            wallet_name = WALLETS[wallet_id]['name']
            progress = status.get('progress', 0)
            trades_executed = status.get('trades_executed', 0)
            successful_trades = status.get('successful_trades', 0)
            
            fig.add_trace(go.Bar(
                name=wallet_name,
                x=[wallet_name],
                y=[progress],
                text=f"{progress:.1f}%<br>({successful_trades}/{trades_executed})",
                textposition='auto',
            ))
    
    fig.update_layout(
        title="Wallet Progress",
        xaxis_title="Wallets",
        yaxis_title="Progress (%)",
        height=400,
        showlegend=False,
        yaxis=dict(range=[0, 100])
    )
    
    return fig

def create_trade_history_chart():
    """Create a trade history chart"""
    trade_history = dashboard_log_handler.get_trade_history()
    if not trade_history:
        return None
    
    df = pd.DataFrame(trade_history)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Group by time and count trades
    df_grouped = df.groupby(df['timestamp'].dt.floor('1min')).size().reset_index(name='trades')
    
    fig = px.line(df_grouped, x='timestamp', y='trades', title='Trades Over Time')
    fig.update_layout(height=400)
    
    return fig

def display_live_logs():
    """Display live logs in the dashboard"""
    logs = dashboard_log_handler.get_logs()
    
    if not logs:
        st.info("No logs available yet")
        return
    
    # Create a container for logs
    log_container = st.container()
    
    with log_container:
        st.subheader("📋 Live Execution Logs")
        
        # Add a refresh button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh Logs", key="refresh_logs"):
                st.rerun()
        with col2:
            if st.button("🗑️ Clear Logs", key="clear_logs"):
                dashboard_log_handler.clear_logs()
                st.rerun()
        
        # Display logs in a scrollable area
        log_text = ""
        for log in logs[-50:]:  # Show last 50 logs
            # Color code based on log level
            if log['level'] == 'ERROR':
                log_text += f"🔴 **{log['timestamp']} ERROR:** {log['message']}\n"
            elif log['level'] == 'WARNING':
                log_text += f"🟡 **{log['timestamp']} WARNING:** {log['message']}\n"
            elif log['level'] == 'INFO':
                log_text += f"🔵 **{log['timestamp']} INFO:** {log['message']}\n"
            else:
                log_text += f"⚪ **{log['timestamp']} {log['level']}:** {log['message']}\n"
        
        # Display in a scrollable text area
        st.text_area(
            "Execution Logs",
            value=log_text,
            height=300,
            disabled=True,
            key="live_logs_display"
        )
        
        # Show log count
        st.caption(f"Showing {len(logs)} most recent logs")

def add_dashboard_log(level: str, message: str):
    """Add a log entry to the dashboard log handler"""
    dashboard_log_handler.add_log(level, message)
    # Also log to the regular logger
    if level == 'ERROR':
        logger.error(message)
    elif level == 'WARNING':
        logger.warning(message)
    else:
        logger.info(message)

def main():
    trade_history = dashboard_log_handler.get_trade_history()
    wallet_status = dashboard_log_handler.get_wallet_status()
    st.title("DeFi TWAP Bot Dashboard")
    st.markdown("---")

    # Add initial log if this is the first run
    if 'dashboard_initialized' not in st.session_state:
        st.session_state.dashboard_initialized = True
        add_dashboard_log('INFO', "Dashboard initialized and ready")
        add_dashboard_log('INFO', f"Network: Optimism Mainnet (Chain ID: {Chain_ID})")
        add_dashboard_log('INFO', "Select your tokens in the sidebar to start trading")

    # Sidebar for configuration
    with st.sidebar:
        st.header("Configuration")
        
        # Load default config
        default_config = get_default_config()
        token_list = get_token_list()
        
        # Token Configuration
        st.subheader("Token Settings")
        
        # Base Token Selection
        st.write("**Base Token (Token you're buying/selling):**")
        base_token_options = list(token_list.keys())
        base_token_selection = st.selectbox(
            "Select Base Token",
            base_token_options,
            index=0,  # Default to OP
            key="base_token_select"
        )
        
        # Custom base token address input
        if base_token_selection == 'Custom Token':
            base_token_address = st.text_input(
                "Base Token Address",
                value="0x...",
                help="Enter the contract address of your base token"
            )
            base_token_final = get_checksum_address_safe(base_token_address)
        else:
            base_token_final = token_list[base_token_selection]
        
        # Quote Token Selection
        st.write("**Quote Token (Token you're trading with):**")
        quote_token_options = list(token_list.keys())
        quote_token_selection = st.selectbox(
            "Select Quote Token",
            quote_token_options,
            index=2,  # Default to USDT
            key="quote_token_select"
        )
        
        # Custom quote token address input
        if quote_token_selection == 'Custom Token':
            quote_token_address = st.text_input(
                "Quote Token Address",
                value="0x...",
                help="Enter the contract address of your quote token"
            )
            quote_token_final = get_checksum_address_safe(quote_token_address)
        else:
            quote_token_final = token_list[quote_token_selection]
        
        # Show selected tokens
        if base_token_final and quote_token_final:
            st.success(f"✅ Trading: {base_token_selection} vs {quote_token_selection}")
            st.caption(f"Base: {base_token_final[:10]}...")
            st.caption(f"Quote: {quote_token_final[:10]}...")
        else:
            st.error("❌ Please select valid token addresses")
        
        # Trade Configuration
        st.subheader("Trade Settings")
        total_quantity = st.number_input(
            "Total Quantity", 
            value=float(default_config['total_quantity']), 
            step=0.00001,
            format="%.5f",
            help="Total amount to trade"
        )
        
        duration_hours = st.number_input(
            "Duration (hours)", 
            value=float(default_config['duration_hours']), 
            step=0.1,
            help="Total duration for TWAP execution"
        )
        st.session_state.duration_hours = duration_hours
        
        interval_minutes = st.number_input(
            "Interval (minutes)", 
            value=float(default_config['interval_minutes']), 
            step=0.1,
            help="Time between trades"
        )
        st.session_state.interval_minutes = interval_minutes
        
        min_quantity = st.number_input(
            "Min Quantity per Trade", 
            value=float(default_config['min_quantity_per_trade']), 
            step=0.00001,
            format="%.5f",
            help="Minimum quantity per individual trade"
        )
        
        max_quantity = st.number_input(
            "Max Quantity per Trade", 
            value=float(default_config['max_quantity_per_trade']), 
            step=0.00001,
            format="%.5f",
            help="Maximum quantity per individual trade"
        )
        
        trade_direction = st.selectbox(
            "Trade Direction",
            ["BUY", "SELL"],
            index=0 if default_config['trade_direction'].upper() == "BUY" else 1,
            help="Direction of trades"
        )
        
        trade_delay = st.number_input(
            "Trade Delay (seconds)", 
            value=float(default_config['trade_delay']), 
            step=1.0,
            help="Delay between wallet starts"
        )
        
        # Network Configuration
        st.subheader("Network Settings")
        network_url = st.text_input(
            "Network URL", 
            value=default_config['network'],
            help="Ethereum network RPC URL"
        )
        
        # Wallet Configuration
        st.subheader("Wallets")
        wallet_config = get_wallet_config()
        
        configured_count = 0
        for wallet_id, wallet_info in wallet_config['wallets'].items():
            if wallet_info['address'] and wallet_info['private_key'] != 'your_private_key':
                st.success(f" {wallet_info['name']}: {wallet_info['address'][:10]}...")
                configured_count += 1
            else:
                st.warning(f"⚠️ {wallet_info['name']}: Not configured")
        
        if configured_count == 0:
            st.error("No wallets configured!")
            st.info("To configure wallets, set these environment variables:")
            st.code("""
WALLET1_ADDRESS=your_ethereum_address
WALLET1_PRIVATE_KEY=your_private_key
WALLET2_ADDRESS=your_ethereum_address
WALLET2_PRIVATE_KEY=your_private_key
WALLET3_ADDRESS=your_ethereum_address
WALLET3_PRIVATE_KEY=your_private_key
            """)
        else:
            st.success(f" {configured_count} wallet(s) configured")
        
        # Create config dictionary
        config = {
            'base_token': base_token_final,
            'quote_token': quote_token_final,
            'total_quantity': total_quantity,
            'duration_hours': duration_hours,
            'interval_minutes': interval_minutes,
            'min_quantity_per_trade': min_quantity,
            'max_quantity_per_trade': max_quantity,
            'trade_direction': trade_direction,
            'trade_delay': trade_delay,
            'network': network_url,
            'factory_address': default_config['factory_address'],
            'position_manager_address': default_config['position_manager_address']
        }

    # Main content area
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🎮 Bot Controls")
        
        # Check wallet configuration
        configured_wallets = []
        for wallet_id, wallet_info in WALLETS.items():
            if wallet_info['address'] and wallet_info['private_key'] != 'your_private_key':
                configured_wallets.append(wallet_info['name'])
        
        # Bot control buttons
        if not st.session_state.bot_running:
            if len(configured_wallets) > 0:
                # Check if tokens are valid
                if not base_token_final or not quote_token_final:
                    st.button("Start Bot", type="primary", use_container_width=True, disabled=True)
                    st.error(" Please select valid token addresses")
                elif base_token_final == quote_token_final:
                    st.button("Start Bot", type="primary", use_container_width=True, disabled=True)
                    st.error(" Base and Quote tokens cannot be the same")
                else:
                    if st.button("Start Bot", type="primary", use_container_width=True):
                        st.session_state.bot_running = True
                        st.session_state.execution_complete = False
                        dashboard_log_handler.clear_logs()
                        add_dashboard_log('INFO', "Starting new bot execution")
                        base_token_name = base_token_selection if 'base_token_selection' in locals() else "Custom"
                        quote_token_name = quote_token_selection if 'quote_token_selection' in locals() else "Custom"
                        add_dashboard_log('INFO', f"Trading: {base_token_name} vs {quote_token_name}")
                        add_dashboard_log('INFO', f"Direction: {trade_direction}")
                        add_dashboard_log('INFO', f"Total Quantity: {total_quantity}")
                        # Start the bot in a background thread
                        def run():
                            import asyncio
                            asyncio.run(run_bot_execution(config))
                        bot_thread = threading.Thread(target=run, daemon=True)
                        bot_thread.start()
                        st.session_state.bot_thread = bot_thread
                        st.rerun()
            else:
                st.button("Start Bot", type="primary", use_container_width=True, disabled=True)
                st.warning(" Configure at least one wallet to start the bot")
        else:
            if st.button("Stop Bot", type="secondary", use_container_width=True):
                st.session_state.bot_running = False
                dashboard_log_handler.request_stop()
                add_dashboard_log('INFO', "Stop requested by user - Bot stopping...")
                st.success("Bot stop requested! Stopping execution...")
                st.rerun()
        
        # Show execution status
        if st.session_state.bot_running and not st.session_state.execution_complete:
            st_autorefresh(interval=2000, key="autorefresh")
            st.info("🔄 Bot is currently executing trades...")

    # Display live logs right after bot controls
    display_live_logs()


    # Wallet Status Section
    st.subheader("Wallet Status")
    
    if wallet_status:
        trade_history = dashboard_log_handler.get_trade_history()
        wallet_status = dashboard_log_handler.get_wallet_status()
        
        wallet_cols = st.columns(len(WALLETS))
        
        for i, (wallet_id, wallet_info) in enumerate(WALLETS.items()):
            with wallet_cols[i]:
                status = wallet_status.get(wallet_id, {})
                status_text = status.get('status', 'unknown')
                
                # Status color mapping
                status_colors = {
                    'starting': '🟡',
                    'initializing': '🟡',
                    'executing': '🟢',
                    'completed': '✅',
                    'stopped': '⏹️',
                    'failed': '❌'
                }
                
                st.metric(
                    wallet_info['name'],
                    f"{status_colors.get(status_text, '⚪')} {status_text.title()}"
                )
                
                if 'progress' in status:
                    st.progress(status['progress'] / 100)
                    st.text(f"Progress: {status['progress']:.1f}%")
                
                if 'trades_executed' in status:
                    st.text(f"Trades: {status['trades_executed']}")
                    st.text(f"Success: {status['successful_trades']}")
                    st.text(f"Failed: {status['failed_trades']}")
                
                if 'total_executed' in status:
                    st.text(f"Total: {status['total_executed']:.4f}")
    else:
        st.info("No wallet status available yet")

    # Charts Section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Progress Chart")
        progress_fig = create_progress_chart()
        if progress_fig:
            st.plotly_chart(progress_fig, use_container_width=True)
        else:
            st.info("No progress data available yet")
    
    with col2:
        st.subheader("Trade History")
        trade_fig = create_trade_history_chart()
        if trade_fig:
            st.plotly_chart(trade_fig, use_container_width=True)
        else:
            st.info("No trade history available yet")
    
    # Trade History Table
    st.subheader("Recent Trades")
    
    if trade_history:
        # Convert to DataFrame for better display
        df = pd.DataFrame(trade_history[-20:])  # Last 20 trades
        
        if not df.empty:
            # Format the DataFrame
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%H:%M:%S')
            df['success'] = df['success'].map({True: '✅', False: '❌'})
            df['quantity'] = df['quantity'].round(4)
            
            # Select columns to display
            display_df = df[['timestamp', 'wallet_name', 'quantity', 'direction', 'success']]
            display_df.columns = ['Time', 'Wallet', 'Quantity', 'Direction', 'Status']
            
            st.dataframe(display_df, use_container_width=True)
        else:
            st.info("No trades executed yet")
    else:
        st.info("No trade history available")

if __name__ == "__main__":
    main() 