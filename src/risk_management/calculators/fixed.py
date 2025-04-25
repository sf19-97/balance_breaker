"""
Fixed percentage risk calculator
"""
from balance_breaker.src.risk_management.calculators.base import RiskCalculator
from balance_breaker.src.risk_management.models.base import MarketContext, AccountState, Direction


class FixedRiskCalculator(RiskCalculator):
    """
    Risk calculator that uses a fixed percentage of account balance
    
    Parameters:
    -----------
    risk_percent : float
        Risk percentage (0.01 = 1%)
    max_risk_percent : float
        Maximum risk percentage allowed
    """
    
    def __init__(self, parameters=None):
        default_params = {
            'risk_percent': 0.02,  # 2% risk per trade
            'max_risk_percent': 0.05  # 5% maximum risk
        }
        if parameters:
            default_params.update(parameters)
        
        super().__init__(default_params)
    
    def calculate_risk(self, context: MarketContext, account: AccountState, 
                      direction: Direction) -> float:
        """Calculate risk as fixed percentage of account"""
        # Apply risk adjustments based on market conditions
        risk_percent = self.parameters['risk_percent']
        
        # Lower risk during drawdown periods
        if account.drawdown > 0.1:  # 10% drawdown
            drawdown_factor = max(0.5, 1.0 - account.drawdown)
            risk_percent *= drawdown_factor
        
        # Enforce maximum risk
        risk_percent = min(risk_percent, self.parameters['max_risk_percent'])
        
        return risk_percent