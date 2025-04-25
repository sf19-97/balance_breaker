"""
Fixed pips stop loss calculator
"""
from typing import Dict, Any

from balance_breaker.src.risk_management.models.base import MarketContext, Direction


class FixedPipsStopCalculator:
    """
    Sets stop loss at fixed pip distance from entry
    
    Parameters:
    -----------
    stop_pips : float
        Distance in pips for stop loss
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'stop_pips': 50.0,
        }
        if parameters:
            default_params.update(parameters)
        
        self.parameters = default_params
        self.name = self.__class__.__name__
    
    def calculate_stop_loss(self, context: MarketContext, direction: Direction) -> float:
        """
        Calculate stop loss price level
        
        Parameters:
        -----------
        context : MarketContext
            Current market context
        direction : Direction
            Trade direction
            
        Returns:
        --------
        float
            Stop loss price level
        """
        stop_pips = self.parameters['stop_pips']
        pip_value = 1.0 / context.pip_factor
        stop_distance = stop_pips * pip_value
        
        # Calculate stop level based on direction
        if direction == Direction.LONG:
            return context.price - stop_distance
        else:  # SHORT
            return context.price + stop_distance