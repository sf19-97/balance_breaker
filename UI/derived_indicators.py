"""
Balance Breaker Derived Indicators Manager
Handles creation and management of derived indicators from base macro data
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
import json
import os

class DerivedIndicatorManager:
    """Manager for derived macro indicators"""
    
    def __init__(self, config_path='derived_indicators_config.json'):
        self.config_path = config_path
        self.derived_configs = self.load_config()
    
    def load_config(self):
        """Load derived indicator configurations"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading derived indicators config: {e}")
                return {}
        return {}
    
    def save_config(self):
        """Save derived indicator configurations"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.derived_configs, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving derived indicators config: {e}")
            return False
    
    def add_derived_config(self, name, config):
        """Add a new derived indicator configuration"""
        self.derived_configs[name] = config
        return self.save_config()
    
    def remove_derived_config(self, name):
        """Remove a derived indicator configuration"""
        if name in self.derived_configs:
            del self.derived_configs[name]
            return self.save_config()
        return False
    
    def generate_derived_indicators(self, macro_data):
        """Generate derived indicators based on configured transformations"""
        result = macro_data.copy()
        
        for name, config in self.derived_configs.items():
            if config.get('active', False):
                try:
                    # Process different types of derivations
                    if config['type'] == 'spread':
                        result = self._generate_spreads(result, config)
                    elif config['type'] == 'difference':
                        result = self._generate_differences(result, config)
                    elif config['type'] == 'ratio':
                        result = self._generate_ratios(result, config)
                    elif config['type'] == 'correlation':
                        result = self._generate_correlations(result, config)
                    elif config['type'] == 'custom':
                        result = self._generate_custom(result, config)
                except Exception as e:
                    print(f"Error generating derived indicator '{name}': {e}")
        
        return result
    
    def _generate_spreads(self, data, config):
        """Generate spread indicators (e.g., US-JP yield spreads)"""
        pattern = config.get('pattern', '{base}-{target}_{term}')
        base_country = config.get('base_country', 'US')
        target_countries = config.get('target_countries', ['JP', 'AU', 'CA', 'EU', 'GB'])
        terms = config.get('terms', ['2Y', '5Y', '10Y'])
        
        # Look for yield columns that match base and target patterns
        for term in terms:
            base_col = f"{base_country}_{term}"
            
            if base_col not in data.columns:
                print(f"Warning: Base column {base_col} not found in data")
                continue
                
            for target in target_countries:
                target_col = f"{target}_{term}"
                
                if target_col in data.columns:
                    # Generate spread name using pattern
                    spread_name = pattern.format(base=base_country, target=target, term=term)
                    
                    # Calculate spread
                    data[spread_name] = data[base_col] - data[target_col]
                    print(f"Generated spread indicator: {spread_name}")
        
        return data
    
    def _generate_differences(self, data, config):
        """Generate difference indicators (e.g., CPI differentials)"""
        pattern = config.get('pattern', '{base}-{target}_{metric}')
        base_country = config.get('base_country', 'US')
        target_countries = config.get('target_countries', ['JP', 'AU', 'CA', 'EU', 'GB'])
        metrics = config.get('metrics', ['CPI_YOY', 'GDP_YOY'])
        
        for metric in metrics:
            base_col = f"{base_country}_{metric}"
            
            if base_col not in data.columns:
                print(f"Warning: Base column {base_col} not found in data")
                continue
                
            for target in target_countries:
                target_col = f"{target}_{metric}"
                
                if target_col in data.columns:
                    # Generate difference name
                    diff_name = pattern.format(base=base_country, target=target, metric=metric)
                    
                    # Calculate difference
                    data[diff_name] = data[base_col] - data[target_col]
                    print(f"Generated difference indicator: {diff_name}")
        
        return data
    
    def _generate_ratios(self, data, config):
        """Generate ratio indicators"""
        pattern = config.get('pattern', '{numerator}_to_{denominator}')
        pairs = config.get('pairs', [])
        
        for pair in pairs:
            numerator = pair.get('numerator')
            denominator = pair.get('denominator')
            
            if numerator in data.columns and denominator in data.columns:
                # Generate ratio name
                ratio_name = pattern.format(numerator=numerator, denominator=denominator)
                
                # Calculate ratio, handling division by zero
                data[ratio_name] = data[numerator] / data[denominator].replace(0, np.nan)
                print(f"Generated ratio indicator: {ratio_name}")
        
        return data
    
    def _generate_correlations(self, data, config):
        """Generate rolling correlation indicators"""
        pattern = config.get('pattern', '{base}_corr_{target}_{window}d')
        base_columns = config.get('base_columns', ['VIX'])
        target_columns = config.get('target_columns', ['US_CPI_YOY', 'US_10Y'])
        windows = config.get('windows', [30, 60, 90])
        
        for base in base_columns:
            if base not in data.columns:
                print(f"Warning: Base column {base} not found in data")
                continue
                
            for target in target_columns:
                if target not in data.columns:
                    continue
                    
                for window in windows:
                    # Generate correlation name
                    corr_name = pattern.format(base=base, target=target, window=window)
                    
                    # Calculate rolling correlation
                    data[corr_name] = data[base].rolling(window).corr(data[target])
                    print(f"Generated correlation indicator: {corr_name}")
        
        return data
    
    def _generate_custom(self, data, config):
        """Generate custom indicators based on formula"""
        formula = config.get('formula', '')
        output_name = config.get('output_name', 'custom_indicator')
        
        # This is just a placeholder - would need a safe formula evaluator
        # or predefined transformation types in practice
        print(f"Custom formula '{formula}' would generate {output_name}")
        
        return data


class DerivedIndicatorDialog:
    """Dialog for managing derived indicators"""
    
    def __init__(self, parent, repo_manager, indicator_manager=None):
        self.parent = parent
        self.repo_manager = repo_manager
        
        # Create or use existing indicator manager
        if indicator_manager:
            self.indicator_manager = indicator_manager
        else:
            self.indicator_manager = DerivedIndicatorManager()
        
        self.create_dialog()
    
    def create_dialog(self):
        """Create the derived indicators dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Derived Indicators Manager")
        self.dialog.geometry("800x600")
        self.dialog.minsize(800, 600)
        self.dialog.transient(self.parent)
        
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="10 10 10 10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)
        
        # Create the various tabs
        self.create_spreads_tab()
        self.create_differences_tab()
        self.create_ratios_tab()
        self.create_correlations_tab()
        self.create_custom_tab()
        self.create_preview_tab()
        
        # Bottom buttons
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        ttk.Button(btn_frame, text="Close", command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Save All", command=self.save_all_configs).pack(side=tk.RIGHT, padx=5)
    
    def create_spreads_tab(self):
        """Create the spreads configuration tab"""
        spreads_frame = ttk.Frame(self.notebook)
        self.notebook.add(spreads_frame, text="Yield Spreads")
        
        # Description
        desc_frame = ttk.Frame(spreads_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Configure yield spread calculations", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="Yield spreads measure the difference between yields of similar maturity bonds from different countries.",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Configuration section
        config_frame = ttk.LabelFrame(spreads_frame, text="Spread Configuration")
        config_frame.pack(fill=tk.X, padx=0, pady=10)
        
        # Base country
        base_frame = ttk.Frame(config_frame)
        base_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(base_frame, text="Base Country:").pack(side=tk.LEFT)
        self.spread_base_var = tk.StringVar(value="US")
        ttk.Entry(base_frame, textvariable=self.spread_base_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Target countries
        target_frame = ttk.Frame(config_frame)
        target_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Countries (comma separated):").pack(side=tk.LEFT)
        self.spread_targets_var = tk.StringVar(value="JP,AU,CA,EU,GB")
        ttk.Entry(target_frame, textvariable=self.spread_targets_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Terms
        terms_frame = ttk.Frame(config_frame)
        terms_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(terms_frame, text="Terms (comma separated):").pack(side=tk.LEFT)
        self.spread_terms_var = tk.StringVar(value="2Y,5Y,10Y")
        ttk.Entry(terms_frame, textvariable=self.spread_terms_var, width=20).pack(side=tk.LEFT, padx=5)
        
        # Pattern
        pattern_frame = ttk.Frame(config_frame)
        pattern_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pattern_frame, text="Output Pattern:").pack(side=tk.LEFT)
        self.spread_pattern_var = tk.StringVar(value="{base}-{target}_{term}")
        ttk.Entry(pattern_frame, textvariable=self.spread_pattern_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(pattern_frame, text="Use {base}, {target}, {term} as placeholders").pack(side=tk.LEFT, padx=5)
        
        # Active checkbox
        active_frame = ttk.Frame(config_frame)
        active_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.spread_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(active_frame, text="Generate Yield Spreads", 
                       variable=self.spread_active_var).pack(anchor=tk.W)
        
        # Result preview
        preview_frame = ttk.LabelFrame(spreads_frame, text="Example Outputs")
        preview_frame.pack(fill=tk.X, padx=0, pady=10)
        
        # Add example outputs based on current settings
        example_text = "With current settings, the following indicators will be generated:\n\n"
        example_text += "US-JP_2Y, US-AU_2Y, US-CA_2Y, US-EU_2Y, US-GB_2Y\n"
        example_text += "US-JP_5Y, US-AU_5Y, US-CA_5Y, US-EU_5Y, US-GB_5Y\n"
        example_text += "US-JP_10Y, US-AU_10Y, US-CA_10Y, US-EU_10Y, US-GB_10Y"
        
        example_label = ttk.Label(preview_frame, text=example_text, wraplength=700)
        example_label.pack(padx=10, pady=10, anchor=tk.W)
        
        # Update button
        ttk.Button(preview_frame, text="Update Examples", 
                  command=lambda: self.update_spread_examples(example_label)).pack(anchor=tk.W, padx=10, pady=5)
    
    def update_spread_examples(self, label):
        """Update spread examples based on current settings"""
        base = self.spread_base_var.get()
        targets = [t.strip() for t in self.spread_targets_var.get().split(',')]
        terms = [t.strip() for t in self.spread_terms_var.get().split(',')]
        pattern = self.spread_pattern_var.get()
        
        example_text = "With current settings, the following indicators will be generated:\n\n"
        
        for term in terms:
            examples = []
            for target in targets:
                examples.append(pattern.format(base=base, target=target, term=term))
            example_text += ", ".join(examples) + "\n"
        
        label.config(text=example_text)
    
    def create_differences_tab(self):
        """Create the differences configuration tab"""
        diff_frame = ttk.Frame(self.notebook)
        self.notebook.add(diff_frame, text="Metric Differences")
        
        # Description
        desc_frame = ttk.Frame(diff_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Configure economic metric differences", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="Calculate differences between economic metrics (like CPI, GDP growth) across countries.",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Configuration section
        config_frame = ttk.LabelFrame(diff_frame, text="Difference Configuration")
        config_frame.pack(fill=tk.X, padx=0, pady=10)
        
        # Base country
        base_frame = ttk.Frame(config_frame)
        base_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(base_frame, text="Base Country:").pack(side=tk.LEFT)
        self.diff_base_var = tk.StringVar(value="US")
        ttk.Entry(base_frame, textvariable=self.diff_base_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Target countries
        target_frame = ttk.Frame(config_frame)
        target_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Countries (comma separated):").pack(side=tk.LEFT)
        self.diff_targets_var = tk.StringVar(value="JP,AU,CA,EU,GB")
        ttk.Entry(target_frame, textvariable=self.diff_targets_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Metrics
        metrics_frame = ttk.Frame(config_frame)
        metrics_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(metrics_frame, text="Metrics (comma separated):").pack(side=tk.LEFT)
        self.diff_metrics_var = tk.StringVar(value="CPI_YOY,GDP_YOY,PMI")
        ttk.Entry(metrics_frame, textvariable=self.diff_metrics_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Pattern
        pattern_frame = ttk.Frame(config_frame)
        pattern_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pattern_frame, text="Output Pattern:").pack(side=tk.LEFT)
        self.diff_pattern_var = tk.StringVar(value="{base}-{target}_{metric}")
        ttk.Entry(pattern_frame, textvariable=self.diff_pattern_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(pattern_frame, text="Use {base}, {target}, {metric} as placeholders").pack(side=tk.LEFT, padx=5)
        
        # Active checkbox
        active_frame = ttk.Frame(config_frame)
        active_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.diff_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(active_frame, text="Generate Metric Differences", 
                       variable=self.diff_active_var).pack(anchor=tk.W)
        
        # Example outputs
        example_frame = ttk.LabelFrame(diff_frame, text="Example Outputs")
        example_frame.pack(fill=tk.X, padx=0, pady=10)
        
        example_text = "With current settings, the following indicators will be generated:\n\n"
        example_text += "US-JP_CPI_YOY, US-AU_CPI_YOY, US-CA_CPI_YOY, US-EU_CPI_YOY, US-GB_CPI_YOY\n"
        example_text += "US-JP_GDP_YOY, US-AU_GDP_YOY, US-CA_GDP_YOY, US-EU_GDP_YOY, US-GB_GDP_YOY\n"
        example_text += "US-JP_PMI, US-AU_PMI, US-CA_PMI, US-EU_PMI, US-GB_PMI"
        
        example_label = ttk.Label(example_frame, text=example_text, wraplength=700)
        example_label.pack(padx=10, pady=10, anchor=tk.W)
        
        # Update button
        ttk.Button(example_frame, text="Update Examples", 
                  command=lambda: self.update_diff_examples(example_label)).pack(anchor=tk.W, padx=10, pady=5)
    
    def update_diff_examples(self, label):
        """Update difference examples based on current settings"""
        base = self.diff_base_var.get()
        targets = [t.strip() for t in self.diff_targets_var.get().split(',')]
        metrics = [m.strip() for m in self.diff_metrics_var.get().split(',')]
        pattern = self.diff_pattern_var.get()
        
        example_text = "With current settings, the following indicators will be generated:\n\n"
        
        for metric in metrics:
            examples = []
            for target in targets:
                examples.append(pattern.format(base=base, target=target, metric=metric))
            example_text += ", ".join(examples) + "\n"
        
        label.config(text=example_text)
    
    def create_ratios_tab(self):
        """Create the ratios configuration tab"""
        ratio_frame = ttk.Frame(self.notebook)
        self.notebook.add(ratio_frame, text="Ratio Indicators")
        
        # Description
        desc_frame = ttk.Frame(ratio_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Configure ratio indicators", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="Calculate ratios between different economic indicators (e.g. VIX/10Y yield).",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Configuration section
        config_frame = ttk.LabelFrame(ratio_frame, text="Ratio Configuration")
        config_frame.pack(fill=tk.X, padx=0, pady=10)
        
        # Ratio pairs frame
        pairs_frame = ttk.Frame(config_frame)
        pairs_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Example for a single ratio pair
        self.ratio_pair1_num = tk.StringVar(value="VIX")
        self.ratio_pair1_denom = tk.StringVar(value="US_10Y")
        
        ttk.Label(pairs_frame, text="Pair 1:").pack(anchor=tk.W, pady=2)
        pair1_frame = ttk.Frame(pairs_frame)
        pair1_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pair1_frame, text="Numerator:").pack(side=tk.LEFT)
        ttk.Entry(pair1_frame, textvariable=self.ratio_pair1_num, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(pair1_frame, text="Denominator:").pack(side=tk.LEFT, padx=10)
        ttk.Entry(pair1_frame, textvariable=self.ratio_pair1_denom, width=15).pack(side=tk.LEFT, padx=5)
        
        # Second ratio pair
        self.ratio_pair2_num = tk.StringVar(value="GOLD")
        self.ratio_pair2_denom = tk.StringVar(value="SILVER")
        
        ttk.Label(pairs_frame, text="Pair 2:").pack(anchor=tk.W, pady=2)
        pair2_frame = ttk.Frame(pairs_frame)
        pair2_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(pair2_frame, text="Numerator:").pack(side=tk.LEFT)
        ttk.Entry(pair2_frame, textvariable=self.ratio_pair2_num, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Label(pair2_frame, text="Denominator:").pack(side=tk.LEFT, padx=10)
        ttk.Entry(pair2_frame, textvariable=self.ratio_pair2_denom, width=15).pack(side=tk.LEFT, padx=5)
        
        # Output pattern
        pattern_frame = ttk.Frame(config_frame)
        pattern_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pattern_frame, text="Output Pattern:").pack(side=tk.LEFT)
        self.ratio_pattern_var = tk.StringVar(value="{numerator}_to_{denominator}")
        ttk.Entry(pattern_frame, textvariable=self.ratio_pattern_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(pattern_frame, text="Use {numerator}, {denominator} as placeholders").pack(side=tk.LEFT, padx=5)
        
        # Active checkbox
        active_frame = ttk.Frame(config_frame)
        active_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.ratio_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(active_frame, text="Generate Ratio Indicators", 
                       variable=self.ratio_active_var).pack(anchor=tk.W)
    
    def create_correlations_tab(self):
        """Create the correlations configuration tab"""
        corr_frame = ttk.Frame(self.notebook)
        self.notebook.add(corr_frame, text="Correlations")
        
        # Description
        desc_frame = ttk.Frame(corr_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Configure rolling correlation indicators", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="Calculate rolling correlations between pairs of indicators (e.g. VIX vs inflation).",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Configuration section
        config_frame = ttk.LabelFrame(corr_frame, text="Correlation Configuration")
        config_frame.pack(fill=tk.X, padx=0, pady=10)
        
        # Base indicators
        base_frame = ttk.Frame(config_frame)
        base_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(base_frame, text="Base Indicators (comma separated):").pack(side=tk.LEFT)
        self.corr_base_var = tk.StringVar(value="VIX,SPX")
        ttk.Entry(base_frame, textvariable=self.corr_base_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Target indicators
        target_frame = ttk.Frame(config_frame)
        target_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Target Indicators (comma separated):").pack(side=tk.LEFT)
        self.corr_target_var = tk.StringVar(value="US_CPI_YOY,US_10Y,US_2Y")
        ttk.Entry(target_frame, textvariable=self.corr_target_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Windows
        window_frame = ttk.Frame(config_frame)
        window_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(window_frame, text="Windows (days, comma separated):").pack(side=tk.LEFT)
        self.corr_windows_var = tk.StringVar(value="30,60,90")
        ttk.Entry(window_frame, textvariable=self.corr_windows_var, width=15).pack(side=tk.LEFT, padx=5)
        
        # Pattern
        pattern_frame = ttk.Frame(config_frame)
        pattern_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pattern_frame, text="Output Pattern:").pack(side=tk.LEFT)
        self.corr_pattern_var = tk.StringVar(value="{base}_corr_{target}_{window}d")
        ttk.Entry(pattern_frame, textvariable=self.corr_pattern_var, width=30).pack(side=tk.LEFT, padx=5)
        ttk.Label(pattern_frame, text="Use {base}, {target}, {window} as placeholders").pack(side=tk.LEFT, padx=5)
        
        # Active checkbox
        active_frame = ttk.Frame(config_frame)
        active_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.corr_active_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(active_frame, text="Generate Correlation Indicators", 
                       variable=self.corr_active_var).pack(anchor=tk.W)
        
        # Example outputs
        example_frame = ttk.LabelFrame(corr_frame, text="Example Outputs")
        example_frame.pack(fill=tk.X, padx=0, pady=10)
        
        example_text = "With current settings, the following indicators will be generated:\n\n"
        example_text += "VIX_corr_US_CPI_YOY_30d, VIX_corr_US_10Y_30d, VIX_corr_US_2Y_30d\n"
        example_text += "VIX_corr_US_CPI_YOY_60d, VIX_corr_US_10Y_60d, VIX_corr_US_2Y_60d\n"
        example_text += "VIX_corr_US_CPI_YOY_90d, VIX_corr_US_10Y_90d, VIX_corr_US_2Y_90d\n\n"
        example_text += "SPX_corr_US_CPI_YOY_30d, SPX_corr_US_10Y_30d, SPX_corr_US_2Y_30d\n"
        example_text += "SPX_corr_US_CPI_YOY_60d, SPX_corr_US_10Y_60d, SPX_corr_US_2Y_60d\n"
        example_text += "SPX_corr_US_CPI_YOY_90d, SPX_corr_US_10Y_90d, SPX_corr_US_2Y_90d"
        
        example_label = ttk.Label(example_frame, text=example_text, wraplength=700)
        example_label.pack(padx=10, pady=10, anchor=tk.W)
        
        # Update button
        ttk.Button(example_frame, text="Update Examples", 
                  command=lambda: self.update_corr_examples(example_label)).pack(anchor=tk.W, padx=10, pady=5)
    
    def update_corr_examples(self, label):
        """Update correlation examples based on current settings"""
        bases = [b.strip() for b in self.corr_base_var.get().split(',')]
        targets = [t.strip() for t in self.corr_target_var.get().split(',')]
        windows = [w.strip() for w in self.corr_windows_var.get().split(',')]
        pattern = self.corr_pattern_var.get()
        
        example_text = "With current settings, the following indicators will be generated:\n\n"
        
        for base in bases:
            for window in windows:
                examples = []
                for target in targets:
                    examples.append(pattern.format(base=base, target=target, window=window))
                example_text += ", ".join(examples) + "\n"
            example_text += "\n"
        
        label.config(text=example_text)
    
    def create_custom_tab(self):
        """Create the custom formulas tab"""
        custom_frame = ttk.Frame(self.notebook)
        self.notebook.add(custom_frame, text="Custom")
        
        # Description
        desc_frame = ttk.Frame(custom_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Custom Indicator Formulas", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="Define custom calculations for specialized indicators.",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Add note about development
        note_frame = ttk.LabelFrame(custom_frame, text="Note")
        note_frame.pack(fill=tk.X, padx=0, pady=10)
        
        ttk.Label(note_frame, text="Custom indicator formulas are not yet implemented. This feature will be available in a future update.",
                 wraplength=700).pack(padx=10, pady=10)
        
        # Placeholder for future development
        placeholder_frame = ttk.LabelFrame(custom_frame, text="Future Implementation")
        placeholder_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)
        
        ttk.Label(placeholder_frame, text="This section will allow defining custom formulas using Python expressions.",
                 wraplength=700).pack(padx=10, pady=10, anchor=tk.W)
        
        # Example placeholder
        ttk.Label(placeholder_frame, text="Example future formula: (US_10Y + US_2Y) / 2 - (DE_10Y + DE_2Y) / 2",
                 wraplength=700).pack(padx=10, pady=5, anchor=tk.W)
    
    def create_preview_tab(self):
        """Create the preview tab"""
        preview_frame = ttk.Frame(self.notebook)
        self.notebook.add(preview_frame, text="Preview")
        
        # Description
        desc_frame = ttk.Frame(preview_frame)
        desc_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Label(desc_frame, text="Generated Indicators Preview", 
                 font=("", 10, "bold")).pack(anchor=tk.W)
        ttk.Label(desc_frame, text="View all indicators that will be generated based on current settings.",
                 wraplength=700).pack(anchor=tk.W, pady=5)
        
        # Select macro repository
        repo_frame = ttk.LabelFrame(preview_frame, text="Select Data Source")
        repo_frame.pack(fill=tk.X, padx=0, pady=10)
        
        ttk.Label(repo_frame, text="Macro Repository:").pack(side=tk.LEFT, padx=5)
        
        # Get available repositories
        repo_names = []
        try:
            repo_names = list(self.repo_manager.repositories.get('macro', {}).keys())
        except:
            pass
            
        self.preview_repo_var = tk.StringVar()
        if repo_names:
            self.preview_repo_var.set(repo_names[0])
            
        repo_combo = ttk.Combobox(repo_frame, textvariable=self.preview_repo_var, 
                                 values=repo_names, width=25, state="readonly")
        repo_combo.pack(side=tk.LEFT, padx=5)
        
        # Load button
        ttk.Button(repo_frame, text="Load Indicators", 
                  command=self.load_preview_data).pack(side=tk.LEFT, padx=10)
        
        # Preview table
        preview_table_frame = ttk.LabelFrame(preview_frame, text="Generated Indicators")
        preview_table_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=10)
        
        # Create treeview
        tree_frame = ttk.Frame(preview_table_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add scrollbars
        vsb = ttk.Scrollbar(tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
        
        # Create treeview
        self.preview_tree = ttk.Treeview(tree_frame, columns=("type", "pattern"), 
                                        show="headings", 
                                        yscrollcommand=vsb.set,
                                        xscrollcommand=hsb.set)
        
        # Configure scrollbars
        vsb.config(command=self.preview_tree.yview)
        hsb.config(command=self.preview_tree.xview)
        
        # Set headings
        self.preview_tree.heading("type", text="Type")
        self.preview_tree.heading("pattern", text="Indicator")
        
        # Set column widths
        self.preview_tree.column("type", width=100)
        self.preview_tree.column("pattern", width=300)
        
        # Pack treeview and scrollbars
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    def load_preview_data(self):
        """Load preview data and show all indicators that would be generated"""
        repo_name = self.preview_repo_var.get()
        
        if not repo_name:
            messagebox.showinfo("No Repository", "Please select a macro data repository")
            return
        
        # Clear treeview
        for item in self.preview_tree.get_children():
            self.preview_tree.delete(item)
        
        # Add yield spreads
        if self.spread_active_var.get():
            base = self.spread_base_var.get()
            targets = [t.strip() for t in self.spread_targets_var.get().split(',')]
            terms = [t.strip() for t in self.spread_terms_var.get().split(',')]
            pattern = self.spread_pattern_var.get()
            
            for term in terms:
                for target in targets:
                    indicator = pattern.format(base=base, target=target, term=term)
                    self.preview_tree.insert("", tk.END, values=("Spread", indicator))
        
        # Add differences
        if self.diff_active_var.get():
            base = self.diff_base_var.get()
            targets = [t.strip() for t in self.diff_targets_var.get().split(',')]
            metrics = [m.strip() for m in self.diff_metrics_var.get().split(',')]
            pattern = self.diff_pattern_var.get()
            
            for metric in metrics:
                for target in targets:
                    indicator = pattern.format(base=base, target=target, metric=metric)
                    self.preview_tree.insert("", tk.END, values=("Difference", indicator))
        
        # Add ratios
        if self.ratio_active_var.get():
            pattern = self.ratio_pattern_var.get()
            
            # Pair 1
            num1 = self.ratio_pair1_num.get()
            denom1 = self.ratio_pair1_denom.get()
            indicator1 = pattern.format(numerator=num1, denominator=denom1)
            self.preview_tree.insert("", tk.END, values=("Ratio", indicator1))
            
            # Pair 2
            num2 = self.ratio_pair2_num.get()
            denom2 = self.ratio_pair2_denom.get()
            indicator2 = pattern.format(numerator=num2, denominator=denom2)
            self.preview_tree.insert("", tk.END, values=("Ratio", indicator2))
        
        # Add correlations
        if self.corr_active_var.get():
            bases = [b.strip() for b in self.corr_base_var.get().split(',')]
            targets = [t.strip() for t in self.corr_target_var.get().split(',')]
            windows = [w.strip() for w in self.corr_windows_var.get().split(',')]
            pattern = self.corr_pattern_var.get()
            
            for base in bases:
                for window in windows:
                    for target in targets:
                        indicator = pattern.format(base=base, target=target, window=window)
                        self.preview_tree.insert("", tk.END, values=("Correlation", indicator))
    
    def save_all_configs(self):
        """Save all derived indicator configurations"""
        # Save yield spreads config
        if self.spread_active_var.get():
            spread_config = {
                'type': 'spread',
                'active': True,
                'base_country': self.spread_base_var.get(),
                'target_countries': [t.strip() for t in self.spread_targets_var.get().split(',')],
                'terms': [t.strip() for t in self.spread_terms_var.get().split(',')],
                'pattern': self.spread_pattern_var.get()
            }
            self.indicator_manager.add_derived_config('yield_spreads', spread_config)
        
        # Save differences config
        if self.diff_active_var.get():
            diff_config = {
                'type': 'difference',
                'active': True,
                'base_country': self.diff_base_var.get(),
                'target_countries': [t.strip() for t in self.diff_targets_var.get().split(',')],
                'metrics': [m.strip() for m in self.diff_metrics_var.get().split(',')],
                'pattern': self.diff_pattern_var.get()
            }
            self.indicator_manager.add_derived_config('metric_differences', diff_config)
        
        # Save ratios config
        if self.ratio_active_var.get():
            pairs = [
                {'numerator': self.ratio_pair1_num.get(), 'denominator': self.ratio_pair1_denom.get()},
                {'numerator': self.ratio_pair2_num.get(), 'denominator': self.ratio_pair2_denom.get()}
            ]
            
            ratio_config = {
                'type': 'ratio',
                'active': True,
                'pairs': pairs,
                'pattern': self.ratio_pattern_var.get()
            }
            self.indicator_manager.add_derived_config('indicator_ratios', ratio_config)
        
        # Save correlations config
        if self.corr_active_var.get():
            corr_config = {
                'type': 'correlation',
                'active': True,
                'base_columns': [b.strip() for b in self.corr_base_var.get().split(',')],
                'target_columns': [t.strip() for t in self.corr_target_var.get().split(',')],
                'windows': [int(w.strip()) for w in self.corr_windows_var.get().split(',')],
                'pattern': self.corr_pattern_var.get()
            }
            self.indicator_manager.add_derived_config('rolling_correlations', corr_config)
        
        # Save configurations
        success = self.indicator_manager.save_config()
        
        if success:
            messagebox.showinfo("Success", "Derived indicator configurations saved successfully")
        else:
            messagebox.showerror("Error", "Failed to save derived indicator configurations")


# Function to integrate with main UI
def show_derived_indicators_dialog(parent, repo_manager):
    """Show the derived indicators dialog"""
    dialog = DerivedIndicatorDialog(parent, repo_manager)
    return dialog.indicator_manager