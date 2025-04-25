"""
Base data models for risk management system
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
import datetime


class Direction(Enum):
    """Trade direction enum"""
    LONG = 1
    SHORT = -1


@dataclass
class MarketContext:
    """Current market conditions and instrument data"""
    price: float
    instrument: str
    timestamp: datetime.datetime
    pip_value: float
    pip_factor: float  # 100 for JPY, 10000 for others
    volatility: Optional[float] = None  # ATR or similar measure
    spread: Optional[float] = None
    regime: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None


@dataclass
class AccountState:
    """Current account state"""
    balance: float
    equity: float
    open_positions: Dict[str, Any]
    drawdown: float = 0.0
    high_water_mark: float = 0.0


@dataclass
class TradeParameters:
    """Complete trade parameters"""
    instrument: str
    direction: Direction
    entry_price: float
    stop_loss: float
    take_profit: List[float]  # Support multiple targets
    position_size: float
    timestamp: datetime.datetime
    risk_amount: float  # Absolute risk in account currency
    risk_percent: float  # Risk as percentage of account
    additional_params: Optional[Dict[str, Any]] = None