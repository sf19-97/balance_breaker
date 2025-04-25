"""
Standard position sizer implementation
"""
from balance_breaker.src.risk_management.position.base import PositionSizer
from balance_breaker.src.risk_management.models.base import MarketContext, AccountState, Direction


class StandardPositionSizer(PositionSizer):
    """
    Standard position sizer based on risk amount and stop distance
    
    Parameters:
    -----------
    min_position : float
        Minimum position size allowed
    max_position : float
        Maximum position size allowed
    position_rounding : float
        Rounding increment for position sizing
    """
    
    def __init__(self, parameters=None):
        default_params = {
            'min_position': 0.01,  # Minimum position size
            'max_position': 10.0,  # Maximum position size
            'position_rounding': 0.01  # Round to 0.01 lots
        }
        if parameters:
            default_params.update(parameters)
        
        super().__init__(default_params)
    
    def calculate_position_size(self, context: MarketContext, account: AccountState,
                               direction: Direction, risk_amount: float,
                               stop_loss: float = None) -> float:
        """
        Calculate position size based on risk amount and stop distance
        
        This uses the formula:
        position_size = (account_balance * risk_percent) / (entry_price - stop_loss) * pip_factor
        """
        entry_price = context.price
        
        # If stop loss not provided, use a default distance
        if stop_loss is None:
            default_stop_pips = 50
            pip_value = 1.0 / context.pip_factor
            stop_distance = default_stop_pips * pip_value
            
            stop_loss = entry_price - stop_distance if direction == Direction.LONG else entry_price + stop_distance
        
        # Calculate stop distance in price terms
        stop_distance = abs(entry_price - stop_loss)
        
        # Avoid division by zero
        if stop_distance <= 0:
            return self.parameters['min_position']
        
        # Calculate risk amount in account currency
        risk_amount_currency = account.balance * risk_amount
        
        # Calculate position size
        # For a 1 lot position, a 1 pip move = pip_value currency units
        # So position_size = risk_amount / (stop_distance_in_pips * pip_value_per_pip)
        stop_distance_pips = stop_distance * context.pip_factor
        
        # Different brokers have different pip values, so this is simplified
        # A more complete implementation would include specific pip value calculations
        standard_lot_pip_value = 10.0  # Typical value for 1 standard lot
        
        position_size = risk_amount_currency / (stop_distance_pips * standard_lot_pip_value)
        
        # Apply min/max constraints
        position_size = max(position_size, self.parameters['min_position'])
        position_size = min(position_size, self.parameters['max_position'])
        
        # Round to specified increment
        increment = self.parameters['position_rounding']
        position_size = round(position_size / increment) * increment
        
        return position_size