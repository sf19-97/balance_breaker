"""
Portfolio Management Interface Contracts

This module defines the core interfaces for the portfolio management subsystem.
These interfaces provide contracts that components must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime

from balance_breaker.src.core.interface_registry import interface
from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction


@interface
class Allocator(ABC):
    """
    Interface for portfolio allocators
    
    Allocators determine how to distribute capital across different instruments
    based on signals, portfolio state, and market conditions.
    """
    
    @abstractmethod
    def allocate(self, signals: Dict[str, Dict[str, Any]], portfolio: Portfolio) -> Dict[str, float]:
        """
        Allocate capital across instruments based on signals
        
        Args:
            signals: Dictionary of signals by instrument
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of target weights by instrument
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get allocator parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set allocator parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class Constraint(ABC):
    """
    Interface for portfolio constraints
    
    Constraints enforce rules on portfolio allocations, such as maximum exposure,
    correlation limits, or instrument restrictions.
    """
    
    @abstractmethod
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply constraint to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of allocation instructions
        """
        pass
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets this constraint
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        return {'valid': True, 'violations': []}
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get constraint parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set constraint parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class Rebalancer(ABC):
    """
    Interface for portfolio rebalancers
    
    Rebalancers determine when and how a portfolio should be rebalanced to 
    maintain target allocations or respond to changing market conditions.
    """
    
    @abstractmethod
    def should_rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                        current_time: datetime) -> bool:
        """
        Determine if the portfolio should be rebalanced
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            current_time: Current timestamp
            
        Returns:
            True if portfolio should be rebalanced, False otherwise
        """
        pass
    
    @abstractmethod
    def rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                 risk_manager: Any, timestamp: datetime) -> List[AllocationInstruction]:
        """
        Generate rebalancing instructions for the portfolio
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Current timestamp
            
        Returns:
            List of rebalancing instructions
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get rebalancer parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set rebalancer parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class PerformanceTracker(ABC):
    """
    Interface for portfolio performance trackers
    
    Performance trackers record portfolio state over time and calculate
    performance metrics for analysis and reporting.
    """
    
    @abstractmethod
    def update(self, portfolio: Portfolio, timestamp: datetime) -> None:
        """
        Update tracker with current portfolio state
        
        Args:
            portfolio: Current portfolio state
            timestamp: Current timestamp
        """
        pass
    
    @abstractmethod
    def calculate_metrics(self, time_window: str = 'all', 
                         risk_free_rate: float = 0.0) -> Dict[str, Any]:
        """
        Calculate performance metrics for the specified time window
        
        Args:
            time_window: Time window for metrics ('day', 'week', 'month', 'year', 'all')
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            
        Returns:
            Dictionary of performance metrics
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get tracker parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set tracker parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)