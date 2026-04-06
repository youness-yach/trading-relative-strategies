import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import asyncio
from API import Binance
import logging
from typing import Optional, Dict
import numpy as np

# Setup logging
logger = logging.getLogger(__name__)

class CryptoCorrelationDashboard:
    # Define default tickers as class variable
    DEFAULT_TICKERS = [
        'AAVE/USDT', 'APE/USDT'  ,'AVAX/USDT',   'BNB/USDT', 
        'BTC/USDT', 'CAKE/USDT',    'CHZ/USDT', 'CRV/USDT', 
        'DOGE/USDT',    'ETH/USDT',     'FIL/USDT', 'LINK/USDT',
        'POL/USDT', 'NEAR/USDT',    'SAND/USDT',    'SHIB/USDT',
        'SOL/USDT', 'TON/USDT', 'TRX/USDT', 'UNI/USDT', 'USDC/USDT',
        'XRP/USDT'
    ]

    def __init__(self):
        """Initialize the dashboard"""
        self.setup_page_config()
        self.binance = Binance()

    @staticmethod
    def setup_page_config():
        """Setup Streamlit page configuration"""
        st.set_page_config(
            page_title="Crypto Correlations Dashboard",
            page_icon="📊",
            layout="wide"
        )

    async def fetch_data(self) -> Optional[pd.DataFrame]:
        """
        Fetch data from Binance API
        Returns:
            Optional[pd.DataFrame]: DataFrame with crypto data or None if error occurs
        """
        try:
            async with Binance() as binance:
                df = await binance.get_weekend_data(
                    tickers=st.session_state.get('selected_tickers', self.DEFAULT_TICKERS),
                    use_previous_week=st.session_state.get('use_previous_week', False)
                )
                return df
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}", exc_info=True)
            st.error(f"Error fetching data: {str(e)}")
            return None

    def calculate_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate daily log returns for each cryptocurrency
        """
        returns_df = df.copy()
        
        # Sort the dataframe by ticker and timestamp
        returns_df = returns_df.sort_values(['ticker', 'timestamp'])
        
        # Calculate returns for each ticker separately
        for ticker in returns_df['ticker'].unique():
            ticker_data = returns_df[returns_df['ticker'] == ticker].copy()
            ticker_data.loc[:, 'returns'] = np.log(ticker_data['close'] / ticker_data['close'].shift(1))
            returns_df.loc[ticker_data.index, 'returns'] = ticker_data['returns']
        
        # Drop rows with NaN returns
        returns_df = returns_df.dropna(subset=['returns'])
        
        return returns_df

    def calculate_returns_correlation(self, returns_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate returns correlation matrix
        """
        # Create pivot table for returns
        returns_pivot = returns_df.pivot_table(
            index='timestamp',
            columns='ticker',
            values='returns',
            aggfunc='first'
        )
        
        # Calculate correlation matrix
        corr_matrix = returns_pivot.corr(method='pearson')
        
        # Round to 4 decimal places
        corr_matrix = corr_matrix.round(4)
        
        return corr_matrix

    def calculate_correlations(self, df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Calculate correlations between different aspects of the data
        
        Args:
            df (pd.DataFrame): Raw data from API with columns [timestamp, ticker, close, ...]
            
        Returns:
            Dict[str, pd.DataFrame]: Dictionary containing price and returns correlation matrices
            pd.DataFrame: Returns data formatted for plotting
        """
        # First create price pivot table
        price_pivot = df.pivot_table(
            index='timestamp',
            columns='ticker',
            values='close',
            aggfunc='first'
        ).sort_index()
        
        # Calculate log returns directly from the price pivot
        returns_pivot = price_pivot.pct_change().dropna()
        
        # Calculate correlations
        price_corr = price_pivot.corr(method='pearson')
        returns_corr = returns_pivot.corr(method='pearson')
        #print(price_pivot)
        #print(returns_pivot)
        #print(returns_corr)

        # Create returns dataframe for plotting
        returns_df = returns_pivot.reset_index().melt(
            id_vars=['timestamp'],
            var_name='ticker',
            value_name='returns'
        ).dropna()
        
        correlations = {
            'price': price_corr,
            'returns': returns_corr
        }
        
        return correlations, returns_df

    def render_correlation_heatmap(self, correlations: Dict, correlation_type: str):
        """
        Render correlation heatmap
        """
        corr_matrix = correlations[correlation_type]
        
        # Create mask for lower triangle
        mask = np.triu(np.ones(corr_matrix.shape), k=1)
        corr_matrix_masked = np.where(mask, np.nan, corr_matrix)
        text_matrix = np.where(mask, '', corr_matrix.round(3).astype(str))
        
        # Create custom colorscale
        colors = [
            [0.0, '#d7191c'],     # Strong negative correlation (red)
            [0.25, '#fdae61'],    # Weak negative correlation (orange)
            [0.5, '#ffffbf'],     # No correlation (light yellow)
            [0.75, '#abd9e9'],    # Weak positive correlation (light blue)
            [1.0, '#2c7bb6']      # Strong positive correlation (dark blue)
        ]
        
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix_masked,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            zmin=-1,
            zmax=1,
            text=text_matrix,
            texttemplate='%{text}',
            textfont={'size': 14, 'color': 'black'},
            hoverongaps=False,
            colorscale=colors,
            showscale=True,
            colorbar=dict(
                title=dict(text='Correlation'),
                thickness=15,
                len=0.75,
                tickmode='array',
                ticktext=['-1.0', '-0.5', '0.0', '0.5', '1.0'],
                tickvals=[-1, -0.5, 0, 0.5, 1],
                tickfont={'size': 12}
            )
        ))
        
        # Update layout
        fig.update_layout(
            title={
                'text': f"{correlation_type.capitalize()} Correlation Matrix",
                'y': 0.95,
                'x': 0.5,
                'xanchor': 'center',
                'yanchor': 'top',
                'font': {'size': 20}
            },
            width=800,
            height=800,
            xaxis={
                'side': 'bottom',
                'tickangle': 45,
                'tickfont': {'size': 12},
                'title': {'text': '', 'standoff': 10}
            },
            yaxis={
                'autorange': 'reversed',
                'tickfont': {'size': 12},
                'title': {'text': '', 'standoff': 10}
            },
            margin={'t': 100, 'b': 100, 'l': 100, 'r': 100}
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Add explanation
        st.markdown("""
        **Interpretation:**
        - Dark Blue (1.0): Perfect positive correlation
        - Light Blue (0.5): Moderate positive correlation
        - Light Yellow (0.0): No correlation
        - Orange (-0.5): Moderate negative correlation
        - Red (-1.0): Perfect negative correlation
        """)

    def render_returns_chart(self, df: pd.DataFrame):
        """
        Render returns chart
        Args:
            df (pd.DataFrame): DataFrame containing returns data
        """
        fig = px.line(
            df,
            x='timestamp',
            y='returns',
            color='ticker',
            title="Daily Returns Over Time"
        )
        fig.update_layout(
            height=600,
            yaxis_title="Daily Returns (%)",
            yaxis_tickformat='.2%'
        )
        st.plotly_chart(fig, use_container_width=True)

    def render_price_chart(self, df: pd.DataFrame):
        """
        Render price movement chart
        Args:
            df (pd.DataFrame): DataFrame containing price data
        """
        fig = px.line(
            df,
            x='timestamp',
            y='close',
            color='ticker',
            title="Price Movement Over Time"
        )
        fig.update_layout(height=600)
        st.plotly_chart(fig, use_container_width=True)

    def render_sidebar(self):
        """Render sidebar controls"""
        with st.sidebar:
            st.header("Settings")
            
            selected_tickers = st.multiselect(
                "Select Cryptocurrencies",
                options=self.DEFAULT_TICKERS,
                default=self.DEFAULT_TICKERS
            )
            st.session_state['selected_tickers'] = selected_tickers
            
            st.session_state['use_previous_week'] = st.checkbox(
                "Use Previous Week's Data",
                value=False,
                help="If checked, shows last week's Monday to Friday data. Otherwise shows previous Friday to current Monday."
            )
            
            if st.button("Refresh Data"):
                st.session_state['refresh'] = True

    def render_statistics(self, returns_df: pd.DataFrame):
        """
        Render basic statistics for returns
        Args:
            returns_df (pd.DataFrame): DataFrame containing returns data
        """
        st.subheader("Returns Statistics")
        
        # Calculate statistics for each ticker
        stats = []
        for ticker in returns_df['ticker'].unique():
            ticker_returns = returns_df[returns_df['ticker'] == ticker]['returns']
            stats.append({
                'Ticker': ticker,
                'Mean Return': ticker_returns.mean(),
                'Std Dev': ticker_returns.std(),
                'Min': ticker_returns.min(),
                'Max': ticker_returns.max(),
                'Sharpe Ratio': ticker_returns.mean() / ticker_returns.std() if ticker_returns.std() != 0 else 0
            })
        
        stats_df = pd.DataFrame(stats)
        stats_df = stats_df.set_index('Ticker')
        
        # Format percentages
        for col in ['Mean Return', 'Std Dev', 'Min', 'Max']:
            stats_df[col] = stats_df[col].map('{:.2%}'.format)
        
        stats_df['Sharpe Ratio'] = stats_df['Sharpe Ratio'].map('{:.2f}'.format)
        
        st.dataframe(stats_df)

    async def run(self):
        """Main method to run the dashboard"""
        st.title("Crypto Correlations Dashboard")
        
        # Render sidebar
        self.render_sidebar()

        # Initialize or handle refresh state
        if 'refresh' not in st.session_state:
            st.session_state['refresh'] = True

        # Fetch and process data
        if st.session_state['refresh']:
            with st.spinner("Fetching data..."):
                df = await self.fetch_data()
                if df is not None:
                    st.session_state['data'] = df
                st.session_state['refresh'] = False

        # Render visualizations
        if 'data' in st.session_state and not st.session_state['data'].empty:
            df = st.session_state['data']
            correlations, returns_df = self.calculate_correlations(df)
            
            tab1, tab2, tab3, tab4 = st.tabs([
                "Price Correlations",
                "Returns Correlations",
                "Price & Returns Charts",
                "Statistics"
            ])
            
            with tab1:
                st.subheader("Price Correlations")
                self.render_correlation_heatmap(correlations, 'price')

            with tab2:
                st.subheader("Returns Correlations")
                self.render_correlation_heatmap(correlations, 'returns')

            with tab3:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Price Charts")
                    self.render_price_chart(df)
                with col2:
                    st.subheader("Returns Charts")
                    self.render_returns_chart(returns_df)

            with tab4:
                self.render_statistics(returns_df)

        else:
            st.warning("No data available. Please check your selection and try again.")

