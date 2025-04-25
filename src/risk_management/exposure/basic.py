"""
Basic exposure manager implementation
"""
from typing import Dict, Any, List


class BasicExposureManager:
    """
    Manages overall account exposure
    
    Parameters:
    -----------
    max_total_risk : float
        Maximum total risk as percentage of account (e.g., 0.10 = 10%)
    max_correlated_risk : float
        Maximum risk for correlated instruments
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        default_params = {
            'max_total_risk': 0.10,        # 10% max total risk
            'max_correlated_risk': 0.06,   # 6% max correlated risk
            'max_instruments': 5,          # Max concurrent instruments
        }
        if parameters:
            default_params.update(parameters)
        
        self.parameters = default_params
        self.current_exposure = {}
    
    def check_exposure(self, instrument: str, risk_amount: float, 
                      direction: int) -> bool:
        """
        Check if a trade would exceed exposure limits
        
        Parameters:
        -----------
        instrument : str
            Instrument being traded
        risk_amount : float
            Risk amount as percentage of account
        direction : int
            Trade direction (1 for long, -1 for short)
            
        Returns:
        --------
        bool
            True if trade is acceptable, False if it would exceed limits
        """
        # Update the current exposure with this potential trade
        total_exposure = sum(self.current_exposure.values()) + risk_amount
        
        # Basic checks
        if total_exposure > self.parameters['max_total_risk']:
            return False
        
        if len(self.current_exposure) >= self.parameters['max_instruments']:
            return False
        
        # Simple correlation check (just using instrument prefix)
        # A more sophisticated implementation would use actual correlations
        instrument_prefix = instrument[:3]  # e.g., "USD" from "USDJPY"
        correlated_exposure = 0
        
        for instr, risk in self.current_exposure.items():
            if instr[:3] == instrument_prefix:
                correlated_exposure += risk
        
        if correlated_exposure + risk_amount > self.parameters['max_correlated_risk']:
            return False
        
        return True
    
    def add_exposure(self, instrument: str, risk_amount: float):
        """Record a new trade exposure"""
        self.current_exposure[instrument] = risk_amount
    
    def remove_exposure(self, instrument: str):
        """Remove an instrument from exposure"""
        if instrument in self.current_exposure:
            del self.current_exposure[instrument]