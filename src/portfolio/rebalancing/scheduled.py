"""
Time-based portfolio rebalancing

This module defines a time-based rebalancing strategy that triggers rebalancing
at scheduled intervals, regardless of position drift.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import calendar

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction, AllocationAction
from balance_breaker.src.portfolio.rebalance.base import Rebalancer
from balance_breaker.src.risk_management.orchestrator import RiskManager


class TimeBasedRebalancer(Rebalancer):
    """
    Time-based portfolio rebalancer
    
    This rebalancer triggers rebalancing at scheduled intervals, such as weekly,
    monthly, or quarterly, regardless of position drift.
    
    Parameters:
    -----------
    frequency : str
        Rebalancing frequency ('daily', 'weekly', 'monthly', 'quarterly', 'yearly')
    day_of_week : int
        Day of week for weekly rebalancing (0=Monday, 6=Sunday)
    day_of_month : int
        Day of month for monthly rebalancing (1-31)
    month_of_quarter : int
        Month of quarter for quarterly rebalancing (1-3)
    all_positions : bool
        Whether to rebalance all positions or only those with significant drift
    min_drift : float
        Minimum relative drift to rebalance individual positions
    min_trade_size : float
        Minimum position size change to generate a rebalancing instruction
    hour_of_day : int
        Hour of day for rebalancing (0-23)
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Rebalancer parameters
        """
        default_params = {
            'frequency': 'monthly',     # Monthly rebalancing
            'day_of_week': 0,           # Monday for weekly
            'day_of_month': 1,          # 1st of month for monthly
            'month_of_quarter': 1,      # First month of quarter for quarterly
            'all_positions': True,      # Rebalance all positions
            'min_drift': 0.05,          # Minimum 5% drift to rebalance
            'min_trade_size': 0.01,     # Minimum trade size
            'hour_of_day': 0            # Midnight
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.last_rebalance_time = None
    
    def should_rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                        current_time: datetime) -> bool:
        """
        Determine if the portfolio should be rebalanced based on scheduled time
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            current_time: Current timestamp
            
        Returns:
            True if portfolio should be rebalanced, False otherwise
        """
        # Skip if no positions
        if not portfolio.positions:
            return False
        
        # Get frequency and other parameters
        frequency = self.parameters['frequency'].lower()
        hour_of_day = self.parameters['hour_of_day']
        
        # Check if we already rebalanced based on frequency
        if self.last_rebalance_time is not None:
            if frequency == 'daily' and current_time.date() <= self.last_rebalance_time.date():
                return False
            elif frequency == 'weekly' and (current_time - self.last_rebalance_time).days < 7:
                return False
            elif frequency == 'monthly' and (
                current_time.year < self.last_rebalance_time.year or
                (current_time.year == self.last_rebalance_time.year and 
                 current_time.month <= self.last_rebalance_time.month)
            ):
                return False
            elif frequency == 'quarterly' and (
                current_time.year < self.last_rebalance_time.year or
                (current_time.year == self.last_rebalance_time.year and 
                 (current_time.month - 1) // 3 <= (self.last_rebalance_time.month - 1) // 3)
            ):
                return False
            elif frequency == 'yearly' and current_time.year <= self.last_rebalance_time.year:
                return False
        
        # Check if current time matches the rebalancing schedule
        if frequency == 'daily':
            # Rebalance at specified hour
            return current_time.hour == hour_of_day
        
        elif frequency == 'weekly':
            # Rebalance on specified day of week at specified hour
            day_of_week = self.parameters['day_of_week']
            return current_time.weekday() == day_of_week and current_time.hour == hour_of_day
        
        elif frequency == 'monthly':
            # Rebalance on specified day of month at specified hour
            day_of_month = min(self.parameters['day_of_month'], 
                              calendar.monthrange(current_time.year, current_time.month)[1])
            return current_time.day == day_of_month and current_time.hour == hour_of_day
        
        elif frequency == 'quarterly':
            # Rebalance on specified month of quarter (1-3) and day of month
            month_of_quarter = self.parameters['month_of_quarter']
            quarter_month = ((current_time.month - 1) % 3) + 1
            
            if quarter_month != month_of_quarter:
                return False
                
            day_of_month = min(self.parameters['day_of_month'], 
                              calendar.monthrange(current_time.year, current_time.month)[1])
            return current_time.day == day_of_month and current_time.hour == hour_of_day
        
        elif frequency == 'yearly':
            # Rebalance on January (or specified month) and day of month
            month = self.parameters.get('month_of_year', 1)
            
            if current_time.month != month:
                return False
                
            day_of_month = min(self.parameters['day_of_month'], 
                              calendar.monthrange(current_time.year, current_time.month)[1])
            return current_time.day == day_of_month and current_time.hour == hour_of_day
        
        else:
            self.logger.warning(f"Unknown frequency: {frequency}")
            return False
    
    def rebalance(self, portfolio: Portfolio, current_prices: Dict[str, float], 
                 risk_manager: RiskManager, timestamp: datetime) -> List[AllocationInstruction]:
        """
        Generate time-based rebalancing instructions
        
        Args:
            portfolio: Current portfolio state
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Current timestamp
            
        Returns:
            List of rebalancing instructions
        """
        self.last_rebalance_time = timestamp
        self.logger.info(f"Generating scheduled rebalancing instructions at {timestamp}")
        
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
        all_positions = self.parameters['all_positions']
        min_drift = self.parameters['min_drift']
        min_trade_size = self.parameters['min_trade_size']
        
        for instrument, position in portfolio.positions.items():
            # Skip positions without price data
            if instrument not in current_prices:
                continue
                
            current_price = current_prices[instrument]
            current_weight = current_weights.get(instrument, 0)
            target_weight = target_weights.get(instrument, 0)
            
            # Calculate drift
            rel_drift = abs(current_weight - target_weight) / target_weight if target_weight > 0 else float('inf')
            
            # Determine if this position needs rebalancing
            needs_rebalance = all_positions or rel_drift > min_drift
            
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
                
                # Determine action (rebalance)
                action = AllocationAction.REBALANCE
                
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
                        'rebalance_reason': 'scheduled',
                        'frequency': self.parameters['frequency'],
                        'current_weight': current_weight,
                        'target_weight': target_weight,
                        'drift': rel_drift
                    }
                ))
                
                self.logger.info(f"Generated scheduled rebalance instruction for {instrument}: "
                               f"current_weight={current_weight:.2%}, "
                               f"target_weight={target_weight:.2%}, "
                               f"drift={rel_drift:.2%}")
        
        self.logger.info(f"Generated {len(instructions)} scheduled rebalancing instructions")
        return instructions