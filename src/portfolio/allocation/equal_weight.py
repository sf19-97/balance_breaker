"""
Equal Weight Allocation Strategy

This allocator distributes capital equally across all instruments with valid signals.
"""

from typing import Dict, Any, Optional
import logging

from balance_breaker.src.portfolio.models import Portfolio
from balance_breaker.src.portfolio.allocation.base import Allocator


class EqualWeightAllocator(Allocator):
    """
    Equal Weight Allocator
    
    This allocator distributes capital equally across all instruments with valid signals.
    It's the simplest allocation strategy and serves as a baseline.
    
    Parameters:
    -----------
    min_signal_strength : float
        Minimum signal strength to include an instrument (0.0 to 1.0)
    max_instruments : int
        Maximum number of instruments to include
    weight_cap : float
        Maximum weight for any single instrument (0.0 to 1.0)
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Allocator parameters
        """
        default_params = {
            'min_signal_strength': 0.0,  # No minimum by default
            'max_instruments': 10,       # Default max instruments
            'weight_cap': 0.25          # Maximum 25% allocation per instrument
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
    
    def allocate(self, signals: Dict[str, Dict[str, Any]], portfolio: Portfolio) -> Dict[str, float]:
        """
        Allocate capital equally across instruments with valid signals
        
        Args:
            signals: Dictionary of signals by instrument
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        if not signals:
            return {}
        
        self.logger.info(f"Allocating with equal weight across {len(signals)} instruments")
        
        # Filter signals by minimum strength
        min_strength = self.parameters['min_signal_strength']
        valid_signals = {}
        
        for instrument, signal in signals.items():
            # Skip instruments with no direction
            if signal.get('direction', 0) == 0:
                continue
                
            # If signal strength is provided, check against minimum
            strength = signal.get('strength', 1.0)
            if strength >= min_strength:
                valid_signals[instrument] = signal
        
        if not valid_signals:
            self.logger.info("No valid signals after filtering")
            return {}
        
        # Limit to max instruments if needed
        max_instruments = self.parameters['max_instruments']
        if len(valid_signals) > max_instruments:
            # Sort by signal strength if available
            sorted_signals = sorted(
                valid_signals.items(), 
                key=lambda x: x[1].get('strength', 1.0),
                reverse=True
            )
            # Keep only the top signals
            valid_signals = dict(sorted_signals[:max_instruments])
            
            self.logger.info(f"Limited to top {max_instruments} instruments by signal strength")
        
        # Calculate equal weight
        count = len(valid_signals)
        weight = 1.0 / count if count > 0 else 0.0
        
        # Apply weight cap if needed
        weight_cap = self.parameters['weight_cap']
        if weight > weight_cap:
            weight = weight_cap
            self.logger.info(f"Capped weight to {weight_cap}")
        
        # Create weights dictionary
        weights = {instrument: weight for instrument in valid_signals}
        
        self.logger.info(f"Allocated equal weight of {weight:.2%} to {count} instruments")
        return weights