"""
Risk Parity Allocation Strategy

This allocator distributes risk equally across all instruments instead of capital.
"""

from typing import Dict, Any, Optional, List
import logging
import numpy as np
import pandas as pd
from scipy import optimize

from balance_breaker.src.portfolio.models import Portfolio
from balance_breaker.src.portfolio.allocation.base import Allocator


class RiskParityAllocator(Allocator):
    """
    Risk Parity Allocator
    
    This allocator distributes risk rather than capital equally across instruments.
    It aims to achieve equal risk contribution from each instrument in the portfolio.
    
    Parameters:
    -----------
    volatility_lookback : int
        Number of periods to use for volatility calculation
    correlation_lookback : int
        Number of periods to use for correlation calculation
    min_weight : float
        Minimum weight for any instrument (0.0 to 1.0)
    max_weight : float
        Maximum weight for any instrument (0.0 to 1.0)
    risk_target : float
        Target portfolio risk level
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Allocator parameters
        """
        default_params = {
            'volatility_lookback': 60,   # 60 periods for volatility
            'correlation_lookback': 120, # 120 periods for correlation
            'min_weight': 0.05,          # Minimum 5% allocation
            'max_weight': 0.25,          # Maximum 25% allocation
            'risk_target': 0.1           # 10% annualized risk target
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
        
        # Cache for volatility and correlation data
        self.volatility_cache = {}
        self.correlation_matrix = None
        self.historical_data = {}
    
    def allocate(self, signals: Dict[str, Dict[str, Any]], portfolio: Portfolio) -> Dict[str, float]:
        """
        Allocate with risk parity across instruments
        
        Args:
            signals: Dictionary of signals by instrument
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        if not signals:
            return {}
        
        self.logger.info(f"Allocating with risk parity across {len(signals)} instruments")
        
        # Get instruments with valid signals (non-zero direction)
        valid_instruments = [instr for instr, signal in signals.items() if signal.get('direction', 0) != 0]
        
        if not valid_instruments:
            return {}
        
        # Try to get volatility and correlation data
        # In a real implementation, this would come from:
        # 1. Historical price data passed to the allocator
        # 2. Volatility and correlation estimates from market data
        # 3. Risk model estimates
        
        # For this example, we'll use signal metadata if available, or defaults
        volatilities = self._get_volatilities(signals, valid_instruments)
        correlation_matrix = self._get_correlation_matrix(signals, valid_instruments)
        
        # Calculate covariance matrix
        cov_matrix = self._calculate_covariance(volatilities, correlation_matrix)
        
        # Calculate risk parity weights
        weights = self._calculate_risk_parity_weights(valid_instruments, cov_matrix)
        
        # Adjust for signal direction (flip weights for short signals)
        for instrument in valid_instruments:
            direction = signals[instrument].get('direction', 1)
            if direction < 0:
                weights[instrument] *= 0.8  # Reduce short position sizes by 20%
        
        self.logger.info(f"Allocated risk parity weights to {len(weights)} instruments")
        return weights
    
    def _get_volatilities(self, signals: Dict[str, Dict[str, Any]], 
                         instruments: List[str]) -> Dict[str, float]:
        """Get volatilities for instruments"""
        volatilities = {}
        
        for instrument in instruments:
            # Try to get volatility from signal metadata
            if 'volatility' in signals[instrument]:
                volatilities[instrument] = signals[instrument]['volatility']
            elif instrument in self.volatility_cache:
                # Use cached volatility if available
                volatilities[instrument] = self.volatility_cache[instrument]
            else:
                # Use default by instrument type
                if 'JPY' in instrument:
                    volatilities[instrument] = 0.08  # 8% annualized for JPY pairs
                else:
                    volatilities[instrument] = 0.10  # 10% annualized for other pairs
        
        return volatilities
    
    def _get_correlation_matrix(self, signals: Dict[str, Dict[str, Any]], 
                               instruments: List[str]) -> np.ndarray:
        """Get correlation matrix for instruments"""
        n = len(instruments)
        
        # If we have a cached correlation matrix, use it
        if self.correlation_matrix is not None and self.correlation_matrix.shape[0] == n:
            return self.correlation_matrix
        
        # Create a default correlation matrix
        # In a real implementation, this would be calculated from historical data
        correlation_matrix = np.eye(n)  # Identity matrix (all 1's on diagonal, 0's elsewhere)
        
        # Add some realistic correlation values
        for i in range(n):
            for j in range(i+1, n):
                instr_i = instruments[i]
                instr_j = instruments[j]
                
                # Assign correlations based on currency pairs
                # These are simplified approximations
                if 'USD' in instr_i and 'USD' in instr_j:
                    # USD pairs tend to be correlated
                    correlation_matrix[i, j] = 0.5
                elif 'EUR' in instr_i and 'GBP' in instr_j or 'EUR' in instr_j and 'GBP' in instr_i:
                    # EUR and GBP tend to be highly correlated
                    correlation_matrix[i, j] = 0.7
                elif 'AUD' in instr_i and 'NZD' in instr_j or 'AUD' in instr_j and 'NZD' in instr_i:
                    # AUD and NZD tend to be highly correlated
                    correlation_matrix[i, j] = 0.8
                elif 'USD' in instr_i and 'JPY' in instr_j or 'USD' in instr_j and 'JPY' in instr_i:
                    # USD and JPY can be negatively correlated in risk-off environments
                    correlation_matrix[i, j] = -0.3
                else:
                    # Default low correlation
                    correlation_matrix[i, j] = 0.2
                
                # Correlation matrix is symmetric
                correlation_matrix[j, i] = correlation_matrix[i, j]
        
        return correlation_matrix
    
    def _calculate_covariance(self, volatilities: Dict[str, float], 
                             correlation_matrix: np.ndarray) -> np.ndarray:
        """Calculate covariance matrix from volatilities and correlations"""
        instruments = list(volatilities.keys())
        n = len(instruments)
        
        # Create volatility vector
        vol_vector = np.array([volatilities[instr] for instr in instruments])
        
        # Create volatility matrix (diagonal matrix with volatilities)
        vol_matrix = np.diag(vol_vector)
        
        # Calculate covariance matrix: Σ = D * R * D
        # Where D is diagonal matrix of volatilities and R is correlation matrix
        cov_matrix = vol_matrix @ correlation_matrix @ vol_matrix
        
        return cov_matrix
    
    def _calculate_risk_parity_weights(self, instruments: List[str], 
                                      cov_matrix: np.ndarray) -> Dict[str, float]:
        """
        Calculate risk parity weights using numerical optimization
        
        This implements a simplified risk parity algorithm that aims to equalize
        risk contribution from each asset in the portfolio.
        """
        n = len(instruments)
        
        if n == 0:
            return {}
        
        if n == 1:
            return {instruments[0]: 1.0}
        
        # Initial guess: equal weight
        initial_weights = np.ones(n) / n
        
        # Ensure covariance matrix is positive definite
        cov_matrix = np.clip(cov_matrix, 1e-8, None)
        
        # Define risk contribution function
        def risk_contribution(weights):
            # Portfolio variance
            portfolio_var = weights.T @ cov_matrix @ weights
            
            # Risk contribution of each asset
            marginal_risk = cov_matrix @ weights
            risk_contrib = weights * marginal_risk / np.sqrt(portfolio_var)
            
            # Target: equal risk contribution
            target_risk = np.sqrt(portfolio_var) / n
            
            # Squared error between actual and target risk contribution
            error = np.sum((risk_contrib - target_risk) ** 2)
            
            return error
        
        # Constraint: weights sum to 1
        constraint = {'type': 'eq', 'fun': lambda w: np.sum(w) - 1}
        
        # Weight bounds
        min_weight = self.parameters['min_weight']
        max_weight = self.parameters['max_weight']
        bounds = [(min_weight, max_weight) for _ in range(n)]
        
        # Solve optimization problem
        result = optimize.minimize(
            risk_contribution, 
            initial_weights, 
            method='SLSQP',
            constraints=constraint,
            bounds=bounds
        )
        
        # Get optimized weights
        optimal_weights = result.x
        
        # Normalize weights to sum to 1 (in case of numerical issues)
        optimal_weights = optimal_weights / np.sum(optimal_weights)
        
        # Create weights dictionary
        weights = {instruments[i]: float(optimal_weights[i]) for i in range(n)}
        
        # Log risk contributions
        portfolio_var = optimal_weights.T @ cov_matrix @ optimal_weights
        portfolio_vol = np.sqrt(portfolio_var)
        
        marginal_risk = cov_matrix @ optimal_weights
        risk_contrib = optimal_weights * marginal_risk / portfolio_vol
        
        risk_contributions = {instruments[i]: float(risk_contrib[i]) for i in range(n)}
        
        self.logger.info(f"Portfolio volatility: {portfolio_vol:.2%}")
        self.logger.info(f"Risk contributions: {risk_contributions}")
        
        return weights
    
    def update_historical_data(self, data: Dict[str, pd.DataFrame]) -> None:
        """
        Update historical data for volatility and correlation calculations
        
        Args:
            data: Dictionary of historical price data by instrument
        """
        self.historical_data = data
        
        # Update volatility cache
        lookback = self.parameters['volatility_lookback']
        
        for instrument, prices in data.items():
            if len(prices) >= lookback:
                returns = prices['close'].pct_change().dropna()
                if len(returns) >= lookback:
                    # Calculate annualized volatility
                    vol = returns.tail(lookback).std() * np.sqrt(252)  # Assuming daily data
                    self.volatility_cache[instrument] = vol
        
        # Update correlation matrix
        self._update_correlation_matrix()
    
    def _update_correlation_matrix(self) -> None:
        """Update correlation matrix from historical data"""
        if not self.historical_data:
            return
        
        # Get instruments with enough data
        lookback = self.parameters['correlation_lookback']
        valid_instruments = []
        returns_data = {}
        
        for instrument, prices in self.historical_data.items():
            if len(prices) >= lookback:
                returns = prices['close'].pct_change().dropna()
                if len(returns) >= lookback:
                    valid_instruments.append(instrument)
                    returns_data[instrument] = returns.tail(lookback)
        
        if len(valid_instruments) < 2:
            return
        
        # Create returns DataFrame
        returns_df = pd.DataFrame({instr: returns_data[instr] for instr in valid_instruments})
        
        # Calculate correlation matrix
        self.correlation_matrix = returns_df.corr().values