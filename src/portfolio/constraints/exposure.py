# src/portfolio/constraints/exposure.py

from typing import Dict, Any, List
import logging

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction
from balance_breaker.src.portfolio.constraints.base import Constraint


class MaxExposureConstraint(Constraint):
    """
    Maximum exposure constraint
    
    Ensures that the total portfolio exposure (risk) doesn't exceed
    a specified threshold.
    
    Parameters:
    -----------
    max_exposure : float
        Maximum portfolio exposure as percentage (0.0 to 1.0)
    apply_to_new_only : bool
        If True, only apply to new positions, otherwise scale all positions
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Constraint parameters
        """
        default_params = {
            'max_exposure': 0.5,        # 50% max exposure
            'apply_to_new_only': False  # Apply to all positions
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
    
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply maximum exposure constraint to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of allocation instructions
        """
        if not instructions:
            return []
        
        max_exposure = self.parameters['max_exposure']
        apply_to_new_only = self.parameters['apply_to_new_only']
        
        # Calculate total risk from instructions
        total_risk = sum(instr.risk_percent for instr in instructions)
        
        # If considering existing positions, add their risk too
        if not apply_to_new_only:
            # Add risk from existing positions that aren't being closed
            existing_risk = 0.0
            for pos in portfolio.positions.values():
                # Skip positions that are being closed in the instructions
                is_closing = any(
                    instr.instrument == pos.instrument and 
                    instr.action.value == "close" 
                    for instr in instructions
                )
                if not is_closing:
                    existing_risk += pos.risk_percent
            
            total_risk += existing_risk
        
        # Apply constraint if necessary
        if total_risk > max_exposure:
            # Calculate scale factor
            scale_factor = max_exposure / total_risk
            
            self.logger.info(
                f"Scaling positions by {scale_factor:.2f} to meet max exposure of {max_exposure:.1%}"
            )
            
            # Apply scaling to instructions
            for instr in instructions:
                instr.target_size *= scale_factor
                instr.risk_percent *= scale_factor
                
                # Add constraint metadata
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'scale_factor': scale_factor,
                    'reason': 'max_exposure_limit'
                })
        
        return instructions
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets this constraint
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        max_exposure = self.parameters['max_exposure']
        current_exposure = portfolio.total_exposure
        
        valid = current_exposure <= max_exposure
        
        return {
            'valid': valid,
            'current_exposure': current_exposure,
            'max_exposure': max_exposure,
            'violations': [] if valid else ['total_exposure_exceeded']
        }