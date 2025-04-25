"""
Portfolio Management Data Models

This module defines the core data models for the portfolio management system.
These models are used across different components of the portfolio system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from enum import Enum
import datetime
import uuid


class AllocationAction(Enum):
    """Possible allocation actions"""
    CREATE = "create"         # Create a new position
    INCREASE = "increase"     # Increase an existing position
    DECREASE = "decrease"     # Decrease an existing position
    CLOSE = "close"           # Close an existing position
    REBALANCE = "rebalance"   # Rebalance an existing position


@dataclass
class PortfolioPosition:
    """
    Portfolio position that extends risk management position with portfolio metadata
    """
    instrument: str
    direction: int
    entry_price: float
    position_size: float
    position_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    stop_loss: Optional[float] = None
    take_profit: Optional[List[float]] = None
    entry_time: Optional[datetime.datetime] = None
    last_update_time: Optional[datetime.datetime] = None
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    strategy_name: Optional[str] = None
    risk_amount: float = 0.0
    risk_percent: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    

@dataclass
class AllocationInstruction:
    """
    Instruction for position allocation
    """
    instrument: str
    action: AllocationAction
    direction: int
    target_size: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[List[float]] = None
    risk_percent: float = 0.0
    position_id: Optional[str] = None
    strategy_name: Optional[str] = None
    timestamp: datetime.datetime = field(default_factory=datetime.datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Portfolio:
    """
    Portfolio data model representing the complete portfolio state
    """
    name: str
    base_currency: str
    positions: Dict[str, PortfolioPosition] = field(default_factory=dict)
    initial_capital: float = 100000.0
    current_equity: float = 100000.0
    cash: float = 100000.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    high_water_mark: float = 100000.0
    creation_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    last_update_time: datetime.datetime = field(default_factory=datetime.datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    transaction_history: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def drawdown(self) -> float:
        """Calculate current drawdown as percentage"""
        if self.high_water_mark <= 0:
            return 0.0
        return max(0.0, 1.0 - (self.current_equity / self.high_water_mark))
    
    @property
    def total_exposure(self) -> float:
        """Calculate total exposure as sum of all position risk percentages"""
        return sum(position.risk_percent for position in self.positions.values())
    
    @property
    def position_count(self) -> int:
        """Get current number of open positions"""
        return len(self.positions)
    
    def update_equity(self) -> float:
        """Update current equity based on position PnL"""
        self.unrealized_pnl = sum(position.unrealized_pnl for position in self.positions.values())
        self.current_equity = self.cash + self.unrealized_pnl
        
        # Update high water mark if needed
        if self.current_equity > self.high_water_mark:
            self.high_water_mark = self.current_equity
            
        self.last_update_time = datetime.datetime.now()
        return self.current_equity
    
    def add_transaction(self, transaction_type: str, details: Dict[str, Any]) -> None:
        """Add a transaction to the history"""
        transaction = {
            'timestamp': datetime.datetime.now(),
            'type': transaction_type,
            **details
        }
        self.transaction_history.append(transaction)
        
    def get_position_by_id(self, position_id: str) -> Optional[PortfolioPosition]:
        """Get position by ID"""
        for position in self.positions.values():
            if position.position_id == position_id:
                return position
        return None


@dataclass
class PortfolioMetrics:
    """Portfolio performance metrics"""
    total_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_profit_per_trade: float = 0.0
    avg_loss_per_trade: float = 0.0
    avg_trade: float = 0.0
    alpha: float = 0.0
    beta: float = 0.0
    correlation: float = 0.0
    time_window: str = "all"  # 'day', 'week', 'month', 'year', 'all'
    start_date: Optional[datetime.datetime] = None
    end_date: Optional[datetime.datetime] = None
    additional_metrics: Dict[str, Any] = field(default_factory=dict)