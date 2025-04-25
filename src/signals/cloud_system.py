import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation as R
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression

class EnhancedCloudSystem:
    def __init__(self, num_points=300, pair="USDJPY", window_size=60):
        self.num_points = num_points
        self.scale = 0.20  # Rotation magnitude
        self.pair = pair  # Default pair
        self.window_size = window_size  # For trailing computations
        
        # Currency pair to indicator mapping
        self.pair_to_codes = {
            "USDJPY": "JP",
            "USDCAD": "CA",
            "AUDUSD": "AU",  # Note: inverted, so forces will be negated
            "EURUSD": "EU",  # Note: inverted, so forces will be negated
            "GBPUSD": "GB"   # Note: inverted, so forces will be negated
        }
        
        # Economic model parameters (from the paper)
        self.psi = 1.5  # Parameter from monetary policy rule
        self.lower_bound = 0.0  # Lower bound on interest rates
        self.natural_rate = 0.5  # Initial estimate, will be updated
        
        # Historical data storage for computing correlations and estimating parameters
        self.vix_history = []
        self.inflation_exp_history = []
        self.interest_rate_history = []
        self.natural_rate_history = []
        self.macro_history = []
        
        # Correlation storage
        self.vix_inflation_corr = 0.0
        self.vix_rates_corr = 0.0
        
        try:
            # Generate the probability distribution-based cloud
            self.generate_cloud()
            
            # Store state
            self.current_points = self.initial_points.copy()
            self.prev_points = self.initial_points.copy()
        except Exception as e:
            print(f"Error initializing cloud: {e}")
            # Create fallback points if cloud generation fails
            self.initial_points = np.zeros((self.num_points, 3))
            self.current_points = self.initial_points.copy()
            self.prev_points = self.initial_points.copy()
        
        # Metrics storage
        self.metrics = {
            'avg_delta': [],
            'cloud_entropy': [],
            'principal_axis_angle': [],
            'rotational_energy': [],
            'vix_inflation_correlation': [],
            'vix_rates_correlation': [],
            'regime': [],
            'lower_bound_probability': []
        }
    
    def generate_cloud(self):
        """Generate points based on a multivariate normal distribution
        representing the joint probability of the three economic dimensions"""
        np.random.seed(42)  # For reproducibility
        
        # Mean vector - centered on current estimates
        mean_vector = np.array([0.0, 0.0, 0.0])
        
        # Initial covariance - will adapt based on regime
        covariance = np.array([
            [1.0, 0.1, -0.1],  # X: Monetary dimension
            [0.1, 1.0, -0.1],  # Y: Inflation dimension
            [-0.1, -0.1, 1.0]  # Z: Risk dimension
        ])
        
        try:
            # Generate points from multivariate normal distribution
            self.initial_points = np.random.multivariate_normal(mean_vector, covariance, self.num_points)
            
            # Add small noise for numerical stability
            noise = 0.01
            self.initial_points += np.random.normal(0, noise, (self.num_points, 3))
        except Exception as e:
            print(f"Error in cloud generation: {e}")
            # Fallback to simple random points
            self.initial_points = np.random.rand(self.num_points, 3) * 2 - 1
    
    def update_cloud_distribution(self, macro_data):
        """Update the probability distribution based on current macro state and regime"""
        try:
            curr_code = self.get_currency_code()
            is_inverted = self.is_inverted_pair()
            force_multiplier = -1.0 if is_inverted else 1.0
            
            # Get relevant data
            yield_2y_key = f'US-{curr_code}_2Y'
            yield_10y_key = f'US-{curr_code}_10Y'
            inflation_key = f'US-{curr_code}_CPI_YOY'
            
            # Extract values or use defaults
            yield_spread_2y = macro_data.get(yield_2y_key, 0) * force_multiplier
            yield_spread_10y = macro_data.get(yield_10y_key, 0) * force_multiplier
            inflation_diff = macro_data.get(inflation_key, 0) * force_multiplier
            vix = macro_data.get('VIX', 20)
            
            # Normalize to create mean vector for distribution
            monetary_factor = 0.5 * yield_spread_2y + 0.5 * yield_spread_10y
            monetary_factor = np.tanh(monetary_factor / 2.0)
            
            inflation_factor = np.tanh(inflation_diff / 3.0)
            
            risk_factor = -1.0 * np.tanh((vix - 20) / 15.0)
            
            # Adjust risk factor for currency characteristics
            if curr_code == "JP" and not is_inverted:  # JPY is a traditional safe haven
                risk_factor *= -1.0
            elif curr_code == "AU" and is_inverted:  # AUD is typically risk-on
                risk_factor *= 1.0
            
            # Create mean vector centered on the current state
            mean_vector = np.array([monetary_factor, inflation_factor, risk_factor])
            
            # Update covariance based on regime
            regime = self.detect_market_regime()
            lower_bound_prob = self.calculate_lower_bound_probability()
            
            # Stronger relationships when near lower bound (based on paper)
            if regime == "LOWER_BOUND_RISK":
                sensitivity = min(0.8, lower_bound_prob * 1.5)  # Cap at 0.8
                covariance = np.array([
                    [1.0, 0.3 * sensitivity, -0.4 * sensitivity],
                    [0.3 * sensitivity, 1.0, -0.3 * sensitivity],
                    [-0.4 * sensitivity, -0.3 * sensitivity, 1.0]
                ])
            else:
                covariance = np.array([
                    [1.0, 0.1, -0.1],
                    [0.1, 1.0, -0.1],
                    [-0.1, -0.1, 1.0]
                ])
            
            # Generate new points from this distribution
            self.current_points = np.random.multivariate_normal(mean_vector, covariance, self.num_points)
        except Exception as e:
            print(f"Error updating cloud distribution: {e}")
            # Keep existing distribution as fallback
            pass
        
    def get_currency_code(self):
        """Get the appropriate currency code"""
        if self.pair in self.pair_to_codes:
            return self.pair_to_codes[self.pair]
        else:
            # Default to JPY if pair not found
            return "JP"
    
    def is_inverted_pair(self):
        """Check if pair is inverted (USD as quote currency)"""
        return self.pair in ["AUDUSD", "EURUSD", "GBPUSD"]
    
    def estimate_natural_rate(self, macro_data):
        """Estimate the natural rate of interest based on macro data"""
        try:
            # Store macro history for trailing calculations
            self.macro_history.append(macro_data)
            if len(self.macro_history) > self.window_size:
                self.macro_history.pop(0)
            
            # Get currency code
            curr_code = self.get_currency_code()
            
            # Get relevant data
            yield_10y_key = f'US-{curr_code}_10Y'
            inflation_key = f'US-{curr_code}_CPI_YOY'
            
            # Extract values or use defaults
            yield_spread_10y = macro_data.get(yield_10y_key, 0)
            inflation_diff = macro_data.get(inflation_key, 0)
            
            # Simple heuristic based on 10-year - inflation
            natural_rate_estimate = yield_spread_10y - inflation_diff/2
            
            # Smooth using exponential moving average
            if not hasattr(self, 'natural_rate') or self.natural_rate is None:
                self.natural_rate = natural_rate_estimate
            else:
                self.natural_rate = 0.95 * self.natural_rate + 0.05 * natural_rate_estimate
            
            # Store for historical tracking
            self.natural_rate_history.append(self.natural_rate)
            if len(self.natural_rate_history) > self.window_size:
                self.natural_rate_history.pop(0)
                
            return self.natural_rate
        except Exception as e:
            print(f"Error estimating natural rate: {e}")
            # Return previous natural rate as fallback
            return self.natural_rate if hasattr(self, 'natural_rate') else 0.5
    
    def detect_market_regime(self):
        """Determine market regime based on interest rates and uncertainty"""
        try:
            lower_bound_prob = self.calculate_lower_bound_probability()
            
            # From the paper: the threshold for regime determination is (psi-1)/psi
            threshold = (self.psi - 1) / self.psi
            
            if lower_bound_prob < threshold:
                return "TARGET_EQUILIBRIUM"
            else:
                return "LOWER_BOUND_RISK"
        except Exception as e:
            print(f"Error detecting market regime: {e}")
            # Default to TARGET_EQUILIBRIUM as fallback
            return "TARGET_EQUILIBRIUM"
    
    def calculate_lower_bound_probability(self):
        """Calculate the probability of the lower bound constraint binding"""
        try:
            if not self.natural_rate_history:
                return 0.1  # Default value if no history
                
            # Simplified estimate based on how close natural rate is to lower bound
            rate_gap = self.natural_rate - self.lower_bound
            
            # Convert gap to probability using a logistic function
            prob = 1 / (1 + np.exp(2 * rate_gap))
            
            return prob
        except Exception as e:
            print(f"Error calculating lower bound probability: {e}")
            # Default moderate probability as fallback
            return 0.1
    
    def calculate_correlations(self, macro_data):
        """Calculate trailing correlations between VIX and inflation/interest rates"""
        try:
            # Store VIX data
            vix = macro_data.get('VIX', None)
            if vix is not None:
                self.vix_history.append(vix)
                if len(self.vix_history) > self.window_size:
                    self.vix_history.pop(0)
            
            # Store inflation expectations
            curr_code = self.get_currency_code()
            inflation_key = f'US-{curr_code}_CPI_YOY'
            inflation = macro_data.get(inflation_key, None)
            if inflation is not None:
                self.inflation_exp_history.append(inflation)
                if len(self.inflation_exp_history) > self.window_size:
                    self.inflation_exp_history.pop(0)
            
            # Store interest rate data
            yield_key = f'US-{curr_code}_10Y'
            rate = macro_data.get(yield_key, None)
            if rate is not None:
                self.interest_rate_history.append(rate)
                if len(self.interest_rate_history) > self.window_size:
                    self.interest_rate_history.pop(0)
            
            # Calculate correlations if enough data points are available
            vix_inflation_corr = np.nan
            vix_rates_corr = np.nan
            
            # Need at least 3 points to calculate changes and then correlation
            if len(self.vix_history) >= 3 and len(self.inflation_exp_history) >= 3:
                # Calculate changes
                vix_changes = np.diff(self.vix_history)
                inflation_changes = np.diff(self.inflation_exp_history)
                
                # Ensure same length
                min_len = min(len(vix_changes), len(inflation_changes))
                
                # Only calculate correlation if there's variation in both series
                if min_len >= 2 and np.std(vix_changes[-min_len:]) > 0 and np.std(inflation_changes[-min_len:]) > 0:
                    corr_matrix = np.corrcoef(vix_changes[-min_len:], inflation_changes[-min_len:])
                    vix_inflation_corr = corr_matrix[0, 1]
            
            if len(self.vix_history) >= 3 and len(self.interest_rate_history) >= 3:
                # Calculate changes
                vix_changes = np.diff(self.vix_history)
                rate_changes = np.diff(self.interest_rate_history)
                
                # Ensure same length
                min_len = min(len(vix_changes), len(rate_changes))
                
                # Only calculate correlation if there's variation in both series
                if min_len >= 2 and np.std(vix_changes[-min_len:]) > 0 and np.std(rate_changes[-min_len:]) > 0:
                    corr_matrix = np.corrcoef(vix_changes[-min_len:], rate_changes[-min_len:])
                    vix_rates_corr = corr_matrix[0, 1]
            
            # Update stored correlations if we got valid values
            if not np.isnan(vix_inflation_corr):
                self.vix_inflation_corr = vix_inflation_corr
                
            if not np.isnan(vix_rates_corr):
                self.vix_rates_corr = vix_rates_corr
                
            return self.vix_inflation_corr, self.vix_rates_corr
        except Exception as e:
            print(f"Error calculating correlations: {e}")
            # Return existing correlations as fallback
            return self.vix_inflation_corr, self.vix_rates_corr
    
    def map_macro_to_forces(self, macro_data, pair=None):
        """Convert macro indicators to rotation forces, with adjustments
        based on market regime and correlations"""
        try:
            # Use instance pair if none specified
            if pair is not None:
                self.pair = pair
                
            # Get the appropriate currency code
            curr_code = self.get_currency_code()
                
            # Check if we need to invert forces (for pairs where USD is quote currency)
            is_inverted = self.is_inverted_pair()
            force_multiplier = -1.0 if is_inverted else 1.0
                
            # 1. X-Axis: Monetary Force (Rate Differentials)
            # Extract the yield spread data
            yield_2y_key = f'US-{curr_code}_2Y'
            yield_10y_key = f'US-{curr_code}_10Y'
            
            us_curr_2y_spread = macro_data.get(yield_2y_key, 0)
            us_curr_10y_spread = macro_data.get(yield_10y_key, 0)
            
            # Normalize to suitable rotation magnitude
            force_x = 0.5 * us_curr_2y_spread + 0.5 * us_curr_10y_spread
            force_x = np.tanh(force_x / 2.0) * force_multiplier  # Scale to [-1, 1] and apply direction
            
            # 2. Y-Axis: Growth/Inflation Force
            inflation_key = f'US-{curr_code}_CPI_YOY'
            us_curr_inflation_diff = macro_data.get(inflation_key, 0)
            force_y = np.tanh(us_curr_inflation_diff / 3.0) * force_multiplier  # Scale to [-1, 1] and apply direction
            
            # 3. Z-Axis: Risk Sentiment Force
            vix = macro_data.get('VIX', 20)
            # Invert VIX so higher risk appetite = positive force
            # For risk sentiment, direction depends on whether the currency is considered "risk-on" or "risk-off"
            risk_force_multiplier = force_multiplier
            # Adjust for specific currencies known to respond differently to risk
            if curr_code == "JP" and not is_inverted:  # JPY is a traditional safe haven
                risk_force_multiplier = -1.0 * force_multiplier
            elif curr_code == "AU" and is_inverted:  # AUD is typically risk-on
                risk_force_multiplier = 1.0 * force_multiplier
                
            force_z = -1.0 * np.tanh((vix - 20) / 15.0) * risk_force_multiplier  # Normalize around VIX=20
            
            # Adjust forces based on regime and correlations
            regime = self.detect_market_regime()
            
            # Modify the impact of uncertainty based on regime
            if regime == "LOWER_BOUND_RISK" and vix > 20:
                # Uncertainty has stronger effect in lower bound regime
                # This is the key insight from the paper
                if not np.isnan(self.vix_inflation_corr) and self.vix_inflation_corr < -0.1:
                    uncertainty_impact = 1.0 + 0.5 * abs(self.vix_inflation_corr)
                    force_x *= uncertainty_impact
                    force_y *= uncertainty_impact
            
            return force_x, force_y, force_z
        except Exception as e:
            print(f"Error mapping macro to forces: {e}")
            # Return neutral forces as fallback
            return 0.0, 0.0, 0.0
    
    def apply_rotation(self, force_x, force_y, force_z):
        """Apply rotation forces to the point cloud"""
        try:
            # Create quaternion rotations
            rot_x = R.from_rotvec(np.array([force_x * self.scale, 0, 0]))
            rot_y = R.from_rotvec(np.array([0, force_y * self.scale, 0]))
            rot_z = R.from_rotvec(np.array([0, 0, force_z * self.scale]))
            
            # Convert to matrices
            mat_x = rot_x.as_matrix()
            mat_y = rot_y.as_matrix()
            mat_z = rot_z.as_matrix()
            
            # Compose rotations (order matters: Z * Y * X)
            composed_matrix = mat_z @ mat_y @ mat_x
            
            # Store previous state for metrics
            self.prev_points = self.current_points.copy()
            
            # Apply rotation to each point
            for i in range(len(self.current_points)):
                self.current_points[i] = composed_matrix @ self.current_points[i]
        except Exception as e:
            print(f"Error applying rotation: {e}")
            # Keep previous state as fallback
            pass
    
    def calculate_metrics(self):
        """Calculate cloud metrics that detect regime changes,
        including correlations and regime indicators"""
        try:
            from scipy.stats import entropy
            from scipy.spatial.distance import pdist, squareform
            
            # 1. Average position delta
            delta = np.mean(np.linalg.norm(self.current_points - self.prev_points, axis=1))
            self.metrics['avg_delta'].append(delta)
            
            # 2. Cloud entropy (distribution of distances)
            dist_matrix = squareform(pdist(self.current_points))
            hist, _ = np.histogram(dist_matrix, bins=20, range=(0, 5))
            hist = hist / np.sum(hist)
            cloud_entropy = entropy(hist)
            self.metrics['cloud_entropy'].append(cloud_entropy)
            
            # 3. Principal axis orientation
            # Check for NaN or infinite values
            data = self.current_points.copy()
            if np.isnan(data).any() or np.isinf(data).any():
                # Replace with zeros or other appropriate values
                data = np.nan_to_num(data, nan=0.0, posinf=0.0, neginf=0.0)
                
            # When calculating PCA, add error handling
            try:
                pca = PCA(n_components=3)
                # Add a small epsilon to avoid division by zero
                if np.allclose(np.var(data), 0):
                    # Add small random noise
                    data += np.random.normal(0, 1e-10, size=data.shape)
                pca.fit(data)
                principal_axis = pca.components_[0]
                
                # Calculate angle from reference axis [1,0,0]
                ref_axis = np.array([1, 0, 0])
                cos_angle = np.dot(principal_axis, ref_axis) / (np.linalg.norm(principal_axis) * np.linalg.norm(ref_axis))
                angle = np.arccos(np.clip(cos_angle, -1.0, 1.0))
                self.metrics['principal_axis_angle'].append(angle)
            except Exception as e:
                print(f"PCA calculation error: {e}")
                # Handle gracefully by returning default values
                # Use the previous angle or default to 0
                if len(self.metrics['principal_axis_angle']) > 0:
                    self.metrics['principal_axis_angle'].append(self.metrics['principal_axis_angle'][-1])
                else:
                    self.metrics['principal_axis_angle'].append(0.0)
            
            # 4. Rotational energy
            if len(self.metrics['avg_delta']) > 1:
                rotational_energy = 0
                for i in range(self.num_points):
                    # Calculate angular momentum-like quantity
                    r = self.current_points[i]
                    v = self.current_points[i] - self.prev_points[i]
                    # L = r × v (cross product)
                    L = np.cross(r, v)
                    rotational_energy += np.sum(L**2)
                
                rotational_energy /= self.num_points
                self.metrics['rotational_energy'].append(rotational_energy)
            else:
                self.metrics['rotational_energy'].append(0)
            
            # 5. Add regime metrics
            current_regime = self.detect_market_regime()
            current_lb_prob = self.calculate_lower_bound_probability()
            
            self.metrics['regime'].append(current_regime)
            self.metrics['lower_bound_probability'].append(current_lb_prob)
            
            # Store latest correlations
            self.metrics['vix_inflation_correlation'].append(self.vix_inflation_corr)
            self.metrics['vix_rates_correlation'].append(self.vix_rates_corr)
            
            # 6. Calculate derived metrics
            if len(self.metrics['avg_delta']) > 5:
                # Calculate precession (rate of change in orientation)
                recent_angles = self.metrics['principal_axis_angle'][-5:]
                precession = np.gradient(recent_angles).mean()
                
                # Calculate structural instability
                recent_energy = self.metrics['rotational_energy'][-5:]
                recent_delta = self.metrics['avg_delta'][-5:]
                instability = np.mean(recent_energy) / (np.mean(recent_delta) + 1e-6)
                
                # Calculate market mood (directional bias)
                # Check for NaN or infinite values in the difference data
                diff_data = self.current_points - self.prev_points
                if np.isnan(diff_data).any() or np.isinf(diff_data).any():
                    # Replace with zeros or other appropriate values
                    diff_data = np.nan_to_num(diff_data, nan=0.0, posinf=0.0, neginf=0.0)
                
                try:
                    recent_pca = PCA(n_components=3)
                    # Add a small epsilon to avoid division by zero
                    if np.allclose(np.var(diff_data), 0):
                        # Add small random noise
                        diff_data += np.random.normal(0, 1e-10, size=diff_data.shape)
                    recent_pca.fit(diff_data)
                    flow_direction = recent_pca.components_[0]
                    
                    # Project onto macro axes
                    monetary_axis = np.array([1, 0, 0])  # X axis
                    inflation_axis = np.array([0, 1, 0])  # Y axis
                    risk_axis = np.array([0, 0, 1])      # Z axis
                    
                    monetary_bias = np.dot(flow_direction, monetary_axis)
                    inflation_bias = np.dot(flow_direction, inflation_axis)
                    risk_bias = np.dot(flow_direction, risk_axis)
                    
                    # Composite bias (positive = USD strength)
                    market_mood = monetary_bias * 0.4 + inflation_bias * 0.3 + risk_bias * 0.3
                except Exception as e:
                    print(f"Flow direction PCA calculation error: {e}")
                    # Default to neutral market mood
                    market_mood = 0.0
                
                return {
                    'precession': precession,
                    'instability': instability,
                    'market_mood': market_mood,
                    'avg_delta': delta,
                    'cloud_entropy': cloud_entropy,
                    'regime': current_regime,
                    'lower_bound_probability': current_lb_prob,
                    'vix_inflation_correlation': self.vix_inflation_corr,
                    'vix_rates_correlation': self.vix_rates_corr
                }
            else:
                return {
                    'precession': 0,
                    'instability': 0,
                    'market_mood': 0,
                    'avg_delta': delta,
                    'cloud_entropy': cloud_entropy,
                    'regime': current_regime,
                    'lower_bound_probability': current_lb_prob,
                    'vix_inflation_correlation': self.vix_inflation_corr,
                    'vix_rates_correlation': self.vix_rates_corr
                }
        except Exception as e:
            print(f"Error calculating metrics: {e}")
            # Return default metrics as fallback
            return {
                'precession': 0,
                'instability': 0,
                'market_mood': 0,
                'avg_delta': 0,
                'cloud_entropy': 0,
                'regime': "TARGET_EQUILIBRIUM",
                'lower_bound_probability': 0.1,
                'vix_inflation_correlation': 0,
                'vix_rates_correlation': 0
            }
    
    def generate_signal(self, metrics, threshold_precession=0.15, threshold_instability=1.5):
        """Generate trading signal based on cloud metrics and regime"""
        try:
            signal = "NEUTRAL"
            
            # Only generate signals when we have enough data
            if metrics['precession'] == 0:
                return signal, metrics
            
            # Get key metrics
            precession = metrics['precession']
            market_mood = metrics['market_mood']
            instability = metrics['instability']
            regime = metrics['regime']
            
            # Check for signal conditions
            if abs(precession) > threshold_precession:
                # We have significant precession (rotation rate)
                
                # Check direction using market mood
                if market_mood > 0.05:  # Bullish
                    if regime == "LOWER_BOUND_RISK" and not np.isnan(self.vix_inflation_corr) and self.vix_inflation_corr < -0.2:
                        # Strong correlation effect in lower bound regime
                        signal = "STRONG_BUY" if instability > threshold_instability else "BUY"
                    else:
                        signal = "STRONG_BUY" if instability > threshold_instability else "BUY"
                elif market_mood < -0.05:  # Bearish
                    if regime == "LOWER_BOUND_RISK" and not np.isnan(self.vix_inflation_corr) and self.vix_inflation_corr < -0.2:
                        # Strong correlation effect in lower bound regime
                        signal = "STRONG_SELL" if instability > threshold_instability else "SELL"
                    else:
                        signal = "STRONG_SELL" if instability > threshold_instability else "SELL"
            
            return signal, metrics
        except Exception as e:
            print(f"Error generating signal: {e}")
            # Return neutral signal as fallback
            return "NEUTRAL", metrics
    
    def run_step(self, macro_data, pair=None):
        """Process one step with current macro data"""
        try:
            # Update pair if specified
            if pair is not None:
                self.pair = pair
            
            # 1. Estimate the natural rate based on macro data
            self.estimate_natural_rate(macro_data)
            
            # 2. Calculate correlations (properly handled now)
            self.calculate_correlations(macro_data)
            
            # 3. Update the cloud distribution based on macro state and regime
            self.update_cloud_distribution(macro_data)
            
            # 4. Map macro data to rotation forces
            force_x, force_y, force_z = self.map_macro_to_forces(macro_data, self.pair)
            
            # 5. Apply rotation to the cloud
            self.apply_rotation(force_x, force_y, force_z)
            
            # 6. Calculate and return metrics
            metrics = self.calculate_metrics()
            
            # 7. Generate signal
            signal, metrics = self.generate_signal(metrics)
            metrics['signal'] = signal
            
            return metrics
        except Exception as e:
            print(f"Error in run_step: {e}")
            # Return basic metrics as fallback
            default_metrics = {
                'precession': 0,
                'instability': 0,
                'market_mood': 0,
                'avg_delta': 0,
                'cloud_entropy': 0,
                'regime': "TARGET_EQUILIBRIUM",
                'lower_bound_probability': 0.1,
                'vix_inflation_correlation': 0,
                'vix_rates_correlation': 0,
                'signal': "NEUTRAL"
            }
            return default_metrics
    
    def reset(self):
        """Reset the system to initial state"""
        try:
            self.current_points = self.initial_points.copy()
            self.prev_points = self.initial_points.copy()
            
            # Clear metrics
            for key in self.metrics:
                self.metrics[key] = []
            
            # Clear histories
            self.vix_history = []
            self.inflation_exp_history = []
            self.interest_rate_history = []
            self.natural_rate_history = []
            self.macro_history = []
            
            # Reset natural rate
            self.natural_rate = 0.5
            
            # Reset correlations
            self.vix_inflation_corr = 0.0
            self.vix_rates_corr = 0.0
        except Exception as e:
            print(f"Error resetting: {e}")
            # Reinitialize if reset fails
            self.__init__(self.num_points, self.pair, self.window_size)