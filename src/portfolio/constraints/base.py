"""
Base interface for portfolio constraints
"""

import logging
from abc import abstractmethod
from typing import Dict, Any, List, Optional, Tuple

from balance_breaker.src.core.interface_registry import implements
from balance_breaker.src.core.parameter_manager import ParameterizedComponent
from balance_breaker.src.core.error_handling import ErrorHandler, PortfolioError, ErrorSeverity, ErrorCategory
from balance_breaker.src.portfolio.interfaces import Constraint as IConstraint
from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction


@implements("Constraint")
class Constraint(ParameterizedComponent, IConstraint):
    """
    Base class for portfolio constraints
    
    Constraints enforce rules on portfolio allocations, such as maximum exposure,
    correlation limits, or instrument restrictions. Each constraint implements
    a specific rule that can be applied to a set of allocation instructions.
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Constraint parameters specific to each constraint type
        """
        super().__init__(parameters)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.error_handler = ErrorHandler(self.logger)
        self.name = self.__class__.__name__
    
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply constraint to allocation instructions
        
        This method calls the implementation method and handles errors.
        
        Args:
            instructions: List of allocation instructions to be constrained
            portfolio: Current portfolio state for context
            
        Returns:
            Updated list of allocation instructions that satisfy the constraint
        """
        try:
            return self._apply_impl(instructions, portfolio)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Constraint application error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.ERROR,
                    category=ErrorCategory.EXECUTION,
                    context={
                        'instructions_count': len(instructions),
                        'portfolio_positions': len(portfolio.positions)
                    },
                    original_exception=e
                )
            )
            # Return original instructions on error
            return instructions
    
    @abstractmethod
    def _apply_impl(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Implementation method for constraint logic - to be overridden by subclasses
        
        Args:
            instructions: List of allocation instructions to be constrained
            portfolio: Current portfolio state for context
            
        Returns:
            Updated list of allocation instructions that satisfy the constraint
        """
        pass
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets this constraint
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results containing at minimum:
            - valid: Boolean indicating if the constraint is satisfied
            - violations: List of violation descriptions if not valid
        """
        try:
            return self._validate_impl(portfolio)
        except Exception as e:
            self.error_handler.handle_error(
                PortfolioError(
                    message=f"Constraint validation error: {str(e)}",
                    component=self.name,
                    severity=ErrorSeverity.WARNING,
                    category=ErrorCategory.VALIDATION,
                    context={'portfolio_positions': len(portfolio.positions)},
                    original_exception=e
                )
            )
            # Return default validation result on error
            return {'valid': False, 'violations': [f"Validation error: {str(e)}"]}
    
    def _validate_impl(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Implementation method for constraint validation - can be overridden by subclasses
        
        Default implementation assumes the constraint is satisfied.
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        return {'valid': True, 'violations': []}
    
    def explain(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> str:
        """
        Explain constraint effect on allocation instructions
        
        This method provides a human-readable explanation of how the constraint
        would affect the given set of allocation instructions.
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            String explanation of constraint effects
        """
        # Default implementation - can be overridden for more specific explanations
        constraint_name = self.name.replace('Constraint', '')
        params_str = ', '.join(f"{k}={v}" for k, v in self.parameters.items())
        
        return f"{constraint_name} constraint with parameters: {params_str}"
    
    def get_violation_details(self, portfolio: Portfolio) -> List[Dict[str, Any]]:
        """
        Get detailed information about constraint violations
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            List of violation details, each containing:
            - type: Type of violation
            - description: Human-readable description
            - severity: Severity level ('info', 'warning', 'critical')
            - affected_positions: List of affected position IDs (if applicable)
        """
        validation = self.validate(portfolio)
        
        if validation.get('valid', True):
            return []
            
        # Default implementation - can be overridden for more specific details
        return [
            {
                'type': violation,
                'description': f"Portfolio violates {violation} rule",
                'severity': 'warning',
                'affected_positions': []
            }
            for violation in validation.get('violations', [])
        ]