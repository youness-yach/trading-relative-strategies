import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import numpy as np
import logging
import os
from pathlib import Path

class MeanReversion: #encapsulate mean reversion logic
    def __init__(self, log_level=logging.INFO): #defines the class constructor with an optional loglevel parameter
        #Initialize the MeanReversion trading class 
        #log_level: Logging level (default: logging.INFO)
        self.logger = self.setup_logging(log_level) #sets up logging for the class instance
        self.logger.info("Initializing MeanReversion trading system") #logs an info message indicating the initialization of the trading system
        if not mt5.initialize(): #attempts to connect MT5 terminal
            self.logger.error("MT5 initialization failed") #logs an error if MT5 connection fails
            raise RuntimeError("MT5 initialization failed") #raises a runtime error if MT5 connection fails
        self.logger.info("MT5 connection established successfully") #logs a message indicating successful MT5 connection
    def _setup_logging(self, log_level): #defines a private method to set up logging
        #Set up logging config 
        #Args: 
            #log_level: Desired logging level
        #Returns:
            #logging.Logger: Configured logger instance
        log_dir = Path("logs") #creates path object for a directory named logs
        log_dir.mkdir(exist_ok=True) #creates the directory if it doesn't exist
        logger = logging.getLogger("MeanReversion") #creates a logger object named MeanReversion
        logger.setLevel(log_level) #sets the logger level INFO
        file_hanlder = logging.FileHandler(
            f"logs/meanrev_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log" #creates a file handler for a timestamped log file 
        )
        console_handler = logging.StreamHandler()  #creates a console handler for logging to the console
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s' #defines the log message format
        )
        file_hanlder.setFormatter(formatter) #applies the formatter to the file handler
        console_handler.setFormatter(formatter) #applies the formatter to the console handler
        logger.addHandler(file_hanlder) #adds the file handler to the logger
        logger.addHandler(console_handler) #adds the console handler to the logger
        return logger #returns the configured logger instance
    
    def __del__(self): #defines the class destructor
        #cleanup when the object is destroyed
        self.logger.info("MT5 connection closed") #logs a message indicating the MT5 connection has been closed
        mt5.shutdown() #shuts down the MT5 connection

        #changed timeframe to M15
        def get_close_prices(self, symbol, timeframe=mt5.TIMEFRAME_M15, start_date=None, end_date=None): #defines a method to fetch historical close prices
            #Get historical close prices for a given symbol and timeframe
            #Args:
                #symbol (str): Trading symbol (e.g., "EURUSD")
                #timeframe: MT5 Timeframe for the data (default: mt5.TIMEFRAME_M15)
                #start_date: Start date for data retrieval (default: 30 days ago)
                #end_date: End date for data retrieval (default: now)
            #Returns:
                #pd.DataFrame: DataFrame with close prices
            if start_date is None: #if no start date is provided
                start_date = datetime.now() - timedelta(days=1000) #set start date to 1000 days before the end date
            if end_date is None: #if no end date is provided
                end_date = datetime.now() #set end date to current date and time
            rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date) #retrieves historical rates from MT5
            if rates is None or len(rates) == 0: #checks if no data was retrieved
                self.logger.error(f"No data retrieved for {symbol}") #logs an error message if no data was retrieved
                raise ValueError(f"Failed to get data for {symbol}") #raises a value error if no data was retrieved
            df = pd.DataFrame(rates)[["time", "close"]] #converts the rates to a pandas DataFrame keeping only time and close columns
            df['time'] = pd.to_datetime(df['time'], unit='s') #converts the time column to datetime format
            df.set_index('time', inplace=True) #sets the time column as the DataFrame index
            df.columns = [f"{symbol}"] #renames the close column to the symbol name
            return df #returns the close prices as a pandas DataFrame 
        
        def calculate_zscore(self, prices, window=20): #defines a method to calculate the z-score for a price series
            #Calculate the z-score for a given price series using log returns
            #Args:
                #prices (pd.Series): Series of prices
                #window (int): Rolling window for calculation
            #Returns:
                #pd.Series: z-scores
            self.logger.info(f"Caculating z-score with window size {window}") #logs an info message indicating the start of z-score calculation
            self.logger.info(f"Caculating logarithmic returns") #logs an info message indicating the start of logarithmic return calculation
            data = np.log(prices.shift(1) / prices.shift(2)) #calculates the logarithmic returns by dividing the price shifted by 1 by the price shifted by 2 and taking the natural log
            self.logger.debug(f"Log returns stats - Mean: {data.mean():.6f}, Std: {data.std():.6f}") #logs debug information about the mean and standard deviation of the log returns
            rolling_mean = data.rolling(window=window).mean() #calculates the rolling mean of the log returns
            rolling_std = data.rolling(window=window).std() #calculates the rolling standard deviation of the log returns
            zscore = (data - rolling_mean) / rolling_std #computes z-score using the formula 
            self.logger.debug(f"Z-score stats - Mean: {zscore.mean():.2f}, Std: {zscore.std():.2f}") #logs debug information about the mean and standard deviation of the z-scores
            return zscore #returns the computed z-scores as a pandas Series
        def calculate_signals(self, zscore, threshold=2): 
            #defines a method to generate trading signals based on zscore threshold       
            #args:
                #zscore (pd.Series): z-scores values
                #threshold (float): Z-score threshold for generating signals
            #returns:   
                #pd.Series: Trading signals (-1 for sell, 1 for buy, 0 for no action)
            self.logger.info(f"Generating trading signals with threshold {threshold}") #logs an info message indicating the start of signal generation
            signals = pd.Series(0, index=zscore.index) #creates a series of zeros with the same index as the z-score series to hold the trading signals
            signals[zscore < -threshold] = 1 #sets the signal to -1 (sell) where the z-score exceeds the positive threshold
            signals[zscore > threshold] = -1 #sets the signal to 1 (buy) where the z-score exceeds the negative threshold
            signals[(zscore >= -0.1) & (zscore <= 0.1)] = 0 #sets the signal to 0 (no action) where the z-score is between -0.1 and 0.1
            signal_counts = signals.value_counts() #counts the frequency of each signal value (-1, 1, 0) 
            self.logger.debug(f"Signal counts: {signal_counts.to_dict()}") #logs the signal distribution (debug level)
            return signals #returns the generated trading signals as a pandas Series
