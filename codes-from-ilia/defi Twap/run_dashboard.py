#!/usr/bin/env python3
"""
DeFi TWAP Bot Dashboard Launcher
Run this script to start the Streamlit dashboard
"""

import subprocess
import sys
import os

if __name__ == "__main__":
    print("Starting DeFi TWAP Bot Dashboard...")
    print("Dashboard will be available at: http://localhost:8501")
    print("Press Ctrl+C to stop the dashboard")
    print("-" * 50)
    
    try:
        # Run streamlit with the dashboard
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "streamlit_dashboard.py",
            "--server.port", "8501",
            "--browser.gatherUsageStats", "false"
        ])
    except KeyboardInterrupt:
        print("\n Dashboard stopped by user")
    except Exception as e:
        print(f" Error starting dashboard: {e}")
        sys.exit(1) 