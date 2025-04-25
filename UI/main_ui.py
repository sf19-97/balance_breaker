"""
Balance Breaker System - Interactive User Interface
Interfaces with the new modular strategy and backtest architecture
"""

import sys
sys.path.append('/home/millet_frazier/playground_folder')
import builtins  # Import builtins for print function handling

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import json
import os
import pandas as pd
import numpy as np
import matplotlib
# Configure matplotlib to use Agg backend for thread safety
matplotlib.use('Agg')  # Important: must be before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from datetime import datetime
import traceback

# Path standardization for imports
# Try to add the src directory to sys.path if it's not already there
SRC_PATH = '/home/millet_frazier/playground_folder/balance_breaker/src'
if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

UI_PATH = '/home/millet_frazier/playground_folder/balance_breaker/UI'
if UI_PATH not in sys.path:
    sys.path.append(UI_PATH)

# Import the new strategy and backtest engine classes
try:
    from strategy_base import Strategy
    from balance_breaker_strategy import BalanceBreakerStrategy
    from backtest_engine import BacktestEngine
    print("Successfully imported strategy modules")
except ImportError as e:
    print(f"Error importing strategy modules: {e}")
    messagebox.showerror("Import Error", f"Could not import strategy modules: {e}")
    sys.exit(1)

# Import the visualization class
try:
    from visualizer import BalanceBreakerVisualizer
    print("Successfully imported visualizer module")
except ImportError as e:
    print(f"Error importing visualizer: {e}")
    print("Warning: BalanceBreakerVisualizer not found. Visualization features will be limited.")

# Import repository manager (for repository tab)
try:
    from repo_manager import RepositoryManager
    print("Successfully imported repository manager")
except ImportError as e:
    print(f"Error importing repository manager: {e}")
    # Fallback class in case the import fails
    class RepositoryManager:
        def __init__(self, config_path='repository_config.json'):
            self.repositories = {'price': {}, 'macro': {}}
        def get_repository_list(self, repo_type):
            return []

# Try to import the derived indicators module
try:
    from derived_indicators import show_derived_indicators_dialog, DerivedIndicatorManager
    HAS_DERIVED_INDICATORS = True
    print("Successfully imported derived indicators module")
except ImportError as e:
    print(f"Error importing derived indicators: {e}")
    print("Derived indicators module not available. Some features will be disabled.")
    HAS_DERIVED_INDICATORS = False

# Import normalize_price_data function from our updated data_preview module
try:
    from data_preview import normalize_price_data
    print("Successfully imported normalize_price_data function")
except ImportError as e:
    print(f"Error importing normalize_price_data: {e}")
    # Define a basic version if we can't import it
    def normalize_price_data(df):
        """Basic normalization if import fails"""
        print("Warning: Using basic normalization function instead of imported one")
        normalized = df.copy()
        
        # Ensure OHLC columns exist
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in normalized.columns:
                print(f"Warning: Missing required column '{col}', using defaults")
                if col == 'volume':
                    normalized[col] = 1
                elif 'close' in normalized.columns:
                    normalized[col] = normalized['close']
                else:
                    normalized[col] = 0
        
        return normalized[required_columns]

class BalanceBreakerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Balance Breaker Trading System")
        self.root.geometry("1200x800")
        self.root.minsize(900, 700)
        
        # Set default parameters
        self.available_pairs = ['USDJPY', 'USDCAD', 'EURUSD', 'GBPUSD', 'AUDUSD']
        self.default_params = {
            'start_date': '2022-01-01',
            'end_date': '',
            'tp_pips': 300,
            'sl_pips': 100,
            'max_hold': 672,
            'target_eq_precession_threshold': 0.15, 
            'lower_bound_precession_threshold': 0.12,
            'target_eq_mood_threshold': 0.25,
            'lower_bound_mood_threshold': 0.15,
            'vix_inflation_corr_threshold': -0.2,
            'use_enhanced_system': True,
            'selected_pairs': ['USDJPY'],
            'price_repository': '',  # Added for repository integration
            'macro_repository': ''   # Added for repository integration
        }
        
        # Load saved parameters if available
        self.config_file = 'balance_breaker_config.json'
        self.load_config()
        
        # Initialize repository manager
        try:
            self.repo_manager = RepositoryManager()
            print("Repository manager initialized")
        except Exception as e:
            print(f"Error initializing repository manager: {e}")
            self.repo_manager = None
        
        # Initialize derived indicator manager if available
        self.derived_indicator_manager = None
        if HAS_DERIVED_INDICATORS:
            try:
                self.derived_indicator_manager = DerivedIndicatorManager()
                print("Derived indicators module loaded successfully")
            except Exception as e:
                print(f"Error initializing derived indicator manager: {e}")
        
        # Create UI components
        self.create_menu()
        self.create_notebook()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Console output
        self.console_frame = ttk.LabelFrame(root, text="Console Output")
        self.console_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)
        
        self.console = scrolledtext.ScrolledText(self.console_frame, height=8, wrap=tk.WORD)
        self.console.pack(fill=tk.BOTH, expand=True)
        self.console.config(state=tk.DISABLED)
        
        # Initialize backtest variables
        self.strategy = None
        self.backtest_engine = None
        self.backtest_thread = None
        self.stop_backtest = False
        
        # Set up print override
        self.setup_print_override()
    
    def setup_print_override(self):
        """Set up print function override"""
        # Store original print
        self.original_print = builtins.print
        # Override print
        builtins.print = self.custom_print
    
    def custom_print(self, *args, **kwargs):
        """Custom print function that outputs to both console and UI"""
        # Call the original print function
        self.original_print(*args, **kwargs)
        
        # Format the message
        message = " ".join(map(str, args))
        
        # Add to UI console
        def update_console():
            self.console.config(state=tk.NORMAL)
            self.console.insert(tk.END, message + "\n")
            self.console.see(tk.END)
            self.console.config(state=tk.DISABLED)
        
        # Update UI from main thread
        self.root.after(0, update_console)
    
    def load_config(self):
        """Load saved configuration if available"""
        self.params = self.default_params.copy()
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    saved_params = json.load(f)
                    # Update params with saved values
                    for key, value in saved_params.items():
                        if key in self.params:
                            self.params[key] = value
        except Exception as e:
            print(f"Error loading config: {e}")
        
    def save_config(self):
        """Save current configuration"""
        try:
            self.update_params_from_ui()
            with open(self.config_file, 'w') as f:
                json.dump(self.params, f, indent=4)
            messagebox.showinfo("Configuration Saved", "Settings saved successfully")
        except Exception as e:
            print(f"Error saving config: {e}")
            messagebox.showerror("Save Error", f"Could not save configuration: {e}")
    
    def create_menu(self):
        """Create application menu"""
        menubar = tk.Menu(self.root)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Load Data Directory", command=self.select_data_directory)
        file_menu.add_command(label="Save Configuration", command=self.save_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Tools menu
        tools_menu = tk.Menu(menubar, tearoff=0)
        tools_menu.add_command(label="View Recent Results", command=self.view_recent_results)
        
        # Add derived indicators to the Tools menu if available
        if HAS_DERIVED_INDICATORS:
            tools_menu.add_separator()
            tools_menu.add_command(label="Derived Indicators", command=self.show_derived_indicators)
        
        # Add developer console
        tools_menu.add_separator()
        tools_menu.add_command(label="Developer Console", command=self.show_dev_console)
            
        menubar.add_cascade(label="Tools", menu=tools_menu)
        
        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Documentation", command=self.show_documentation)
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def show_derived_indicators(self):
        """Show the derived indicators manager dialog"""
        if HAS_DERIVED_INDICATORS:
            try:
                # Show the dialog and get the updated manager
                self.derived_indicator_manager = show_derived_indicators_dialog(
                    self.root, self.repo_manager)
                print("Derived indicators configuration updated")
            except Exception as e:
                print(f"Error showing derived indicators dialog: {e}")
                messagebox.showerror("Error", f"Could not open derived indicators manager: {e}")
        else:
            messagebox.showinfo("Not Available", 
                             "Derived indicators module is not available.\n"
                             "Please install the required module first.")
    
    def create_notebook(self):
        """Create tabbed interface"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_backtest_tab()
        self.create_results_tab()
        self.create_visualization_tab()  # Visualization tab
        self.create_repository_tab()     # Repository tab
        self.create_risk_management_tab() # Risk Management tab
    
    def create_backtest_tab(self):
        """Create backtest configuration tab"""
        backtest_frame = ttk.Frame(self.notebook)
        self.notebook.add(backtest_frame, text="Backtest")
        
        # Left panel for basic settings
        left_panel = ttk.LabelFrame(backtest_frame, text="Basic Configuration")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Date range
        date_frame = ttk.Frame(left_panel)
        date_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(date_frame, text="Start Date:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.start_date_var = tk.StringVar(value=self.params['start_date'])
        ttk.Entry(date_frame, textvariable=self.start_date_var).grid(row=0, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        
        ttk.Label(date_frame, text="End Date:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.end_date_var = tk.StringVar(value=self.params['end_date'])
        ttk.Entry(date_frame, textvariable=self.end_date_var).grid(row=1, column=1, sticky=tk.W+tk.E, padx=5, pady=5)
        ttk.Label(date_frame, text="(Leave blank for today)").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        
        # Trade parameters
        trade_frame = ttk.LabelFrame(left_panel, text="Trade Parameters")
        trade_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(trade_frame, text="Take Profit (pips):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.tp_pips_var = tk.IntVar(value=self.params['tp_pips'])
        ttk.Entry(trade_frame, textvariable=self.tp_pips_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(trade_frame, text="Stop Loss (pips):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.sl_pips_var = tk.IntVar(value=self.params['sl_pips'])
        ttk.Entry(trade_frame, textvariable=self.sl_pips_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(trade_frame, text="Max Hold (hours):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.max_hold_var = tk.IntVar(value=self.params['max_hold'])
        ttk.Entry(trade_frame, textvariable=self.max_hold_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Center panel for threshold settings
        center_panel = ttk.LabelFrame(backtest_frame, text="Threshold Settings")
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Target equilibrium thresholds
        target_frame = ttk.LabelFrame(center_panel, text="Target Equilibrium Thresholds")
        target_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Precession Threshold:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_precession_var = tk.DoubleVar(value=self.params['target_eq_precession_threshold'])
        ttk.Entry(target_frame, textvariable=self.target_precession_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(target_frame, text="Market Mood Threshold:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.target_mood_var = tk.DoubleVar(value=self.params['target_eq_mood_threshold'])
        ttk.Entry(target_frame, textvariable=self.target_mood_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Lower bound regime thresholds
        lower_frame = ttk.LabelFrame(center_panel, text="Lower Bound Regime Thresholds")
        lower_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(lower_frame, text="Precession Threshold:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.lower_precession_var = tk.DoubleVar(value=self.params['lower_bound_precession_threshold'])
        ttk.Entry(lower_frame, textvariable=self.lower_precession_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(lower_frame, text="Market Mood Threshold:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.lower_mood_var = tk.DoubleVar(value=self.params['lower_bound_mood_threshold'])
        ttk.Entry(lower_frame, textvariable=self.lower_mood_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(lower_frame, text="VIX-Inflation Correlation:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.vix_corr_var = tk.DoubleVar(value=self.params['vix_inflation_corr_threshold'])
        ttk.Entry(lower_frame, textvariable=self.vix_corr_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # System options
        system_frame = ttk.LabelFrame(center_panel, text="System Options")
        system_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.use_enhanced_var = tk.BooleanVar(value=self.params['use_enhanced_system'])
        ttk.Checkbutton(system_frame, text="Use Enhanced System", 
                       variable=self.use_enhanced_var).pack(anchor=tk.W, padx=5, pady=5)
        
        # Right panel for pair selection
        right_panel = ttk.LabelFrame(backtest_frame, text="Currency Pairs")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pair selection
        self.pair_vars = {}
        for i, pair in enumerate(self.available_pairs):
            var = tk.BooleanVar(value=pair in self.params['selected_pairs'])
            self.pair_vars[pair] = var
            ttk.Checkbutton(right_panel, text=pair, variable=var).pack(anchor=tk.W, padx=10, pady=5)
        
        ttk.Button(right_panel, text="Select All", command=self.select_all_pairs).pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(right_panel, text="Clear All", command=self.clear_all_pairs).pack(fill=tk.X, padx=10, pady=5)
        
        # Control buttons
        controls_frame = ttk.Frame(backtest_frame)
        controls_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=10)
        
        ttk.Button(controls_frame, text="Run Backtest", command=self.run_backtest).pack(side=tk.LEFT, padx=10)
        self.stop_button = ttk.Button(controls_frame, text="Stop", command=self.stop_backtest_run, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=10)
        ttk.Button(controls_frame, text="Save Settings", command=self.save_config).pack(side=tk.RIGHT, padx=10)
    
    def create_results_tab(self):
        """Create results display tab"""
        results_frame = ttk.Frame(self.notebook)
        self.notebook.add(results_frame, text="Results")
        
        # Control panel
        control_panel = ttk.Frame(results_frame)
        control_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(control_panel, text="Result:").pack(side=tk.LEFT, padx=5)
        self.result_type_var = tk.StringVar(value="Performance Summary")
        result_combo = ttk.Combobox(control_panel, textvariable=self.result_type_var, 
                                  values=["Performance Summary", "Trades Chart", "Regime Analysis", "Playbook"], 
                                  state="readonly", width=20)
        result_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(control_panel, text="Pair:").pack(side=tk.LEFT, padx=5)
        self.result_pair_var = tk.StringVar(value="USDJPY")
        pair_combo = ttk.Combobox(control_panel, textvariable=self.result_pair_var, 
                                 values=self.available_pairs, state="readonly", width=10)
        pair_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(control_panel, text="Show", 
                  command=self.show_selected_result).pack(side=tk.LEFT, padx=5)
        
        # Results display area
        self.results_display_frame = ttk.LabelFrame(results_frame, text="Backtest Results")
        self.results_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Placeholder text
        placeholder = ttk.Label(self.results_display_frame, 
                               text="Results will appear here after running a backtest.\nSelect the type of result to display from the dropdown.")
        placeholder.pack(expand=True)
    
    def create_visualization_tab(self):
        """Create visualization tab"""
        viz_frame = ttk.Frame(self.notebook)
        self.notebook.add(viz_frame, text="Visualization")
        
        # Control panel
        control_panel = ttk.Frame(viz_frame)
        control_panel.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # Visualization type selection
        ttk.Label(control_panel, text="Visualization:").pack(side=tk.LEFT, padx=5)
        self.viz_type_var = tk.StringVar(value="Cloud System")
        viz_combo = ttk.Combobox(control_panel, textvariable=self.viz_type_var, 
                              values=["Cloud System", "Animate Cloud", "Metrics and Trades", "Monthly Performance", "Playbook"], 
                              state="readonly", width=20)
        viz_combo.pack(side=tk.LEFT, padx=5)
        
        # Pair selection for visualizations
        ttk.Label(control_panel, text="Pair:").pack(side=tk.LEFT, padx=5)
        self.viz_pair_var = tk.StringVar(value="USDJPY")
        pair_combo = ttk.Combobox(control_panel, textvariable=self.viz_pair_var, 
                                 values=self.available_pairs, state="readonly", width=10)
        pair_combo.pack(side=tk.LEFT, padx=5)
        
        # Date range for visualization
        ttk.Label(control_panel, text="Start:").pack(side=tk.LEFT, padx=5)
        self.viz_start_var = tk.StringVar()
        ttk.Entry(control_panel, textvariable=self.viz_start_var, width=10).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(control_panel, text="End:").pack(side=tk.LEFT, padx=5)
        self.viz_end_var = tk.StringVar()
        ttk.Entry(control_panel, textvariable=self.viz_end_var, width=10).pack(side=tk.LEFT, padx=2)
        
        # Generate button
        ttk.Button(control_panel, text="Generate", 
                  command=self.generate_visualization).pack(side=tk.LEFT, padx=10)
        
        # Save animation option (only visible for animation)
        self.save_anim_var = tk.BooleanVar(value=False)
        self.save_anim_cb = ttk.Checkbutton(control_panel, text="Save Animation", 
                                           variable=self.save_anim_var)
        # Only show this when animation is selected
        viz_combo.bind("<<ComboboxSelected>>", self.update_viz_controls)
        
        # Visualization display area
        self.viz_display_frame = ttk.LabelFrame(viz_frame, text="Visualization")
        self.viz_display_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Initial placeholder
        placeholder = ttk.Label(self.viz_display_frame, 
                               text="Select a visualization type and click 'Generate'")
        placeholder.pack(expand=True)
    
    def create_repository_tab(self):
        """Create repository management tab"""
        repo_frame = ttk.Frame(self.notebook)
        self.notebook.add(repo_frame, text="Data Repositories")
        
        # Only proceed if repo_manager is available
        if not self.repo_manager:
            ttk.Label(repo_frame, text="Repository manager not available. Check imports.").pack(pady=20)
            return
        
        # Create a frame with two sections side by side
        left_frame = ttk.LabelFrame(repo_frame, text="Price Data Repositories")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        right_frame = ttk.LabelFrame(repo_frame, text="Macroeconomic Data Repositories")
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Price repositories listbox
        self.price_repos_var = tk.StringVar()
        self.price_repos = tk.Listbox(left_frame, listvariable=self.price_repos_var, height=10)
        self.price_repos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Price repository buttons
        price_btn_frame = ttk.Frame(left_frame)
        price_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Button(price_btn_frame, text="Add...", 
                  command=self.add_price_repository).pack(fill=tk.X, pady=2)
        ttk.Button(price_btn_frame, text="Edit...", 
                  command=self.edit_price_repository).pack(fill=tk.X, pady=2)
        ttk.Button(price_btn_frame, text="Remove", 
                  command=self.remove_price_repository).pack(fill=tk.X, pady=2)
        ttk.Button(price_btn_frame, text="Preview...", 
                  command=self.preview_price_repository).pack(fill=tk.X, pady=2)
        
        # Macro repositories listbox
        self.macro_repos_var = tk.StringVar()
        self.macro_repos = tk.Listbox(right_frame, listvariable=self.macro_repos_var, height=10)
        self.macro_repos.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Macro repository buttons
        macro_btn_frame = ttk.Frame(right_frame)
        macro_btn_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Button(macro_btn_frame, text="Add...", 
                  command=self.add_macro_repository).pack(fill=tk.X, pady=2)
        ttk.Button(macro_btn_frame, text="Edit...", 
                  command=self.edit_macro_repository).pack(fill=tk.X, pady=2)
        ttk.Button(macro_btn_frame, text="Remove", 
                  command=self.remove_macro_repository).pack(fill=tk.X, pady=2)
        ttk.Button(macro_btn_frame, text="Preview...", 
                  command=self.preview_macro_repository).pack(fill=tk.X, pady=2)
        
        # Active repository selection
        select_frame = ttk.LabelFrame(repo_frame, text="Active Repositories")
        select_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        ttk.Label(select_frame, text="Active Price Repository:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.active_price_var = tk.StringVar()
        self.active_price_combo = ttk.Combobox(select_frame, textvariable=self.active_price_var, state="readonly")
        self.active_price_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(select_frame, text="Active Macro Repository:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.active_macro_var = tk.StringVar()
        self.active_macro_combo = ttk.Combobox(select_frame, textvariable=self.active_macro_var, state="readonly")
        self.active_macro_combo.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Button(select_frame, text="Set as Active", 
                  command=self.set_active_repositories).grid(row=0, column=2, rowspan=2, padx=10, pady=5)
        
        # Update listboxes and combos
        self.update_repository_lists()
    
    def update_viz_controls(self, event=None):
        """Update visualization controls based on selected visualization type"""
        viz_type = self.viz_type_var.get()
        
        # Show/hide save animation checkbox
        if viz_type == "Animate Cloud":
            self.save_anim_cb.pack(side=tk.LEFT, padx=5)
        else:
            self.save_anim_cb.pack_forget()
    
    # Repository management methods
    def update_repository_lists(self):
        """Update repository listboxes and combo boxes"""
        if not self.repo_manager:
            return
            
        # Get repository lists
        try:
            price_repos = self.repo_manager.get_repository_list('price')
            macro_repos = self.repo_manager.get_repository_list('macro')
            
            # Update listboxes
            self.price_repos_var.set(price_repos)
            self.macro_repos_var.set(macro_repos)
            
            # Update combo boxes
            self.active_price_combo['values'] = price_repos
            self.active_macro_combo['values'] = macro_repos
            
            # Set current active repositories
            if price_repos and not self.active_price_var.get():
                self.active_price_var.set(price_repos[0])
            
            if macro_repos and not self.active_macro_var.get():
                self.active_macro_var.set(macro_repos[0])
        except Exception as e:
            print(f"Error updating repository lists: {e}")
    
    def add_price_repository(self):
        """Add a new price data repository"""
        try:
            from balance_breaker.UI.dialogues.price_repository import PriceRepositoryDialog
            PriceRepositoryDialog(self.root, self.repo_manager, self.update_repository_lists)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import repository dialogs: {e}")
            print(f"Error importing repository dialogs: {e}")
    
    def edit_price_repository(self):
        """Edit selected price repository"""
        selection = self.price_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to edit")
            return
        
        repo_name = self.price_repos.get(selection[0])
        try:
            from balance_breaker.UI.dialogues.price_repository import PriceRepositoryDialog
            PriceRepositoryDialog(self.root, self.repo_manager, self.update_repository_lists, repo_name)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import repository dialogs: {e}")
    
    def remove_price_repository(self):
        """Remove selected price repository"""
        selection = self.price_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to remove")
            return
        
        repo_name = self.price_repos.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove '{repo_name}'?"):
            self.repo_manager.remove_repository('price', repo_name)
            self.update_repository_lists()
    
    def preview_price_repository(self):
        """Preview selected price repository"""
        selection = self.price_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to preview")
            return
        
        repo_name = self.price_repos.get(selection[0])
        try:
            from data_preview import DataPreview
            DataPreview(self.root, self.repo_manager, 'price', repo_name)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import data preview: {e}")
    
    # Macro repository management methods
    def add_macro_repository(self):
        """Add a new macro data repository"""
        try:
            from balance_breaker.UI.dialogues.macro_repository import MacroRepositoryDialog
            MacroRepositoryDialog(self.root, self.repo_manager, self.update_repository_lists)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import repository dialogs: {e}")
    
    def edit_macro_repository(self):
        """Edit selected macro repository"""
        selection = self.macro_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to edit")
            return
        
        repo_name = self.macro_repos.get(selection[0])
        try:
            from balance_breaker.UI.dialogues.macro_repository import MacroRepositoryDialog
            MacroRepositoryDialog(self.root, self.repo_manager, self.update_repository_lists, repo_name)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import repository dialogs: {e}")
    
    def remove_macro_repository(self):
        """Remove selected macro repository"""
        selection = self.macro_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to remove")
            return
        
        repo_name = self.macro_repos.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove '{repo_name}'?"):
            self.repo_manager.remove_repository('macro', repo_name)
            self.update_repository_lists()
    
    def preview_macro_repository(self):
        """Preview selected macro repository"""
        selection = self.macro_repos.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a repository to preview")
            return
        
        repo_name = self.macro_repos.get(selection[0])
        try:
            from data_preview import DataPreview
            DataPreview(self.root, self.repo_manager, 'macro', repo_name)
        except ImportError as e:
            messagebox.showerror("Import Error", f"Could not import data preview: {e}")
    
    def set_active_repositories(self):
        """Set the active repositories for backtesting"""
        price_repo = self.active_price_var.get()
        macro_repo = self.active_macro_var.get()
        
        if not price_repo or not macro_repo:
            messagebox.showinfo("Selection Required", "Please select both price and macro repositories")
            return
        
        # Save to configuration
        self.params['price_repository'] = price_repo
        self.params['macro_repository'] = macro_repo
        
        # Update status
        self.status_var.set(f"Active repositories set: Price={price_repo}, Macro={macro_repo}")
        
        # Save configuration
        self.save_config()
    
    def generate_visualization(self):
        """Generate the selected visualization"""
        viz_type = self.viz_type_var.get()
        pair = self.viz_pair_var.get()
        start_date = self.viz_start_var.get() if self.viz_start_var.get() else None
        end_date = self.viz_end_var.get() if self.viz_end_var.get() else None
        
        # Check if we need backtest data
        if viz_type not in ["Cloud System", "Animate Cloud"]:
            if self.backtest_engine is None:
                messagebox.showinfo("No Data", "Please run a backtest first")
                return
        
        # Clear display frame
        for widget in self.viz_display_frame.winfo_children():
            widget.destroy()
        
        try:
            # Create visualizer
            if viz_type in ["Cloud System", "Animate Cloud"]:
                # These visualizations don't require backtest data
                visualizer = BalanceBreakerVisualizer()
            else:
                # For new architecture, we need to get trades and signals from backtest_engine results
                if not hasattr(self, 'backtest_engine') or self.backtest_engine is None:
                    messagebox.showinfo("No Data", "Please run a backtest first")
                    return
                
                # Get price data and results from backtest engine
                price_data = self.backtest_engine.price_data
                
                # Get trades and signals from the latest backtest results
                trades = [t for t in self.backtest_engine.trades if t.get('pair') == pair]
                signals = [s for s in self.backtest_engine.signals if s.get('pair') == pair]
                
                visualizer = BalanceBreakerVisualizer(
                    backtest=None,  # We don't need to pass the whole backtest object
                    price_data=price_data,
                    signals=signals,
                    trades=trades
                )
            
            # Generate the selected visualization
            if viz_type == "Cloud System":
                fig, ax = visualizer.visualize_cloud()
                canvas = FigureCanvasTkAgg(fig, master=self.viz_display_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Add toolbar
                toolbar_frame = ttk.Frame(self.viz_display_frame)
                toolbar_frame.pack(fill=tk.X)
                toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                toolbar.update()
                
            elif viz_type == "Animate Cloud":
                # For animation, we'll use a custom approach
                save = self.save_anim_var.get()
                save_path = f"{pair}_cloud_animation.mp4" if save else None
                
                if save:
                    # Background thread for animation with save
                    def run_animation():
                        self.update_status("Generating animation...")
                        visualizer.animate_cloud(save_path=save_path)
                        self.update_status("Animation saved to " + save_path)
                    
                    animation_thread = threading.Thread(target=run_animation)
                    animation_thread.daemon = True
                    animation_thread.start()
                    
                    # Show message
                    msg = ttk.Label(self.viz_display_frame, 
                                   text=f"Creating animation and saving to {save_path}...\nThis may take a few minutes.")
                    msg.pack(expand=True)
                else:
                    # Regular animation display
                    ani = visualizer.animate_cloud()
                    
                    # We need a reference to keep animation alive
                    self.animation = ani
                    
                    # Create a canvas to show animation
                    canvas = FigureCanvasTkAgg(ani.fig, master=self.viz_display_frame)
                    canvas.draw()
                    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
            elif viz_type == "Metrics and Trades":
                fig = visualizer.visualize_metrics_and_trades(start_date, end_date, pair)
                
                canvas = FigureCanvasTkAgg(fig, master=self.viz_display_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Add toolbar
                toolbar_frame = ttk.Frame(self.viz_display_frame)
                toolbar_frame.pack(fill=tk.X)
                toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                toolbar.update()
                
            elif viz_type == "Monthly Performance":
                fig = visualizer.visualize_monthly_performance()
                
                canvas = FigureCanvasTkAgg(fig, master=self.viz_display_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Add toolbar
                toolbar_frame = ttk.Frame(self.viz_display_frame)
                toolbar_frame.pack(fill=tk.X)
                toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                toolbar.update()
                
            elif viz_type == "Playbook":
                fig = visualizer.visualize_playbook()
                
                canvas = FigureCanvasTkAgg(fig, master=self.viz_display_frame)
                canvas.draw()
                canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                
                # Add toolbar
                toolbar_frame = ttk.Frame(self.viz_display_frame)
                toolbar_frame.pack(fill=tk.X)
                toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                toolbar.update()
            
        except Exception as e:
            error_msg = f"Error generating visualization: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            messagebox.showerror("Visualization Error", error_msg)
            
            # Show error message in the display frame
            error_label = ttk.Label(self.viz_display_frame, text=error_msg)
            error_label.pack(expand=True)
    
    def select_all_pairs(self):
        """Select all currency pairs"""
        for var in self.pair_vars.values():
            var.set(True)
    
    def clear_all_pairs(self):
        """Clear all currency pair selections"""
        for var in self.pair_vars.values():
            var.set(False)
    
    def get_selected_pairs(self):
        """Get list of selected pairs"""
        return [pair for pair, var in self.pair_vars.items() if var.get()]
    
    def update_params_from_ui(self):
        """Update parameters from UI inputs"""
        try:
            self.params['start_date'] = self.start_date_var.get()
            self.params['end_date'] = self.end_date_var.get()
            self.params['tp_pips'] = self.tp_pips_var.get()
            self.params['sl_pips'] = self.sl_pips_var.get()
            self.params['max_hold'] = self.max_hold_var.get()
            self.params['target_eq_precession_threshold'] = self.target_precession_var.get()
            self.params['target_eq_mood_threshold'] = self.target_mood_var.get()
            self.params['lower_bound_precession_threshold'] = self.lower_precession_var.get()
            self.params['lower_bound_mood_threshold'] = self.lower_mood_var.get()
            self.params['vix_inflation_corr_threshold'] = self.vix_corr_var.get()
            self.params['use_enhanced_system'] = self.use_enhanced_var.get()
            self.params['selected_pairs'] = self.get_selected_pairs()
            
            # Validate date format
            if self.params['start_date']:
                datetime.strptime(self.params['start_date'], '%Y-%m-%d')
            if self.params['end_date']:
                datetime.strptime(self.params['end_date'], '%Y-%m-%d')
                
            return True
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please check your inputs: {str(e)}")
            return False
    
    def select_data_directory(self):
        """Select directory containing price and macro data"""
        directory = filedialog.askdirectory(title="Select Data Directory")
        if directory:
            # Check for required subdirectories
            price_dir = os.path.join(directory, "data", "price")
            macro_dir = os.path.join(directory, "data", "macro")
            
            if os.path.exists(price_dir) and os.path.exists(macro_dir):
                # Update data paths
                self.data_directory = directory
                self.status_var.set(f"Data directory set: {directory}")
            else:
                messagebox.showerror("Invalid Directory", 
                                     "Selected directory must contain data/price and data/macro subdirectories")
    
    def run_backtest(self):
        """Run backtest with current settings"""
        # Validate and update parameters
        if not self.update_params_from_ui():
            return
        
        # Check for selected pairs
        selected_pairs = self.get_selected_pairs()
        if not selected_pairs:
            messagebox.showerror("No Pairs Selected", "Please select at least one currency pair")
            return
        
        # Update UI state
        self.stop_button.config(state=tk.NORMAL)
        self.stop_backtest = False
        self.status_var.set("Starting backtest...")
        
        # Clear console
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        # Start backtest in a separate thread
        self.backtest_thread = threading.Thread(target=self.run_backtest_thread)
        self.backtest_thread.daemon = True
        self.backtest_thread.start()
    
    def run_backtest_thread(self):
        """Run backtest in a separate thread using the new architecture"""
        try:
            # Get parameters from UI
            start_date = self.params['start_date']
            end_date = self.params['end_date'] if self.params['end_date'] else None
            selected_pairs = self.params['selected_pairs']
            
            # Update status
            self.update_status(f"Initializing backtest for {', '.join(selected_pairs)}...")
            
            # Create strategy with parameters from UI
            strategy_params = {
                'tp_pips': self.params['tp_pips'],
                'sl_pips': self.params['sl_pips'],
                'max_hold': self.params['max_hold'],
                'target_eq_precession_threshold': self.params['target_eq_precession_threshold'],
                'lower_bound_precession_threshold': self.params['lower_bound_precession_threshold'],
                'target_eq_mood_threshold': self.params['target_eq_mood_threshold'],
                'lower_bound_mood_threshold': self.params['lower_bound_mood_threshold'],
                'vix_inflation_corr_threshold': self.params['vix_inflation_corr_threshold']
            }
            
            # Create Balance Breaker strategy
            self.strategy = BalanceBreakerStrategy(parameters=strategy_params)
            print(f"Created {self.strategy.name} strategy with parameters: {strategy_params}")
            
            # Check if we have active repositories
            price_repo = self.params.get('price_repository')
            macro_repo = self.params.get('macro_repository')
            
            # Dictionary to store price data for all pairs
            all_price_data = {}
            aligned_macro_data = {}
            
            # Load data for each pair
            for pair in selected_pairs:
                if self.stop_backtest:
                    self.update_status("Backtest stopped by user")
                    break
                
                self.update_status(f"Loading data for {pair}...")
                
                # Load price data from repository
                if self.repo_manager and price_repo:
                    try:
                        price_data = self.repo_manager.load_price_data(price_repo, pair, start_date, end_date)
                        print(f"Loaded {len(price_data)} rows of price data for {pair}")
                        
                        # Normalize data format - make sure we have OHLCV data
                        price_data = normalize_price_data(price_data)
                        print(f"Normalized price data with columns: {price_data.columns.tolist()}")
                        
                        # Make sure it has a pip_factor column
                        if 'pip_factor' not in price_data.columns:
                            price_data['pip_factor'] = 100.0 if 'JPY' in pair else 10000.0
                        
                        all_price_data[pair] = price_data
                        
                        # Load macro data if needed
                        if macro_repo:
                            # Load macro data
                            macro_data = self.repo_manager.load_macro_data(macro_repo, start_date, end_date)
                            print(f"Loaded {len(macro_data)} rows of macro data with {len(macro_data.columns)} indicators")
                            
                            # Align with price data
                            # Reindex and forward fill
                            aligned = macro_data.reindex(price_data.index, method='ffill')
                            
                            # Handle any remaining NaNs
                            aligned = aligned.ffill().bfill()
                            
                            aligned_macro_data[pair] = aligned
                    except Exception as e:
                        print(f"Error loading data for {pair}: {e}")
                        print(traceback.format_exc())
                        messagebox.showerror("Data Error", f"Error loading data for {pair}: {e}")
                        continue  # Skip this pair but continue with others
                
                # If we're loading another pair, add a short delay
                if len(selected_pairs) > 1 and pair != selected_pairs[-1]:
                    self.update_status(f"Loaded data for {pair}, preparing next pair...")
            
            # Process derived indicators if available
            if HAS_DERIVED_INDICATORS and self.derived_indicator_manager:
                try:
                    self.update_status("Generating derived indicators...")
                    
                    # Process each pair's aligned macro data with derived indicators
                    for pair in selected_pairs:
                        if pair in aligned_macro_data:
                            # Apply derived indicators
                            aligned_macro_data[pair] = self.derived_indicator_manager.generate_derived_indicators(
                                aligned_macro_data[pair])
                            print(f"Added derived indicators for {pair}")
                except Exception as e:
                    print(f"Error generating derived indicators: {e}")
                    print(traceback.format_exc())
                    self.update_status(f"Warning: Could not generate derived indicators: {e}")
            
            # Now run backtest for each pair
            all_results = {}
            for pair in selected_pairs:
                if self.stop_backtest:
                    self.update_status("Backtest stopped by user")
                    break
                
                self.update_status(f"Running backtest for {pair}...")
                
                # Get data for this pair
                price_data = all_price_data.get(pair)
                macro_data = aligned_macro_data.get(pair)
                
                if price_data is None:
                    print(f"Warning: No price data for {pair}, skipping")
                    continue
                
                # Create backtest engine for this pair
                self.backtest_engine = BacktestEngine(
                    strategy=self.strategy,
                    price_data=price_data,
                    additional_data=macro_data
                )
                
                # Run backtest with progress updates
                def update_progress(progress, elapsed, eta):
                    self.update_status(f"Backtest for {pair}: {progress:.1%} complete - ETA: {eta:.1f}s")
                
                # Start with a warmup period to allow indicators to stabilize
                results = self.backtest_engine.run_backtest(
                    start_idx=100,  # Skip first 100 candles for indicator warmup
                    progress_callback=update_progress
                )
                
                # Store results
                all_results[pair] = results
                
                self.update_status(f"Completed backtest for {pair}")
            
            # Generate playbook if all pairs completed
            if not self.stop_backtest and self.backtest_engine is not None:
                self.update_status("Generating trading playbook...")
                playbook = self.backtest_engine.generate_playbook()
                
                self.update_status("Backtest completed successfully")
                
                # Switch to results tab
                self.root.after(0, lambda: self.notebook.select(1))  # Select Results tab
                self.root.after(100, self.show_summary_results)
            
        except Exception as e:
            error_msg = f"Error in backtest: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            self.update_status(error_msg)
            messagebox.showerror("Backtest Error", error_msg)
        finally:
            # Reset UI state
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))
            self.stop_backtest = False
    
    def update_status(self, message):
        """Update status bar message"""
        self.root.after(0, lambda: self.status_var.set(message))
    
    def stop_backtest_run(self):
        """Stop the currently running backtest"""
        if self.backtest_thread and self.backtest_thread.is_alive():
            self.stop_backtest = True
            self.status_var.set("Stopping backtest...")
            messagebox.showinfo("Stopping Backtest", "Backtest will stop after completing the current pair.")
    
    def show_selected_result(self):
        """Show the selected result type"""
        result_type = self.result_type_var.get()
        pair = self.result_pair_var.get()
        
        if self.backtest_engine is None:
            messagebox.showinfo("No Data", "Please run a backtest first")
            return
        
        # Clear display frame
        for widget in self.results_display_frame.winfo_children():
            widget.destroy()
        
        if result_type == "Performance Summary":
            self.show_performance_summary(pair)
        elif result_type == "Trades Chart":
            self.show_trades_chart(pair)
        elif result_type == "Regime Analysis":
            self.show_regime_analysis(pair)
        elif result_type == "Playbook":
            self.show_playbook()
    
    def show_performance_summary(self, pair):
        """Show performance summary for the selected pair"""
        if not hasattr(self.backtest_engine, 'performance_metrics'):
            messagebox.showinfo("No Data", f"No results available for {pair}")
            return
        
        # Get results for the pair
        metrics = self.backtest_engine.performance_metrics
        
        # Create text widget to display results
        text = scrolledtext.ScrolledText(self.results_display_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        
        # Insert performance summary
        text.insert(tk.END, f"--- Performance Summary for {pair} ---\n\n")
        text.insert(tk.END, f"Total Trades: {metrics.get('total_trades', 0)}\n")
        text.insert(tk.END, f"Win Rate: {metrics.get('win_rate', 0):.1%}\n")
        text.insert(tk.END, f"Total Pips: {metrics.get('total_pips', 0):.1f}\n")
        text.insert(tk.END, f"Profit Factor: {metrics.get('profit_factor', 0):.2f}\n")
        text.insert(tk.END, f"Avg Win: {metrics.get('avg_win', 0):.1f} pips, Avg Loss: {metrics.get('avg_loss', 0):.1f} pips\n")
        text.insert(tk.END, f"Take Profit: {metrics.get('tp_count', 0)}, Stop Loss: {metrics.get('sl_count', 0)}, Time Exit: {metrics.get('time_count', 0)}\n")
        text.insert(tk.END, f"Avg Time to Max Move: {metrics.get('avg_time_to_max', 0):.1f} hours\n\n")
        
        # Add regime performance if available
        if 'regime_performance' in metrics:
            text.insert(tk.END, "Performance by Regime:\n")
            for regime, perf in metrics['regime_performance'].items():
                text.insert(tk.END, f"  {regime}: {perf['count']} trades, {perf['win_rate']:.1%} win rate, {perf['pips']:.1f} pips\n")
            text.insert(tk.END, "\n")
            
        # Add signal performance if available
        if 'signal_performance' in metrics:
            text.insert(tk.END, "Performance by Signal Type:\n")
            for signal, perf in metrics['signal_performance'].items():
                text.insert(tk.END, f"  {signal}: {perf['count']} trades, {perf['win_rate']:.1%} win rate, {perf['pips']:.1f} pips\n")
            text.insert(tk.END, "\n")
        
        text.insert(tk.END, "Monthly Performance:\n")
        if 'monthly_performance' in metrics:
            for month, stats in sorted(metrics['monthly_performance'].items()):
                win_rate = stats['wins'] / stats['count'] if stats['count'] > 0 else 0
                text.insert(tk.END, f"  {month}: {stats['count']} trades, {stats['pips']:.1f} pips, {win_rate:.1%} win rate\n")
        
        # Make it read-only
        text.config(state=tk.DISABLED)
    
    def show_trades_chart(self, pair):
        """Show trades chart for the selected pair"""
        if self.backtest_engine is None:
            messagebox.showinfo("No Data", f"No results available for {pair}")
            return
        
        try:
            # Create figure
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # Plot price data
            price_data = self.backtest_engine.price_data
            ax.plot(price_data.index, price_data['close'], color='#333333', alpha=0.8)
            ax.set_title(f"{pair} Price with Trades")
            ax.grid(True, alpha=0.3)
            
            # Add trades
            for trade in self.backtest_engine.trades:
                # Skip trades for other pairs
                if trade.get('pair') != pair:
                    continue
                    
                # Entry point
                marker = '^' if trade['direction'] > 0 else 'v'
                color = 'green' if trade['direction'] > 0 else 'red'
                ax.scatter(trade['entry_time'], trade['entry_price'], marker=marker, color=color, s=100, zorder=5)
                
                # Exit point
                result_color = 'green' if trade['pips'] > 0 else 'red'
                ax.scatter(trade['exit_time'], trade['exit_price'], marker='o', color=result_color, s=80, zorder=5)
                
                # Connect with line
                ax.plot([trade['entry_time'], trade['exit_time']], 
                      [trade['entry_price'], trade['exit_price']], 
                      color=color, linestyle='--', alpha=0.5)
            
            # Embed in UI
            canvas = FigureCanvasTkAgg(fig, master=self.results_display_frame)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar
            toolbar_frame = ttk.Frame(self.results_display_frame)
            toolbar_frame.pack(fill=tk.X)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            
        except Exception as e:
            error_msg = f"Error displaying chart: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            messagebox.showerror("Chart Error", error_msg)
    
    def show_regime_analysis(self, pair):
        """Show regime analysis for the selected pair"""
        if self.backtest_engine is None or not hasattr(self.backtest_engine, 'performance_metrics'):
            messagebox.showinfo("No Data", f"No results available for {pair}")
            return
        
        # Get results
        metrics = self.backtest_engine.performance_metrics
        
        if 'regime_performance' not in metrics:
            messagebox.showinfo("No Regime Data", f"No regime analysis available for {pair}. Make sure you used the enhanced system.")
            return
        
        # Create frame to display results
        frame = ttk.Frame(self.results_display_frame)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Create a figure for regime performance chart
        fig, ax = plt.subplots(figsize=(8, 4))
        
        # Prepare data for plotting
        regimes = list(metrics['regime_performance'].keys())
        win_rates = [metrics['regime_performance'][r]['win_rate'] * 100 for r in regimes]
        avg_pips = [metrics['regime_performance'][r]['pips'] / metrics['regime_performance'][r]['count'] for r in regimes]
        counts = [metrics['regime_performance'][r]['count'] for r in regimes]
        
        # Plot win rates
        x = np.arange(len(regimes))
        width = 0.35
        
        ax.bar(x - width/2, win_rates, width, label='Win Rate %')
        ax.set_ylim(0, 100)
        ax.set_ylabel('Win Rate %')
        
        # Add counts as text
        for i, v in enumerate(win_rates):
            ax.text(i - width/2, v + 5, f"{counts[i]} trades", ha='center')
        
        # Create second y-axis for average pips
        ax2 = ax.twinx()
        ax2.bar(x + width/2, avg_pips, width, color='orange', label='Avg Pips')
        ax2.set_ylabel('Average Pips')
        
        # Set x-ticks
        ax.set_xticks(x)
        ax.set_xticklabels(regimes)
        
        # Add legend
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # Set title
        plt.title(f"Regime Performance for {pair}")
        
        # Embed in UI
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def show_playbook(self):
        """Show trading playbook"""
        if self.backtest_engine is None:
            messagebox.showinfo("No Data", "Please run a backtest first")
            return
        
        # Generate playbook from backtest engine
        try:
            playbook = self.backtest_engine.generate_playbook()
        except Exception as e:
            error_msg = f"Error generating playbook: {str(e)}"
            print(error_msg)
            print(traceback.format_exc())
            messagebox.showerror("Playbook Error", error_msg)
            return
        
        # Create text widget to display playbook
        text = scrolledtext.ScrolledText(self.results_display_frame, wrap=tk.WORD, padx=10, pady=10)
        text.pack(fill=tk.BOTH, expand=True)
        
        # Insert playbook header
        text.insert(tk.END, "🔖 TRADING PLAYBOOK - 'The Balance Breaker' 🔖\n")
        text.insert(tk.END, "=============================================\n\n")
        
        # Check if playbook exists
        if playbook:
            for setup in playbook:
                # Basic setup info
                text.insert(tk.END, f"{setup['pair']} when Market Mood is {setup['market_mood']} with {setup['precession']} precession:\n")
                text.insert(tk.END, f"  Win rate: {setup['win_rate']:.1%}, Avg pips: {setup['avg_pips']:.1f}\n")
                text.insert(tk.END, f"  Sample: {setup['sample_size']} trades, Avg time to max: {setup['avg_time_to_max']:.1f} hours\n")
                
                # Enhanced info
                if 'regime' in setup:
                    text.insert(tk.END, f"  Regime: {setup['regime']}\n")
                    
                text.insert(tk.END, f"  Expected value: {setup['win_rate'] * setup['avg_pips']:.1f} pips per trade\n")
                text.insert(tk.END, "---------------------------------------------\n")
        else:
            text.insert(tk.END, "No playbook data available. Run the backtest first.")
        
        # Make it read-only
        text.config(state=tk.DISABLED)
    
    def show_summary_results(self):
        """Show summary results after backtest completes"""
        self.result_type_var.set("Performance Summary")
        if self.params['selected_pairs']:
            self.result_pair_var.set(self.params['selected_pairs'][0])
        self.show_selected_result()
    
    def view_recent_results(self):
        """View recently saved results"""
        # Look for backtest_results directory
        results_dir = os.path.join(os.getcwd(), "backtest_results")
        if not os.path.exists(results_dir):
            messagebox.showinfo("No Results", "No saved backtest results found")
            return
        
        # Find run directories
        run_dirs = [d for d in os.listdir(results_dir) if d.startswith('run') and os.path.isdir(os.path.join(results_dir, d))]
        if not run_dirs:
            messagebox.showinfo("No Results", "No saved backtest runs found")
            return
        
        # Sort by run number
        run_dirs.sort(key=lambda x: int(x.replace('run', '')) if x.replace('run', '').isdigit() else 0, reverse=True)
        
        # Create selection dialog
        run_selection = tk.Toplevel(self.root)
        run_selection.title("Select Backtest Run")
        run_selection.geometry("400x300")
        run_selection.transient(self.root)
        
        ttk.Label(run_selection, text="Select a backtest run to view:").pack(pady=10)
        
        # Create listbox for runs
        run_list = tk.Listbox(run_selection, width=50, height=10)
        run_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Add runs to listbox
        for run_dir in run_dirs:
            # Try to get date from parameters.txt
            params_file = os.path.join(results_dir, run_dir, 'parameters.txt')
            timestamp = ""
            if os.path.exists(params_file):
                try:
                    with open(params_file, 'r') as f:
                        for line in f:
                            if 'timestamp:' in line.lower():
                                timestamp = line.split(':', 1)[1].strip()
                                break
                except:
                    pass
                    
            run_list.insert(tk.END, f"{run_dir} - {timestamp}")
        
        # Add buttons
        button_frame = ttk.Frame(run_selection)
        button_frame.pack(fill=tk.X, pady=10)
        
        def load_selected_run():
            selection = run_list.curselection()
            if not selection:
                messagebox.showinfo("No Selection", "Please select a run to load")
                return
                
            selected_run = run_dirs[selection[0]]
            run_selection.destroy()
            
            messagebox.showinfo("Load Results", f"Loading results from {selected_run} is not implemented yet")
        
        ttk.Button(button_frame, text="Load", command=load_selected_run).pack(side=tk.RIGHT, padx=10)
        ttk.Button(button_frame, text="Cancel", command=run_selection.destroy).pack(side=tk.RIGHT, padx=10)
    
    def show_documentation(self):
        """Show system documentation"""
        messagebox.showinfo("Documentation", 
                           "Balance Breaker System Documentation\n\n"
                           "This system implements the Balance Breaker trading algorithm using "
                           "a quaternion cloud system to model market dynamics and generate trading signals.\n\n"
                           "The Enhanced System includes:\n"
                           "- Regime awareness (target equilibrium vs. lower bound)\n"
                           "- VIX-inflation correlation analysis\n"
                           "- Adaptive signal generation based on market conditions\n\n"
                           "For more information, refer to the included documentation files.")
    
    def show_about(self):
        """Show about dialog"""
        messagebox.showinfo("About Balance Breaker", 
                          "Balance Breaker Trading System\n"
                          "Version 2.0\n\n"
                          "A modular trading system using quaternion cloud physics\n"
                          "to model macroeconomic market dynamics.\n\n"
                          "Built with the new modular strategy architecture.")
                          
    def create_risk_management_tab(self):
        """Create risk management configuration tab"""
        risk_frame = ttk.Frame(self.notebook)
        self.notebook.add(risk_frame, text="Risk Management")
        
        # Left panel for risk model selection
        left_panel = ttk.LabelFrame(risk_frame, text="Risk Model")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Risk model selection
        ttk.Label(left_panel, text="Risk Model:").pack(anchor=tk.W, padx=5, pady=5)
        self.risk_model_var = tk.StringVar(value="Fixed")
        model_combo = ttk.Combobox(left_panel, textvariable=self.risk_model_var, 
                                values=["Fixed", "Percentage", "ATR"], 
                                state="readonly", width=15)
        model_combo.pack(anchor=tk.W, padx=5, pady=5)
        model_combo.bind("<<ComboboxSelected>>", self.update_risk_parameters)
        
        # Risk model description
        description_frame = ttk.LabelFrame(left_panel, text="Description")
        description_frame.pack(fill=tk.X, padx=5, pady=10)
        
        self.risk_description_var = tk.StringVar(value="Fixed risk model with constant position size and fixed pip targets/stops")
        ttk.Label(description_frame, textvariable=self.risk_description_var, 
                 wraplength=300).pack(padx=10, pady=10)
        
        # Right panel for risk parameters
        right_panel = ttk.LabelFrame(risk_frame, text="Risk Parameters")
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create parameter frames for each risk model
        self.risk_param_frames = {}
        
        # Fixed risk parameters
        fixed_frame = ttk.Frame(right_panel)
        self.risk_param_frames['Fixed'] = fixed_frame
        
        ttk.Label(fixed_frame, text="Position Size (lots):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.fixed_position_var = tk.DoubleVar(value=1.0)
        ttk.Entry(fixed_frame, textvariable=self.fixed_position_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(fixed_frame, text="Take Profit (pips):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.fixed_tp_var = tk.IntVar(value=300)
        ttk.Entry(fixed_frame, textvariable=self.fixed_tp_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(fixed_frame, text="Stop Loss (pips):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.fixed_sl_var = tk.IntVar(value=100)
        ttk.Entry(fixed_frame, textvariable=self.fixed_sl_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Percentage risk parameters
        pct_frame = ttk.Frame(right_panel)
        self.risk_param_frames['Percentage'] = pct_frame
        
        ttk.Label(pct_frame, text="Risk Per Trade (%):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.pct_risk_var = tk.DoubleVar(value=2.0)
        ttk.Entry(pct_frame, textvariable=self.pct_risk_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(pct_frame, text="Reward Ratio:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.pct_reward_var = tk.DoubleVar(value=3.0)
        ttk.Entry(pct_frame, textvariable=self.pct_reward_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(pct_frame, text="Max Position (%):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.pct_max_pos_var = tk.DoubleVar(value=10.0)
        ttk.Entry(pct_frame, textvariable=self.pct_max_pos_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # ATR risk parameters
        atr_frame = ttk.Frame(right_panel)
        self.risk_param_frames['ATR'] = atr_frame
        
        ttk.Label(atr_frame, text="Risk Per Trade (%):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.atr_risk_var = tk.DoubleVar(value=1.0)
        ttk.Entry(atr_frame, textvariable=self.atr_risk_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(atr_frame, text="ATR Multiplier:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.atr_mult_var = tk.DoubleVar(value=2.0)
        ttk.Entry(atr_frame, textvariable=self.atr_mult_var, width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(atr_frame, text="Reward Multiplier:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.atr_reward_var = tk.DoubleVar(value=2.5)
        ttk.Entry(atr_frame, textvariable=self.atr_reward_var, width=8).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(atr_frame, text="ATR Period:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=5)
        self.atr_period_var = tk.IntVar(value=14)
        ttk.Entry(atr_frame, textvariable=self.atr_period_var, width=8).grid(row=3, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Show only the selected risk model's parameters
        self.update_risk_parameters()
        
        # Bottom panel for test area
        bottom_panel = ttk.LabelFrame(risk_frame, text="Test Risk Model")
        bottom_panel.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)
        
        # Test inputs
        test_frame = ttk.Frame(bottom_panel)
        test_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(test_frame, text="Account Balance:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.test_balance_var = tk.DoubleVar(value=10000.0)
        ttk.Entry(test_frame, textvariable=self.test_balance_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(test_frame, text="Entry Price:").grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.test_price_var = tk.DoubleVar(value=1.1000)
        ttk.Entry(test_frame, textvariable=self.test_price_var, width=10).grid(row=0, column=3, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(test_frame, text="Direction:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.test_direction_var = tk.StringVar(value="Buy")
        ttk.Combobox(test_frame, textvariable=self.test_direction_var, 
                   values=["Buy", "Sell"], state="readonly", width=8).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(test_frame, text="ATR:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.test_atr_var = tk.DoubleVar(value=0.0010)
        ttk.Entry(test_frame, textvariable=self.test_atr_var, width=10).grid(row=1, column=3, sticky=tk.W, padx=5, pady=5)
        
        # Test button and results
        test_button = ttk.Button(test_frame, text="Test Risk Model", command=self.test_risk_model)
        test_button.grid(row=2, column=0, columnspan=2, sticky=tk.W, padx=5, pady=10)
        
        # Results frame
        results_frame = ttk.LabelFrame(bottom_panel, text="Risk Model Results")
        results_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(results_frame, text="Position Size:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.result_size_var = tk.StringVar(value="-")
        ttk.Label(results_frame, textvariable=self.result_size_var).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(results_frame, text="Stop Loss:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.result_sl_var = tk.StringVar(value="-")
        ttk.Label(results_frame, textvariable=self.result_sl_var).grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        ttk.Label(results_frame, text="Take Profit:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.result_tp_var = tk.StringVar(value="-")
        ttk.Label(results_frame, textvariable=self.result_tp_var).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        return risk_frame

    def update_risk_parameters(self, event=None):
        """Update risk parameter UI based on selected risk model"""
        selected_model = self.risk_model_var.get()
        
        # Hide all parameter frames
        for frame in self.risk_param_frames.values():
            frame.pack_forget()
        
        # Show selected model's parameters
        if selected_model in self.risk_param_frames:
            self.risk_param_frames[selected_model].pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Update description
        descriptions = {
            'Fixed': "Fixed risk model with constant position size and fixed pip targets/stops.",
            'Percentage': "Percentage-based risk model that risks a fixed percentage of account balance per trade.",
            'ATR': "Volatility-based risk model using Average True Range (ATR) to set position size and stops."
        }
        
        self.risk_description_var.set(descriptions.get(selected_model, ""))

    def test_risk_model(self):
        """Test the current risk model with provided test values"""
        try:
            from balance_breaker.src.risk_management import create_risk_manager
            
            # Get selected risk model
            model_type = self.risk_model_var.get()
            
            # Get model parameters based on type
            if model_type == 'Fixed':
                params = {
                    'position_size': self.fixed_position_var.get(),
                    'tp_pips': self.fixed_tp_var.get(),
                    'sl_pips': self.fixed_sl_var.get()
                }
            elif model_type == 'Percentage':
                params = {
                    'risk_percent': self.pct_risk_var.get(),
                    'reward_ratio': self.pct_reward_var.get(),
                    'max_position_percent': self.pct_max_pos_var.get()
                }
            elif model_type == 'ATR':
                params = {
                    'risk_percent': self.atr_risk_var.get(),
                    'atr_multiplier': self.atr_mult_var.get(),
                    'reward_multiplier': self.atr_reward_var.get(),
                    'atr_period': self.atr_period_var.get()
                }
            else:
                messagebox.showerror("Error", f"Unknown risk model type: {model_type}")
                return
            
            # Create risk manager
            risk_manager = create_risk_manager(model_type, params)
            
            # Get test values
            context = {
                'account_balance': self.test_balance_var.get(),
                'entry_price': self.test_price_var.get(),
                'direction': 1 if self.test_direction_var.get() == "Buy" else -1,
                'atr': self.test_atr_var.get(),
                'pip_factor': 10000,  # Assuming 4-digit currency pair
                'pip_value': 10.0     # Assuming standard lot
            }
            
            # Calculate and display results
            position_size = risk_manager.calculate_position_size(context)
            stop_loss = risk_manager.calculate_stop_loss(context)
            
            # Update context with stop price for take profit calculation
            context['stop_price'] = stop_loss
            take_profit = risk_manager.calculate_take_profit(context)
            
            # Show results
            self.result_size_var.set(f"{position_size:.2f} lots")
            self.result_sl_var.set(f"{stop_loss:.5f} ({abs(context['entry_price'] - stop_loss) * context['pip_factor']:.1f} pips)")
            self.result_tp_var.set(f"{take_profit:.5f} ({abs(take_profit - context['entry_price']) * context['pip_factor']:.1f} pips)")
            
        except Exception as e:
            print(f"Error testing risk model: {e}")
            print(traceback.format_exc())
            messagebox.showerror("Error", f"Error testing risk model: {e}")
            
    def show_dev_console(self):
        """Show developer console for interactive debugging"""
        # Create a new toplevel window
        console_window = tk.Toplevel(self.root)
        console_window.title("Developer Console")
        console_window.geometry("800x600")
        console_window.transient(self.root)
        
        # Split the window into input and output areas
        paned_window = ttk.PanedWindow(console_window, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Input frame
        input_frame = ttk.LabelFrame(paned_window, text="Python Code Input")
        paned_window.add(input_frame, weight=1)
        
        # Code input area
        code_input = scrolledtext.ScrolledText(input_frame, wrap=tk.WORD, height=10)
        code_input.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(input_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Output frame
        output_frame = ttk.LabelFrame(paned_window, text="Output")
        paned_window.add(output_frame, weight=2)
        
        # Output area
        output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=20)
        output_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        output_text.config(state=tk.DISABLED)
        
        # Function to run code
        def run_code():
            # Get the code from the input area
            code = code_input.get("1.0", tk.END)
            
            # Create a dictionary with relevant objects to make available in the executed code
            locals_dict = {
                'app': self,
                'tk': tk,
                'ttk': ttk,
                'np': np,
                'pd': pd,
                'plt': plt,
                'strategy': self.strategy,
                'backtest_engine': self.backtest_engine
            }
            
            # Redirect stdout to capture print statements
            import io
            from contextlib import redirect_stdout
            
            output_buffer = io.StringIO()
            
            # Enable output text for writing
            output_text.config(state=tk.NORMAL)
            output_text.delete("1.0", tk.END)
            output_text.insert(tk.END, "Executing code...\n\n")
            output_text.update()
            
            try:
                # Execute the code with both global and local contexts
                with redirect_stdout(output_buffer):
                    exec(code, globals(), locals_dict)
                
                # Get the captured output
                output = output_buffer.getvalue()
                
                # Show the output
                output_text.insert(tk.END, "Output:\n")
                output_text.insert(tk.END, output)
                
                # If there was no output but execution succeeded
                if not output:
                    output_text.insert(tk.END, "Code executed successfully with no output.")
                    
            except Exception as e:
                # Show the error
                output_text.insert(tk.END, f"Error:\n{str(e)}\n\n")
                output_text.insert(tk.END, traceback.format_exc())
            
            # Disable the text widget again
            output_text.config(state=tk.DISABLED)
        
        # Add buttons
        ttk.Button(button_frame, text="Run Code", command=run_code).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Input", command=lambda: code_input.delete("1.0", tk.END)).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Output", 
                  command=lambda: (output_text.config(state=tk.NORMAL), 
                                  output_text.delete("1.0", tk.END), 
                                  output_text.config(state=tk.DISABLED))).pack(side=tk.LEFT, padx=5)
        
        # Add some helpful tips
        tips_frame = ttk.LabelFrame(console_window, text="Tips")
        tips_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tips_text = "Available objects:\n"
        tips_text += "- app: The main application instance\n"
        tips_text += "- tk, ttk: Tkinter modules\n"
        tips_text += "- np, pd: NumPy and pandas\n"
        tips_text += "- plt: Matplotlib.pyplot\n"
        tips_text += "- strategy: Current strategy instance (if loaded)\n"
        tips_text += "- backtest_engine: Current backtest engine (if available)\n"
        
        ttk.Label(tips_frame, text=tips_text, justify=tk.LEFT).pack(anchor=tk.W, padx=5, pady=5)

# Entry point
if __name__ == "__main__":
    root = tk.Tk()
    app = BalanceBreakerApp(root)
    root.mainloop()