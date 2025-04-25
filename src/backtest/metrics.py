# src/backtest/metrics.py
class PerformanceMetrics:
    """Calculate and store performance metrics"""
    
    def __init__(self, trades, signals, parameters=None):
        self.trades = trades
        self.signals = signals
        self.parameters = parameters or {}
        self.metrics = {}
        
    def calculate_all(self):
        """Calculate all performance metrics"""
        self.calculate_basic_metrics()
        self.calculate_risk_metrics()
        self.calculate_time_metrics()
        return self.metrics
        
    def calculate_basic_metrics(self):
        """Calculate basic performance metrics"""
        # Implementation...