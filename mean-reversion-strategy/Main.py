import time
from datetime import datetime, timedelta
import logging
from meanrev import MeanReversion # Assuming MeanReversion is defined in meanrev.py
from execution import MT5Execution # Assuming MT5Execution is defined in execution.py
import pandas as pd 
from pathlib import Path

def setup_logging():
    #""setup logging for the main script""
    log_dir = Path("logs") #creates path object for a directory named logs
    log_dir.mkdir(exist_ok=True) #creates the directory if it doesn't exist
    logger = logging.getLogger("MeanReversionMain") #creates a logger object named MeanReversionMain
    logger.setLevel(logging.INFO) #sets the logging level to INFO
    file_handler = logging.FileHandler( #creates a file handler for logging
        log_dir / f"main_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log" #creates a file handler that writes log messages to a file named main_YYYYMMDD_HHMMSS.log in the logs directory
    )
    console_handler = logging.StreamHandler() #creates a console handler to output log messages to the terminal
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s" #creates a formatter to format log messages
    )
    file_handler.setFormatter(formatter) #sets the formatter for the file handler
    console_handler.setFormatter(formatter) #sets the formatter for the console handler
    logger.addHandler(file_handler) #adds the file handler to the logger
    logger.addHandler(console_handler) #adds the console handler to the logger
    return logger

def main():
    logger = setup_logging() #calls setup_loging function to set up logging
    logger.info("Starting Mean Reversion Trading Strategy") #logs an info message indicating the start of the strategy
    running = True #sets a variable named running to True (boolean to control trading loop until interrupted Ctrl+C)
    try: #starts a try block to catch exceptions during execution like keyboard interrupt
        symbols = ["EURUSD", "USDCHF", "USDCAD"] #list of currency pairs to trade
        window = 20 #number of periods for moving average and standard deviation calculations / rolling window size for z-score calculations
        threshold = 1.5 #z-score threshold to trigger trades (trading signal) 
        check_interval = 30 #time interval (in seconds) between each check for trading signals
        initial_capital = 1000 #initial capital for the trading strategy
        strategy = MeanReversion() #creates an instance of the MeanReversion class
        executor = MT5Execution(capital=initial_capital, symbols=symbols) #creates an instance of the MT5Execution class with initial capital and symbols
        logger.info(f"Strategy initialized with parameters::") #logs a message indicating strategy initialization 
        logger.info(f"Symbols:{",".join(symbols)}") #logs the list of trading symbols 
        logger.info(f"Window:{window}") #logs the z score window size
        logger.info(f"Threshold:{threshold}") #logs the z score threshold
        logger.info(f"Check interval:{check_interval} seconds") #logs the check interval in
        while running: #infinite loop continuing as long as running is True
            try: #another try block to catch errors
                for symbol in symbols:  # Correction : utiliser 'symbol' pour l'élément courant
                    prices = strategy.get_close_prices(symbol)  # 'symbol' au lieu de 'symbols'
                    if prices.empty: #check is prices data is empty 
                        logger.error(f"No price data received for {symbol}") #error message 
                        continue
                    zscore = strategy.calculate_zscore(prices[symbol], window=window) #calculates z scores for the symbol prices using the window specified
                    signals = strategy.calculate_signals(zscore, threshold=threshold) #generates trading signals based on the calculated zscore and threshold 
                    current_signal = signals.iloc[-1] #gets the most recent trading signal from signals series
                    returns = prices[symbol].pct_change() #calculates daily returns for the symbol prices
                    current_volatility = returns.rolling(window=window).std().iloc[-1] #calculates the rolling standard deviation of returns and takes the lastest value
                    executor.execute_trade(symbol, current_signal, current_volatility) #executes a trade for the symbol based on the signal and volatility 
                    logger.info(f"{symbol} current state - Price: {prices[symbol].iloc[-1]:.5f}, "
                                f"Z-Score: {zscore.iloc[-1]:.2f}, Signal: {current_signal}, "
                                f"Volatility: {current_volatility:.5f}") #logs the current state of symbol, price, zscore, signal, and volatility
                    time.sleep(30) #waits for the check interval before checking the next symbol
            except Exception as e: #catches any exceptions during the trading loop
                logger.error(f"Error in trading loop: {str(e)}") #logs the error message
                time.sleep(1) #waits for 1 second before retrying
                continue #continues to the next iteration of the while loop
    except KeyboardInterrupt: #catches keyboard interrupt (Ctrl+C)
        logger.info("Received shutdown signal. Gracefully stopping the trading system...") #logs a message indicating shutdown signal received
        running = False #sets running to False to exit the trading loop
    except Exception as e: #catches any other exceptions during setup or initialization
        logger.error(f"Fatal error: {str(e)}") #logs the fatal error message
        running = False #sets running to False to exit the trading loop
    finally: #finally block to ensure cleanup actions are performed
        logger.info("Shutting down the trading system.") #logs a message indicating shutdown
        if __name__ == "__main__":
            main() #calls the main function to start the trading strategy