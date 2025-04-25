"""
Stop loss calculator implementations
"""
from balance_breaker.src.risk_management.stops.fixed import FixedPipsStopCalculator
from balance_breaker.src.risk_management.stops.atr import AtrStopCalculator

__all__ = [
    'FixedPipsStopCalculator',
    'AtrStopCalculator'
]