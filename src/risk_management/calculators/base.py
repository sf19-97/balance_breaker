"""
Base class for take profit calculators
"""

import logging
from abc import abstractmethod
from typing import Dict, Any, Optional, List, Union

from balance_breaker.src.core.interface_registry import implements
from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, RiskManagementError, ErrorSeverity, ErrorCategory
from balance_breaker.src.risk_management.interfaces import TakeProfitCalculator as ITakeProfitCalculator


@implements("TakeProfitCalculator")
class TakeProfitCalculator(ParameterizedComponent, ITakeProfitCalculator):
    """
    Base class for take profit calculators
    
    Take profit calculators determine take profit levels based on
    instrument, price, stop loss, and risk parameters.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize calculator with parameters
        
        Args:
            parameters: Take profit calculator parameters
        """
        super().__init__(parameters)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_handler = ErrorHandler(self.logger)
        self.name = self.__class__.__name__
    
    def calculate_take_profit(self, context: Dict[str, Any]) -> Union[float, List[float]]:
        """
        Calculate take profit level(s)
        
        This method calls the implementation method and handles errors.
        
        Args:
            context: Risk context including:
                - entry_price: Entry price
                - direction: Trade direction (1 for long, -1 for short)
                - stop_loss: Stop loss price level
                - instrument: Instrument name
                - additional parameters as needed
            
        Returns:
            Take profit price level or list of levels for multiple targets
        """
        try:
            # Validate required context keys
            required_keys = ['entry_price', 'direction', 'instrument']
            if not self.validate_context(context, required_keys):
                raise ValueError(f"Missing required context keys: {[k for k in required_keys if k not in context]}")
            
            return self._calculate_take_profit_impl(context)
        except Exception as e:
            self.error_handler.handle_error(
                RiskManagementError(
                    message=f"Take profit calculation error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context=context,
                    original_exception=e
                )
            )
            # Default fallback (2% of price)
            entry_price = context.get('entry_price', 0)
            direction = context.get('direction', 0)
            if entry_price > 0 and direction in [-1, 1]:
                return entry_price * (1 + 0.02 * direction)
            else:
                return 0.0
    
    @abstractmethod
    def _calculate_take_profit_impl(self, context: Dict[str, Any]) -> Union[float, List[float]]:
        """
        Implementation method for take profit calculation
        
        Args:
            context: Risk context
            
        Returns:
            Take profit price level or list of levels for multiple targets
        """
        pass
    
    def validate_context(self, context: Dict[str, Any], required_keys: List[str]) -> bool:
        """
        Validate that required context keys are present
        
        Args:
            context: Risk context
            required_keys: List of required keys
            
        Returns:
            True if all required keys are present, False otherwise
        """
        missing_keys = [key for key in required_keys if key not in context]
        if missing_keys:
            self.logger.warning(f"Missing required context keys: {missing_keys}")
            return False
        return True