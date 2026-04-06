# DeFi Trading System

A comprehensive DeFi trading system built for Optimism network that implements TWAP (Time-Weighted Average Price) trading strategy using Uniswap V3.

## Overview

This system provides automated trading capabilities on the Optimism network using Uniswap V3 protocol. It implements a TWAP strategy to execute trades over a specified time period, helping to minimize market impact and achieve better average prices.

## Features

- TWAP (Time-Weighted Average Price) trading strategy
- Support for both buying and selling operations
- Automated trade execution with configurable parameters
- Real-time trade logging to CSV files
- Slack notifications for trade execution and status
- Comprehensive error handling and logging
- Gas optimization and slippage protection
- Support for multiple token pairs (currently configured for OP/USDT)

## System Components

### Core Components

1. **TWAP Executor** (`twap.py`)
   - Implements the TWAP trading strategy
   - Handles trade scheduling and execution
   - Manages trade quantities and intervals
   - Supports random quantity distribution within bounds

2. **Uniswap V3 Interface** (`w3.py`)
   - Main interface for interacting with Uniswap V3 protocol
   - Handles token swaps, approvals, and pool interactions
   - Manages transaction building and execution
   - Implements gas optimization strategies

3. **Main Application** (`main.py`)
   - Entry point for the trading system
   - Initializes components and manages execution flow
   - Handles environment setup and configuration

### Configuration Files

1. **Trade Configuration** (`configs/trade_config.py`)
   - Defines trading parameters
   - Sets token addresses and trading direction
   - Configures TWAP parameters (duration, intervals, quantities)

2. **Wallet Configuration** (`configs/wallets_config.py`)
   - Manages wallet credentials and network settings
   - Defines contract addresses for Optimism network
   - Configures network endpoints and chain IDs

3. **ABI Configuration** (`configs/abi_config.py`)
   - Contains all necessary contract ABIs
   - Includes Uniswap V3, ERC20, and other contract interfaces

### Logging and Notifications

1. **CSV Logger** (`csv_logger.py`)
   - Logs all trades to CSV files
   - Records trade details, gas usage, and transaction hashes
   - Organizes logs by date

2. **Logger Configuration** (`configs/logger_config.py`)
   - Sets up logging infrastructure
   - Configures log levels and formats
   - Manages log file rotation

3. **Slack Notifier** (`slack_notifier.py`)
   - Sends real-time trade notifications to Slack
   - Provides detailed trade information and status updates
   - Includes transaction links and error reporting

## Directory Structure

```
defi/
├── configs/
│   ├── abi_config.py
│   ├── logger_config.py
│   ├── slack_notifier.py
│   ├── trade_config.py
│   └── wallets_config.py
├── logs/
│   ├── all_*.log
│   └── error_*.log
├── trade_logs/
│   └── trades_*.csv
├── utils/
│   └── Ctypes.py
├── main.py
├── twap.py
├── w3.py
└── csv_logger.py
```

## Configuration

### Trading Parameters

Configure your trading parameters in `configs/trade_config.py`:

```python
total_quantity = 1  # Total amount of Base asset to spend
duration_hours = 2/60  # Execute over 2 minutes
interval_minutes = 1  # Execute every 1 minute
min_quantity_per_trade = 0.1  # Minimum amount per trade
max_quantity_per_trade = 0.7  # Maximum amount per trade
trade_direction = TradeDirection.SELL  # Trade direction (BUY or SELL)
```

### Network Configuration

Configure network settings in `configs/wallets_config.py`:

```python
Network = 'https://optimism-mainnet.infura.io/v3/YOUR_API_KEY'
Chain_ID = 10  # Optimism Mainnet Chain ID
```

### Slack Integration

Configure Slack notifications in `configs/wallets_config.py`:

```python
SLACK_WEBHOOK_URL = 'YOUR_SLACK_WEBHOOK_URL'
```

## Usage

1. Set up your environment variables and configurations
2. Install required dependencies
3. Run the main script:

```bash
python main.py
```

## Features in Detail

### TWAP Strategy

The TWAP strategy breaks down large trades into smaller chunks executed over time to:
- Minimize market impact
- Achieve better average prices
- Reduce slippage
- Avoid price manipulation

### Trade Execution

The system:
- Automatically calculates optimal trade sizes
- Handles token approvals
- Manages gas optimization
- Implements slippage protection
- Provides real-time trade status updates

### Logging and Monitoring

- Detailed CSV logs of all trades
- Comprehensive error logging
- Real-time Slack notifications
- Transaction tracking and verification

### Security Features

- Secure private key handling
- Transaction verification
- Error handling and recovery
- Gas optimization and protection

## Dependencies

- web3.py
- python-dotenv
- requests
- datetime
- csv
- logging

## Error Handling

The system implements comprehensive error handling:
- Transaction failures
- Network issues
- Gas estimation errors
- Token approval failures
- Slippage protection

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## Trading Teams Algo Rules

1) DONT ADD SENTHIL (he is trying to reverse engineer everything :D)
2) make sure you send Bonker trades to defi and generate enough USDT profit to buy Ferrari