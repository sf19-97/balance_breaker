"""
Base interfaces for portfolio performance tracking

This module defines the base interfaces for the performance tracking components
that calculate and monitor portfolio performance metrics.
"""

import logging
from abc import abstractmethod
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import pandas as pd

from balance_breaker.src.core.interface_registry import implements
from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, PortfolioError, ErrorSeverity, ErrorCategory
from balance_breaker.src.portfolio.interfaces import PerformanceTracker as IPerformanceTracker
from balance_breaker.src.portfolio.models import Portfolio, PortfolioMetrics


@implements("PerformanceTracker")
class PerformanceTracker(ParameterizedComponent, IPerformanceTracker):
    """
    Base class for portfolio performance trackers
    
    Performance trackers record portfolio state over time and calculate
    performance metrics for analysis and reporting.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Tracker parameters
        """
        super().__init__(parameters)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_handler = ErrorHandler(self.logger)
        self.name = self.__class__.__name__
        
        # Initialize history storage
        self.equity_history = []
        self.trade_history = []
    
    def update(self, portfolio: Portfolio, timestamp: datetime) -> None:
        """
        Update tracker with current portfolio state
        
        This method calls the implementation method and handles errors.
        
        Args:
            portfolio: Current portfolio state
            timestamp: Current timestamp
        """
        try:
            self._update_impl(portfolio, timestamp)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Performance tracker update error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATA,
                    context={'portfolio_positions': len(portfolio.positions)},
                    original_exception=e
                )
            )
    
    @abstractmethod
    def _update_impl(self, portfolio: Portfolio, timestamp: datetime) -> None:
        """
        Implementation method for updating tracker state
        
        Args:
            portfolio: Current portfolio state
            timestamp: Current timestamp
        """
        pass
    
    def calculate_metrics(self, time_window: str = 'all', 
                         risk_free_rate: float = 0.0) -> Dict[str, Any]:
        """
        Calculate performance metrics for the specified time window
        
        This method calls the implementation method and handles errors.
        
        Args:
            time_window: Time window for metrics ('day', 'week', 'month', 'year', 'all')
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            
        Returns:
            Dictionary of performance metrics
        """
        try:
            metrics = self._calculate_metrics_impl(time_window, risk_free_rate)
            
            # Convert to dictionary if PortfolioMetrics object
            if isinstance(metrics, PortfolioMetrics):
                # Extract all fields from dataclass
                metrics_dict = {}
                for field_name in metrics.__dataclass_fields__:
                    metrics_dict[field_name] = getattr(metrics, field_name)
                
                # Add additional metrics if present
                if hasattr(metrics, 'additional_metrics'):
                    metrics_dict.update(metrics.additional_metrics)
                
                return metrics_dict
            
            return metrics
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Performance metrics calculation error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATA,
                    context={'time_window': time_window},
                    original_exception=e
                )
            )
            # Return minimal metrics on error
            return {'error': str(e), 'time_window': time_window}
    
    @abstractmethod
    def _calculate_metrics_impl(self, time_window: str = 'all', 
                              risk_free_rate: float = 0.0) -> Union[Dict[str, Any], PortfolioMetrics]:
        """
        Implementation method for calculating metrics
        
        Args:
            time_window: Time window for metrics
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            
        Returns:
            Performance metrics (dictionary or PortfolioMetrics object)
        """
        pass
    
    @abstractmethod
    def get_equity_curve(self, time_window: str = 'all') -> pd.Series:
        """
        Get equity curve for the specified time window
        
        Args:
            time_window: Time window for equity curve ('day', 'week', 'month', 'year', 'all')
            
        Returns:
            Series with equity values indexed by timestamp
        """
        pass