"""
Correlation constraint for portfolio management

This constraint ensures that the portfolio doesn't contain too many highly correlated
positions, which helps with diversification and risk management.
"""

import logging
import numpy as np
from typing import Dict, Any, List, Optional, Tuple, Set

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction, AllocationAction
from balance_breaker.src.portfolio.constraints.base import Constraint


class CorrelationConstraint(Constraint):
    """
    Correlation constraint
    
    Ensures that positions in the portfolio don't exceed specified correlation thresholds.
    Helps maintain diversification by preventing too many highly correlated positions.
    
    Parameters:
    -----------
    max_correlation : float
        Maximum allowed correlation between any two positions (0.0 to 1.0)
    max_avg_correlation : float
        Maximum allowed average correlation for the portfolio (0.0 to 1.0)
    correlation_data : dict
        Correlation data between instruments. Can be updated dynamically.
    rejection_threshold : float
        Correlation threshold above which to reject positions outright
    scaling_method : str
        Method to use when scaling positions ('reject', 'scale', 'prioritize')
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Constraint parameters
        """
        default_params = {
            'max_correlation': 0.7,        # Maximum pairwise correlation
            'max_avg_correlation': 0.5,    # Maximum average correlation
            'correlation_data': {},        # Empty initial correlation data
            'rejection_threshold': 0.9,    # Reject positions with correlation > 0.9
            'scaling_method': 'scale'      # Scale positions rather than reject
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
        
        # Initialize correlation matrix if not provided
        if not self.parameters['correlation_data']:
            self.parameters['correlation_data'] = self._create_default_correlation()
    
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply correlation constraint to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of allocation instructions
        """
        if not instructions:
            return []
        
        # For each new or increased position, check correlations with existing positions
        # that aren't being closed
        
        # First, identify which instruments are being closed
        closing_instruments = {
            instr.instrument for instr in instructions 
            if instr.action == AllocationAction.CLOSE
        }
        
        # Identify existing positions that will remain after these instructions
        remaining_positions = {
            inst: pos for inst, pos in portfolio.positions.items()
            if inst not in closing_instruments
        }
        
        # Identify new or increased positions
        new_or_increased = [
            instr for instr in instructions
            if instr.action in [AllocationAction.CREATE, AllocationAction.INCREASE, AllocationAction.REBALANCE]
        ]
        
        # Updated instructions list (start with originals)
        updated_instructions = instructions.copy()
        
        # For each new/increased position, check correlations
        for instr in new_or_increased:
            # Skip if already being handled by other constraints
            if 'skip_correlation_check' in instr.metadata:
                continue
                
            instrument = instr.instrument
            
            # Get correlations with existing positions
            correlations = []
            for existing_inst, position in remaining_positions.items():
                # Skip self-correlation
                if existing_inst == instrument:
                    continue
                
                # Get correlation between this instrument and existing one
                correlation = self._get_correlation(instrument, existing_inst)
                correlations.append((existing_inst, correlation))
            
            # Check if any correlation exceeds limits
            high_correlations = [
                (inst, corr) for inst, corr in correlations
                if corr > self.parameters['max_correlation']
            ]
            
            # If correlations exceed threshold, apply the constraint
            if high_correlations:
                # Method selection
                method = self.parameters['scaling_method']
                
                if method == 'reject' or any(corr > self.parameters['rejection_threshold'] 
                                           for _, corr in high_correlations):
                    # Reject the position entirely
                    self.logger.info(f"Rejecting {instrument} due to high correlation")
                    
                    # Remove this instruction from updated list
                    updated_instructions = [
                        i for i in updated_instructions if i.instrument != instrument or i.action == AllocationAction.CLOSE
                    ]
                    
                    # Add metadata about rejection
                    for i in instructions:
                        if i.instrument == instrument and i not in updated_instructions:
                            if 'applied_constraints' not in i.metadata:
                                i.metadata['applied_constraints'] = []
                            
                            i.metadata['applied_constraints'].append({
                                'constraint': self.name,
                                'action': 'rejected',
                                'reason': 'high_correlation',
                                'correlations': [
                                    {'instrument': inst, 'correlation': corr}
                                    for inst, corr in high_correlations
                                ]
                            })
                    
                elif method == 'scale':
                    # Scale down the position based on the highest correlation
                    highest_corr = max(corr for _, corr in high_correlations)
                    
                    # Calculate scale factor (linear reduction based on how much it exceeds limit)
                    max_corr = self.parameters['max_correlation']
                    excess = highest_corr - max_corr
                    scale_factor = max(0.1, 1.0 - excess)  # Don't scale below 10%
                    
                    # Apply scaling
                    for i in updated_instructions:
                        if i.instrument == instrument and i.action != AllocationAction.CLOSE:
                            i.target_size *= scale_factor
                            if hasattr(i, 'risk_percent'):
                                i.risk_percent *= scale_factor
                            
                            # Add metadata about scaling
                            if 'applied_constraints' not in i.metadata:
                                i.metadata['applied_constraints'] = []
                            
                            i.metadata['applied_constraints'].append({
                                'constraint': self.name,
                                'action': 'scaled',
                                'scale_factor': scale_factor,
                                'reason': 'high_correlation',
                                'correlations': [
                                    {'instrument': inst, 'correlation': corr}
                                    for inst, corr in high_correlations
                                ]
                            })
                            
                    self.logger.info(f"Scaled {instrument} by {scale_factor:.2f} due to high correlation")
                    
                elif method == 'prioritize':
                    # Prioritize based on signal strength or other metrics
                    # This would require additional context like signal strength
                    
                    # If we have signal strength in metadata, use it for prioritization
                    if 'strength' in instr.metadata:
                        # For now, just log the prioritization
                        self.logger.info(f"Prioritizing {instrument} based on signal strength")
                        
                        # Simple implementation: if strength < 0.5, scale down
                        strength = instr.metadata['strength']
                        if strength < 0.5:
                            scale_factor = strength * 2  # scale from 0 to 1
                            
                            # Apply scaling
                            for i in updated_instructions:
                                if i.instrument == instrument and i.action != AllocationAction.CLOSE:
                                    i.target_size *= scale_factor
                                    if hasattr(i, 'risk_percent'):
                                        i.risk_percent *= scale_factor
                            
                            self.logger.info(f"Scaled {instrument} by {scale_factor:.2f} due to prioritization")
                    else:
                        # Without strength info, default to mild scaling
                        scale_factor = 0.7
                        
                        # Apply scaling
                        for i in updated_instructions:
                            if i.instrument == instrument and i.action != AllocationAction.CLOSE:
                                i.target_size *= scale_factor
                                if hasattr(i, 'risk_percent'):
                                    i.risk_percent *= scale_factor
                        
                        self.logger.info(f"Applied default scaling to {instrument} due to high correlation")
        
        # Check average portfolio correlation (including new positions)
        # This is a more complex check that would require looking at the entire correlation matrix
        # For simplicity, we'll skip it in this implementation
        
        return updated_instructions
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets correlation constraints
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        if len(portfolio.positions) < 2:
            return {'valid': True, 'violations': []}
        
        # Calculate all pairwise correlations
        instruments = list(portfolio.positions.keys())
        high_correlations = []
        all_correlations = []
        
        for i in range(len(instruments)):
            for j in range(i+1, len(instruments)):
                inst1 = instruments[i]
                inst2 = instruments[j]
                
                correlation = self._get_correlation(inst1, inst2)
                all_correlations.append(correlation)
                
                if correlation > self.parameters['max_correlation']:
                    high_correlations.append({
                        'instrument1': inst1,
                        'instrument2': inst2,
                        'correlation': correlation
                    })
        
        # Calculate average correlation
        avg_correlation = sum(all_correlations) / len(all_correlations) if all_correlations else 0
        
        # Determine validity
        valid = (len(high_correlations) == 0 and 
                avg_correlation <= self.parameters['max_avg_correlation'])
        
        # Create violation list
        violations = []
        if len(high_correlations) > 0:
            violations.append('high_pairwise_correlation')
        if avg_correlation > self.parameters['max_avg_correlation']:
            violations.append('high_avg_correlation')
        
        return {
            'valid': valid,
            'violations': violations,
            'high_correlations': high_correlations,
            'avg_correlation': avg_correlation,
            'max_correlation': self.parameters['max_correlation'],
            'max_avg_correlation': self.parameters['max_avg_correlation']
        }
    
    def get_violation_details(self, portfolio: Portfolio) -> List[Dict[str, Any]]:
        """
        Get detailed information about correlation constraint violations
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            List of violation details
        """
        validation = self.validate(portfolio)
        
        if validation.get('valid', True):
            return []
            
        details = []
        
        # Handle high pairwise correlations
        if 'high_pairwise_correlation' in validation.get('violations', []):
            high_corrs = validation.get('high_correlations', [])
            
            for corr_info in high_corrs:
                details.append({
                    'type': 'high_pairwise_correlation',
                    'description': (f"High correlation ({corr_info['correlation']:.2f}) between "
                                   f"{corr_info['instrument1']} and {corr_info['instrument2']}"),
                    'severity': 'warning',
                    'affected_positions': [corr_info['instrument1'], corr_info['instrument2']],
                    'correlation': corr_info['correlation'],
                    'max_allowed': self.parameters['max_correlation']
                })
        
        # Handle high average correlation
        if 'high_avg_correlation' in validation.get('violations', []):
            details.append({
                'type': 'high_avg_correlation',
                'description': (f"Portfolio average correlation ({validation['avg_correlation']:.2f}) "
                               f"exceeds maximum ({self.parameters['max_avg_correlation']:.2f})"),
                'severity': 'warning',
                'affected_positions': list(portfolio.positions.keys()),
                'avg_correlation': validation['avg_correlation'],
                'max_allowed': self.parameters['max_avg_correlation']
            })
            
        return details
    
    def explain(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> str:
        """
        Explain correlation constraint effect on allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            String explanation of constraint effects
        """
        validation = self.validate(portfolio)
        
        explanation = [
            f"Correlation Constraint (max={self.parameters['max_correlation']:.2f}, "
            f"avg max={self.parameters['max_avg_correlation']:.2f}):"
        ]
        
        if not instructions:
            explanation.append("  No allocation instructions to evaluate.")
            return "\n".join(explanation)
        
        # Count new/increased positions
        new_positions = [
            instr.instrument for instr in instructions
            if instr.action in [AllocationAction.CREATE, AllocationAction.INCREASE]
        ]
        
        if not new_positions:
            explanation.append("  No new or increased positions to evaluate for correlation.")
            return "\n".join(explanation)
        
        # Check portfolio state
        if validation.get('valid', True):
            explanation.append("  Current portfolio satisfies correlation constraints.")
        else:
            for violation in validation.get('violations', []):
                if violation == 'high_pairwise_correlation':
                    high_corrs = validation.get('high_correlations', [])
                    explanation.append(f"  {len(high_corrs)} high correlation pairs in current portfolio.")
                    
                    # List a few examples
                    for i, corr in enumerate(high_corrs[:3]):  # Show at most 3 examples
                        explanation.append(
                            f"    - {corr['instrument1']} and {corr['instrument2']}: "
                            f"{corr['correlation']:.2f}"
                        )
                    
                    if len(high_corrs) > 3:
                        explanation.append(f"    - ... and {len(high_corrs) - 3} more.")
                        
                elif violation == 'high_avg_correlation':
                    explanation.append(
                        f"  Portfolio average correlation ({validation['avg_correlation']:.2f}) "
                        f"exceeds maximum ({self.parameters['max_avg_correlation']:.2f})."
                    )
        
        # Explain potential effects on new positions
        explanation.append(f"\n  Evaluating {len(new_positions)} new/increased positions:")
        
        for instrument in new_positions:
            # Find existing correlated instruments
            correlated_instruments = []
            
            for existing_inst in portfolio.positions:
                if existing_inst != instrument:
                    correlation = self._get_correlation(instrument, existing_inst)
                    if correlation > self.parameters['max_correlation']:
                        correlated_instruments.append((existing_inst, correlation))
            
            if correlated_instruments:
                explanation.append(f"    - {instrument} may be affected due to correlation with:")
                for inst, corr in correlated_instruments:
                    explanation.append(f"      * {inst}: {corr:.2f}")
                
                # Explain what would happen
                method = self.parameters['scaling_method']
                if method == 'reject':
                    explanation.append(f"      → Position would be rejected due to correlation.")
                elif method == 'scale':
                    # Estimate scaling based on highest correlation
                    highest_corr = max(corr for _, corr in correlated_instruments)
                    excess = highest_corr - self.parameters['max_correlation']
                    scale_factor = max(0.1, 1.0 - excess)
                    explanation.append(f"      → Position would be scaled by ~{scale_factor:.2f}.")
                elif method == 'prioritize':
                    explanation.append(f"      → Position would be prioritized based on signal strength.")
            else:
                explanation.append(f"    - {instrument}: No correlation issues expected.")
        
        return "\n".join(explanation)
    
    def _get_correlation(self, instrument1: str, instrument2: str) -> float:
        """
        Get correlation between two instruments
        
        Args:
            instrument1: First instrument
            instrument2: Second instrument
            
        Returns:
            Correlation value between 0 and 1
        """
        correlation_data = self.parameters['correlation_data']
        
        # Check if we have data for this pair
        key = f"{instrument1}_{instrument2}"
        reverse_key = f"{instrument2}_{instrument1}"
        
        if key in correlation_data:
            return correlation_data[key]
        elif reverse_key in correlation_data:
            return correlation_data[reverse_key]
        else:
            # Use default correlation estimates if not available
            return self._estimate_correlation(instrument1, instrument2)
    
    def _estimate_correlation(self, instrument1: str, instrument2: str) -> float:
        """
        Estimate correlation between two instruments based on currency pairs
        
        Args:
            instrument1: First instrument
            instrument2: Second instrument
            
        Returns:
            Estimated correlation
        """
        # This is a very simple model for FX pairs
        # A more accurate implementation would use historical data or a proper correlation model
        
        # If the same instrument, correlation is 1.0
        if instrument1 == instrument2:
            return 1.0
        
        # Extract currencies from pair names (assuming format like "EURUSD")
        def extract_currencies(pair):
            if len(pair) >= 6:
                base = pair[0:3]
                quote = pair[3:6]
                return base, quote
            return pair, ""
        
        base1, quote1 = extract_currencies(instrument1)
        base2, quote2 = extract_currencies(instrument2)
        
        # Check for common currencies in pairs
        common_currencies = set([base1, quote1]).intersection(set([base2, quote2]))
        
        # No common currencies
        if not common_currencies:
            # Default low correlation for unrelated pairs
            return 0.2
        
        # Special cases with known high correlations
        high_corr_pairs = [
            ({"EUR", "GBP"}, 0.7),    # EUR and GBP pairs
            ({"AUD", "NZD"}, 0.8),    # AUD and NZD pairs
            ({"USD", "CAD"}, 0.65),   # USD and CAD pairs
        ]
        
        currencies = {base1, quote1, base2, quote2}
        for pair_set, corr in high_corr_pairs:
            if len(pair_set.intersection(currencies)) >= 2:
                return corr
        
        # Same base currency
        if base1 == base2:
            return 0.5
        
        # Same quote currency
        if quote1 == quote2:
            return 0.5
        
        # Inverse pairs (e.g., EURUSD and USDCHF)
        if base1 == quote2 or quote1 == base2:
            return -0.5
        
        # Default moderate correlation
        return 0.3
    
    def _create_default_correlation(self) -> Dict[str, float]:
        """
        Create default correlation data for common FX pairs
        
        Returns:
            Dictionary with correlation data
        """
        # Common FX pairs
        pairs = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
        
        correlations = {}
        
        # Calculate all pairwise correlations
        for i in range(len(pairs)):
            for j in range(i+1, len(pairs)):
                pair1 = pairs[i]
                pair2 = pairs[j]
                
                # Estimate correlation
                correlation = self._estimate_correlation(pair1, pair2)
                
                # Store in dictionary
                key = f"{pair1}_{pair2}"
                correlations[key] = correlation
        
        return correlations
    
    def update_correlation_data(self, correlation_matrix: Dict[str, float]) -> None:
        """
        Update correlation data with new values
        
        Args:
            correlation_matrix: Dictionary with correlation data
        """
        self.parameters['correlation_data'].update(correlation_matrix)
        self.logger.info(f"Updated correlation data with {len(correlation_matrix)} values")
    
    def update_instrument_correlations(self, instrument: str, correlations: Dict[str, float]) -> None:
        """
        Update correlations for a specific instrument
        
        Args:
            instrument: Instrument name
            correlations: Dictionary with correlations to other instruments
        """
        for other_instrument, correlation in correlations.items():
            key = f"{instrument}_{other_instrument}"
            self.parameters['correlation_data'][key] = correlation
        
        self.logger.info(f"Updated correlations for {instrument} with {len(correlations)} values")