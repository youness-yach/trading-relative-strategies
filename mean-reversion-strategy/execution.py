import MetaTrader5 as mt5
from datetime import datetime 
import logging 
import pandas as pd
import numpy as np 
import time 

class MT5Execution:
    def __init__(self, log_level=logging.INFO, capital=10000, symbol=None): #defines the constructor with parameters for logging, capital, symbols
        #Initialize MT5 execution class
        #Args
        #log_level: logging level
        #capital: total portfolio capital
        #symbol: list of trading symbols
        if not mt5.initialize(): #attempts to connect 
            raise Exception("MT5 initialization failed")
        self.logger = self.setup_logger(log_level) #sets up logger
        self.logger.info(f"MT5 execution initialzed successfully") #logs successful initialization MT5
        self.capital = capital #stores the capital
        self.symbols = symbol if symbol is not None else [] #stores the symbols' list and default to empty list
        self.n_assets = len(self.symbols) if self.symbols else 1 #number of assets to default 1 if no symbols
        self.logger.info(f"Trading {self.n_assets} assets: {",".join(self.symbols) if self.symbols else "None specified"}") #logs the number and list of assets
        for symbol in self.symbols: #itirates over the symbols list
            self.current_position[symbol] = 0 #initializes current position for each symbol to 0
            self.logger.info(f"Intialized position tracking for {symbol}") #logs the initialization of position tracking for each symbol
            self.sync_positions() #syncs the positions to align with actual MT5 positions
    
    def _setup_logger(self, log_level): #private method to configure logging
        #set up logging configuration
        logger = logging.getLogger("MT5Execution") #creates a logger instance named MT5Execution
        logger.setLevel(log_level) #sets the logging level
        file_handler = logging.FileHandler(
            f"logs/mt5_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ) #creates a file handler to write logs to a file with a timestamped filename
        console_handler = logging.StreamHandler() #creates a console handler to output logs to the console
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ) #defines the log message format
        file_handler.setFormatter(formatter) #applies the formatter to the file handler
        console_handler.setFormatter(formatter) #applies the formatter to the console handler
        logger.addHandler(file_handler) #adds the file handler to the logger
        logger.addHandler(console_handler) #adds the console handler to the logger
        return logger #returns the configured logger
    
    def calculate_position_size(self, symbol, volatility): #method to calculate position size based on volatility
        #calculate position size based on volatility scaling 
        #Args:
            #symbol (str): trading symbol
            #volatility (float): rolling standard deviation of log returns 
        #returns
            #float: position size in lots
        tick = mt5.symbol_info_tick(symbol) #fetches current tick (bid and ask) data for symbol
        if tick is None: #checks if the tick is unavailable 
            self.logger.error(f"Failed to get tick data for {symbol}") #logs an error message
            return 0.0 #returns 0 to skip trading 
        price = (tick.ask + tick.bid) / 2
        symbol_info = mt5.symbol_info(symbol) #fetches info information (contract size, lot limits)
        if symbol_info is None: #if unavailable
            self.logger.error(f"Failed to get symbol info for {symbol}") #logs an error message
            return 0.0
        account_info = mt5.account_info() #fetches account information equity
        if account_info is None: 
            self.logger.error("Failed to get account info")
            return 0.0
        risk_amount = account_info.equity * 0.01 #risk 1% of equity
        position_size = risk_amount / (self.n_assets * volatility * price) #calculates position size based on risk amount, number of assets, volatility, and price
        contract_size = symbol_info.trade_contract_size #gets the contract size for the symbol
        lot_size = position_size / contract_size #converts position size to lot size
        min_lot = symbol_info.volume_min #get minimum lot size for the symbo
        max_lot = min(symbol_info.volume_max, 400.0) #maximum lot size capped at 400
        lot_size = max(min(lot_size, max_lot), min_lot) #ensures lot size is within min and max limits
        lot_step = symbol_info.volume_step #gets the lot size increment (0.01)
        lot_size = round(lot_size / lot_step) * lot_step #rounds the lot size to the nearest valid increment
        self.logger.info(f"Position size calculation for {symbol}:") #logs the start of position size logging
        self.logger.info(f"Account equity: {account_info.equity}") #logs account equity
        self.logger.info(f"Risk amount (1% equity): {risk_amount}") #logs risk amount
        self.logger.info(f"Price: {price}") #logs price
        self.logger.info(f"Volatility: {volatility}") #logs volatility
        self.logger.info(f"Price: {price}") #logs price
        self.logger.info(f"Min Lot: {min_lot}, Max Lot: {max_lot}, Lot Step: {lot_step}") #logs min, max, and step lot sizes
        self.logger.info(f"Final Lot Size: {lot_size}") #logs the final calculated lot size
        return lot_size #returns the calculated lot size
    
    def sync_positions(self): #method to synchronize internal position tracking with actual MT5 positions
        #sync internal position tracking with actual MT5 positions
        for symbol in self.symbols: #iterates over each symbol
            self.current_position[symbol] = 0 #resets current position to 0
            positions = mt5.positions_get() #fetches all open positions from MT5
            if positions is None: #if no positions are returned
                self.logger.warning(f"No positions found in MT5") #logs no positions found
                return
            for pos in positions: #iterates over each position
                if pos.symbol in self.symbols: #if the position's symbol is in the trading list
                    self.current_position[pos.symbol] = 1 if pos.type == mt5.POSITION_TYPE_BUY else -1 #sets current position to 1 for buy and -1 for sell
                    self.logger.info(f"Synchronized position for {pos.symbol}: {self.current_position[pos.symbol]}") #logs the synchronized position for the symbol
                else:
                    self.logger.warning(f"Ignoring position for {pos.symbol} not in trading list") #logs ignoring positions not in the trading list
    
    def close_position(self, symbol): #method to close an open position for a given symbol
        #close all positions for a symbol
        self.logger.info(f"Closing positions for {symbol}") #logs message of closing all positions for specified symbol
        positions = mt5.positions_get(symbol = symbol) #fetches all open positions for the specified symbol
        if not positions: #if no positions returned
            self.logger.info(f"No positions for {symbol}") #logs message that no positions returned for specified symbol
            return
        for pos in positions: #iterates over each position for a symbol (processes each position to close it individually)
            if pos.type == mt5.POSITION_TYPE_BUY: #check if position buy to determine right position to close it
                request = {
                    "action": mt5.TRADE_ACTION_DEAL, #for market orders
                    "symbol": symbol, 
                    "volume": pos.volume, #position size
                    "type": mt5.ORDER_TYPE_SELL,
                    "position": pos.ticket,
                    "type_time": mt5.ORDER_TIME_GTC, #for good till cancelled
                    "type_filling": mt5.ORDER_TYPE_FOK #for fill or kill 
                } #dictionarry defining a sell order to close buy
            elif pos.type == mt5.POSITION_TYPE_SELL: #if position is sell
                request = {
                    "action": mt5.TRADE_ACTION_DEAL, #for market orders
                    "symbol": symbol, #symbol
                    "volume": pos.volume, #position size
                    "type": mt5.ORDER_TYPE_BUY, #buy to close sell
                    "position": pos.ticket, #ticket number of the position to close
                    "type_time": mt5.ORDER_TIME_GTC, #good till cancelled
                    "type_filling": mt5.ORDER_TYPE_FOK #fill or kill 
                } #dictionary defining a buy order to close sell
            else: 
                self.logger.warning(f"Unknown position type for {symbol}: {pos.type}") #logs unknown position type
                continue
            result = mt5.send_request(request) #sends the close order request to MT5
            if result.retcode != mt5.TRADE_RETCODE_DONE: #checks if order not successfully executed
                self.logger.error(f"Failed to close position for {symbol}: {result.comment}") #logs error message with return code
            else: 
                self.logger.info(f"Closed position for {symbol}, ticket {pos.ticket}") #logs successful position closure with ticket number
                time.sleep(0.1) #short delay to avoid overloading MT5 with requests
    
    def execute_trade(self, symbol, signal, volatility): 
        #executes trade based on signal and volatility
        #Args:
            #symbol (str): trading symbol
            #signal (int): trading signal (1 for buy, -1 for sell, 0 for hold)
            #volatility (float): rolling std for log returns
        self.logger.info(f"Executing trade for {symbol} with signal {signal}") #logs the trade execution
        self.sync_positions() #syncs positions to ensure internal tracking is up to date (accuracy)
        current_position = self.current_position.get(symbol, 0) #gets the current position for the symbol, default to 0 if not found
        if signal == 0: 
            if current_position != 0: 
                self.close_position(symbol)
                self.current_position[symbol] = 0 #updates internal tracking to reflect no position (to 0)
                return
            elif (signal ==1 and current_position == -1) or (signal == -1 and current_position == 1):
                self.close_position(symbol)
                self.current_position[symbol] = 0 #updates internal tracking to reflect no position (to 0)
        if signal != 0 and current_position == 0:
            lot_size = self.calculate_position_size(symbol, volatility) #calculates position size based on volatility
            if lot_size <= 0:
                self.logger.error(f"Invalid lot size for {symbol}: {lot_size}") #logs warning if lot size is non-positive
                return
        tick = mt5.symbol_info_tick(symbol) #fetches current tick data for the symbol
        if tick is None:
            self.logger.error(f"Failed to get tick data for {symbol}") #logs error if tick data unavailable
            return
        request = {
            "action": mt5.TRADE_ACTION_DEAL, #for market orders
            "symbol": symbol,
            "volume": lot_size, #position size in lots
            "type": mt5.ORDER_TYPE_BUY if signal == 1 else mt5.ORDER_TYPE_SELL, #buy for signal 1, sell for -1
            "price": tick.ask if signal == 1 else tick.bid, #ask price for buy, bid price for sell
            "type_time": mt5.ORDER_TIME_GTC, #good till cancelled
            "type_filling": mt5.ORDER_TYPE_FOK #fill or kill
        } #dictionary defining the trade order request
        result = mt5.send_request(request) #sends the trade order request to MT5
        if result.retcode != mt5.TRADE_RETCODE_DONE: #checks if order
            self.logger.error(f"Trade execution failed for {symbol}: {result.comment}") #logs error message with return code
        else: 
            self.current_position[symbol] = signal #updates internal tracking to reflect new position
        self.logger.info(f"Trade executed for {symbol}: {"Buy" if signal ==1 else "Sell"}", f"Volume: {lot_size}, ticket: {result.deal}") #logs successful trade execution with order ticket
        time.sleep(0.1) #short delay to avoid overloading MT5 with requests
    
    def __del__(self): #destructor to clean up resources
        #clean up resources
        self.logger.info("Shutting down MT5 connection") #logs the shutdown of the MT5 connection
        mt5.shutdown() #shuts down the MT5 connection
        
