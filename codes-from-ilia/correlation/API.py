import pandas as pd
import ccxt.async_support as ccxt
from datetime import datetime, timedelta
import asyncio
from typing import List, Dict

class Binance:
    def __init__(self):
        self.exchange = ccxt.binance()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.exchange.close()

    async def get_data(self, symbol: str, timeframe='1d', limit=1000):
        try:
            return await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            print(f"Error fetching data for {symbol}: {str(e)}")
            return []

    async def get_weekend_data(self, tickers: List[str], use_previous_week=False) -> pd.DataFrame:
        """
        Asynchronously fetch data for multiple tickers either from:
        - Previous Friday to current Monday (use_previous_week=False)
        - Last week's Monday to Friday (use_previous_week=True)
        """
        today = datetime.utcnow()
        
        if use_previous_week:
            # Last week's Monday to Friday
            # Calculate last Friday by getting days since Friday (where Friday is 4 in weekday())
            # and adding 7 to go back a week
            last_friday = today - timedelta(days=(today.weekday() - 4 + 7))
            last_monday = today - timedelta(days=(today.weekday() + 7))  # Go back to previous Monday
            since = int(last_monday.timestamp() * 1000)
            until = int(last_friday.timestamp() * 1000)
        else:
            # Previous Friday to current Monday
            last_friday = today - timedelta(days=today.weekday() + 4)
            this_monday = today - timedelta(days=today.weekday())
            since = int(last_friday.timestamp() * 1000)
            until = int(this_monday.timestamp() * 1000)

        # Fetch data for all tickers concurrently
        tasks = [self.get_data(ticker, timeframe='1d', limit=1000) for ticker in tickers]
        results = await asyncio.gather(*tasks)
        
        dfs = []
        for ticker, ohlcv in zip(tickers, results):
            if not ohlcv:  # Skip if no data
                continue
                
            # Filter data for the specified date range
            filtered_data = [entry for entry in ohlcv if since <= entry[0] <= until]
            
            if filtered_data:  # Only create DataFrame if we have data
                df = pd.DataFrame(filtered_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['ticker'] = ticker
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                dfs.append(df)
        
        return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

    @staticmethod
    def calculate_correlations(df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Calculate correlations between different aspects of the data
        """
        # Pivot the data for correlation calculations
        price_pivot = df.pivot(index='timestamp', columns='ticker', values='close')
        volume_pivot = df.pivot(index='timestamp', columns='ticker', values='volume')
        
        correlations = {
            'price': price_pivot.corr(),
            'volume': volume_pivot.corr(),
        }
        
        return correlations
    
    
