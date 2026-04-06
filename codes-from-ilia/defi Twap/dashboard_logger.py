from datetime import datetime
from configs.logger_config import setup_logger

logger = setup_logger('streamlit_dashboard')

class DashboardLogHandler:
    def __init__(self, max_logs=100):
        self.logs = []
        self.max_logs = max_logs
        self.wallet_status = {}
        self.trade_history = []
        self.execution_results = {}
        self._stop_requested = False

    def add_log(self, level, message):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append({
            'timestamp': timestamp,
            'level': level,
            'message': message
        })
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]

    def get_logs(self):
        return self.logs.copy()

    def clear_logs(self):
        self.logs.clear()
    
     # New methods for status and history
    def update_wallet_status(self, wallet_id, status_data):
        self.wallet_status[wallet_id] = status_data

    def get_wallet_status(self):
        return self.wallet_status.copy()

    def add_trade_to_history(self, trade_data):
        self.trade_history.append(trade_data)

    def get_trade_history(self):
        return self.trade_history.copy()

    def set_execution_results(self, results):
        self.execution_results = results

    def get_execution_results(self):
        return self.execution_results.copy()
    
    def request_stop(self):
        self._stop_requested = True

    def clear_stop(self):
        self._stop_requested = False

    def get_stop_requested(self):
        return self._stop_requested

# Global instance
dashboard_log_handler = DashboardLogHandler()

def add_dashboard_log(level: str, message: str, exc_info=False):
    dashboard_log_handler.add_log(level, message)
    if level == 'ERROR':
        logger.error(message, exc_info=exc_info)
    elif level == 'WARNING':
        logger.warning(message)
    elif level == 'DEBUG':
        logger.debug(message)
    else:
        logger.info(message) 