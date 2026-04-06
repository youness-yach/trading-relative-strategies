import pandas as pd
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import numpy as np
import logging
import os
from pathlib import Path

class MeanReversion:
    def __init__(self, log_level=logging.INFO):
        """
        Initialize the MeanReversion trading class.
        
        Args:
            log_level: Logging level (default: logging.INFO)
        """
        # Set up logging
        self.logger = self._setup_logging(log_level)
        
        self.logger.info("Initializing MeanReversion trading system")
        if not mt5.initialize():
            self.logger.error("MT5 initialization failed")
            raise RuntimeError("MT5 initialization failed")
        
        # Check if connection is established
        if not mt5.terminal_info().connected:
            self.logger.error("MT5 terminal is not connected")
            raise RuntimeError("MT5 terminal is not connected")
        
        self.logger.info("MT5 connection established successfully")
            
    def _setup_logging(self, log_level):
        """
        Set up logging configuration.
        
        Args:
            log_level: Desired logging level
            
        Returns:
            logging.Logger: Configured logger instance
        """
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Create logger
        logger = logging.getLogger("MeanReversion")
        logger.setLevel(log_level)
        
        # Create handlers
        # File handler with timestamp
        file_handler = logging.FileHandler(
            f"logs/meanrev_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        # Console handler
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
            
    def __del__(self):
        """Cleanup when the object is destroyed."""
        self.logger.info("Shutting down MT5 connection")
        mt5.shutdown()
    """CHANGED TIMEFRAME TO M15"""
    def get_close_prices(self, symbol, timeframe=mt5.TIMEFRAME_M15, start_date=None, end_date=None):
        """
        Get historical close prices for a symbol.
        
        Args:
            symbol (str): The trading symbol (e.g., "EURUSD")
            timeframe: MT5 timeframe (default: TIMEFRAME_M15)
            start_date (datetime): Start date for historical data
            end_date (datetime): End date for historical data
            
        Returns:
            pd.DataFrame: DataFrame with close prices
        """
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=1000)
        if end_date is None:
            end_date = datetime.now()
            
        
        # Request historical data
        rates = mt5.copy_rates_range(symbol, timeframe, start_date, end_date)
        
        if rates is None or len(rates) == 0:
            self.logger.error(f"Failed to get data for {symbol}")
            raise ValueError(f"Failed to get data for {symbol}")
            
        # Convert to pandas DataFrame and keep only close prices
        df = pd.DataFrame(rates)[['time', 'close']]
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        # Rename the column to be more descriptive
        df.columns = [f'{symbol}']
        
        
        return df
    def calculate_zscore(self, prices, window=20):
        """
        Calculate the z-score for a price series using log returns.
        
        Args:
            prices (pd.Series): Price series
            window (int): Rolling window for calculations
            
        Returns:
            pd.Series: Z-scores
        """
        self.logger.info(f"Calculating z-scores with window size {window}")
        
        # Calculate log returns
        self.logger.info("Calculating logarithmic returns")
        data = np.log(prices.shift(1) / prices.shift(2))
        self.logger.debug(f"Log returns stats - Mean: {data.mean():.6f}, Std: {data.std():.6f}")
        
        # Calculate rolling mean and standard deviation
        rolling_mean = data.rolling(window=window).mean()
        rolling_std = data.rolling(window=window).std()
        
        # Calculate z-score as (price - mean) / std
        zscore = (data - rolling_mean) / rolling_std
        
        self.logger.debug(f"Z-score stats - Mean: {zscore.mean():.2f}, Std: {zscore.std():.2f}")
        
        return zscore


    def calculate_signals(self, zscore, threshold=2):
        """
        Generate trading signals based on z-score thresholds.
        
        Args:
            zscore (pd.Series): Z-score values
            threshold (float): Z-score threshold for generating signals
            
        Returns:
            pd.Series: Trading signals (1 for buy, -1 for sell, 0 for no action)
        """
        self.logger.info(f"Generating signals with threshold {threshold}")
        
        signals = pd.Series(0, index=zscore.index)
        
        # Generate buy signals when z-score < -threshold
        signals[zscore < -threshold] = 1
        
        # Generate sell signals when z-score > threshold  
        signals[zscore > threshold] = -1
        
        # Generate close signals when z-score is between -0.1 and 0.1
        signals[(zscore >= -0.1) & (zscore <= 0.1)] = 0
        
        signal_counts = signals.value_counts()
        self.logger.debug(f"Signal distribution: {signal_counts.to_dict()}")
        
        return signals
