"""
Portfolio Orchestrator

The central coordinator for the portfolio management system, responsible for
integrating signals, risk parameters, and portfolio constraints.
"""

import logging
from typing import Dict, List, Any, Optional, Union, Type, Callable
import datetime
import uuid
import pandas as pd
import numpy as np

from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, PortfolioError, ErrorSeverity, ErrorCategory
from balance_breaker.src.core.integration_tools import integrates_with, IntegrationType, event_bus
from balance_breaker.src.core.interface_registry import registry
from balance_breaker.src.portfolio.interfaces import Allocator, Constraint, Rebalancer, PerformanceTracker
from balance_breaker.src.portfolio.models import (
    Portfolio, PortfolioPosition, AllocationInstruction, AllocationAction, PortfolioMetrics
)
from balance_breaker.src.risk_management.orchestrator import RiskManager
from balance_breaker.src.risk_management.models.base import Direction, TradeParameters


class PortfolioOrchestrator(ParameterizedComponent):
    """
    Portfolio Orchestrator
    
    Coordinates all portfolio management activities, including:
    - Processing signals from strategies
    - Consulting risk management for position parameters
    - Applying portfolio-level constraints
    - Generating allocation instructions
    - Managing the portfolio lifecycle
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the portfolio orchestrator
        
        Args:
            config: Configuration parameters including:
                - initial_capital: Initial portfolio capital
                - base_currency: Base currency for the portfolio
                - portfolio_name: Name of the portfolio
                - max_positions: Maximum number of positions
                - max_exposure: Maximum total exposure
                - max_correlation: Maximum correlation between positions
                - rebalance_threshold: Threshold for rebalancing
        """
        super().__init__(config)
        self.logger = logging.getLogger(__name__)
        self.error_handler = ErrorHandler(self.logger)
        
        # Initialize portfolio
        self.portfolio = Portfolio(
            name=self.parameters.get('portfolio_name', 'Default Portfolio'),
            base_currency=self.parameters.get('base_currency', 'USD'),
            initial_capital=self.parameters.get('initial_capital', 100000.0),
            current_equity=self.parameters.get('initial_capital', 100000.0),
            cash=self.parameters.get('initial_capital', 100000.0),
        )
        
        # Configure portfolio constraints
        self.max_positions = self.parameters.get('max_positions', 10)
        self.max_exposure = self.parameters.get('max_exposure', 0.5)  # 50% max exposure
        self.max_position_risk = self.parameters.get('max_position_risk', 0.05)  # 5% max per position
        self.max_correlation = self.parameters.get('max_correlation', 0.7)
        
        # Initialize component registries
        self.allocators: Dict[str, Allocator] = {}
        self.constraints: Dict[str, Constraint] = {}
        self.rebalancers: Dict[str, Rebalancer] = {}
        self.performance_trackers: Dict[str, PerformanceTracker] = {}
        
        # Default mode is 'equal_weight' if not specified
        self.allocation_mode = self.parameters.get('allocation_mode', 'equal_weight')
        self.rebalance_mode = self.parameters.get('rebalance_mode', 'threshold')
        
        self.logger.info(f"Portfolio Orchestrator initialized with {self.portfolio.name}")
    
    def register_allocator(self, name: str, allocator: Allocator) -> None:
        """
        Register an allocation component
        
        Args:
            name: Allocator name
            allocator: Allocator component
        """
        # Validate component implements Allocator interface
        validation = registry.validate_implementation(allocator, "Allocator")
        if not validation['valid']:
            error_msg = f"Component {allocator.__class__.__name__} does not implement Allocator interface correctly"
            self.logger.error(f"{error_msg}: {validation}")
            raise ValueError(error_msg)
            
        self.allocators[name] = allocator
        self.logger.debug(f"Registered allocator: {name}")
    
    def register_constraint(self, name: str, constraint: Constraint) -> None:
        """
        Register a constraint component
        
        Args:
            name: Constraint name
            constraint: Constraint component
        """
        # Validate component implements Constraint interface
        validation = registry.validate_implementation(constraint, "Constraint")
        if not validation['valid']:
            error_msg = f"Component {constraint.__class__.__name__} does not implement Constraint interface correctly"
            self.logger.error(f"{error_msg}: {validation}")
            raise ValueError(error_msg)
            
        self.constraints[name] = constraint
        self.logger.debug(f"Registered constraint: {name}")
    
    def register_rebalancer(self, name: str, rebalancer: Rebalancer) -> None:
        """
        Register a rebalancing component
        
        Args:
            name: Rebalancer name
            rebalancer: Rebalancer component
        """
        # Validate component implements Rebalancer interface
        validation = registry.validate_implementation(rebalancer, "Rebalancer")
        if not validation['valid']:
            error_msg = f"Component {rebalancer.__class__.__name__} does not implement Rebalancer interface correctly"
            self.logger.error(f"{error_msg}: {validation}")
            raise ValueError(error_msg)
            
        self.rebalancers[name] = rebalancer
        self.logger.debug(f"Registered rebalancer: {name}")
    
    def register_performance_tracker(self, name: str, tracker: PerformanceTracker) -> None:
        """
        Register a performance tracking component
        
        Args:
            name: Tracker name
            tracker: Performance tracker component
        """
        # Validate component implements PerformanceTracker interface
        validation = registry.validate_implementation(tracker, "PerformanceTracker")
        if not validation['valid']:
            error_msg = f"Component {tracker.__class__.__name__} does not implement PerformanceTracker interface correctly"
            self.logger.error(f"{error_msg}: {validation}")
            raise ValueError(error_msg)
            
        self.performance_trackers[name] = tracker
        self.logger.debug(f"Registered performance tracker: {name}")
    
    @integrates_with(
        target_subsystem='risk_management',
        integration_type=IntegrationType.SERVICE,
        description='Gets risk parameters for new positions and position modifications'
    )
    def process_signals(self, 
                       signals: Dict[str, Dict[str, Any]], 
                       risk_manager: RiskManager,
                       timestamp: Optional[datetime.datetime] = None) -> List[AllocationInstruction]:
        """
        Process signals from strategies and generate allocation instructions
        
        Args:
            signals: Dictionary of signals by instrument
                Each signal should contain:
                - 'instrument': Instrument name
                - 'direction': Trade direction (1 for long, -1 for short)
                - 'strength': Signal strength (0.0 to 1.0) - optional
                - 'price': Current price
                - 'strategy': Strategy name
            risk_manager: Risk manager instance
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            List of allocation instructions
        """
        try:
            if not signals:
                self.logger.info("No signals to process")
                return []
            
            if timestamp is None:
                timestamp = datetime.datetime.now()
            
            self.logger.info(f"Processing {len(signals)} signals at {timestamp}")
            
            # Update portfolio state
            self.portfolio.last_update_time = timestamp
            
            # 1. Apply allocator to determine target weights
            target_weights = self._calculate_target_weights(signals)
            
            # 2. Generate initial allocation instructions
            instructions = []
            
            for instrument, signal in signals.items():
                # Skip instruments with no weight allocated
                if instrument not in target_weights or target_weights[instrument] <= 0:
                    continue
                
                # Get current price
                price = signal.get('price', 0)
                if price <= 0:
                    self.logger.warning(f"Invalid price for {instrument}: {price}")
                    continue
                
                # Get direction
                direction = signal.get('direction', 0)
                if direction not in [-1, 1]:
                    self.logger.warning(f"Invalid direction for {instrument}: {direction}")
                    continue
                
                # Determine action based on existing positions
                action = AllocationAction.CREATE
                position_id = None
                
                # Check if we already have a position for this instrument
                if instrument in self.portfolio.positions:
                    existing_position = self.portfolio.positions[instrument]
                    position_id = existing_position.position_id
                    
                    # If same direction, increase or maintain position
                    if existing_position.direction == direction:
                        action = AllocationAction.INCREASE
                    else:
                        # If opposite direction, close existing position and create new one
                        # First add instruction to close existing position
                        instructions.append(AllocationInstruction(
                            instrument=instrument,
                            action=AllocationAction.CLOSE,
                            direction=existing_position.direction,
                            target_size=0,
                            entry_price=price,
                            position_id=position_id,
                            strategy_name=existing_position.strategy_name,
                            timestamp=timestamp
                        ))
                        
                        # Then create new position (keep action as CREATE)
                        position_id = None
                
                # Calculate risk parameters using risk manager
                risk_params = risk_manager.calculate_trade_parameters(
                    instrument=instrument,
                    price=price,
                    direction=Direction.LONG if direction == 1 else Direction.SHORT,
                    balance=self.portfolio.current_equity,
                    pip_factor=signal.get('pip_factor', 10000),
                    open_positions={pos.instrument: pos for pos in self.portfolio.positions.values()}
                )
                
                # Skip if risk manager rejected the trade
                if risk_params is None:
                    self.logger.info(f"Risk manager rejected trade for {instrument}")
                    continue
                
                # Apply portfolio weight to position size
                portfolio_weight = target_weights[instrument]
                adjusted_size = risk_params.position_size * portfolio_weight
                
                # Ensure position is worth taking
                min_position_size = self.parameters.get('min_position_size', 0.01)
                if adjusted_size < min_position_size:
                    self.logger.info(f"Position size for {instrument} too small: {adjusted_size}")
                    continue
                
                # Create allocation instruction
                instructions.append(AllocationInstruction(
                    instrument=instrument,
                    action=action,
                    direction=direction,
                    target_size=adjusted_size,
                    entry_price=price,
                    stop_loss=risk_params.stop_loss,
                    take_profit=risk_params.take_profit,
                    risk_percent=risk_params.risk_percent * portfolio_weight,
                    position_id=position_id,
                    strategy_name=signal.get('strategy', 'Unknown'),
                    timestamp=timestamp
                ))
            
            # 3. Apply portfolio constraints
            final_instructions = self._apply_constraints(instructions)
            
            self.logger.info(f"Generated {len(final_instructions)} allocation instructions")
            
            # Publish event for other subsystems
            event_bus.publish('portfolio_allocation_created', {
                'instructions_count': len(final_instructions),
                'timestamp': timestamp.isoformat()
            })
            
            return final_instructions
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Signal processing error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={'signals_count': len(signals)},
                    original_exception=e
                )
            )
            # Return empty list on error
            return []
    
    def _calculate_target_weights(self, signals: Dict[str, Dict[str, Any]]) -> Dict[str, float]:
        """
        Calculate target weights for each instrument
        
        This is where we would use the registered allocators. For now, we'll use a simple
        equal weight approach as the default.
        
        Args:
            signals: Dictionary of signals by instrument
            
        Returns:
            Dictionary of target weights by instrument
        """
        # Get valid signals (with direction != 0)
        valid_signals = {k: v for k, v in signals.items() if v.get('direction', 0) != 0}
        
        if not valid_signals:
            return {}
        
        # Use selected allocation mode if available
        if self.allocation_mode in self.allocators:
            return self.allocators[self.allocation_mode].allocate(valid_signals, self.portfolio)
        
        # Default: Equal weight allocation
        count = len(valid_signals)
        weight = 1.0 / count if count > 0 else 0.0
        
        return {instrument: weight for instrument in valid_signals}
    
    def _apply_constraints(self, instructions: List[AllocationInstruction]) -> List[AllocationInstruction]:
        """
        Apply portfolio constraints to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            
        Returns:
            Adjusted list of allocation instructions
        """
        if not instructions:
            return []
        
        try:
            # Apply registered constraints in order
            constrained_instructions = instructions.copy()
            for constraint_name, constraint in self.constraints.items():
                constrained_instructions = constraint.apply(constrained_instructions, self.portfolio)
            
            # Apply built-in constraints
            
            # 1. Max positions constraint
            if len(constrained_instructions) > self.max_positions:
                # Sort by risk-adjusted strength (if available) or just by risk
                constrained_instructions.sort(
                    key=lambda x: x.metadata.get('strength', 1.0) / (x.risk_percent or 0.01), 
                    reverse=True
                )
                # Keep only the top positions
                constrained_instructions = constrained_instructions[:self.max_positions]
            
            # 2. Max exposure constraint
            total_risk = sum(instr.risk_percent for instr in constrained_instructions)
            
            if total_risk > self.max_exposure:
                # Scale down all positions proportionally
                scale_factor = self.max_exposure / total_risk
                for instr in constrained_instructions:
                    instr.target_size *= scale_factor
                    instr.risk_percent *= scale_factor
            
            # 3. Max position size constraint
            for instr in constrained_instructions:
                if instr.risk_percent > self.max_position_risk:
                    # Scale down to max position risk
                    scale_factor = self.max_position_risk / instr.risk_percent
                    instr.target_size *= scale_factor
                    instr.risk_percent *= scale_factor
            
            return constrained_instructions
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Constraint application error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={'instructions_count': len(instructions)},
                    original_exception=e
                )
            )
            # Return original instructions on error
            return instructions
    
    @integrates_with(
        target_subsystem='risk_management',
        integration_type=IntegrationType.SERVICE,
        description='Gets risk parameters for rebalancing positions'
    )
    def rebalance(self, 
                 current_prices: Dict[str, float],
                 risk_manager: RiskManager,
                 timestamp: Optional[datetime.datetime] = None) -> List[AllocationInstruction]:
        """
        Rebalance existing portfolio positions
        
        Args:
            current_prices: Dictionary of current prices by instrument
            risk_manager: Risk manager instance
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            List of rebalancing instructions
        """
        try:
            if not self.portfolio.positions:
                return []
            
            if timestamp is None:
                timestamp = datetime.datetime.now()
            
            self.logger.info(f"Rebalancing portfolio at {timestamp}")
            
            # Update portfolio state
            self.update_portfolio_state(current_prices, timestamp)
            
            # Use selected rebalancer if available
            if self.rebalance_mode in self.rebalancers:
                # Check if we should rebalance
                if not self.rebalancers[self.rebalance_mode].should_rebalance(
                    self.portfolio, current_prices, timestamp
                ):
                    self.logger.info("Rebalancing not needed at this time")
                    return []
                    
                # Generate rebalancing instructions
                return self.rebalancers[self.rebalance_mode].rebalance(
                    self.portfolio, current_prices, risk_manager, timestamp
                )
            
            # Simple default rebalancing: Check for drift exceeding threshold
            threshold = self.parameters.get('rebalance_threshold', 0.1)  # 10% drift threshold
            instructions = []
            
            # Get target weights (equal weight by default)
            target_weight = 1.0 / len(self.portfolio.positions) if self.portfolio.positions else 0.0
            
            # Estimate position values (very simplified - would need more sophistication in practice)
            position_values = {
                pos.instrument: pos.position_size * current_prices.get(pos.instrument, pos.entry_price)
                for pos in self.portfolio.positions.values()
            }
            
            total_value = sum(position_values.values())
            
            if total_value <= 0:
                return []
            
            # Calculate current weights
            current_weights = {instr: value / total_value for instr, value in position_values.items()}
            
            # Check for drift exceeding threshold
            for instrument, position in self.portfolio.positions.items():
                if instrument not in current_prices:
                    continue
                    
                current_weight = current_weights.get(instrument, 0.0)
                weight_drift = abs(current_weight - target_weight) / target_weight
                
                if weight_drift > threshold:
                    # Calculate target size
                    current_price = current_prices[instrument]
                    target_value = total_value * target_weight
                    target_size = target_value / current_price
                    
                    # Create rebalancing instruction
                    instructions.append(AllocationInstruction(
                        instrument=instrument,
                        action=AllocationAction.REBALANCE,
                        direction=position.direction,
                        target_size=target_size,
                        entry_price=current_price,
                        stop_loss=position.stop_loss,
                        take_profit=position.take_profit,
                        risk_percent=position.risk_percent,
                        position_id=position.position_id,
                        strategy_name=position.strategy_name,
                        timestamp=timestamp,
                        metadata={'rebalance_reason': 'weight_drift'}
                    ))
            
            self.logger.info(f"Generated {len(instructions)} rebalancing instructions")
            
            # Publish event for other subsystems
            event_bus.publish('portfolio_rebalance_created', {
                'instructions_count': len(instructions),
                'timestamp': timestamp.isoformat()
            })
            
            return instructions
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Rebalancing error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={'positions_count': len(self.portfolio.positions)},
                    original_exception=e
                )
            )
            # Return empty list on error
            return []
    
    def update_portfolio_state(self, 
                              current_prices: Dict[str, float],
                              timestamp: Optional[datetime.datetime] = None) -> Portfolio:
        """
        Update portfolio state with current prices
        
        Args:
            current_prices: Dictionary of current prices by instrument
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Updated portfolio
        """
        try:
            if timestamp is None:
                timestamp = datetime.datetime.now()
            
            self.portfolio.last_update_time = timestamp
            
            # Update each position's unrealized P&L
            for instrument, position in self.portfolio.positions.items():
                if instrument in current_prices:
                    current_price = current_prices[instrument]
                    
                    # Calculate price change in position direction
                    price_change = (current_price - position.entry_price) * position.direction
                    
                    # Very simplified P&L calculation - would need refinement in practice
                    # to account for pip values, leverage, etc.
                    position.unrealized_pnl = price_change * position.position_size
                    position.last_update_time = timestamp
            
            # Update portfolio equity
            self.portfolio.update_equity()
            
            # Update performance trackers
            for tracker in self.performance_trackers.values():
                tracker.update(self.portfolio, timestamp)
            
            return self.portfolio
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Portfolio state update error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATA,
                    context={},
                    original_exception=e
                )
            )
            # Return portfolio unchanged on error
            return self.portfolio
    
    @integrates_with(
        target_subsystem='execution',
        integration_type=IntegrationType.COMMAND,
        description='Sends execution instructions to execution subsystem'
    )
    def execute_instructions(self, 
                            instructions: List[AllocationInstruction],
                            execution_prices: Dict[str, float],
                            timestamp: Optional[datetime.datetime] = None) -> None:
        """
        Execute allocation instructions and update portfolio
        
        Args:
            instructions: List of allocation instructions
            execution_prices: Dictionary of execution prices by instrument
            timestamp: Optional timestamp (defaults to now)
        """
        if not instructions:
            return
        
        try:
            if timestamp is None:
                timestamp = datetime.datetime.now()
            
            self.logger.info(f"Executing {len(instructions)} instructions at {timestamp}")
            
            for instruction in instructions:
                instrument = instruction.instrument
                action = instruction.action
                direction = instruction.direction
                target_size = instruction.target_size
                
                # Get execution price (or use the price from instruction if not available)
                exec_price = execution_prices.get(instrument, instruction.entry_price)
                
                # Execute based on action
                if action == AllocationAction.CREATE:
                    # Create new position
                    self._create_position(instruction, exec_price, timestamp)
                    
                elif action == AllocationAction.INCREASE:
                    # Increase existing position
                    self._modify_position(instruction, exec_price, timestamp, increase=True)
                    
                elif action == AllocationAction.DECREASE:
                    # Decrease existing position
                    self._modify_position(instruction, exec_price, timestamp, increase=False)
                    
                elif action == AllocationAction.CLOSE:
                    # Close existing position
                    self._close_position(instruction, exec_price, timestamp)
                    
                elif action == AllocationAction.REBALANCE:
                    # Rebalance position (close and reopen at target size)
                    self._rebalance_position(instruction, exec_price, timestamp)
            
            # Update portfolio state
            self.portfolio.update_equity()
            
            # Publish event for other subsystems
            event_bus.publish('portfolio_instructions_executed', {
                'instructions_count': len(instructions),
                'portfolio_value': self.portfolio.current_equity,
                'positions_count': self.portfolio.position_count,
                'timestamp': timestamp.isoformat()
            })
            
            self.logger.info(f"Portfolio updated: {self.portfolio.position_count} positions, "
                            f"Equity: {self.portfolio.current_equity:.2f}, "
                            f"Exposure: {self.portfolio.total_exposure:.2%}")
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Instruction execution error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={'instructions_count': len(instructions)},
                    original_exception=e
                )
            )
    
    def _create_position(self, instruction: AllocationInstruction, exec_price: float, 
                        timestamp: datetime.datetime) -> None:
        """Create a new position in the portfolio"""
        instrument = instruction.instrument
        
        # Skip if position already exists
        if instrument in self.portfolio.positions:
            self.logger.warning(f"Position already exists for {instrument}")
            return
        
        # Calculate cash required for the position (simplified)
        position_value = instruction.target_size * exec_price
        
        # Check if we have enough cash
        if position_value > self.portfolio.cash:
            self.logger.warning(f"Insufficient cash for {instrument} position")
            # Scale down the position to available cash
            scale_factor = self.portfolio.cash / position_value
            instruction.target_size *= scale_factor
            position_value *= scale_factor
        
        # Create the position
        position = PortfolioPosition(
            instrument=instrument,
            direction=instruction.direction,
            entry_price=exec_price,
            position_size=instruction.target_size,
            stop_loss=instruction.stop_loss,
            take_profit=instruction.take_profit,
            entry_time=timestamp,
            last_update_time=timestamp,
            strategy_name=instruction.strategy_name,
            risk_amount=position_value * instruction.risk_percent,
            risk_percent=instruction.risk_percent,
            metadata=instruction.metadata
        )
        
        # Add to portfolio
        self.portfolio.positions[instrument] = position
        
        # Update cash
        self.portfolio.cash -= position_value
        
        # Record transaction
        self.portfolio.add_transaction('create_position', {
            'instrument': instrument,
            'direction': instruction.direction,
            'size': instruction.target_size,
            'price': exec_price,
            'value': position_value,
            'position_id': position.position_id
        })
        
        # Publish event
        event_bus.publish('position_opened', {
            'instrument': instrument,
            'direction': instruction.direction,
            'size': instruction.target_size,
            'price': exec_price,
            'value': position_value,
            'position_id': position.position_id,
            'strategy': instruction.strategy_name,
            'timestamp': timestamp.isoformat()
        })
        
        self.logger.info(f"Created position: {instrument}, Size: {instruction.target_size}, "
                       f"Price: {exec_price}, Value: {position_value:.2f}")
    
    def _modify_position(self, instruction: AllocationInstruction, exec_price: float, 
                        timestamp: datetime.datetime, increase: bool) -> None:
        """Modify an existing position (increase or decrease)"""
        instrument = instruction.instrument
        position_id = instruction.position_id
        
        # Get the position
        position = None
        if position_id:
            position = self.portfolio.get_position_by_id(position_id)
        
        if not position and instrument in self.portfolio.positions:
            position = self.portfolio.positions[instrument]
        
        if not position:
            self.logger.warning(f"Position not found for {instrument}")
            return
        
        # Calculate change in size
        current_size = position.position_size
        target_size = instruction.target_size
        
        if increase and target_size <= current_size:
            self.logger.info(f"Target size {target_size} not greater than current size {current_size}")
            return
            
        if not increase and target_size >= current_size:
            self.logger.info(f"Target size {target_size} not less than current size {current_size}")
            return
        
        size_change = target_size - current_size
        
        # Calculate value change
        value_change = size_change * exec_price
        
        # For increase, check if we have enough cash
        if increase:
            if value_change > self.portfolio.cash:
                self.logger.warning(f"Insufficient cash to increase {instrument} position")
                # Scale down the increase to available cash
                scale_factor = self.portfolio.cash / value_change
                size_change *= scale_factor
                value_change *= scale_factor
                target_size = current_size + size_change
            
            # Update position
            position.position_size = target_size
            position.last_update_time = timestamp
            
            # Update cash
            self.portfolio.cash -= value_change
            
            # Record transaction
            self.portfolio.add_transaction('increase_position', {
                'instrument': instrument,
                'direction': position.direction,
                'size_change': size_change,
                'price': exec_price,
                'value_change': value_change,
                'position_id': position.position_id
            })
            
            # Publish event
            event_bus.publish('position_increased', {
                'instrument': instrument,
                'direction': position.direction,
                'size_change': size_change,
                'price': exec_price,
                'value_change': value_change,
                'position_id': position.position_id,
                'timestamp': timestamp.isoformat()
            })
            
            self.logger.info(f"Increased position: {instrument}, Size: {current_size} -> {target_size}, "
                           f"Price: {exec_price}, Value Change: {value_change:.2f}")
        else:
            # For decrease, calculate realized P&L
            avg_price = position.entry_price  # Simplified - should consider previous modifications
            price_change = (exec_price - avg_price) * position.direction
            realized_pnl = price_change * (-size_change)  # Size change is negative
            
            # Update position
            position.position_size = target_size
            position.realized_pnl += realized_pnl
            position.last_update_time = timestamp
            
            # Update portfolio
            self.portfolio.cash += -value_change  # Value change is negative
            self.portfolio.realized_pnl += realized_pnl
            
            # Record transaction
            self.portfolio.add_transaction('decrease_position', {
                'instrument': instrument,
                'direction': position.direction,
                'size_change': size_change,
                'price': exec_price,
                'value_change': value_change,
                'realized_pnl': realized_pnl,
                'position_id': position.position_id
            })
            
            # Publish event
            event_bus.publish('position_decreased', {
                'instrument': instrument,
                'direction': position.direction,
                'size_change': size_change,
                'price': exec_price,
                'value_change': value_change,
                'realized_pnl': realized_pnl,
                'position_id': position.position_id,
                'timestamp': timestamp.isoformat()
            })
            
            self.logger.info(f"Decreased position: {instrument}, Size: {current_size} -> {target_size}, "
                           f"Price: {exec_price}, Value Change: {value_change:.2f}, PnL: {realized_pnl:.2f}")
    
    def _close_position(self, instruction: AllocationInstruction, exec_price: float, 
                       timestamp: datetime.datetime) -> None:
        """Close an existing position"""
        instrument = instruction.instrument
        position_id = instruction.position_id
        
        # Get the position
        position = None
        if position_id:
            position = self.portfolio.get_position_by_id(position_id)
        
        if not position and instrument in self.portfolio.positions:
            position = self.portfolio.positions[instrument]
        
        if not position:
            self.logger.warning(f"Position not found for {instrument}")
            return
        
        # Calculate realized P&L
        price_change = (exec_price - position.entry_price) * position.direction
        realized_pnl = price_change * position.position_size
        
        # Calculate position value
        position_value = position.position_size * exec_price
        
        # Update portfolio
        self.portfolio.cash += position_value
        self.portfolio.realized_pnl += realized_pnl
        
        # Record transaction
        self.portfolio.add_transaction('close_position', {
            'instrument': instrument,
            'direction': position.direction,
            'size': position.position_size,
            'price': exec_price,
            'value': position_value,
            'realized_pnl': realized_pnl,
            'position_id': position.position_id
        })
        
        # Publish event
        event_bus.publish('position_closed', {
            'instrument': instrument,
            'direction': position.direction,
            'size': position.position_size,
            'price': exec_price,
            'value': position_value,
            'realized_pnl': realized_pnl,
            'position_id': position.position_id,
            'timestamp': timestamp.isoformat()
        })
        
        # Remove position
        if instrument in self.portfolio.positions:
            del self.portfolio.positions[instrument]
        
        self.logger.info(f"Closed position: {instrument}, Size: {position.position_size}, "
                       f"Price: {exec_price}, Value: {position_value:.2f}, PnL: {realized_pnl:.2f}")
    
    def _rebalance_position(self, instruction: AllocationInstruction, exec_price: float, 
                           timestamp: datetime.datetime) -> None:
        """Rebalance an existing position (close and reopen at target size)"""
        instrument = instruction.instrument
        position_id = instruction.position_id
        
        # Get the position
        position = None
        if position_id:
            position = self.portfolio.get_position_by_id(position_id)
        
        if not position and instrument in self.portfolio.positions:
            position = self.portfolio.positions[instrument]
        
        if not position:
            self.logger.warning(f"Position not found for {instrument}")
            return
        
        # Calculate realized P&L from the close
        price_change = (exec_price - position.entry_price) * position.direction
        realized_pnl = price_change * position.position_size
        
        # Close old position value
        old_position_value = position.position_size * exec_price
        
        # Open new position value
        new_position_value = instruction.target_size * exec_price
        
        # Net cash effect
        cash_effect = old_position_value - new_position_value
        
        # Update portfolio cash
        self.portfolio.cash += cash_effect
        self.portfolio.realized_pnl += realized_pnl
        
        # Update position
        position.entry_price = exec_price
        position.position_size = instruction.target_size
        position.last_update_time = timestamp
        position.realized_pnl += realized_pnl
        position.unrealized_pnl = 0.0  # Reset unrealized P&L
        
        # Record transaction
        self.portfolio.add_transaction('rebalance_position', {
            'instrument': instrument,
            'direction': position.direction,
            'old_size': position.position_size,
            'new_size': instruction.target_size,
            'price': exec_price,
            'cash_effect': cash_effect,
            'realized_pnl': realized_pnl,
            'position_id': position.position_id
        })
        
        # Publish event
        event_bus.publish('position_rebalanced', {
            'instrument': instrument,
            'direction': position.direction,
            'old_size': position.position_size,
            'new_size': instruction.target_size,
            'price': exec_price,
            'cash_effect': cash_effect,
            'realized_pnl': realized_pnl,
            'position_id': position.position_id,
            'timestamp': timestamp.isoformat()
        })
        
        self.logger.info(f"Rebalanced position: {instrument}, "
                       f"Size: {position.position_size} -> {instruction.target_size}, "
                       f"Price: {exec_price}, Cash Effect: {cash_effect:.2f}, PnL: {realized_pnl:.2f}")
        
    def calculate_portfolio_metrics(self, 
                                   time_window: str = 'all',
                                   risk_free_rate: float = 0.0) -> PortfolioMetrics:
        """
        Calculate portfolio performance metrics
        
        Args:
            time_window: Time window for metrics calculation ('day', 'week', 'month', 'year', 'all')
            risk_free_rate: Risk-free rate for Sharpe ratio calculation
            
        Returns:
            PortfolioMetrics object
        """
        try:
            # If we have a performance tracker, use it
            if 'default' in self.performance_trackers:
                metrics_dict = self.performance_trackers['default'].calculate_metrics(
                    time_window=time_window,
                    risk_free_rate=risk_free_rate
                )
                
                # If metrics_dict is already a PortfolioMetrics object, return it
                if isinstance(metrics_dict, PortfolioMetrics):
                    return metrics_dict
                
                # Otherwise, create a PortfolioMetrics object from the dictionary
                return PortfolioMetrics(**metrics_dict)
            
            # Get transaction history
            history = self.portfolio.transaction_history
            
            if not history:
                return PortfolioMetrics(time_window=time_window)
            
            # Filter history by time window
            now = datetime.datetime.now()
            if time_window == 'day':
                start_date = now - datetime.timedelta(days=1)
            elif time_window == 'week':
                start_date = now - datetime.timedelta(weeks=1)
            elif time_window == 'month':
                start_date = now - datetime.timedelta(days=30)
            elif time_window == 'year':
                start_date = now - datetime.timedelta(days=365)
            else:
                # All time
                start_date = datetime.datetime.min
            
            filtered_history = [tx for tx in history if tx['timestamp'] >= start_date]
            
            if not filtered_history:
                return PortfolioMetrics(time_window=time_window, start_date=start_date, end_date=now)
            
            # Calculate basic metrics
            total_pnl = sum(tx.get('realized_pnl', 0) for tx in filtered_history if 'realized_pnl' in tx)
            total_pnl += self.portfolio.unrealized_pnl
            
            # Calculate total return
            starting_equity = self.portfolio.initial_capital
            total_return = total_pnl / starting_equity if starting_equity > 0 else 0
            
            # Count trades
            closes = [tx for tx in filtered_history if tx['type'] == 'close_position']
            win_count = sum(1 for tx in closes if tx.get('realized_pnl', 0) > 0)
            loss_count = sum(1 for tx in closes if tx.get('realized_pnl', 0) <= 0)
            
            # Calculate win rate
            total_trades = win_count + loss_count
            win_rate = win_count / total_trades if total_trades > 0 else 0
            
            # Calculate average profit/loss
            win_pnl = sum(tx.get('realized_pnl', 0) for tx in closes if tx.get('realized_pnl', 0) > 0)
            loss_pnl = sum(tx.get('realized_pnl', 0) for tx in closes if tx.get('realized_pnl', 0) <= 0)
            
            avg_profit = win_pnl / win_count if win_count > 0 else 0
            avg_loss = loss_pnl / loss_count if loss_count > 0 else 0
            avg_trade = total_pnl / total_trades if total_trades > 0 else 0
            
            # Calculate profit factor
            profit_factor = abs(win_pnl / loss_pnl) if loss_pnl != 0 else float('inf')
            
            # Simplified drawdown calculation - for more precise calculation would need equity curve
            max_drawdown = 1.0 - (self.portfolio.current_equity / self.portfolio.high_water_mark)
            max_drawdown = max(0.0, max_drawdown)  # Ensure non-negative
            
            # Create metrics object
            metrics = PortfolioMetrics(
                total_return=total_return,
                win_rate=win_rate,
                profit_factor=profit_factor,
                avg_profit_per_trade=avg_profit,
                avg_loss_per_trade=avg_loss,
                avg_trade=avg_trade,
                max_drawdown=max_drawdown,
                time_window=time_window,
                start_date=start_date,
                end_date=now
            )
            
            return metrics
            
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Metrics calculation error: {str(e)}",
                    component="PortfolioOrchestrator",
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.DATA,
                    context={'time_window': time_window},
                    original_exception=e
                )
            )
            # Return minimal metrics on error
            return PortfolioMetrics(time_window=time_window)
    
    def get_portfolio_state(self) -> Portfolio:
        """Get current portfolio state"""
        return self.portfolio
    
    def get_allocation_summary(self) -> Dict[str, Dict[str, Any]]:
        """Get current allocation summary"""
        if not self.portfolio.positions:
            return {}
        
        # Calculate total position value
        position_values = {
            pos.instrument: {
                'size': pos.position_size,
                'value': pos.position_size * pos.entry_price,
                'direction': pos.direction,
                'entry_price': pos.entry_price,
                'risk_percent': pos.risk_percent,
                'unrealized_pnl': pos.unrealized_pnl,
                'strategy': pos.strategy_name,
                'entry_time': pos.entry_time
            }
            for pos in self.portfolio.positions.values()
        }
        
        total_value = sum(pos['value'] for pos in position_values.values())
        
        # Calculate allocation percentages
        for instrument, data in position_values.items():
            data['allocation'] = data['value'] / total_value if total_value > 0 else 0
        
        return position_values