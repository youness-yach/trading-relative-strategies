import os
import sys
import logging
from pathlib import Path
import platform
import asyncio
from dashboard import CryptoCorrelationDashboard

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Setup environment variables and paths"""
    # Add the current directory to Python path
    current_dir = Path(__file__).parent.absolute()
    sys.path.append(str(current_dir))
    
    # Set environment variables if needed
    os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
    os.environ['STREAMLIT_SERVER_PORT'] = '8501'

    # Setup correct event loop policy for Windows
    if platform.system() == 'Windows':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            logger.debug("Set Windows event loop policy")
        except Exception as e:
            logger.error(f"Failed to set Windows event loop policy: {str(e)}")

def main():
    """Main entry point of the application"""
    try:
        # Setup environment
        setup_environment()
        logger.info("Starting Crypto Correlation Dashboard...")
        
        # Create and run dashboard
        dashboard = CryptoCorrelationDashboard()
        asyncio.run(dashboard.run())

    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
