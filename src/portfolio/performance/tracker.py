"""
Portfolio performance tracker implementation

This module implements the PortfolioTracker class that records portfolio state
and calculates performance metrics.
"""

from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import copy
import json

from balance_breaker.src.portfolio.models import Portfolio, PortfolioMetrics, PortfolioPosition
from balance_breaker.src.portfolio.performance.base import PerformanceTracker
from balance_breaker.src.portfolio.performance.metrics import BasicMetricsCalculator, AdvancedMetricsCalculator


class PortfolioTracker(PerformanceTracker):
    """
    Portfolio performance tracker implementation
    
    This tracker records portfolio state over time, calculates performance metrics,
    and provides equity curves and trade analysis.
    
    Parameters:
    -----------
    record_frequency : str
        How often to record portfolio state ('tick', 'hour', 'day')
    store_positions : bool
        Whether to store individual position details
    max_history_length : int
        Maximum number of history points to store (0 for unlimited)
    precision : int
        Decimal precision for calculations
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Tracker parameters
        """
        default_params = {
            'record_frequency': 'day',   # Record daily by default
            'store_positions': True,     # Store position details
            'max_history_length': 0,     # Unlimited history
            'precision': 4               # 4 decimal places
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        
        # Initialize history storage
        self.equity_history = []   # List of (timestamp, equity) tuples
        self.trade_history = []    # List of trade dictionaries
        self.position_history = [] # List of (timestamp, positions) tuples if store_positions is True
        self.metrics_cache = {}    # Cache for calculated metrics
        
        # Initialize metrics calculators
        self.basic_calculator = BasicMetricsCalculator()
        self.advanced_calculator = AdvancedMetricsCalculator()
        
        # Last recorded time to manage recording frequency
        self.last_recorded_time = None
    
    def update(self, portfolio: Portfolio, timestamp: datetime) -> None:
        """
        Update tracker with current portfolio state
        
        Args:
            portfolio: Current portfolio state
            timestamp: Current timestamp
        """
        # Check if we should record based on frequency
        if not self._should_record(timestamp):
            return
        
        # Update equity history
        self.equity_history.append({
            'timestamp': timestamp,
            'equity': portfolio.current_equity,
            'cash': portfolio.cash,
            'unrealized_pnl': portfolio.unrealized_pnl,
            'realized_pnl': portfolio.realized_pnl,
            'position_count': len(portfolio.positions)
        })
        
        # Store position details if enabled
        if self.parameters['store_positions']:
            positions_snapshot = {}
            for instrument, position in portfolio.positions.items():
                positions_snapshot[instrument] = {
                    'instrument': position.instrument,
                    'direction': position.direction,
                    'entry_price': position.entry_price,
                    'position_size': position.position_size,
                    'unrealized_pnl': position.unrealized_pnl,
                    'realized_pnl': position.realized_pnl,
                    'risk_percent': position.risk_percent,
                    'strategy_name': position.strategy_name
                }
            
            self.position_history.append({
                'timestamp': timestamp,
                'positions': positions_snapshot
            })
        
        # Add new trades to history
        if hasattr(portfolio, 'transaction_history'):
            # Get only new transactions since last update
            new_transactions = []
            if self.trade_history:
                last_ts = self.trade_history[-1]['timestamp'] if self.trade_history else None
                new_transactions = [tx for tx in portfolio.transaction_history 
                                  if last_ts is None or tx['timestamp'] > last_ts]
            else:
                new_transactions = portfolio.transaction_history
            
            # Add new transactions to history
            self.trade_history.extend(new_transactions)
        
        # Limit history length if needed
        max_length = self.parameters['max_history_length']
        if max_length > 0:
            if len(self.equity_history) > max_length:
                self.equity_history = self.equity_history[-max_length:]
            if len(self.trade_history) > max_length:
                self.trade_history = self.trade_history[-max_length:]
            if self.parameters['store_positions'] and len(self.position_history) > max_length:
                self.position_history = self.position_history[-max_length:]
        
        # Invalidate metrics cache
        self.metrics_cache = {}
        
        # Update last recorded time
        self.last_recorded_time = timestamp
        
        self.logger.debug(f"Updated portfolio tracker at {timestamp}: "
                        f"equity={portfolio.current_equity:.2f}, "
                        f"positions={len(portfolio.positions)}")
    
    def _should_record(self, timestamp: datetime) -> bool:
        """
        Determine if we should record based on frequency
        
        Args:
            timestamp: Current timestamp
            
        Returns:
            True if we should record, False otherwise
        """
        # If no previous recording, always record
        if self.last_recorded_time is None:
            return True
        
        # Get recording frequency
        frequency = self.parameters['record_frequency'].lower()
        
        if frequency == 'tick':
            # Record every update
            return True
        
        elif frequency == 'hour':
            # Record if hour has changed
            return (timestamp.replace(minute=0, second=0, microsecond=0) > 
                    self.last_recorded_time.replace(minute=0, second=0, microsecond=0))
        
        elif frequency == 'day':
            # Record if day has changed
            return timestamp.date() > self.last_recorded_time.date()
        
        elif frequency == 'week':
            # Record if week has changed
            current_week = timestamp.isocalendar()[1]
            last_week = self.last_recorded_time.isocalendar()[1]
            return (timestamp.year > self.last_recorded_time.year or 
                   (timestamp.year == self.last_recorded_time.year and current_week > last_week))
        
        elif frequency == 'month':
            # Record if month has changed
            return (timestamp.year > self.last_recorded_time.year or 
                   (timestamp.year == self.last_recorded_time.year and 
                    timestamp.month > self.last_recorded_time.month))
        
        else:
            # Unknown frequency, default to tick
            self.logger.warning(f"Unknown record frequency: {frequency}, defaulting to tick")
            return True
    
    def calculate_metrics(self, 
                         time_window: str = 'all', 
                         risk_free_rate: float = 0.0,
                         benchmark_returns: Optional[pd.Series] = None) -> PortfolioMetrics:
        """
        Calculate performance metrics for the specified time window
        
        Args:
            time_window: Time window for metrics ('day', 'week', 'month', 'year', 'all')
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            benchmark_returns: Optional benchmark returns for comparison
            
        Returns:
            PortfolioMetrics object
        """
        # Check cache first
        cache_key = f"{time_window}_{risk_free_rate}"
        if cache_key in self.metrics_cache:
            return self.metrics_cache[cache_key]
        
        # Get filtered equity curve and trade history
        equity_curve = self.get_equity_curve(time_window)
        
        if equity_curve.empty:
            # Return empty metrics if no data
            return PortfolioMetrics(time_window=time_window)
        
        # Filter trade history
        start_date = equity_curve.index[0] if not equity_curve.empty else None
        filtered_trades = self._filter_trades_by_time(start_date, time_window)
        
        # Calculate basic metrics
        basic_metrics = self.basic_calculator.calculate(
            equity_curve, 
            filtered_trades, 
            risk_free_rate, 
            benchmark_returns
        )
        
        # Calculate advanced metrics
        advanced_metrics = self.advanced_calculator.calculate(
            equity_curve, 
            filtered_trades, 
            risk_free_rate, 
            benchmark_returns
        )
        
        # Combine metrics
        combined_metrics = {**basic_metrics, **advanced_metrics}
        
        # Create metrics object
        start_date = equity_curve.index[0] if not equity_curve.empty else None
        end_date = equity_curve.index[-1] if not equity_curve.empty else None
        
        metrics = PortfolioMetrics(
            total_return=combined_metrics.get('total_return', 0.0),
            sharpe_ratio=combined_metrics.get('sharpe_ratio', 0.0),
            sortino_ratio=combined_metrics.get('sortino_ratio', 0.0),
            max_drawdown=combined_metrics.get('max_drawdown', 0.0),
            win_rate=combined_metrics.get('win_rate', 0.0),
            profit_factor=combined_metrics.get('profit_factor', 0.0),
            avg_profit_per_trade=combined_metrics.get('avg_profit', 0.0),
            avg_loss_per_trade=combined_metrics.get('avg_loss', 0.0),
            avg_trade=combined_metrics.get('avg_trade', 0.0),
            alpha=combined_metrics.get('alpha', 0.0),
            beta=combined_metrics.get('beta', 0.0),
            correlation=combined_metrics.get('correlation', 0.0),
            time_window=time_window,
            start_date=start_date,
            end_date=end_date,
            additional_metrics={k: v for k, v in combined_metrics.items() 
                              if k not in PortfolioMetrics.__dataclass_fields__}
        )
        
        # Cache metrics
        self.metrics_cache[cache_key] = metrics
        
        return metrics
    
    def get_equity_curve(self, time_window: str = 'all') -> pd.Series:
        """
        Get equity curve for the specified time window
        
        Args:
            time_window: Time window for equity curve ('day', 'week', 'month', 'year', 'all')
            
        Returns:
            Series with equity values indexed by timestamp
        """
        if not self.equity_history:
            return pd.Series()
        
        # Convert equity history to DataFrame
        df = pd.DataFrame(self.equity_history)
        df.set_index('timestamp', inplace=True)
        
        # Filter by time window
        if time_window != 'all':
            end_date = df.index.max()
            start_date = self._calculate_start_date(end_date, time_window)
            df = df[df.index >= start_date]
        
        # Extract equity series
        equity_curve = df['equity']
        
        return equity_curve
    
    def _calculate_start_date(self, end_date: datetime, time_window: str) -> datetime:
        """
        Calculate start date based on time window
        
        Args:
            end_date: End date
            time_window: Time window ('day', 'week', 'month', 'year')
            
        Returns:
            Start date
        """
        if time_window == 'day':
            return end_date - timedelta(days=1)
        elif time_window == 'week':
            return end_date - timedelta(days=7)
        elif time_window == 'month':
            # Approximate month as 30 days
            return end_date - timedelta(days=30)
        elif time_window == 'year':
            # Approximate year as 365 days
            return end_date - timedelta(days=365)
        else:
            # Default to all data
            return datetime.min
    
    def _filter_trades_by_time(self, start_date: datetime, 
                              time_window: str) -> List[Dict[str, Any]]:
        """
        Filter trade history by time window
        
        Args:
            start_date: Start date
            time_window: Time window ('day', 'week', 'month', 'year', 'all')
            
        Returns:
            Filtered trade history
        """
        if not self.trade_history or time_window == 'all' or start_date is None:
            return self.trade_history
        
        # Filter trades by timestamp
        return [trade for trade in self.trade_history if trade['timestamp'] >= start_date]
    
    def export_data(self, format: str = 'csv', file_path: Optional[str] = None) -> Optional[str]:
        """
        Export tracker data to file
        
        Args:
            format: Export format ('csv', 'json')
            file_path: Optional file path (default generates a timestamped file)
            
        Returns:
            Path to exported file or None if export failed
        """
        try:
            # Generate default file path if not provided
            if file_path is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_path = f"portfolio_tracker_{timestamp}.{format}"
            
            if format.lower() == 'csv':
                # Export equity history as CSV
                df = pd.DataFrame(self.equity_history)
                df.to_csv(file_path)
                self.logger.info(f"Exported equity history to {file_path}")
                return file_path
                
            elif format.lower() == 'json':
                # Export all history as JSON
                data = {
                    'equity_history': self.equity_history,
                    'trade_history': self.trade_history,
                }
                
                if self.parameters['store_positions']:
                    data['position_history'] = self.position_history
                
                with open(file_path, 'w') as f:
                    json.dump(data, f, default=self._json_serializer, indent=2)
                
                self.logger.info(f"Exported tracker data to {file_path}")
                return file_path
            
            else:
                self.logger.error(f"Unsupported export format: {format}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error exporting tracker data: {str(e)}")
            return None
    
    def _json_serializer(self, obj):
        """Custom JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")