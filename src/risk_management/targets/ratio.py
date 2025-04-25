"""
Risk:Reward ratio based take profit calculator
"""
from typing import Dict, Any, List


class RiskRewardRatioCalculator:
    """
    Sets take profit based on risk:reward ratio from stop loss
    
    Parameters:
    -----------
    risk_reward_ratio : float
        Reward to risk ratio (e.g., 2.0 = 2:1 R:R)
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'risk_reward_ratio': 2.0,
        }
        if parameters:
            default_params.update(parameters)
        
        self.parameters = default_params
    
    def calculate_take_profit(self, entry_price: float, stop_loss: float, direction: int) -> float:
        """
        Calculate take profit level based on risk:reward ratio
        
        Parameters:
        -----------
        entry_price : float
            Entry price
        stop_loss : float
            Stop loss price level
        direction : int
            Trade direction (1 for long, -1 for short)
            
        Returns:
        --------
        float
            Take profit price level
        """
        stop_distance = abs(entry_price - stop_loss)
        
        # Calculate take profit distance using R:R ratio
        tp_distance = stop_distance * self.parameters['risk_reward_ratio']
        
        # Calculate take profit level based on direction
        if direction == 1:  # LONG
            take_profit = entry_price + tp_distance
        else:  # SHORT
            take_profit = entry_price - tp_distance
        
        return take_profit