"""Complete risk management implementation"""
from typing import Dict, Any, Optional

from balance_breaker.src.risk_management.models import TradeParameters, Direction
from balance_breaker.src.risk_management.exposure.basic import BasicExposureManager
from balance_breaker.src.risk_management.targets.ratio import RiskRewardRatioCalculator
from balance_breaker.src.risk_management.adjusters.correlation import CorrelationAdjuster


class RiskManager:
    """
    Comprehensive risk manager for trading systems
    
    This manager orchestrates all risk-related decisions including:
    - Position sizing based on account risk
    - Stop loss placement
    - Take profit targets
    - Exposure management
    - Correlation-based adjustments
    """
    
    def __init__(self, config=None):
        """
        Initialize the risk manager
        
        Parameters:
        -----------
        config : dict, optional
            Configuration dictionary with the following possible keys:
            - risk_percent: Default risk per trade (as decimal)
            - stop_pips: Default stop distance in pips
            - min_position: Minimum position size
            - max_position: Maximum position size
            - exposure: Exposure manager parameters
            - take_profit: Take profit calculator parameters
            - adjuster: Trade adjuster parameters
        """
        self.config = config or {}
        self.default_risk = 0.02  # 2% risk per trade
        
        # Initialize exposure manager
        exposure_config = self.config.get('exposure', {})
        self.exposure_manager = BasicExposureManager(exposure_config)
        
        # Initialize take profit calculator
        tp_config = self.config.get('take_profit', {})
        self.tp_calculator = RiskRewardRatioCalculator(tp_config)
        
        # Initialize trade adjuster
        adjuster_config = self.config.get('adjuster', {})
        self.trade_adjuster = CorrelationAdjuster(adjuster_config)
    
    def calculate_trade_parameters(self, instrument: str, price: float, 
                                  direction: Direction, balance: float, 
                                  pip_factor: float = 10000,
                                  open_positions: Dict[str, Any] = None) -> Optional[TradeParameters]:
        """
        Calculate complete trade parameters
        
        Parameters:
        -----------
        instrument : str
            Trading instrument (e.g., 'EURUSD')
        price : float
            Current price/entry price
        direction : Direction
            Trade direction (Direction.LONG or Direction.SHORT)
        balance : float
            Account balance
        pip_factor : float, optional
            Pip calculation factor (10000 for most pairs, 100 for JPY pairs)
        open_positions : Dict[str, Any], optional
            Dictionary of current open positions for correlation adjustment
            
        Returns:
        --------
        TradeParameters or None
            Complete trade parameters or None if trade rejected
        """
        # Normalize direction to int if it's not already
        dir_value = direction.value if isinstance(direction, Direction) else direction
        
        # 1. Set risk amount
        risk_percent = self.config.get('risk_percent', self.default_risk)
        
        # 2. Check exposure limits
        if not self.exposure_manager.check_exposure(instrument, risk_percent, dir_value):
            return None  # Trade rejected due to exposure limits
        
        # 3. Set stop loss (simple fixed pip stop)
        stop_loss = self.calculate_stop_loss(price, dir_value, pip_factor)
        
        # 4. Calculate position size
        position_size = self.calculate_position_size(balance, risk_percent, 
                                                   stop_loss, price, pip_factor)
        
        # 5. Calculate take profit using the target calculator
        take_profit = self.tp_calculator.calculate_take_profit(price, stop_loss, dir_value)
        
        # 6. Create trade parameters
        trade_params = TradeParameters(
            instrument=instrument,
            direction=dir_value,
            entry_price=price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            position_size=position_size,
            risk_percent=risk_percent
        )
        
        # 7. Apply final adjustments if open positions are provided
        if open_positions:
            trade_params = self.trade_adjuster.adjust_trade(trade_params, open_positions)
        
        # 8. Record exposure (using adjusted risk)
        self.exposure_manager.add_exposure(instrument, trade_params.risk_percent)
        
        return trade_params
    
    def calculate_stop_loss(self, price: float, direction: int, pip_factor: float) -> float:
        """
        Calculate stop loss level
        
        Parameters:
        -----------
        price : float
            Entry price
        direction : int
            Trade direction (1 for long, -1 for short)
        pip_factor : float
            Pip calculation factor
            
        Returns:
        --------
        float
            Stop loss price level
        """
        stop_pips = self.config.get('stop_pips', 50)
        pip_value = 1.0 / pip_factor
        stop_distance = stop_pips * pip_value
        
        if direction == 1:  # LONG
            return price - stop_distance
        else:  # SHORT
            return price + stop_distance
    
    def calculate_position_size(self, balance: float, risk_percent: float, 
                               stop_loss: float, entry_price: float, 
                               pip_factor: float) -> float:
        """
        Calculate position size based on risk and stop distance
        
        Parameters:
        -----------
        balance : float
            Account balance
        risk_percent : float
            Risk percentage (0.02 = 2%)
        stop_loss : float
            Stop loss price level
        entry_price : float
            Entry price
        pip_factor : float
            Pip calculation factor
            
        Returns:
        --------
        float
            Position size in lots
        """
        # Risk amount in account currency
        risk_amount = balance * risk_percent
        
        # Calculate stop distance in pips
        stop_distance_price = abs(entry_price - stop_loss)
        stop_distance_pips = stop_distance_price * pip_factor
        
        # Standard lot pip value (approximate - should be specified per currency pair and account currency)
        standard_lot_pip_value = 10.0
        
        # Calculate position size
        position_size = risk_amount / (stop_distance_pips * standard_lot_pip_value)
        
        # Round to 0.01 lots
        position_size = round(position_size * 100) / 100
        
        # Apply min/max constraints
        min_position = self.config.get('min_position', 0.01)
        max_position = self.config.get('max_position', 10.0)
        
        position_size = max(position_size, min_position)
        position_size = min(position_size, max_position)
        
        return position_size
    
    def remove_exposure(self, instrument: str):
        """
        Remove instrument from exposure tracking
        
        Call this when a trade is closed
        
        Parameters:
        -----------
        instrument : str
            Instrument to remove
        """
        self.exposure_manager.remove_exposure(instrument)
    
    def get_current_exposure(self) -> Dict[str, float]:
        """
        Get current exposure information
        
        Returns:
        --------
        Dict[str, float]
            Current exposure by instrument
        """
        return self.exposure_manager.current_exposure
    
    def adjust_for_drawdown(self, drawdown: float):
        """
        Adjust risk parameters based on account drawdown
        
        Parameters:
        -----------
        drawdown : float
            Current drawdown as a decimal (0.10 = 10% drawdown)
        """
        if drawdown > 0.05:  # Only adjust if drawdown exceeds 5%
            # Reduce risk linearly based on drawdown
            reduction_factor = max(0.5, 1.0 - drawdown)  # Reduce risk up to 50%
            
            # Update the default risk
            self.default_risk = self.config.get('risk_percent', 0.02) * reduction_factor