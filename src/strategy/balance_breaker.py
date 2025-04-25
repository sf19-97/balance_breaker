# src/strategy/balance_breaker.py
from balance_breaker.src.strategy.base import Strategy
from balance_breaker.src.signals.cloud_system import EnhancedCloudSystem

class BalanceBreakerStrategy(Strategy):
    """
    Balance Breaker trading strategy based on quantum cloud physics.
    Uses macroeconomic flow to generate signals.
    """
    
    def __init__(self, parameters=None, signal_generator=None, risk_manager=None):
        """
        Initialize the Balance Breaker strategy.
        
        Parameters:
        -----------
        parameters : dict, optional
            Strategy parameters
        signal_generator : EnhancedCloudSystem, optional
            Cloud system signal generator
        risk_manager : RiskManager, optional
            Risk management component
        """
        # Default strategy parameters
        default_params = {
            'tp_pips': 300,                         # Take profit in pips
            'sl_pips': 100,                         # Stop loss in pips
            'max_hold': 672,                        # Max hold time in hours
            'target_eq_precession_threshold': 0.15, # Precession threshold in target equilibrium
            'lower_bound_precession_threshold': 0.12, # Lower threshold in lower bound regime
            'target_eq_mood_threshold': 0.25,       # Market mood threshold in target equilibrium
            'lower_bound_mood_threshold': 0.15,     # Lower threshold in lower bound regime
            'vix_inflation_corr_threshold': -0.2    # Threshold for VIX-inflation correlation
        }
        
        # Override defaults with provided parameters
        if parameters:
            default_params.update(parameters)
        
        # Create cloud system if not provided
        if signal_generator is None:
            signal_generator = EnhancedCloudSystem()
        
        super().__init__("Balance Breaker", signal_generator, risk_manager, default_params)
    
    def generate_signal(self, current_data, historical_data=None):
        """
        Generate trading signal using the cloud system.
        
        Parameters:
        -----------
        current_data : dict
            Current market data point including price and indicators
        historical_data : pd.DataFrame, optional
            Historical data for additional context
            
        Returns:
        --------
        tuple
            (signal, metrics) where signal is a string and metrics is a dict
        """
        # Extract pair if available
        pair = current_data.get('pair', 'USDJPY')
        
        # Extract macro data from current data
        macro_data = {k: v for k, v in current_data.items() 
                     if k not in ['open', 'high', 'low', 'close', 'volume', 'pair', 'pip_factor']}
        
        # Run cloud system step
        metrics = self.signal_generator.run_step(macro_data, pair)
        
        # Generate signal with custom thresholds from parameters
        signal, updated_metrics = self._generate_signal_with_params(metrics)
        
        return signal, updated_metrics
    
    def _generate_signal_with_params(self, metrics):
        """
        Generate trading signal based on metrics, with parameter adjustments.
        
        Parameters:
        -----------
        metrics : dict
            Cloud system metrics
            
        Returns:
        --------
        tuple
            (signal, updated_metrics)
        """
        signal = "NEUTRAL"
        
        # Only generate signals when we have enough data
        if metrics.get('precession', 0) == 0:
            return signal, metrics
        
        # Extract key metrics
        precession = metrics.get('precession', 0)
        market_mood = metrics.get('market_mood', 0)
        instability = metrics.get('instability', 0)
        
        # Default thresholds from parameters
        precession_threshold = self.parameters['target_eq_precession_threshold']
        mood_threshold = self.parameters['target_eq_mood_threshold']
        instability_threshold = 1.5
        
        # Adjust thresholds based on regime if available
        if 'regime' in metrics:
            regime = metrics['regime']
            
            # Lower thresholds in lower bound regime (more sensitive)
            if regime == "LOWER_BOUND_RISK":
                precession_threshold = self.parameters['lower_bound_precession_threshold']
                mood_threshold = self.parameters['lower_bound_mood_threshold']
                
            # Check for strong VIX-inflation correlation in lower bound regime
            if regime == "LOWER_BOUND_RISK" and 'vix_inflation_correlation' in metrics:
                vix_inflation_corr = metrics['vix_inflation_correlation']
                
                # Strong negative correlation should amplify signals
                if vix_inflation_corr < self.parameters['vix_inflation_corr_threshold']:
                    # Make it even easier to generate signals
                    precession_threshold *= 0.8
                    mood_threshold *= 0.8
        
        # Check for signal conditions
        if abs(precession) > precession_threshold:
            # We have significant precession (rotation rate)
            
            # Check direction using market mood
            if market_mood > mood_threshold:  # Bullish
                if instability > instability_threshold:
                    signal = "STRONG_BUY"
                else:
                    signal = "BUY"
            elif market_mood < -mood_threshold:  # Bearish
                if instability > instability_threshold:
                    signal = "STRONG_SELL"
                else:
                    signal = "SELL"
        
        return signal, metrics
    
    def reset(self):
        """Reset the strategy to its initial state"""
        super().reset()  # Call parent reset method
    
    def get_description(self):
        """
        Get a description of the Balance Breaker strategy.
        
        Returns:
        --------
        str
            Description of the strategy
        """
        return """Balance Breaker: A macroeconomic flow-based trading strategy using quaternion cloud physics.
        
This strategy models the interaction between monetary policy, inflation dynamics, and risk appetite
using a three-dimensional point cloud that rotates according to macro forces. Trading signals are
generated based on the rotational characteristics of the cloud, specifically:
- Precession rate (speed of rotation)
- Market mood (directional bias)
- Structural instability (chaotic energy)

The strategy also incorporates market regime detection, distinguishing between:
- Target Equilibrium: Normal monetary policy environment
- Lower Bound Risk: When interest rates are near zero lower bound

Performance varies significantly by regime, with signal sensitivity automatically adjusted.
"""
    
    def get_required_indicators(self):
        """
        Get a list of required indicators for this strategy.
        
        Returns:
        --------
        list
            List of required indicator names
        """
        # Get currency pair codes
        if hasattr(self.signal_generator, 'pair_to_codes'):
            pair_codes = list(self.signal_generator.pair_to_codes.values())
        else:
            pair_codes = ['JP', 'AU', 'CA', 'EU', 'GB']
        
        # Generate required indicator lists for all supported pairs
        required = ['VIX']
        
        for code in pair_codes:
            required.extend([
                f'US-{code}_2Y',
                f'US-{code}_10Y',
                f'US-{code}_CPI_YOY'
            ])
            
        return required