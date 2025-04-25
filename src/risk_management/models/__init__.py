"""Base data models for risk management"""
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum


class Direction(Enum):
    """Trade direction enum"""
    LONG = 1
    SHORT = -1


@dataclass
class TradeParameters:
    """Complete trade parameters"""
    instrument: str
    direction: int  # 1 for long, -1 for short
    entry_price: float
    stop_loss: float
    take_profit: float
    position_size: float
    risk_percent: float