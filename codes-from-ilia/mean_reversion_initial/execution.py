import MetaTrader5 as mt5
from datetime import datetime
import logging
import pandas as pd
import numpy as np
import time

class MT5Execution:
    def __init__(self, log_level=logging.INFO, capital=100000, symbols=None):
        """
        Initialize MT5 execution class.
        
        Args:
            log_level: Logging level
            capital: Total portfolio capital
            symbols: List of trading symbols
        """
        # Initialize MT5 connection
        if not mt5.initialize():
            raise Exception("MT5 initialization failed")
            
        # Setup logging
        self.logger = self._setup_logger(log_level)
        self.logger.info("MT5 execution initialized successfully")
        
        # Track current positions for each symbol
        self.current_positions = {}
        
        # Portfolio parameters
        self.capital = capital
        self.symbols = symbols if symbols is not None else []
        self.n_assets = len(self.symbols) if self.symbols else 1
        self.logger.info(f"Trading {self.n_assets} assets: {', '.join(self.symbols) if self.symbols else 'None specified'}")
        
        # Initialize position tracking for each symbol
        for symbol in self.symbols:
            self.current_positions[symbol] = 0
            self.logger.info(f"Initialized position tracking for {symbol}")
            
        # Sync with actual MT5 positions
        self.sync_positions()

    def _setup_logger(self, log_level):
        """Setup logging configuration."""
        logger = logging.getLogger("MT5Execution")
        logger.setLevel(log_level)
        
        # Create handlers
        file_handler = logging.FileHandler(
            f"logs/mt5_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        console_handler = logging.StreamHandler()
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Set formatter for handlers
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger

    def calculate_position_size(self, symbol, volatility):
        """
        Calculate position size based on volatility scaling.
        
        Args:
            symbol (str): Trading symbol
            volatility (float): Rolling standard deviation of log returns
            
        Returns:
            float: Position size in lots
        """
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get price for {symbol}")
            return 0.0
            
        price = (tick.ask + tick.bid) / 2
        
        # Get symbol information
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Failed to get symbol info for {symbol}")
            return 0.0
            
        # Get account information
        account_info = mt5.account_info()
        if account_info is None:
            self.logger.error("Failed to get account information")
            return 0.0
            
        # Risk 1% of account equity per trade
        risk_amount = account_info.equity * 0.01
          
        # Calculate position size using the formula: Risk/(N * σ * P)
        # But limit it to reasonable bounds
        lot_size = risk_amount / (self.n_assets * volatility * price)
        contract_size = symbol_info.trade_contract_size
        # Convert to lots (standard lot is 100000 units)
        lot_size = lot_size / contract_size
        
        # Apply minimum and maximum lot size constraints
        min_lot = symbol_info.volume_min
        max_lot = min(symbol_info.volume_max, 400.0)  # Cap at 10 lots for safety
        
        lot_size = max(min(lot_size, max_lot), min_lot)
        
        # Round to the number of decimal places allowed by the broker
        lot_step = symbol_info.volume_step
        lot_size = round(lot_size / lot_step) * lot_step
        self.logger.info(f"Position size calculation for {symbol}:")
        self.logger.info(f"Account equity: {account_info.equity}")
        self.logger.info(f"Risk amount: {risk_amount}")
        self.logger.info(f"Volatility: {volatility}")
        self.logger.info(f"Price: {price}")
        self.logger.info(f"Min lot: {min_lot}, Max lot: {max_lot}, Step: {lot_step}")
        self.logger.info(f"Final lot size: {lot_size}")
        
        return lot_size

    def sync_positions(self):
        """Sync current positions with actual MT5 positions."""
        # Reset all positions to 0 first
        for symbol in self.symbols:
            self.current_positions[symbol] = 0
            
        # Get actual positions from MT5
        positions = mt5.positions_get()
        if positions is None:
            self.logger.warning("No positions found in MT5")
            return
            
        # Only update positions for our trading symbols
        for pos in positions:
            if pos.symbol in self.symbols:  # Only track positions for our trading symbols
                # Convert position type to our signal format (1 for buy, -1 for sell)
                self.current_positions[pos.symbol] = 1 if pos.type == mt5.POSITION_TYPE_BUY else -1
                self.logger.info(f"Synced position for {pos.symbol}: {self.current_positions[pos.symbol]}")
            else:
                self.logger.warning(f"Ignoring position for {pos.symbol} as it's not in our trading symbols")
    def close_position(self, symbol, position_type, volume):
        """
        Close an existing position.
        
        Args:
            symbol (str): Trading symbol
            position_type (int): Current position type (1 for buy, -1 for sell)
            volume (float): Position volume
        """
        # Get all open positions
        positions = mt5.positions_get(symbol=symbol)
        if positions is None or len(positions) == 0:
            self.logger.warning(f"No positions found for {symbol}")
            return False
            
        # Get current prices
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get current prices for {symbol}")
            return False
            
        # Close all positions for this symbol
        success = True
        for pos in positions:
            # Determine the order type to close the position
            if pos.type == mt5.POSITION_TYPE_BUY:
                close_type = mt5.ORDER_TYPE_SELL
                close_price = tick.bid
            else:
                close_type = mt5.ORDER_TYPE_BUY
                close_price = tick.ask
                
            close_request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": pos.volume,
                "type": close_type,
                "position": pos.ticket,  # Reference the specific position to close
                "price": close_price,
                "deviation": 20,
                "magic": 234000,
                "comment": "mean reversion close position",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            self.logger.info(f"Attempting to close position with request: {close_request}")
            result = mt5.order_send(close_request)
            
            if result.retcode != mt5.TRADE_RETCODE_DONE:
                self.logger.error(f"Failed to close position {pos.ticket}. Error code: {result.retcode}, "
                                f"Description: {mt5.last_error()}")
                success = False
            else:
                self.logger.info(f"Successfully closed position {pos.ticket} for {symbol}")
                
        # Verify positions are closed
        positions = mt5.positions_get(symbol=symbol)
        if positions is not None and len(positions) > 0:
            self.logger.error(f"Position for {symbol} was not properly closed")
            return False
            
        return success

    def execute_trade(self, symbol, signal, volatility):
        """
        Execute trade based on signal.
        
        Args:
            symbol (str): Trading symbol (e.g., "EURUSD")
            signal (int): Trading signal (1 for buy, -1 for sell)
            volatility (float): Rolling standard deviation of log returns
        """
        # Sync with actual MT5 positions before making decisions
        self.sync_positions()
        
        # Check if MT5 is still connected
        if not mt5.terminal_info().connected:
            self.logger.error("MT5 terminal is not connected. Attempting to reconnect...")
            if not mt5.initialize():
                self.logger.error("Failed to reconnect to MT5")
                return
        
        # Check if symbol is available for trading
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            self.logger.error(f"Symbol {symbol} not found")
            return
            
        if not symbol_info.visible:
            self.logger.warning(f"Symbol {symbol} is not visible. Attempting to add it...")
            if not mt5.symbol_select(symbol, True):
                self.logger.error(f"Failed to add symbol {symbol}")
                return
                
        # Check if trading is allowed for this symbol
        if not symbol_info.trade_mode == mt5.SYMBOL_TRADE_MODE_FULL:
            self.logger.error(f"Trading is not allowed for {symbol}. Trade mode: {symbol_info.trade_mode}")
            return
            
        if signal not in [-1, 1]:
            self.logger.warning(f"Invalid signal {signal}. No trade executed.")
            return
            
        # Get current position for this symbol
        current_position = self.current_positions.get(symbol, 0)
            
        # If signal matches current position, do nothing
        if signal == current_position:
            self.logger.info(f"Already in desired position ({signal}) for {symbol}")
            return
            
        # Calculate position size
        volume = self.calculate_position_size(symbol, volatility)
        if volume == 0:
            self.logger.warning("Position size calculated as 0, skipping trade")
            return
            
        # Get current market prices
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            self.logger.error(f"Failed to get current prices for {symbol}")
            return
            
        self.logger.info(f"Current prices - Bid: {tick.bid}, Ask: {tick.ask}")
            
        # Close existing position if any
        if current_position != 0:
            self.logger.info(f"Closing existing position ({current_position}) for {symbol}")
            if not self.close_position(symbol, current_position, volume):
                self.logger.error(f"Failed to close position for {symbol}, skipping new trade")
                return
            # Wait a moment and sync positions to ensure the close was processed
            time.sleep(1)
            self.sync_positions()
            
            # Verify position was closed
            if self.current_positions.get(symbol, 0) != 0:
                self.logger.error(f"Position for {symbol} was not properly closed")
                return
        
        # Open new position
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": mt5.ORDER_TYPE_BUY if signal == 1 else mt5.ORDER_TYPE_SELL,
            "price": tick.ask if signal == 1 else tick.bid,
            "deviation": 20,
            "magic": 234000,
            "comment": "mean reversion trade",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_FOK,
        }
        
        self.logger.info(f"Attempting to open position with request: {request}")
        
        # Send trade request
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_desc = mt5.last_error()
            self.logger.error(f"Trade execution failed. Error code: {result.retcode}, "
                            f"Description: {error_desc}")
            
            # Additional diagnostic information
            account_info = mt5.account_info()
            if account_info is not None:
                self.logger.info(f"Account balance: {account_info.balance}, "
                               f"Margin free: {account_info.margin_free}")
        else:
            # Wait a moment and sync positions to ensure the open was processed
            time.sleep(1)
            self.sync_positions()
            
            # Update position tracking for this symbol
            self.current_positions[symbol] = signal
            self.logger.info(f"Trade executed successfully for {symbol}. Order ticket: {result.order}, "
                           f"Volume: {volume}, Price: {result.price}")
            
            # Log the trade details
            order = mt5.orders_get(ticket=result.order)
            if order:
                self.logger.info(f"Order details - Type: {order[0].type}, "
                               f"State: {order[0].state}, "
                               f"Volume: {order[0].volume_current}")

    def __del__(self):
        """Cleanup when object is destroyed."""
        self.logger.info("Shutting down MT5 connection")
        mt5.shutdown()
