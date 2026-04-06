import time
from datetime import datetime, timedelta
import logging
from meanrev import MeanReversion
from execution import MT5Execution
import pandas as pd
from pathlib import Path

def setup_logging():
    """Setup logging for the main script."""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logger = logging.getLogger("MeanReversionMain")
    logger.setLevel(logging.INFO)
    
    # Create handlers
    file_handler = logging.FileHandler(
        log_dir / f"main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

def main():
    # Initialize logging
    logger = setup_logging()
    logger.info("Starting Mean Reversion Trading Strategy")
    
    # Flag to control the trading loop
    running = True
    
    try:
        # Trading parameters
        symbols = ["EURUSD","USDCHF","USDCAD"]
        window = 20  # Window for calculating z-scores
        threshold = 1.5  # Z-score threshold for generating signals
        check_interval = 30  # Time between checks in seconds (1 minutes)
        initial_capital = 1000  # Initial capital in account currency
        
        # Initialize strategy and execution classes
        strategy = MeanReversion()
        executor = MT5Execution(capital=initial_capital, symbols=symbols)
        
        logger.info(f"Strategy initialized with parameters:")
        logger.info(f"Symbols: {', '.join(symbols)}")
        logger.info(f"Window: {window}")
        logger.info(f"Threshold: {threshold}")
        logger.info(f"Check interval: {check_interval} seconds")
        while running:
            try:
                for symbol in symbols:
                    # Get latest price data
                    prices = strategy.get_close_prices(symbol)
                    if prices.empty:
                        logger.error(f"No price data received for {symbol}")
                        continue
                    
                    # Calculate z-scores
                    zscore = strategy.calculate_zscore(prices[symbol], window=window)
                    
                    # Generate trading signals
                    signals = strategy.calculate_signals(zscore, threshold=threshold)
                    
                    # Get latest signal
                    current_signal = signals.iloc[-1]
                    
                    # Calculate current volatility for position sizing
                    returns = prices[symbol].pct_change()
                    current_volatility = returns.rolling(window=window).std().iloc[-1]
                    
                    # Execute trade based on signal
                    executor.execute_trade(symbol, current_signal, current_volatility)
                    
                    # Log current state
                    logger.info(f"{symbol} current state - Price: {prices[symbol].iloc[-1]:.5f}, "
                              f"Z-score: {zscore.iloc[-1]:.2f}, Signal: {current_signal}")
                
                time.sleep(30)  # Sleep for 30s
                
            except Exception as e:
                logger.error(f"Error in trading loop: {str(e)}")
                time.sleep(1)  # Short sleep on error
                continue
    except KeyboardInterrupt:
        logger.info("Received shutdown signal. Gracefully stopping the trading system...")
        running = False
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        running = False
    
    finally:
        logger.info("Shutting down trading system")

if __name__ == "__main__":
    main()
