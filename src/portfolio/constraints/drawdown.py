"""
Drawdown constraint for portfolio management

This constraint adjusts position sizing based on current portfolio drawdown
to reduce risk during drawdown periods.
"""

import logging
from typing import Dict, List, Any, Optional

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction, AllocationAction
from balance_breaker.src.portfolio.constraints.base import Constraint


class DrawdownConstraint(Constraint):
    """
    Drawdown constraint
    
    Scales position sizes based on the current portfolio drawdown to reduce
    risk during drawdown periods. Can also block new positions during severe drawdowns.
    
    Parameters:
    -----------
    max_drawdown : float
        Maximum allowed drawdown before blocking new positions (0.0 to 1.0)
    scaling_threshold : float
        Drawdown threshold to start scaling positions (0.0 to 1.0)
    scaling_method : str
        Method to scale positions ('linear', 'exponential', 'step')
    apply_to_existing : bool
        Whether to apply to existing positions or only new ones
    min_scale_factor : float
        Minimum position scale factor during maximum drawdown
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Constraint parameters
        """
        default_params = {
            'max_drawdown': 0.25,         # 25% max drawdown before blocking new positions
            'scaling_threshold': 0.10,    # Start scaling at 10% drawdown
            'scaling_method': 'linear',   # Linear scaling by default
            'apply_to_existing': False,   # Only apply to new positions
            'min_scale_factor': 0.25,     # Minimum 25% of original size
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
    
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply drawdown constraint to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of allocation instructions
        """
        if not instructions:
            return []
        
        # Get current drawdown
        current_drawdown = portfolio.drawdown
        max_drawdown = self.parameters['max_drawdown']
        scaling_threshold = self.parameters['scaling_threshold']
        
        # Log current drawdown
        self.logger.info(f"Current portfolio drawdown: {current_drawdown:.2%}")
        
        # If drawdown exceeds maximum, block new positions
        if current_drawdown >= max_drawdown:
            self.logger.warning(f"Drawdown {current_drawdown:.2%} exceeds maximum {max_drawdown:.2%}, "
                             f"blocking new positions")
            
            # Filter out CREATE instructions, keep others
            filtered_instructions = []
            for instr in instructions:
                if instr.action != AllocationAction.CREATE:
                    filtered_instructions.append(instr)
                else:
                    # Log rejection due to drawdown
                    self.logger.info(f"Rejected new position for {instr.instrument} due to excessive drawdown")
                    
                    # Add metadata about rejection if needed
                    if 'applied_constraints' not in instr.metadata:
                        instr.metadata['applied_constraints'] = []
                    
                    instr.metadata['applied_constraints'].append({
                        'constraint': self.name,
                        'action': 'rejected',
                        'reason': 'max_drawdown_exceeded',
                        'current_drawdown': current_drawdown,
                        'max_drawdown': max_drawdown
                    })
                    
            return filtered_instructions
        
        # If drawdown exceeds scaling threshold, scale down positions
        elif current_drawdown > scaling_threshold:
            # Calculate scale factor based on drawdown
            scale_factor = self._calculate_scale_factor(current_drawdown)
            
            self.logger.info(f"Scaling positions to {scale_factor:.2%} due to drawdown of {current_drawdown:.2%}")
            
            # Apply scaling to instructions
            for instr in instructions:
                # For existing positions, check if we should apply
                if instr.action in [AllocationAction.INCREASE, AllocationAction.REBALANCE]:
                    if not self.parameters['apply_to_existing']:
                        continue
                
                # Skip CLOSE instructions
                if instr.action == AllocationAction.CLOSE:
                    continue
                
                # Apply scaling
                original_size = instr.target_size
                instr.target_size *= scale_factor
                
                # Also scale risk percentage if available
                if hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    instr.risk_percent *= scale_factor
                
                # Add metadata about scaling
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'action': 'scaled',
                    'scale_factor': scale_factor,
                    'reason': 'drawdown',
                    'original_size': original_size,
                    'current_drawdown': current_drawdown
                })
            
        return instructions
    
    def _calculate_scale_factor(self, drawdown: float) -> float:
        """
        Calculate position scale factor based on drawdown
        
        Args:
            drawdown: Current drawdown (0.0 to 1.0)
            
        Returns:
            Scale factor (0.0 to 1.0)
        """
        # Get parameters
        scaling_threshold = self.parameters['scaling_threshold']
        max_drawdown = self.parameters['max_drawdown']
        min_scale = self.parameters['min_scale_factor']
        method = self.parameters['scaling_method']
        
        # Ensure valid drawdown range
        drawdown = max(0.0, min(drawdown, max_drawdown))
        
        # Calculate normalized drawdown (0.0 to 1.0 within the scaling range)
        if drawdown <= scaling_threshold:
            return 1.0  # No scaling below threshold
            
        normalized_drawdown = (drawdown - scaling_threshold) / (max_drawdown - scaling_threshold)
        
        # Apply scaling method
        if method == 'linear':
            # Linear scaling from 1.0 at threshold to min_scale at max_drawdown
            return 1.0 - normalized_drawdown * (1.0 - min_scale)
            
        elif method == 'exponential':
            # Exponential scaling (steeper reduction as drawdown increases)
            # Normalized drawdown to the power of 2 gives an exponential curve
            # This will reduce position sizes more aggressively as drawdown increases
            return 1.0 - normalized_drawdown ** 2 * (1.0 - min_scale)
            
        elif method == 'step':
            # Step-based scaling
            if normalized_drawdown < 0.33:
                return 0.75  # First step: reduce to 75%
            elif normalized_drawdown < 0.66:
                return 0.5   # Second step: reduce to 50%
            else:
                return min_scale  # Final step: reduce to minimum
        
        else:
            # Default to linear if method not recognized
            self.logger.warning(f"Unrecognized scaling method: {method}, defaulting to linear")
            return 1.0 - normalized_drawdown * (1.0 - min_scale)
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets drawdown constraints
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        current_drawdown = portfolio.drawdown
        max_drawdown = self.parameters['max_drawdown']
        scaling_threshold = self.parameters['scaling_threshold']
        
        # Check if drawdown exceeds maximum
        is_max_exceeded = current_drawdown >= max_drawdown
        is_scaling_needed = current_drawdown > scaling_threshold
        
        # Create validation result
        valid = not is_max_exceeded
        violations = []
        
        if is_max_exceeded:
            violations.append('max_drawdown_exceeded')
        
        if is_scaling_needed:
            violations.append('drawdown_scaling_needed')
        
        return {
            'valid': valid,
            'violations': violations,
            'current_drawdown': current_drawdown,
            'max_drawdown': max_drawdown,
            'scaling_threshold': scaling_threshold,
            'scale_factor': self._calculate_scale_factor(current_drawdown) if is_scaling_needed else 1.0
        }
    
    def get_violation_details(self, portfolio: Portfolio) -> List[Dict[str, Any]]:
        """
        Get detailed information about drawdown constraint violations
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            List of violation details
        """
        validation = self.validate(portfolio)
        
        if validation.get('valid', True):
            return []
            
        details = []
        violations = validation.get('violations', [])
        
        if 'max_drawdown_exceeded' in violations:
            details.append({
                'type': 'max_drawdown_exceeded',
                'description': f"Portfolio drawdown ({validation['current_drawdown']:.2%}) "
                              f"exceeds maximum allowed ({validation['max_drawdown']:.2%})",
                'severity': 'critical',
                'affected_positions': list(portfolio.positions.keys()),
                'current_drawdown': validation['current_drawdown'],
                'max_drawdown': validation['max_drawdown']
            })
        
        if 'drawdown_scaling_needed' in violations:
            details.append({
                'type': 'drawdown_scaling_needed',
                'description': f"Portfolio drawdown ({validation['current_drawdown']:.2%}) "
                              f"requires position scaling (factor: {validation['scale_factor']:.2f})",
                'severity': 'warning',
                'affected_positions': list(portfolio.positions.keys()),
                'current_drawdown': validation['current_drawdown'],
                'scaling_threshold': validation['scaling_threshold'],
                'scale_factor': validation['scale_factor']
            })
            
        return details
    
    def explain(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> str:
        """
        Explain drawdown constraint effect on allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            String explanation of constraint effects
        """
        validation = self.validate(portfolio)
        current_drawdown = validation['current_drawdown']
        max_drawdown = validation['max_drawdown']
        scaling_threshold = validation['scaling_threshold']
        
        explanation = [
            f"Drawdown Constraint (current={current_drawdown:.2%}, max={max_drawdown:.2%}, "
            f"scaling threshold={scaling_threshold:.2%}):"
        ]
        
        if current_drawdown >= max_drawdown:
            explanation.append(f"  Portfolio drawdown exceeds maximum. New positions will be blocked.")
            
            # Count affected instructions
            new_positions = sum(1 for instr in instructions if instr.action == AllocationAction.CREATE)
            if new_positions > 0:
                explanation.append(f"  {new_positions} new position(s) would be rejected.")
                
        elif current_drawdown > scaling_threshold:
            scale_factor = self._calculate_scale_factor(current_drawdown)
            explanation.append(f"  Portfolio in drawdown. Positions will be scaled to {scale_factor:.2%} of original size.")
            
            # Count affected instructions
            affected = sum(1 for instr in instructions 
                         if instr.action != AllocationAction.CLOSE and 
                         (instr.action != AllocationAction.INCREASE or self.parameters['apply_to_existing']))
                         
            if affected > 0:
                explanation.append(f"  {affected} allocation instruction(s) would be scaled.")
                
        else:
            explanation.append(f"  Portfolio drawdown below threshold. No constraint effects.")
            
        return "\n".join(explanation)