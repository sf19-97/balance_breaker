"""
Base interface for portfolio allocation strategies
"""

import logging
from typing import Dict, Any, Optional

from balance_breaker.src.core.interface_registry import implements
from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, PortfolioError, ErrorSeverity, ErrorCategory
from balance_breaker.src.portfolio.interfaces import Allocator as IAllocator
from balance_breaker.src.portfolio.models import Portfolio


@implements("Allocator")
class Allocator(ParameterizedComponent, IAllocator):
    """
    Base class for portfolio allocators
    
    Allocators determine how to distribute capital across different instruments
    based on signals, portfolio state, and market conditions.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Allocator parameters
        """
        super().__init__(parameters)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_handler = ErrorHandler(self.logger)
        self.name = self.__class__.__name__
    
    def allocate(self, signals: Dict[str, Dict[str, Any]], portfolio: Portfolio) -> Dict[str, float]:
        """
        Allocate capital across instruments based on signals
        
        Args:
            signals: Dictionary of signals by instrument
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        try:
            return self._allocate_impl(signals, portfolio)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Allocation error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={
                        'signals_count': len(signals),
                        'portfolio_positions': len(portfolio.positions)
                    },
                    original_exception=e
                )
            )
            # Return empty allocation on error
            return {}
            
    def _allocate_impl(self, signals: Dict[str, Dict[str, Any]], portfolio: Portfolio) -> Dict[str, float]:
        """
        Implementation method for allocation logic - to be overridden by subclasses
        
        Args:
            signals: Dictionary of signals by instrument
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        raise NotImplementedError("Subclasses must implement this method")