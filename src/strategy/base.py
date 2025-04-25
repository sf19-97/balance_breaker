# src/strategy/base.py
from abc import ABC, abstractmethod

class Strategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, name, signal_generator=None, risk_manager=None, parameters=None):
        """
        Initialize the strategy.
        
        Parameters:
        -----------
        name : str
            Strategy name
        signal_generator : object, optional
            Signal generator component
        risk_manager : object, optional
            Risk management component
        parameters : dict, optional
            Strategy parameters
        """
        self.name = name
        self.signal_generator = signal_generator
        self.risk_manager = risk_manager
        self.parameters = parameters or {}
    
    @abstractmethod
    def generate_signal(self, current_data, historical_data=None):
        """
        Generate trading signal based on data.
        
        Parameters:
        -----------
        current_data : dict
            Current market data point
        historical_data : pd.DataFrame, optional
            Historical data for context
            
        Returns:
        --------
        tuple
            (signal, metrics) where signal is a string and metrics is a dict
        """
        pass
    
    def calculate_position_size(self, context):
        """
        Calculate position size using risk manager.
        
        Parameters:
        -----------
        context : dict
            Trading context including entry price, account balance, etc.
            
        Returns:
        --------
        float
            Position size
        """
        if self.risk_manager:
            return self.risk_manager.calculate_position_size(context)
        
        # Default fixed size if no risk manager
        return 1.0
    
    def calculate_exit_levels(self, context):
        """
        Calculate stop loss and take profit levels.
        
        Parameters:
        -----------
        context : dict
            Trading context
            
        Returns:
        --------
        tuple
            (stop_loss, take_profit) price levels
        """
        if self.risk_manager:
            stop_loss = self.risk_manager.calculate_stop_loss(context)
            take_profit = self.risk_manager.calculate_take_profit(context)
            return stop_loss, take_profit
        
        # Default fixed pip values if no risk manager
        direction = context.get('direction', 1)
        entry_price = context.get('entry_price', 0)
        pip_factor = context.get('pip_factor', 10000)
        
        # Default values in pips
        sl_pips = self.parameters.get('sl_pips', 100)
        tp_pips = self.parameters.get('tp_pips', 300)
        
        # Convert to price terms
        sl_price = entry_price - (direction * sl_pips / pip_factor)
        tp_price = entry_price + (direction * tp_pips / pip_factor)
        
        return sl_price, tp_price
    
    def get_parameters(self):
        """Get strategy parameters"""
        return self.parameters
    
    def set_parameters(self, parameters):
        """Set strategy parameters"""
        if parameters:
            self.parameters.update(parameters)
            
    def reset(self):
        """Reset strategy state"""
        if self.signal_generator and hasattr(self.signal_generator, 'reset'):
            self.signal_generator.reset()