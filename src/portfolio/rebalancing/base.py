"""
Base interface for portfolio rebalancers

This module defines the base Rebalancer interface that all rebalancing strategies must implement.
Rebalancers determine when and how to rebalance portfolio positions to maintain desired allocations.
"""

import logging
from abc import abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from balance_breaker.src.core.interface_registry import implements
from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, PortfolioError, ErrorSeverity, ErrorCategory
from balance_breaker.src.portfolio.interfaces import Rebalancer as IRebalancer
from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction


@implements("Rebalancer")
class Rebalancer(ParameterizedComponent, IRebalancer):
    """
    Base class for portfolio rebalancers
    
    Rebalancers determine when and how a portfolio should be rebalanced to 
    maintain target allocations or respond to changing market conditions.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Rebalancer parameters
        """
        super().__init__(parameters)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_handler = ErrorHandler(self.logger)
        self.name = self.__class__.__name__
    
    def should_rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                        current_time: datetime) -> bool:
        """
        Determine if the portfolio should be rebalanced
        
        This method calls the implementation method and handles errors.
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            current_time: Current timestamp
            
        Returns:
            True if portfolio should be rebalanced, False otherwise
        """
        try:
            return self._should_rebalance_impl(portfolio, current_prices, current_time)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Rebalance check error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.EXECUTION,
                    context={'portfolio_positions': len(portfolio.positions)},
                    original_exception=e
                )
            )
            # Conservative approach: return False on error
            return False
    
    @abstractmethod
    def _should_rebalance_impl(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                             current_time: datetime) -> bool:
        """
        Implementation method for rebalance logic - to be overridden by subclasses
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            current_time: Current timestamp
            
        Returns:
            True if portfolio should be rebalanced, False otherwise
        """
        pass
    
    def rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                 risk_manager: Any, timestamp: datetime) -> List[AllocationInstruction]:
        """
        Generate rebalancing instructions for the portfolio
        
        This method calls the implementation method and handles errors.
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Current timestamp
            
        Returns:
            List of rebalancing instructions
        """
        try:
            return self._rebalance_impl(portfolio, current_prices, risk_manager, timestamp)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Rebalance execution error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={'portfolio_positions': len(portfolio.positions)},
                    original_exception=e
                )
            )
            # Return empty instructions on error
            return []
    
    @abstractmethod
    def _rebalance_impl(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                      risk_manager: Any, timestamp: datetime) -> List[AllocationInstruction]:
        """
        Implementation method for rebalance execution - to be overridden by subclasses
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Current timestamp
            
        Returns:
            List of rebalancing instructions
        """
        pass
    
    def get_target_weights(self, portfolio: Portfolio) -> Dict[str, float]:
        """
        Get target weights for portfolio positions
        
        This helper method provides a default implementation that returns equal weights.
        Subclasses can override this method to provide different weighting schemes.
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        position_count = len(portfolio.positions)
        if position_count == 0:
            return {}
            
        equal_weight = 1.0 / position_count
        return {instrument: equal_weight for instrument in portfolio.positions}