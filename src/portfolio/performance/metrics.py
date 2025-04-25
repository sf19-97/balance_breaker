"""
Performance metrics calculators for portfolio management

This module implements calculators for basic and advanced portfolio performance metrics.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
import math

from balance_breaker.src.portfolio.performance.base import MetricsCalculator


class BasicMetricsCalculator(MetricsCalculator):
    """
    Basic performance metrics calculator
    
    Calculates fundamental performance metrics including returns, win rate,
    drawdowns, and profit factor.
    
    Parameters:
    -----------
    annualization_factor : int
        Factor used to annualize returns (252 for daily data, 12 for monthly)
    min_trades_for_metrics : int
        Minimum number of trades required for calculating metrics
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Calculator parameters
        """
        default_params = {
            'annualization_factor': 252,  # Daily data by default
            'min_trades_for_metrics': 5,  # Minimum trades for meaningful metrics
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
    
    def calculate(self, 
                 equity_curve: pd.Series, 
                 trade_history: List[Dict[str, Any]],
                 risk_free_rate: float = 0.0,
                 benchmark_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """
        Calculate basic performance metrics
        
        Args:
            equity_curve: Series with equity values indexed by timestamp
            trade_history: List of trade dictionaries
            risk_free_rate: Risk-free rate for calculations (annual)
            benchmark_returns: Optional benchmark returns series
            
        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}
        
        # Check if we have enough data
        if equity_curve.empty:
            return self._create_empty_metrics()
        
        # Extract close trades from history (for win rate, etc.)
        close_trades = [trade for trade in trade_history 
                       if trade.get('type') == 'close_position']
        
        # Total return and annualized return
        initial_equity = equity_curve.iloc[0]
        final_equity = equity_curve.iloc[-1]
        
        metrics['initial_equity'] = initial_equity
        metrics['final_equity'] = final_equity
        metrics['absolute_pnl'] = final_equity - initial_equity
        
        # Calculate total return
        if initial_equity > 0:
            metrics['total_return'] = (final_equity / initial_equity) - 1.0
        else:
            metrics['total_return'] = 0.0
        
        # Calculate annualized return
        days = (equity_curve.index[-1] - equity_curve.index[0]).days
        if days > 0 and metrics['total_return'] > -1.0:
            years = days / 365.0
            metrics['annualized_return'] = (1.0 + metrics['total_return']) ** (1.0 / years) - 1.0
        else:
            metrics['annualized_return'] = 0.0
        
        # Calculate win rate and related metrics
        if close_trades:
            pnls = [trade.get('realized_pnl', 0) for trade in close_trades]
            winning_trades = [pnl for pnl in pnls if pnl > 0]
            losing_trades = [pnl for pnl in pnls if pnl <= 0]
            
            metrics['total_trades'] = len(close_trades)
            metrics['win_count'] = len(winning_trades)
            metrics['loss_count'] = len(losing_trades)
            
            # Win rate
            if metrics['total_trades'] > 0:
                metrics['win_rate'] = metrics['win_count'] / metrics['total_trades']
            else:
                metrics['win_rate'] = 0.0
            
            # Average profit and loss
            metrics['total_profit'] = sum(winning_trades) if winning_trades else 0.0
            metrics['total_loss'] = sum(losing_trades) if losing_trades else 0.0
            
            if winning_trades:
                metrics['avg_profit'] = metrics['total_profit'] / len(winning_trades)
            else:
                metrics['avg_profit'] = 0.0
                
            if losing_trades:
                metrics['avg_loss'] = metrics['total_loss'] / len(losing_trades)
            else:
                metrics['avg_loss'] = 0.0
            
            # Average trade
            metrics['avg_trade'] = sum(pnls) / len(pnls) if pnls else 0.0
            
            # Profit factor
            if metrics['total_loss'] != 0:
                metrics['profit_factor'] = abs(metrics['total_profit'] / metrics['total_loss'])
            else:
                metrics['profit_factor'] = float('inf') if metrics['total_profit'] > 0 else 0.0
            
            # Expectancy
            metrics['expectancy'] = metrics['win_rate'] * metrics['avg_profit'] + \
                                   (1 - metrics['win_rate']) * metrics['avg_loss']
            
            # Risk-adjusted expectancy
            if metrics['avg_loss'] != 0:
                metrics['risk_adjusted_expectancy'] = metrics['expectancy'] / abs(metrics['avg_loss'])
            else:
                metrics['risk_adjusted_expectancy'] = 0.0
        else:
            # No trades
            metrics['total_trades'] = 0
            metrics['win_count'] = 0
            metrics['loss_count'] = 0
            metrics['win_rate'] = 0.0
            metrics['avg_profit'] = 0.0
            metrics['avg_loss'] = 0.0
            metrics['avg_trade'] = 0.0
            metrics['profit_factor'] = 0.0
            metrics['expectancy'] = 0.0
            metrics['risk_adjusted_expectancy'] = 0.0
        
        # Calculate drawdown metrics
        drawdown_metrics = self._calculate_drawdown_metrics(equity_curve)
        metrics.update(drawdown_metrics)
        
        # Calculate daily returns and volatility
        returns = equity_curve.pct_change().dropna()
        
        if len(returns) > 1:
            metrics['daily_return_mean'] = returns.mean()
            metrics['daily_return_std'] = returns.std()
            
            # Annualized volatility
            annualization_factor = self.parameters['annualization_factor']
            metrics['annualized_volatility'] = returns.std() * math.sqrt(annualization_factor)
            
            # Calculate Sharpe Ratio
            if metrics['annualized_volatility'] > 0:
                excess_return = metrics['annualized_return'] - risk_free_rate
                metrics['sharpe_ratio'] = excess_return / metrics['annualized_volatility']
            else:
                metrics['sharpe_ratio'] = 0.0
        else:
            metrics['daily_return_mean'] = 0.0
            metrics['daily_return_std'] = 0.0
            metrics['annualized_volatility'] = 0.0
            metrics['sharpe_ratio'] = 0.0
        
        return metrics
    
    def _calculate_drawdown_metrics(self, equity_curve: pd.Series) -> Dict[str, float]:
        """
        Calculate drawdown-related metrics
        
        Args:
            equity_curve: Series with equity values
            
        Returns:
            Dictionary of drawdown metrics
        """
        if equity_curve.empty:
            return {
                'max_drawdown': 0.0,
                'max_drawdown_duration': 0,
                'current_drawdown': 0.0
            }
        
        # Calculate running maximum
        running_max = equity_curve.cummax()
        
        # Calculate drawdown percentage
        drawdown = (equity_curve / running_max) - 1.0
        
        # Find maximum drawdown
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        # Calculate current drawdown
        current_drawdown = abs(drawdown.iloc[-1]) if len(drawdown) > 0 else 0.0
        
        # Calculate drawdown duration
        is_in_drawdown = drawdown < 0
        drawdown_start = is_in_drawdown.astype(int).diff()
        drawdown_start[0] = 1 if is_in_drawdown[0] else 0
        
        # Find longest drawdown duration in days
        max_duration = 0
        if any(is_in_drawdown):
            # Group consecutive drawdown periods
            groups = (drawdown_start == 1).cumsum()
            for group in groups.unique():
                if any(is_in_drawdown[groups == group]):
                    group_indices = groups[is_in_drawdown & (groups == group)].index
                    if len(group_indices) > 1:
                        duration_days = (group_indices[-1] - group_indices[0]).days
                        max_duration = max(max_duration, duration_days)
        
        return {
            'max_drawdown': max_drawdown,
            'max_drawdown_duration': max_duration,
            'current_drawdown': current_drawdown
        }
    
    def _create_empty_metrics(self) -> Dict[str, float]:
        """
        Create a dictionary of empty metrics when data is insufficient
        
        Returns:
            Dictionary of metrics with default values
        """
        return {
            'initial_equity': 0.0,
            'final_equity': 0.0,
            'absolute_pnl': 0.0,
            'total_return': 0.0,
            'annualized_return': 0.0,
            'total_trades': 0,
            'win_count': 0,
            'loss_count': 0,
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'avg_trade': 0.0,
            'profit_factor': 0.0,
            'expectancy': 0.0,
            'risk_adjusted_expectancy': 0.0,
            'max_drawdown': 0.0,
            'max_drawdown_duration': 0,
            'current_drawdown': 0.0,
            'daily_return_mean': 0.0,
            'daily_return_std': 0.0,
            'annualized_volatility': 0.0,
            'sharpe_ratio': 0.0
        }


class AdvancedMetricsCalculator(MetricsCalculator):
    """
    Advanced performance metrics calculator
    
    Calculates advanced performance metrics including Sortino ratio, 
    Calmar ratio, VaR, and benchmark comparison metrics.
    
    Parameters:
    -----------
    annualization_factor : int
        Factor used to annualize returns (252 for daily data)
    var_confidence : float
        Confidence level for Value at Risk calculation (0.0 to 1.0)
    min_data_points : int
        Minimum data points required for advanced metrics
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Calculator parameters
        """
        default_params = {
            'annualization_factor': 252,  # Daily data by default
            'var_confidence': 0.95,       # 95% confidence for VaR
            'min_data_points': 20,        # Minimum data points for meaningful metrics
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
    
    def calculate(self, 
                 equity_curve: pd.Series, 
                 trade_history: List[Dict[str, Any]],
                 risk_free_rate: float = 0.0,
                 benchmark_returns: Optional[pd.Series] = None) -> Dict[str, float]:
        """
        Calculate advanced performance metrics
        
        Args:
            equity_curve: Series with equity values indexed by timestamp
            trade_history: List of trade dictionaries
            risk_free_rate: Risk-free rate for calculations (annual)
            benchmark_returns: Optional benchmark returns series
            
        Returns:
            Dictionary of calculated metrics
        """
        metrics = {}
        
        # Check if we have enough data
        if equity_curve.empty or len(equity_curve) < self.parameters['min_data_points']:
            return self._create_empty_metrics()
        
        # Calculate returns
        returns = equity_curve.pct_change().dropna()
        
        # Get annualization factor
        annualization_factor = self.parameters['annualization_factor']
        
        # Calculate Sortino ratio (using downside deviation)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_deviation = negative_returns.std() * np.sqrt(annualization_factor)
            if downside_deviation > 0:
                excess_return = (returns.mean() * annualization_factor) - risk_free_rate
                metrics['sortino_ratio'] = excess_return / downside_deviation
            else:
                metrics['sortino_ratio'] = 0.0
        else:
            metrics['sortino_ratio'] = float('inf')  # No negative returns
        
        # Calculate Calmar ratio (annualized return / max drawdown)
        running_max = equity_curve.cummax()
        drawdown = (equity_curve / running_max) - 1.0
        max_drawdown = abs(drawdown.min()) if len(drawdown) > 0 else 0.0
        
        if max_drawdown > 0:
            # Calculate annualized return
            days = (equity_curve.index[-1] - equity_curve.index[0]).days
            if days > 0:
                years = days / 365.0
                annualized_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (1.0 / years) - 1.0
                metrics['calmar_ratio'] = annualized_return / max_drawdown
            else:
                metrics['calmar_ratio'] = 0.0
        else:
            metrics['calmar_ratio'] = float('inf')  # No drawdown
        
        # Calculate Value at Risk (VaR)
        var_confidence = self.parameters['var_confidence']
        var_percentile = 1.0 - var_confidence
        
        metrics['value_at_risk'] = abs(returns.quantile(var_percentile))
        metrics['conditional_var'] = abs(returns[returns < -metrics['value_at_risk']].mean()) \
                                    if len(returns[returns < -metrics['value_at_risk']]) > 0 else metrics['value_at_risk']
        
        # Calculate Omega ratio (probability weighted ratio of gains to losses)
        threshold = 0.0  # Can be risk-free rate or custom threshold
        excess_returns = returns - threshold / annualization_factor
        
        if any(excess_returns < 0):
            positive_returns = excess_returns[excess_returns > 0].sum()
            negative_returns = abs(excess_returns[excess_returns < 0].sum())
            
            if negative_returns > 0:
                metrics['omega_ratio'] = positive_returns / negative_returns
            else:
                metrics['omega_ratio'] = float('inf')
        else:
            metrics['omega_ratio'] = float('inf')
        
        # Calculate Information Ratio if benchmark is provided
        if benchmark_returns is not None:
            # Align benchmark returns with equity curve dates
            aligned_benchmark = benchmark_returns.reindex(returns.index, method='ffill')
            
            # Calculate tracking error (standard deviation of excess returns)
            excess_returns = returns - aligned_benchmark
            tracking_error = excess_returns.std() * np.sqrt(annualization_factor)
            
            # Calculate annualized alpha and beta
            if len(aligned_benchmark) > 1 and aligned_benchmark.std() > 0:
                # Calculate beta (covariance / variance)
                cov_matrix = np.cov(returns, aligned_benchmark)
                beta = cov_matrix[0, 1] / np.var(aligned_benchmark)
                
                # Calculate alpha (annualized)
                alpha = (returns.mean() - beta * aligned_benchmark.mean()) * annualization_factor
                
                # Calculate information ratio
                if tracking_error > 0:
                    information_ratio = (returns.mean() - aligned_benchmark.mean()) * \
                                       annualization_factor / tracking_error
                else:
                    information_ratio = 0.0
                
                # Calculate correlation
                correlation = returns.corr(aligned_benchmark)
                
                # Add benchmark metrics
                metrics['alpha'] = alpha
                metrics['beta'] = beta
                metrics['tracking_error'] = tracking_error
                metrics['information_ratio'] = information_ratio
                metrics['correlation'] = correlation
            else:
                # Default benchmark metrics
                metrics['alpha'] = 0.0
                metrics['beta'] = 0.0
                metrics['tracking_error'] = 0.0
                metrics['information_ratio'] = 0.0
                metrics['correlation'] = 0.0
        else:
            # No benchmark provided
            metrics['alpha'] = 0.0
            metrics['beta'] = 0.0
            metrics['tracking_error'] = 0.0
            metrics['information_ratio'] = 0.0
            metrics['correlation'] = 0.0
        
        # Calculate Kurtosis and Skewness (distribution shape)
        if len(returns) > 3:
            metrics['skewness'] = returns.skew()
            metrics['kurtosis'] = returns.kurtosis()
        else:
            metrics['skewness'] = 0.0
            metrics['kurtosis'] = 0.0
        
        return metrics
    
    def _create_empty_metrics(self) -> Dict[str, float]:
        """
        Create a dictionary of empty metrics when data is insufficient
        
        Returns:
            Dictionary of metrics with default values
        """
        return {
            'sortino_ratio': 0.0,
            'calmar_ratio': 0.0,
            'value_at_risk': 0.0,
            'conditional_var': 0.0,
            'omega_ratio': 0.0,
            'alpha': 0.0,
            'beta': 0.0,
            'tracking_error': 0.0,
            'information_ratio': 0.0,
            'correlation': 0.0,
            'skewness': 0.0,
            'kurtosis': 0.0
        }