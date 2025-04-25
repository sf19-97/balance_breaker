"""
Correlation-based trade adjuster
"""
from typing import Dict, Any, Optional

from balance_breaker.src.risk_management.models import TradeParameters


class CorrelationAdjuster:
    """
    Adjusts trade parameters based on portfolio correlation
    
    This adjuster can reduce position sizes when a trade is highly
    correlated with existing positions in the portfolio.
    
    Parameters:
    -----------
    max_correlation_exposure : float
        Maximum exposure for correlated instruments
    correlation_threshold : float
        Correlation threshold above which adjustment occurs
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'max_correlation_exposure': 0.10,  # 10% max for correlated instruments
            'correlation_threshold': 0.7,      # 0.7+ is considered highly correlated
            'reduction_factor': 0.5            # Reduce by 50% when correlated
        }
        if parameters:
            default_params.update(parameters)
        
        self.parameters = default_params
        
        # Correlation map (simple example - in practice would be more sophisticated)
        self.correlations = {
            'EURUSD': {'GBPUSD': 0.85, 'USDCHF': -0.80, 'USDJPY': 0.30},
            'GBPUSD': {'EURUSD': 0.85, 'USDCHF': -0.70, 'USDJPY': 0.25},
            'USDJPY': {'EURUSD': 0.30, 'GBPUSD': 0.25, 'USDCHF': 0.40},
            'USDCHF': {'EURUSD': -0.80, 'GBPUSD': -0.70, 'USDJPY': 0.40},
            'AUDUSD': {'EURUSD': 0.65, 'GBPUSD': 0.60, 'USDJPY': 0.20, 'USDCAD': -0.55},
            'USDCAD': {'AUDUSD': -0.55, 'EURUSD': -0.40, 'GBPUSD': -0.35}
        }
    
    def adjust_trade(self, trade_params: TradeParameters,
                   open_positions: Dict[str, Any]) -> TradeParameters:
        """
        Adjust trade parameters based on correlation with open positions
        
        Parameters:
        -----------
        trade_params : TradeParameters
            Original trade parameters
        open_positions : Dict[str, Any]
            Dictionary of current open positions
            
        Returns:
        --------
        TradeParameters
            Adjusted trade parameters
        """
        # Make a copy of the trade params to modify
        adjusted_params = trade_params
        
        # Check for correlations with existing positions
        instrument = trade_params.instrument
        correlation_exposure = 0.0
        
        for pos_instrument, position in open_positions.items():
            # Skip if same instrument (already handled by exposure manager)
            if pos_instrument == instrument:
                continue
            
            # Get correlation between instruments
            correlation = self._get_correlation(instrument, pos_instrument)
            
            # Check if correlation exceeds threshold
            if abs(correlation) >= self.parameters['correlation_threshold']:
                # For negative correlation, we actually want to increase exposure
                if correlation < 0:
                    continue
                
                # For positive correlation, add to correlation exposure
                # Weight by position size and risk
                position_exposure = position.get('risk_percent', 0.02)
                correlation_exposure += position_exposure * correlation
        
        # Reduce position size if correlation exposure exceeds threshold
        if correlation_exposure > self.parameters['max_correlation_exposure']:
            # Apply reduction factor
            reduction = self.parameters['reduction_factor']
            
            # Create new adjusted position size
            adjusted_size = trade_params.position_size * reduction
            
            # Update the trade parameters
            adjusted_params = TradeParameters(
                instrument=trade_params.instrument,
                direction=trade_params.direction,
                entry_price=trade_params.entry_price,
                stop_loss=trade_params.stop_loss,
                take_profit=trade_params.take_profit,
                position_size=adjusted_size,  # Reduced size
                risk_percent=trade_params.risk_percent * reduction  # Reduced risk
            )
        
        return adjusted_params
    
    def _get_correlation(self, instrument1: str, instrument2: str) -> float:
        """Get correlation between two instruments from correlation map"""
        if instrument1 in self.correlations and instrument2 in self.correlations[instrument1]:
            return self.correlations[instrument1][instrument2]
        elif instrument2 in self.correlations and instrument1 in self.correlations[instrument2]:
            return self.correlations[instrument2][instrument1]
        else:
            # Default to zero correlation if unknown
            return 0.0