import logging
import os
from datetime import datetime

# Create logs directory if it doesn't exist
if not os.path.exists('logs'):
    os.makedirs('logs')

# Configure logging
def setup_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # File handler for all logs
    all_logs_file = f'logs/all_{datetime.now().strftime("%Y%m%d")}.log'
    all_handler = logging.FileHandler(all_logs_file)
    all_handler.setLevel(logging.DEBUG)
    all_handler.setFormatter(detailed_formatter)

    # File handler for errors only
    error_logs_file = f'logs/error_{datetime.now().strftime("%Y%m%d")}.log'
    error_handler = logging.FileHandler(error_logs_file)
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(detailed_formatter)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple_formatter)

    # Add handlers to logger
    logger.addHandler(all_handler)
    logger.addHandler(error_handler)
    logger.addHandler(console_handler)

    return logger 