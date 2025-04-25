"""
Threshold-based portfolio rebalancing

This module defines a threshold-based rebalancing strategy that triggers rebalancing
when position weights drift beyond specified thresholds.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import numpy as np

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction, AllocationAction
from balance_breaker.src.portfolio.rebalance.base import Rebalancer
from balance_breaker.src.risk_management.orchestrator import RiskManager


class ThresholdRebalancer(Rebalancer):
    """
    Threshold-based portfolio rebalancer
    
    This rebalancer triggers rebalancing when position weights drift beyond
    specified thresholds relative to their target weights.
    
    Parameters:
    -----------
    drift_threshold : float
        Maximum allowed relative drift from target weight (e.g., 0.2 = 20%)
    absolute_threshold : float
        Minimum absolute difference to trigger rebalancing (e.g., 0.05 = 5%)
    min_days_between : int
        Minimum days between rebalancing operations
    all_positions : bool
        Whether to rebalance all positions or only those exceeding thresholds
    min_trade_size : float
        Minimum position size change to generate a rebalancing instruction
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Rebalancer parameters
        """
        default_params = {
            'drift_threshold': 0.2,       # 20% relative drift
            'absolute_threshold': 0.05,   # 5% absolute drift
            'min_days_between': 7,        # Minimum 7 days between rebalances
            'all_positions': False,       # Only rebalance positions exceeding thresholds
            'min_trade_size': 0.01        # Minimum trade size to rebalance
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.last_rebalance_time = None
    
    def should_rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                        current_time: datetime) -> bool:
        """
        Determine if the portfolio should be rebalanced based on position drift
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            current_time: Current timestamp
            
        Returns:
            True if portfolio should be rebalanced, False otherwise
        """
        # Check minimum time between rebalances
        if self.last_rebalance_time is not None:
            min_days = self.parameters['min_days_between']
            if current_time - self.last_rebalance_time < timedelta(days=min_days):
                self.logger.debug(f"Not enough time since last rebalance ({min_days} days minimum)")
                return False
        
        # If no positions, no need to rebalance
        if not portfolio.positions:
            return False
        
        # If price data missing for any position, skip rebalancing
        for instrument in portfolio.positions:
            if instrument not in current_prices:
                self.logger.warning(f"Missing price data for {instrument}, skipping rebalance check")
                return False
        
        # Get target weights
        target_weights = self.get_target_weights(portfolio)
        
        # Calculate current weights
        total_value = 0
        current_values = {}
        
        for instrument, position in portfolio.positions.items():
            # Get current price
            current_price = current_prices.get(instrument, position.entry_price)
            # Calculate position value
            position_value = position.position_size * current_price
            current_values[instrument] = position_value
            total_value += position_value
        
        if total_value <= 0:
            self.logger.warning("Portfolio total value is zero or negative, skipping rebalance")
            return False
        
        # Calculate current weights
        current_weights = {instr: value / total_value for instr, value in current_values.items()}
        
        # Check for drift exceeding thresholds
        drift_threshold = self.parameters['drift_threshold']
        absolute_threshold = self.parameters['absolute_threshold']
        
        for instrument, target_weight in target_weights.items():
            if instrument not in current_weights:
                continue
                
            current_weight = current_weights[instrument]
            
            # Calculate absolute and relative drift
            abs_drift = abs(current_weight - target_weight)
            rel_drift = abs_drift / target_weight if target_weight > 0 else float('inf')
            
            # Check if either threshold is exceeded
            if rel_drift > drift_threshold and abs_drift > absolute_threshold:
                self.logger.info(f"Position {instrument} exceeds drift thresholds: "
                               f"rel_drift={rel_drift:.2%}, abs_drift={abs_drift:.2%}")
                return True
        
        return False
    
    def rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                 risk_manager: RiskManager, timestamp: datetime) -> List[AllocationInstruction]:
        """
        Generate threshold-based rebalancing instructions
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Current timestamp
            
        Returns:
            List of rebalancing instructions
        """
        self.last_rebalance_time = timestamp
        self.logger.info(f"Generating rebalancing instructions at {timestamp}")
        
        # If no positions, nothing to rebalance
        if not portfolio.positions:
            return []
        
        # Get target weights
        target_weights = self.get_target_weights(portfolio)
        
        # Calculate current weights and total portfolio value
        total_value = 0
        current_values = {}
        
        for instrument, position in portfolio.positions.items():
            # Skip positions without price data
            if instrument not in current_prices:
                self.logger.warning(f"Missing price data for {instrument}, skipping in rebalance")
                continue
                
            # Get current price
            current_price = current_prices[instrument]
            # Calculate position value
            position_value = position.position_size * current_price
            current_values[instrument] = position_value
            total_value += position_value
        
        if total_value <= 0:
            self.logger.warning("Portfolio total value is zero or negative, no rebalancing possible")
            return []
        
        # Calculate current weights
        current_weights = {instr: value / total_value for instr, value in current_values.items()}
        
        # Generate rebalancing instructions
        instructions = []
        
        # Get parameters
        drift_threshold = self.parameters['drift_threshold']
        absolute_threshold = self.parameters['absolute_threshold']
        all_positions = self.parameters['all_positions']
        min_trade_size = self.parameters['min_trade_size']
        
        for instrument, position in portfolio.positions.items():
            # Skip positions without price data
            if instrument not in current_prices:
                continue
                
            current_price = current_prices[instrument]
            current_weight = current_weights.get(instrument, 0)
            target_weight = target_weights.get(instrument, 0)
            
            # Calculate drifts
            abs_drift = abs(current_weight - target_weight)
            rel_drift = abs_drift / target_weight if target_weight > 0 else float('inf')
            
            # Determine if this position needs rebalancing
            needs_rebalance = (all_positions or 
                              (rel_drift > drift_threshold and abs_drift > absolute_threshold))
            
            if needs_rebalance:
                # Calculate target position value and size
                target_value = total_value * target_weight
                target_size = target_value / current_price
                
                # Calculate size change
                size_change = target_size - position.position_size
                
                # Skip if change is too small
                if abs(size_change) < min_trade_size:
                    self.logger.debug(f"Size change for {instrument} too small: {size_change}")
                    continue
                
                # Determine action (increase or decrease)
                action = AllocationAction.INCREASE if size_change > 0 else AllocationAction.DECREASE
                
                # Create rebalancing instruction
                instructions.append(AllocationInstruction(
                    instrument=instrument,
                    action=action,
                    direction=position.direction,
                    target_size=target_size,
                    entry_price=current_price,
                    stop_loss=position.stop_loss,
                    take_profit=position.take_profit,
                    risk_percent=position.risk_percent,
                    position_id=position.position_id,
                    strategy_name=position.strategy_name,
                    timestamp=timestamp,
                    metadata={
                        'rebalance_reason': 'weight_drift',
                        'current_weight': current_weight,
                        'target_weight': target_weight,
                        'drift': rel_drift
                    }
                ))
                
                self.logger.info(f"Generated rebalance instruction for {instrument}: "
                               f"current_weight={current_weight:.2%}, "
                               f"target_weight={target_weight:.2%}, "
                               f"drift={rel_drift:.2%}")
        
        self.logger.info(f"Generated {len(instructions)} rebalancing instructions")
        return instructions