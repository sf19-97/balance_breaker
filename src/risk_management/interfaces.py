"""
Risk Management Interface Contracts

This module defines the core interfaces for the risk management subsystem.
These interfaces provide contracts that components must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union
import datetime

from balance_breaker.src.core.interface_registry import interface
from balance_breaker.src.risk_management.models.base import Direction, TradeParameters


@interface
class RiskCalculator(ABC):
    """
    Interface for risk calculators
    
    Risk calculators determine position size and risk parameters
    based on account balance, instrument, and risk settings.
    """
    
    @abstractmethod
    def calculate_position_size(self, context: Dict[str, Any]) -> float:
        """
        Calculate position size based on risk parameters
        
        Args:
            context: Risk context including:
                - account_balance: Current account balance
                - entry_price: Entry price
                - stop_distance: Distance to stop loss in price terms
                - risk_percent: Percentage of account to risk
                - direction: Trade direction (1 for long, -1 for short)
                - instrument: Instrument name
                - additional parameters as needed
            
        Returns:
            Calculated position size
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get calculator parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set calculator parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class StopLossCalculator(ABC):
    """
    Interface for stop loss calculators
    
    Stop loss calculators determine stop loss levels based on
    instrument, price, and risk parameters.
    """
    
    @abstractmethod
    def calculate_stop_loss(self, context: Dict[str, Any]) -> float:
        """
        Calculate stop loss level
        
        Args:
            context: Risk context including:
                - entry_price: Entry price
                - direction: Trade direction (1 for long, -1 for short)
                - instrument: Instrument name
                - volatility: Instrument volatility (if available)
                - additional parameters as needed
            
        Returns:
            Stop loss price level
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get calculator parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set calculator parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class TakeProfitCalculator(ABC):
    """
    Interface for take profit calculators
    
    Take profit calculators determine take profit levels based on
    instrument, price, stop loss, and risk parameters.
    """
    
    @abstractmethod
    def calculate_take_profit(self, context: Dict[str, Any]) -> Union[float, List[float]]:
        """
        Calculate take profit level(s)
        
        Args:
            context: Risk context including:
                - entry_price: Entry price
                - direction: Trade direction (1 for long, -1 for short)
                - stop_loss: Stop loss price level
                - instrument: Instrument name
                - additional parameters as needed
            
        Returns:
            Take profit price level or list of levels for multiple targets
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get calculator parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set calculator parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class ExposureManager(ABC):
    """
    Interface for exposure managers
    
    Exposure managers ensure that overall portfolio exposure
    stays within acceptable limits.
    """
    
    @abstractmethod
    def check_exposure(self, new_position: Dict[str, Any], 
                      existing_positions: Dict[str, Any]) -> bool:
        """
        Check if adding a new position would exceed exposure limits
        
        Args:
            new_position: New position parameters
            existing_positions: Dictionary of existing positions
            
        Returns:
            True if position can be added, False otherwise
        """
        pass
    
    @abstractmethod
    def adjust_position(self, new_position: Dict[str, Any], 
                       existing_positions: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adjust position parameters to stay within exposure limits
        
        Args:
            new_position: New position parameters
            existing_positions: Dictionary of existing positions
            
        Returns:
            Adjusted position parameters
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get manager parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set manager parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)


@interface
class RiskAdjuster(ABC):
    """
    Interface for risk adjusters
    
    Risk adjusters modify risk parameters based on market conditions,
    correlation between positions, or other factors.
    """
    
    @abstractmethod
    def adjust_risk_parameters(self, parameters: TradeParameters, 
                              context: Dict[str, Any]) -> TradeParameters:
        """
        Adjust risk parameters based on context
        
        Args:
            parameters: Original trade parameters
            context: Risk context with additional information
            
        Returns:
            Adjusted trade parameters
        """
        pass
    
    def get_parameters(self) -> Dict[str, Any]:
        """Get adjuster parameters"""
        return getattr(self, 'parameters', {})
    
    def set_parameters(self, parameters: Dict[str, Any]) -> None:
        """Set adjuster parameters"""
        if not hasattr(self, 'parameters'):
            self.parameters = {}
            
        if parameters:
            self.parameters.update(parameters)