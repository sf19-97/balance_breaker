"""
Base interface for position sizers
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from balance_breaker.src.risk_management.models.base import MarketContext, AccountState, Direction


class PositionSizer(ABC):
    """Base class for all position sizers"""
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """Initialize with optional parameters"""
        self.parameters = parameters or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def calculate_position_size(self, context: MarketContext, account: AccountState,
                               direction: Direction, risk_amount: float,
                               stop_loss: float = None) -> float:
        """
        Calculate position size based on risk amount
        
        Parameters:
        -----------
        context : MarketContext
            Current market context
        account : AccountState
            Current account state
        direction : Direction
            Trade direction
        risk_amount : float
            Risk amount as percentage of account
        stop_loss : float, optional
            Stop loss price level if already determined
            
        Returns:
        --------
        float
            Position size in lots/units
        """
        pass