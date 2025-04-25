"""
Instrument constraint for portfolio management

This constraint manages allocation based on instrument-specific rules,
such as maximum exposure per instrument, group limits, and blacklisting.
"""

import logging
from typing import Dict, List, Any, Optional, Set

from balance_breaker.src.portfolio.models import Portfolio, AllocationInstruction, AllocationAction
from balance_breaker.src.portfolio.constraints.base import Constraint


class InstrumentConstraint(Constraint):
    """
    Instrument constraint
    
    Enforces instrument-specific allocation rules such as maximum exposure per 
    instrument, instrument group limits, and instrument blacklisting/whitelisting.
    
    Parameters:
    -----------
    max_instrument_exposure : float
        Maximum exposure per instrument as percentage of portfolio (0.0 to 1.0)
    instrument_limits : dict
        Dictionary of instrument-specific allocation limits
    group_limits : dict
        Dictionary of instrument group allocation limits
    blacklist : list
        List of instruments to exclude from allocation
    whitelist : list
        List of instruments to exclusively allow (if provided)
    instrument_groups : dict
        Dictionary mapping instruments to their groups for group constraints
    """
    
    def __init__(self, parameters: Dict[str, Any] = None):
        """
        Initialize with optional parameters
        
        Args:
            parameters: Constraint parameters
        """
        default_params = {
            'max_instrument_exposure': 0.15,   # Max 15% exposure per instrument
            'instrument_limits': {},           # Individual instrument limits
            'group_limits': {},                # Group limits (e.g., 'forex': 0.5)
            'blacklist': [],                   # Blacklisted instruments
            'whitelist': [],                   # Whitelisted instruments (if provided)
            'instrument_groups': {},           # Map instruments to groups
            'default_group': 'other'           # Default group for instruments
        }
        
        if parameters:
            default_params.update(parameters)
            
        super().__init__(default_params)
        self.logger = logging.getLogger(__name__)
    
    def apply(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply instrument constraints to allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of allocation instructions
        """
        if not instructions:
            return []
        
        # Filter blacklisted/whitelisted instruments
        filtered_instructions = self._filter_by_lists(instructions)
        
        # Apply per-instrument limits
        limited_instructions = self._apply_instrument_limits(filtered_instructions, portfolio)
        
        # Apply group limits
        group_limited_instructions = self._apply_group_limits(limited_instructions, portfolio)
        
        return group_limited_instructions
    
    def _filter_by_lists(self, instructions: List[AllocationInstruction]) -> List[AllocationInstruction]:
        """
        Filter instructions based on blacklist/whitelist
        
        Args:
            instructions: List of allocation instructions
            
        Returns:
            Filtered list of instructions
        """
        blacklist = set(self.parameters['blacklist'])
        whitelist = set(self.parameters['whitelist'])
        
        # If neither list has entries, return all instructions
        if not blacklist and not whitelist:
            return instructions
        
        filtered = []
        for instr in instructions:
            instrument = instr.instrument
            
            # Skip closing positions on blacklisted instruments
            if instr.action == AllocationAction.CLOSE:
                filtered.append(instr)
                continue
                
            # Check whitelist (if provided)
            if whitelist and instrument not in whitelist:
                self.logger.info(f"Instrument {instrument} not in whitelist, skipping")
                
                # Add metadata about rejection
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'action': 'rejected',
                    'reason': 'not_in_whitelist'
                })
                continue
            
            # Check blacklist
            if instrument in blacklist:
                self.logger.info(f"Instrument {instrument} in blacklist, skipping")
                
                # Add metadata about rejection
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'action': 'rejected',
                    'reason': 'in_blacklist'
                })
                continue
            
            # If passes all checks, add to filtered list
            filtered.append(instr)
        
        return filtered
    
    def _apply_instrument_limits(self, instructions: List[AllocationInstruction], 
                               portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply per-instrument exposure limits
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of instructions
        """
        max_exposure = self.parameters['max_instrument_exposure']
        instrument_limits = self.parameters['instrument_limits']
        
        # Calculate current allocations by instrument
        current_allocations = self._calculate_current_allocations(portfolio)
        
        # Calculate new allocations from instructions
        for instr in instructions:
            if instr.action == AllocationAction.CLOSE:
                # For close actions, set allocation to 0
                current_allocations[instr.instrument] = 0
                
            elif instr.action in [AllocationAction.CREATE, AllocationAction.INCREASE, 
                                AllocationAction.REBALANCE]:
                # For new or increased positions, use risk_percent from instruction
                if hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    current_allocations[instr.instrument] = instr.risk_percent
        
        # Apply limits to each instruction
        for instr in instructions:
            instrument = instr.instrument
            
            # Skip CLOSE actions
            if instr.action == AllocationAction.CLOSE:
                continue
                
            # Get current allocation after this instruction
            allocation = current_allocations.get(instrument, 0)
            
            # Determine instrument limit (specific limit or default max)
            limit = instrument_limits.get(instrument, max_exposure)
            
            # Check if allocation exceeds limit
            if allocation > limit:
                # Calculate scale factor
                scale_factor = limit / allocation
                
                # Original values for metadata
                original_size = instr.target_size
                original_risk = instr.risk_percent if hasattr(instr, 'risk_percent') else None
                
                # Scale position size
                instr.target_size *= scale_factor
                
                # Scale risk percentage if available
                if hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    instr.risk_percent *= scale_factor
                
                # Update current allocation for this instrument
                current_allocations[instrument] = limit
                
                # Add metadata about scaling
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'action': 'scaled',
                    'scale_factor': scale_factor,
                    'reason': 'instrument_limit',
                    'original_size': original_size,
                    'original_risk': original_risk,
                    'limit': limit
                })
                
                self.logger.info(f"Scaled {instrument} position to {scale_factor:.2%} due to instrument limit")
        
        return instructions
    
    def _apply_group_limits(self, instructions: List[AllocationInstruction], 
                          portfolio: Portfolio) -> List[AllocationInstruction]:
        """
        Apply instrument group exposure limits
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            Updated list of instructions
        """
        group_limits = self.parameters['group_limits']
        instrument_groups = self.parameters['instrument_groups']
        default_group = self.parameters['default_group']
        
        # If no group limits defined, return unchanged
        if not group_limits:
            return instructions
        
        # Calculate current allocations by instrument
        instrument_allocations = self._calculate_current_allocations(portfolio)
        
        # Calculate allocations from instructions
        for instr in instructions:
            if instr.action == AllocationAction.CLOSE:
                # For close actions, set allocation to 0
                instrument_allocations[instr.instrument] = 0
                
            elif instr.action in [AllocationAction.CREATE, AllocationAction.INCREASE, 
                                AllocationAction.REBALANCE]:
                # For new or increased positions, use risk_percent from instruction
                if hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    instrument_allocations[instr.instrument] = instr.risk_percent
        
        # Calculate group allocations
        group_allocations = {}
        for instrument, allocation in instrument_allocations.items():
            group = instrument_groups.get(instrument, default_group)
            group_allocations[group] = group_allocations.get(group, 0) + allocation
        
        # Check for group limit violations
        violated_groups = {group: alloc for group, alloc in group_allocations.items()
                         if group in group_limits and alloc > group_limits[group]}
        
        if not violated_groups:
            # No violations, return unchanged
            return instructions
        
        # Calculate scale factors per group
        group_scale_factors = {group: group_limits[group] / alloc 
                            for group, alloc in violated_groups.items()}
        
        # Apply scaling to instructions
        for instr in instructions:
            instrument = instr.instrument
            
            # Skip CLOSE actions
            if instr.action == AllocationAction.CLOSE:
                continue
                
            # Get instrument group
            group = instrument_groups.get(instrument, default_group)
            
            # Check if group is violated
            if group in group_scale_factors:
                scale_factor = group_scale_factors[group]
                
                # Original values for metadata
                original_size = instr.target_size
                original_risk = instr.risk_percent if hasattr(instr, 'risk_percent') else None
                
                # Scale position size
                instr.target_size *= scale_factor
                
                # Scale risk percentage if available
                if hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    instr.risk_percent *= scale_factor
                
                # Add metadata about scaling
                if 'applied_constraints' not in instr.metadata:
                    instr.metadata['applied_constraints'] = []
                
                instr.metadata['applied_constraints'].append({
                    'constraint': self.name,
                    'action': 'scaled',
                    'scale_factor': scale_factor,
                    'reason': 'group_limit',
                    'group': group,
                    'original_size': original_size,
                    'original_risk': original_risk,
                    'group_limit': group_limits[group]
                })
                
                self.logger.info(f"Scaled {instrument} position to {scale_factor:.2%} due to group limit for {group}")
        
        return instructions
    
    def _calculate_current_allocations(self, portfolio: Portfolio) -> Dict[str, float]:
        """
        Calculate current allocations by instrument
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary of allocations (risk percentages) by instrument
        """
        return {pos.instrument: pos.risk_percent for pos in portfolio.positions.values()}
    
    def validate(self, portfolio: Portfolio) -> Dict[str, Any]:
        """
        Validate if current portfolio state meets instrument constraints
        
        Args:
            portfolio: Current portfolio state
            
        Returns:
            Dictionary with validation results
        """
        max_exposure = self.parameters['max_instrument_exposure']
        instrument_limits = self.parameters['instrument_limits']
        group_limits = self.parameters['group_limits']
        instrument_groups = self.parameters['instrument_groups']
        default_group = self.parameters['default_group']
        blacklist = set(self.parameters['blacklist'])
        whitelist = set(self.parameters['whitelist'])
        
        # Check for blacklisted instruments
        blacklisted = [i for i in portfolio.positions if i in blacklist]
        
        # Check for instruments not in whitelist (if whitelist provided)
        not_whitelisted = []
        if whitelist:
            not_whitelisted = [i for i in portfolio.positions if i not in whitelist]
        
        # Check for instrument limit violations
        instrument_allocations = self._calculate_current_allocations(portfolio)
        
        instrument_violations = []
        for instrument, allocation in instrument_allocations.items():
            limit = instrument_limits.get(instrument, max_exposure)
            if allocation > limit:
                instrument_violations.append({
                    'instrument': instrument,
                    'allocation': allocation,
                    'limit': limit,
                    'excess': allocation - limit
                })
        
        # Check for group limit violations
        group_allocations = {}
        for instrument, allocation in instrument_allocations.items():
            group = instrument_groups.get(instrument, default_group)
            group_allocations[group] = group_allocations.get(group, 0) + allocation
        
        group_violations = []
        for group, allocation in group_allocations.items():
            if group in group_limits and allocation > group_limits[group]:
                group_violations.append({
                    'group': group,
                    'allocation': allocation,
                    'limit': group_limits[group],
                    'excess': allocation - group_limits[group]
                })
        
        # Determine overall validity
        valid = (not blacklisted and not not_whitelisted and
                not instrument_violations and not group_violations)
        
        # Collect all violations
        violations = []
        if blacklisted:
            violations.append('blacklisted_instruments')
        if not_whitelisted:
            violations.append('non_whitelisted_instruments')
        if instrument_violations:
            violations.append('instrument_limit_exceeded')
        if group_violations:
            violations.append('group_limit_exceeded')
        
        return {
            'valid': valid,
            'violations': violations,
            'blacklisted': blacklisted,
            'not_whitelisted': not_whitelisted if whitelist else [],
            'instrument_violations': instrument_violations,
            'group_violations': group_violations
        }
    
    def get_violation_details(self, portfolio: Portfolio) -> List[Dict[str, Any]]:
        """
        Get detailed information about instrument constraint violations
        
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
        
        # Blacklisted instruments
        if 'blacklisted_instruments' in violations:
            blacklisted = validation.get('blacklisted', [])
            details.append({
                'type': 'blacklisted_instruments',
                'description': f"Portfolio contains blacklisted instruments: {', '.join(blacklisted)}",
                'severity': 'warning',
                'affected_positions': blacklisted
            })
        
        # Non-whitelisted instruments
        if 'non_whitelisted_instruments' in violations:
            not_whitelisted = validation.get('not_whitelisted', [])
            details.append({
                'type': 'non_whitelisted_instruments',
                'description': f"Portfolio contains non-whitelisted instruments: {', '.join(not_whitelisted)}",
                'severity': 'warning',
                'affected_positions': not_whitelisted
            })
        
        # Instrument limit violations
        if 'instrument_limit_exceeded' in violations:
            instrument_violations = validation.get('instrument_violations', [])
            for violation in instrument_violations:
                details.append({
                    'type': 'instrument_limit_exceeded',
                    'description': f"Instrument {violation['instrument']} allocation "
                                  f"({violation['allocation']:.2%}) exceeds limit "
                                  f"({violation['limit']:.2%})",
                    'severity': 'warning',
                    'affected_positions': [violation['instrument']],
                    'allocation': violation['allocation'],
                    'limit': violation['limit'],
                    'excess': violation['excess']
                })
        
        # Group limit violations
        if 'group_limit_exceeded' in violations:
            group_violations = validation.get('group_violations', [])
            for violation in group_violations:
                # Find instruments in this group
                group = violation['group']
                instrument_groups = self.parameters['instrument_groups']
                default_group = self.parameters['default_group']
                
                affected = [i for i, pos in portfolio.positions.items() 
                           if instrument_groups.get(i, default_group) == group]
                
                details.append({
                    'type': 'group_limit_exceeded',
                    'description': f"Group {group} allocation ({violation['allocation']:.2%}) "
                                  f"exceeds limit ({violation['limit']:.2%})",
                    'severity': 'warning',
                    'affected_positions': affected,
                    'group': group,
                    'allocation': violation['allocation'],
                    'limit': violation['limit'],
                    'excess': violation['excess']
                })
            
        return details
    
    def explain(self, instructions: List[AllocationInstruction], portfolio: Portfolio) -> str:
        """
        Explain instrument constraint effect on allocation instructions
        
        Args:
            instructions: List of allocation instructions
            portfolio: Current portfolio state
            
        Returns:
            String explanation of constraint effects
        """
        validation = self.validate(portfolio)
        
        explanation = [
            f"Instrument Constraint:"
        ]
        
        # Describe configuration
        max_exposure = self.parameters['max_instrument_exposure']
        blacklist_count = len(self.parameters['blacklist'])
        whitelist_count = len(self.parameters['whitelist'])
        instrument_limit_count = len(self.parameters['instrument_limits'])
        group_limit_count = len(self.parameters['group_limits'])
        
        explanation.append(f"  Configuration: max exposure={max_exposure:.2%}, "
                         f"{blacklist_count} blacklisted, {whitelist_count} whitelisted, "
                         f"{instrument_limit_count} instrument limits, {group_limit_count} group limits")
        
        # Explain current violations if any
        if not validation.get('valid', True):
            violations = validation.get('violations', [])
            explanation.append("  Current portfolio violations:")
            
            if 'blacklisted_instruments' in violations:
                blacklisted = validation.get('blacklisted', [])
                explanation.append(f"    - Blacklisted instruments: {', '.join(blacklisted)}")
            
            if 'non_whitelisted_instruments' in violations:
                not_whitelisted = validation.get('not_whitelisted', [])
                explanation.append(f"    - Non-whitelisted instruments: {', '.join(not_whitelisted)}")
            
            if 'instrument_limit_exceeded' in violations:
                instrument_violations = validation.get('instrument_violations', [])
                for v in instrument_violations:
                    explanation.append(f"    - {v['instrument']}: {v['allocation']:.2%} "
                                     f"exceeds {v['limit']:.2%} limit")
            
            if 'group_limit_exceeded' in violations:
                group_violations = validation.get('group_violations', [])
                for v in group_violations:
                    explanation.append(f"    - Group {v['group']}: {v['allocation']:.2%} "
                                     f"exceeds {v['limit']:.2%} limit")
        
        # Explain potential effects on instructions
        if instructions:
            # Count instruments by action type
            actions = {}
            for instr in instructions:
                action = instr.action.value
                if action not in actions:
                    actions[action] = []
                actions[action].append(instr.instrument)
            
            explanation.append("\n  Potential effects on current instructions:")
            
            # Blacklist/whitelist filtering
            blacklist = set(self.parameters['blacklist'])
            whitelist = set(self.parameters['whitelist'])
            
            if blacklist or whitelist:
                filtered = []
                
                if blacklist:
                    for action_type, instruments in actions.items():
                        if action_type != 'close':  # Skip close actions
                            filtered.extend([i for i in instruments if i in blacklist])
                
                if whitelist and whitelist:
                    for action_type, instruments in actions.items():
                        if action_type != 'close':  # Skip close actions
                            filtered.extend([i for i in instruments if i not in whitelist])
                
                if filtered:
                    explanation.append(f"    - Would filter out {len(filtered)} instruction(s) due to blacklist/whitelist")
            
            # Instrument limits
            limit_scaled = []
            instrument_allocations = self._calculate_current_allocations(portfolio)
            
            # Update allocations based on instructions
            for instr in instructions:
                if instr.action == AllocationAction.CLOSE:
                    instrument_allocations[instr.instrument] = 0
                elif hasattr(instr, 'risk_percent') and instr.risk_percent is not None:
                    instrument_allocations[instr.instrument] = instr.risk_percent
            
            # Check limits
            for instrument, allocation in instrument_allocations.items():
                limit = self.parameters['instrument_limits'].get(instrument, max_exposure)
                if allocation > limit:
                    limit_scaled.append((instrument, allocation, limit))
            
            if limit_scaled:
                explanation.append(f"    - Would scale {len(limit_scaled)} position(s) due to instrument limits:")
                for instrument, allocation, limit in limit_scaled:
                    scale_factor = limit / allocation
                    explanation.append(f"      * {instrument}: {allocation:.2%} -> {limit:.2%} "
                                     f"(scale factor: {scale_factor:.2f})")
            
            # Group limits
            groups_over_limit = []
            instrument_groups = self.parameters['instrument_groups']
            default_group = self.parameters['default_group']
            group_limits = self.parameters['group_limits']
            
            # Calculate group allocations
            group_allocations = {}
            for instrument, allocation in instrument_allocations.items():
                group = instrument_groups.get(instrument, default_group)
                group_allocations[group] = group_allocations.get(group, 0) + allocation
            
            # Check group limits
            for group, allocation in group_allocations.items():
                if group in group_limits and allocation > group_limits[group]:
                    groups_over_limit.append((group, allocation, group_limits[group]))
            
            if groups_over_limit:
                explanation.append(f"    - Would scale positions in {len(groups_over_limit)} group(s) due to group limits:")
                for group, allocation, limit in groups_over_limit:
                    scale_factor = limit / allocation
                    explanation.append(f"      * Group '{group}': {allocation:.2%} -> {limit:.2%} "
                                     f"(scale factor: {scale_factor:.2f})")
        else:
            explanation.append("\n  No instructions to evaluate.")
        
        return "\n".join(explanation)