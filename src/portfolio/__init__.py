"""
Portfolio Management System

This package provides a comprehensive portfolio management system for trading strategies,
including portfolio allocation, risk constraints, rebalancing, and performance tracking.
"""

# Core models and orchestrator
from balance_breaker.src.portfolio.models import (
    Portfolio, PortfolioPosition, AllocationInstruction, 
    AllocationAction, PortfolioMetrics
)
from balance_breaker.src.portfolio.orchestrator import PortfolioOrchestrator

# Allocation components
from balance_breaker.src.portfolio.allocation.base import Allocator
from balance_breaker.src.portfolio.allocation.equal_weight import EqualWeightAllocator
from balance_breaker.src.portfolio.allocation.risk_parity import RiskParityAllocator

# Constraint components
from balance_breaker.src.portfolio.constraints.base import Constraint
from balance_breaker.src.portfolio.constraints.correlation import CorrelationConstraint
from balance_breaker.src.portfolio.constraints.exposure import MaxExposureConstraint
from balance_breaker.src.portfolio.constraints.drawdown import DrawdownConstraint
from balance_breaker.src.portfolio.constraints.instrument import InstrumentConstraint

# Rebalancing components
from balance_breaker.src.portfolio.rebalancing.base import Rebalancer
from balance_breaker.src.portfolio.rebalancing.threshold import ThresholdRebalancer
from balance_breaker.src.portfolio.rebalancing.scheduled import TimeBasedRebalancer

# Performance tracking components
from balance_breaker.src.portfolio.performance.base import PerformanceTracker, MetricsCalculator
from balance_breaker.src.portfolio.performance.tracker import PortfolioTracker
from balance_breaker.src.portfolio.performance.metrics import (
    BasicMetricsCalculator, AdvancedMetricsCalculator
)

# Convenience functions

def create_default_portfolio(name="Default Portfolio", initial_capital=100000.0, 
                            base_currency="USD") -> Portfolio:
    """
    Create a default portfolio with standard configuration
    
    Args:
        name: Portfolio name
        initial_capital: Initial portfolio capital
        base_currency: Base currency for the portfolio
        
    Returns:
        Configured Portfolio instance
    """
    return Portfolio(
        name=name,
        base_currency=base_currency,
        initial_capital=initial_capital,
        current_equity=initial_capital,
        cash=initial_capital
    )

def create_orchestrator(config=None) -> PortfolioOrchestrator:
    """
    Create a portfolio orchestrator with standard constraints and allocators
    
    Args:
        config: Optional configuration parameters
        
    Returns:
        Configured PortfolioOrchestrator instance
    """
    # Create default configuration if not provided
    if config is None:
        config = {
            'portfolio_name': 'Default Portfolio',
            'initial_capital': 100000.0,
            'base_currency': 'USD',
            'max_positions': 10,
            'max_exposure': 0.5,
            'max_position_risk': 0.05,
            'allocation_mode': 'equal_weight',
            'rebalance_mode': 'threshold'
        }
    
    # Create orchestrator
    orchestrator = PortfolioOrchestrator(config)
    
    # Register default components
    orchestrator.register_allocator('equal_weight', EqualWeightAllocator())
    orchestrator.register_allocator('risk_parity', RiskParityAllocator())
    
    orchestrator.register_constraint('correlation', CorrelationConstraint())
    orchestrator.register_constraint('exposure', MaxExposureConstraint())
    orchestrator.register_constraint('drawdown', DrawdownConstraint())
    orchestrator.register_constraint('instrument', InstrumentConstraint())
    
    orchestrator.register_rebalancer('threshold', ThresholdRebalancer())
    orchestrator.register_rebalancer('scheduled', TimeBasedRebalancer())
    
    return orchestrator

# Define package exports
__all__ = [
    # Core models and orchestrator
    'Portfolio', 'PortfolioPosition', 'AllocationInstruction', 
    'AllocationAction', 'PortfolioMetrics', 'PortfolioOrchestrator',
    
    # Allocation components
    'Allocator', 'EqualWeightAllocator', 'RiskParityAllocator',
    
    # Constraint components
    'Constraint', 'CorrelationConstraint', 'MaxExposureConstraint',
    'DrawdownConstraint', 'InstrumentConstraint',
    
    # Rebalancing components
    'Rebalancer', 'ThresholdRebalancer', 'TimeBasedRebalancer',
    
    # Performance tracking components
    'PerformanceTracker', 'MetricsCalculator', 'PortfolioTracker',
    'BasicMetricsCalculator', 'AdvancedMetricsCalculator',
    
    # Convenience functions
    'create_default_portfolio', 'create_orchestrator'
]