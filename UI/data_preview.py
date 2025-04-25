"""
Balance Breaker Data Preview
Tools for previewing and validating data repositories
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pandas as pd
import numpy as np
import matplotlib
# Configure matplotlib to use Agg backend for thread safety
matplotlib.use('Agg')  # Important: must be before importing pyplot
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.dates import DateFormatter
import traceback  # Add this import for error tracing

def normalize_price_data(df):
    """
    Normalize price data to have consistent column names
    regardless of the original format
    """
    # Make a copy to avoid modifying the original
    normalized = df.copy()
    
    # Check column names
    columns = df.columns.str.lower()
    
    # If we have separate bid/ask columns
    if 'bidclose' in columns and 'askclose' in columns:
        print("Detected Bid/Ask format, converting to OHLCV format")
        # Calculate mid prices
        normalized['open'] = (df['BidOpen'] + df['AskOpen']) / 2
        normalized['high'] = (df['BidHigh'] + df['AskHigh']) / 2
        normalized['low'] = (df['BidLow'] + df['AskLow']) / 2
        normalized['close'] = (df['BidClose'] + df['AskClose']) / 2
        
        # Add a volume column if it doesn't exist
        if 'volume' not in columns and 'tickqty' not in columns:
            normalized['volume'] = 1
        elif 'tickqty' in columns:
            normalized['volume'] = df['TickQty']
            
    # If we have Close but not close (case sensitivity)
    elif 'close' not in columns and 'Close' in df.columns:
        print("Detected capitalized column names, converting to lowercase")
        # Rename columns to lowercase
        column_mapping = {
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        }
        # Only rename columns that exist
        column_mapping = {k: v for k, v in column_mapping.items() if k in df.columns}
        normalized.rename(columns=column_mapping, inplace=True)
        
        # Add missing columns with reasonable defaults
        if 'open' not in normalized.columns:
            normalized['open'] = normalized['close'].shift(1)
        if 'high' not in normalized.columns:
            normalized['high'] = normalized['close']
        if 'low' not in normalized.columns:
            normalized['low'] = normalized['close']
        if 'volume' not in normalized.columns:
            normalized['volume'] = 1
    
    # Ensure all required columns exist
    required_columns = ['open', 'high', 'low', 'close', 'volume']
    for col in required_columns:
        if col not in normalized.columns:
            print(f"Warning: Missing required column '{col}', using defaults")
            if col == 'volume':
                normalized[col] = 1
            else:
                # Use close for missing price columns
                normalized[col] = normalized['close'] if 'close' in normalized.columns else 0
    
    # Keep only the required columns
    normalized = normalized[required_columns]
    
    return normalized

class DataPreview:
    """Data preview window for repository data"""
    def __init__(self, parent, repo_manager, repo_type, repo_name):
        self.parent = parent
        self.repo_manager = repo_manager
        self.repo_type = repo_type
        self.repo_name = repo_name
        self.data = None
        self.create_preview_window()
    
    def create_preview_window(self):
        """Create data preview window"""
        self.window = tk.Toplevel(self.parent)
        self.window.title(f"Data Preview: {self.repo_name} ({self.repo_type})")
        self.window.geometry("1000x700")
        self.window.transient(self.parent)
        
        # Create notebook for different views
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.create_summary_tab()
        self.create_data_tab()
        self.create_chart_tab()
        self.create_validation_tab()
        
        # Load data
        self.load_data()
    
    def create_summary_tab(self):
        """Create summary tab with repository information"""
        self.summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.summary_frame, text="Summary")
        
        # Repository info
        info_frame = ttk.LabelFrame(self.summary_frame, text="Repository Information")
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        # Create a text widget to display info
        self.summary_text = tk.Text(info_frame, wrap=tk.WORD, height=10)
        self.summary_text.pack(fill=tk.X, padx=5, pady=5)
        self.summary_text.config(state=tk.DISABLED)
        
        # Data statistics frame
        stats_frame = ttk.LabelFrame(self.summary_frame, text="Data Statistics")
        stats_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create a text widget for statistics
        self.stats_text = tk.Text(stats_frame, wrap=tk.WORD, height=15)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.stats_text.config(state=tk.DISABLED)
    
    def create_data_tab(self):
        """Create tab showing raw data"""
        self.data_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.data_frame, text="Data")
        
        # Controls frame
        controls_frame = ttk.Frame(self.data_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Filter controls if price data
        if self.repo_type == 'price':
            ttk.Label(controls_frame, text="Pair:").pack(side=tk.LEFT, padx=5)
            self.pair_var = tk.StringVar()
            self.pair_combo = ttk.Combobox(controls_frame, textvariable=self.pair_var, state="readonly", width=10)
            self.pair_combo.pack(side=tk.LEFT, padx=5)
            self.pair_combo.bind("<<ComboboxSelected>>", self.on_pair_selected)
        
        # Rows to display
        ttk.Label(controls_frame, text="Rows:").pack(side=tk.LEFT, padx=5)
        self.rows_var = tk.StringVar(value="100")
        row_choices = ttk.Combobox(controls_frame, textvariable=self.rows_var, 
                                 values=["10", "50", "100", "500", "1000", "All"], 
                                 width=5, state="readonly")
        row_choices.pack(side=tk.LEFT, padx=5)
        row_choices.bind("<<ComboboxSelected>>", self.update_data_view)
        
        # Create treeview for data
        self.tree_frame = ttk.Frame(self.data_frame)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical")
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal")
        
        # Create treeview
        self.tree = ttk.Treeview(self.tree_frame, columns=[], show="headings", 
                                yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        # Configure scrollbars
        vsb.config(command=self.tree.yview)
        hsb.config(command=self.tree.xview)
        
        # Pack treeview and scrollbars
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    
    def create_chart_tab(self):
        """Create chart tab"""
        self.chart_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.chart_frame, text="Chart")
        
        # Controls frame
        controls_frame = ttk.Frame(self.chart_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Chart type
        ttk.Label(controls_frame, text="Chart Type:").pack(side=tk.LEFT, padx=5)
        self.chart_type_var = tk.StringVar(value="Line")
        chart_type_combo = ttk.Combobox(controls_frame, textvariable=self.chart_type_var, 
                                      values=["Line", "Candlestick", "OHLC"], 
                                      width=15, state="readonly")
        chart_type_combo.pack(side=tk.LEFT, padx=5)
        chart_type_combo.bind("<<ComboboxSelected>>", self.update_chart)
        
        # Price type selector (for bid/ask format)
        self.price_type_frame = ttk.Frame(controls_frame)
        self.price_type_frame.pack(side=tk.LEFT, padx=10)
        self.price_type_var = tk.StringVar(value="Bid")
        
        # These will be shown/hidden based on data format
        ttk.Label(self.price_type_frame, text="Price:").pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.price_type_frame, text="Bid", variable=self.price_type_var, 
                       value="Bid", command=self.switch_price_type).pack(side=tk.LEFT)
        ttk.Radiobutton(self.price_type_frame, text="Ask", variable=self.price_type_var, 
                       value="Ask", command=self.switch_price_type).pack(side=tk.LEFT)
        
        # Hide by default until we detect bid/ask format
        self.price_type_frame.pack_forget()
        
        # Column selector (for macro data)
        if self.repo_type == 'macro':
            ttk.Label(controls_frame, text="Column:").pack(side=tk.LEFT, padx=5)
            self.column_var = tk.StringVar()
            self.column_combo = ttk.Combobox(controls_frame, textvariable=self.column_var, 
                                           state="readonly", width=30)
            self.column_combo.pack(side=tk.LEFT, padx=5)
            self.column_combo.bind("<<ComboboxSelected>>", self.update_chart)
        
        # Button to update chart
        ttk.Button(controls_frame, text="Update Chart", 
                  command=self.update_chart).pack(side=tk.LEFT, padx=10)
        
        # Frame for chart
        self.chart_container = ttk.Frame(self.chart_frame)
        self.chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
    
    def create_validation_tab(self):
        """Create data validation tab"""
        self.validation_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.validation_frame, text="Validation")
        
        # Controls frame
        controls_frame = ttk.Frame(self.validation_frame)
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Validation type
        ttk.Label(controls_frame, text="Check:").pack(side=tk.LEFT, padx=5)
        self.validation_type_var = tk.StringVar(value="Missing Values")
        validation_type_combo = ttk.Combobox(controls_frame, textvariable=self.validation_type_var, 
                                           values=["Missing Values", "Outliers", "Duplicates", "Gaps", "Data Types"], 
                                           width=15, state="readonly")
        validation_type_combo.pack(side=tk.LEFT, padx=5)
        
        # Run validation button
        ttk.Button(controls_frame, text="Run Check", 
                  command=self.run_validation).pack(side=tk.LEFT, padx=10)
        
        # Debug button for OHLC validation
        ttk.Button(controls_frame, text="Validate OHLC Data", 
                  command=self.validate_ohlc_data).pack(side=tk.LEFT, padx=10)
        
        # Results frame
        results_frame = ttk.LabelFrame(self.validation_frame, text="Results")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Text widget for results
        self.validation_text = tk.Text(results_frame, wrap=tk.WORD)
        self.validation_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.validation_text.config(state=tk.DISABLED)
    
    def load_data(self):
        """Load repository data"""
        try:
            print(f"Loading data for {self.repo_type} repository: {self.repo_name}")
            
            if self.repo_type == 'price':
                # For price data, we need to find available pairs
                repo_config = self.repo_manager.repositories['price'][self.repo_name]
                directory = repo_config['directory']
                format_type = repo_config.get('format', 'csv')
                
                print(f"Repository directory: {directory}, format: {format_type}")
                
                # Find available pairs
                self.available_pairs = self.find_available_pairs(directory, format_type)
                
                if not self.available_pairs:
                    print("No currency pair files found in repository")
                    messagebox.showerror("Error", "No currency pair files found in repository")
                    self.window.destroy()
                    return
                
                # Set initial pair and update combo
                self.pair_var.set(self.available_pairs[0])
                self.pair_combo['values'] = self.available_pairs
                print(f"Selected initial pair: {self.available_pairs[0]}")
                
                # Load data for first pair
                print(f"Loading data for {self.available_pairs[0]}")
                self.data = self.repo_manager.load_price_data(self.repo_name, self.available_pairs[0])
                
                # Debug data after loading
                print(f"Loaded {len(self.data)} rows of price data")
                print(f"Data columns: {self.data.columns.tolist()}")
                print(f"Data types:")
                for col in self.data.columns:
                    
                    ##print(f"  {col}: {self.data[col].dtypes}")
                    print(f"  {col}: {type(self.data[col]).__name__} {self.data[col].dtypes if hasattr(self.data[col], 'dtypes') else self.data[col].dtype if hasattr(self.data[col], 'dtype') else 'unknown'}")

                print("First 5 rows of data:")
                print(self.data.head(5))
                
                # Check for non-numeric values in expected numeric columns
                numeric_cols = [col for col in self.data.columns if any(term in col.lower() for term in ['open', 'high', 'low', 'close', 'bid', 'ask'])]
                for col in numeric_cols:
                    non_numeric = pd.to_numeric(self.data[col], errors='coerce').isna().sum()
                    if non_numeric > 0:
                        print(f"⚠️ Warning: Column {col} has {non_numeric} non-numeric values")
                
                # Detect and normalize data format
                self.detect_and_normalize_price_format()
                
            elif self.repo_type == 'macro':
                # Load all macro data
                print("Loading macro economic data")
                self.data = self.repo_manager.load_macro_data(self.repo_name)
                print(f"Loaded {len(self.data)} rows of macro data with {len(self.data.columns)} indicators")
                
                # Update column selector
                self.column_var.set(self.data.columns[0])
                self.column_combo['values'] = list(self.data.columns)
            
            # Update all views
            print("Updating data preview views")
            self.update_summary()
            self.update_data_view()
            self.update_chart()
            
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            print(f"Error traceback: {traceback.format_exc()}")
            messagebox.showerror("Error", f"Error loading data: {str(e)}")
            self.window.destroy()
            
    def detect_and_normalize_price_format(self):
        """Detect the price data format and normalize if needed"""
        if self.data is None or len(self.data.columns) == 0:
            return
        
        print("Detecting price data format...")
        
        # Use our universal price normalizer
        original_columns = self.data.columns.tolist()
        print(f"Original columns: {original_columns}")
        
        # Store original data format information before normalization
        self.data_format = "unknown"
        self.price_type_var = tk.StringVar(value="Bid")  # Default value
        
        # Check if we have bid/ask format
        bid_ask_columns = ['BidOpen', 'BidHigh', 'BidLow', 'BidClose', 
                          'AskOpen', 'AskHigh', 'AskLow', 'AskClose']
        has_bid_ask_format = all(col in self.data.columns for col in bid_ask_columns)
        
        # Check if we have standard OHLC format
        ohlc_columns = ['open', 'high', 'low', 'close']
        has_ohlc_format = all(col in self.data.columns for col in ohlc_columns)
        
        # Create a copy of the original data before normalization
        self.original_data = self.data.copy()
        
        # If we have bid/ask format, we'll want to keep it and offer toggling
        if has_bid_ask_format:
            print("Detected Bid/Ask format")
            self.data_format = "bid_ask"
            
            # Check if DateTime column exists and convert to index if needed
            if 'DateTime' in self.data.columns:
                print("Converting DateTime column to index")
                self.data['DateTime'] = pd.to_datetime(self.data['DateTime'])
                self.data.set_index('DateTime', inplace=True)
                
            # Ensure bid/ask columns are numeric
            for col in bid_ask_columns:
                try:
                    print(f"Converting {col} to numeric")
                    self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
                except Exception as e:
                    print(f"Error converting {col} to numeric: {e}")
            
            # Create standard OHLC columns from Bid data by default
            if not has_ohlc_format:
                print("Creating standard OHLC columns from Bid data")
                self.data['open'] = pd.to_numeric(self.data['BidOpen'], errors='coerce')
                self.data['high'] = pd.to_numeric(self.data['BidHigh'], errors='coerce')
                self.data['low'] = pd.to_numeric(self.data['BidLow'], errors='coerce')
                self.data['close'] = pd.to_numeric(self.data['BidClose'], errors='coerce')
                self.data['volume'] = 1  # Default volume
            
            # Show price type selection in chart tab
            if hasattr(self, 'price_type_frame'):
                self.price_type_frame.pack(side=tk.LEFT, padx=10)
        
        # If we don't have the OHLC columns we need for plotting, normalize the data
        elif not has_ohlc_format:
            print("No standard OHLC format detected, normalizing data")
            try:
                normalized = normalize_price_data(self.data)
                print(f"Normalized columns: {normalized.columns.tolist()}")
                
                # Preserve the index
                normalized.index = self.data.index
                
                # Update the data with normalized version
                self.data = normalized
                self.data_format = "normalized"
                
                # Hide price type selection
                if hasattr(self, 'price_type_frame'):
                    self.price_type_frame.pack_forget()
                    
            except Exception as e:
                print(f"Error normalizing data: {e}")
                print(f"Error traceback: {traceback.format_exc()}")
        
        else:
            print("Detected standard OHLC format")
            self.data_format = "ohlc"
            
            # Ensure OHLC columns are numeric
            for col in ohlc_columns:
                try:
                    print(f"Converting {col} to numeric")
                    self.data[col] = pd.to_numeric(self.data[col], errors='coerce')
                except Exception as e:
                    print(f"Error converting {col} to numeric: {e}")
            
            # Add volume if missing
            if 'volume' not in self.data.columns:
                self.data['volume'] = 1
                
            # Hide price type selection
            if hasattr(self, 'price_type_frame'):
                self.price_type_frame.pack_forget()
        
        # Remove any rows with NaN values in OHLC columns if they exist
        if all(col in self.data.columns for col in ['open', 'high', 'low', 'close']):
            print("Checking for NaN values in OHLC data")
            nan_count_before = self.data[['open', 'high', 'low', 'close']].isna().sum().sum()
            if nan_count_before > 0:
                print(f"Found {nan_count_before} NaN values in OHLC data")
                self.data.dropna(subset=['open', 'high', 'low', 'close'], inplace=True)
                print(f"Dropped rows with NaN values, {len(self.data)} rows remaining")
        
        print(f"Data format detection complete: {self.data_format}")
        
    def switch_price_type(self, event=None):
        """Switch between Bid and Ask data for bid/ask format"""
        if self.data_format != "bid_ask":
            return
            
        price_type = self.price_type_var.get()
        print(f"Switching to {price_type} data")
        
        prefix = price_type  # "Bid" or "Ask"
        
        # Update the OHLC columns
        self.data['open'] = self.data[f'{prefix}Open']
        self.data['high'] = self.data[f'{prefix}High']
        self.data['low'] = self.data[f'{prefix}Low']
        self.data['close'] = self.data[f'{prefix}Close']
        
        # Update views
        self.update_chart()
        
    def on_pair_selected(self, event=None):
        """Handle pair selection change"""
        selected_pair = self.pair_var.get()
        try:
            print(f"Loading data for selected pair: {selected_pair}")
            # Load data for selected pair
            self.data = self.repo_manager.load_price_data(self.repo_name, selected_pair)
            print(f"Successfully loaded {len(self.data)} rows")
            
            # Detect and normalize format
            self.detect_and_normalize_price_format()
            
            # Update views
            self.update_summary()
            self.update_data_view()
            self.update_chart()
        except Exception as e:
            print(f"Error loading data for {selected_pair}: {str(e)}")
            messagebox.showerror("Error", f"Error loading data for {selected_pair}: {str(e)}")
    
    def find_available_pairs(self, directory, format_type):
        """Find available currency pairs in the repository"""
        import os
        
        extensions = {
            'csv': ['.csv', '.CSV'],
            'excel': ['.xlsx', '.xls', '.XLSX', '.XLS']
        }
        
        file_extensions = extensions.get(format_type, ['.csv', '.CSV'])
        currency_pairs = []
        
        # Common pairs to look for
        common_pairs = ['USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD']
        
        print(f"Searching for currency pairs in {directory} with extensions {file_extensions}")
        
        # Look for files with pair names
        for root, _, files in os.walk(directory):
            for file in files:
                print(f"Examining file: {file}")
                # Case-insensitive file extension check
                if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                    # Try to identify pair from filename (case insensitive)
                    found_pair = None
                    for pair in common_pairs:
                        if pair.lower() in file.lower():
                            found_pair = pair
                            print(f"Found pair {pair} in file {file}")
                            break
                    
                    if found_pair and found_pair not in currency_pairs:
                        currency_pairs.append(found_pair)
        
        print(f"Found {len(currency_pairs)} currency pairs: {currency_pairs}")
        return currency_pairs
    
    def on_pair_selected(self, event=None):
        """Handle pair selection change"""
        selected_pair = self.pair_var.get()
        try:
            print(f"Loading data for selected pair: {selected_pair}")
            # Load data for selected pair
            self.data = self.repo_manager.load_price_data(self.repo_name, selected_pair)
            print(f"Successfully loaded {len(self.data)} rows")
            
            # Update views
            self.update_summary()
            self.update_data_view()
            self.update_chart()
        except Exception as e:
            print(f"Error loading data for {selected_pair}: {str(e)}")
            messagebox.showerror("Error", f"Error loading data for {selected_pair}: {str(e)}")
    
    def update_summary(self):
        """Update summary information"""
        if self.data is None:
            return
        
        # Enable text widgets for editing
        self.summary_text.config(state=tk.NORMAL)
        self.stats_text.config(state=tk.NORMAL)
        
        # Clear text widgets
        self.summary_text.delete(1.0, tk.END)
        self.stats_text.delete(1.0, tk.END)
        
        # Add repository info
        if self.repo_type == 'price':
            repo_config = self.repo_manager.repositories['price'][self.repo_name]
            self.summary_text.insert(tk.END, f"Repository Name: {self.repo_name}\n")
            self.summary_text.insert(tk.END, f"Type: Price Data\n")
            self.summary_text.insert(tk.END, f"Directory: {repo_config['directory']}\n")
            self.summary_text.insert(tk.END, f"Format: {repo_config.get('format', 'csv')}\n")
            self.summary_text.insert(tk.END, f"Last Updated: {repo_config.get('last_updated', 'Unknown')}\n")
            self.summary_text.insert(tk.END, f"Current Pair: {self.pair_var.get()}\n")
            self.summary_text.insert(tk.END, f"Available Pairs: {', '.join(self.available_pairs)}\n")
            
            # Add data format info
            if hasattr(self, 'data_format') and self.data_format:
                if self.data_format == "bid_ask":
                    self.summary_text.insert(tk.END, f"Data Format: Bid/Ask format (includes both Bid and Ask prices)\n")
                    # Show price type selection in chart tab
                    if hasattr(self, 'price_type_frame'):
                        self.price_type_frame.pack(side=tk.LEFT, padx=10)
                elif self.data_format == "ohlc":
                    self.summary_text.insert(tk.END, f"Data Format: Standard OHLC format\n")
                    # Hide price type selection
                    if hasattr(self, 'price_type_frame'):
                        self.price_type_frame.pack_forget()
                elif self.data_format == "normalized":
                    self.summary_text.insert(tk.END, f"Data Format: Normalized OHLC format\n")
                    # Hide price type selection
                    if hasattr(self, 'price_type_frame'):
                        self.price_type_frame.pack_forget()
        else:
            repo_config = self.repo_manager.repositories['macro'][self.repo_name]
            self.summary_text.insert(tk.END, f"Repository Name: {self.repo_name}\n")
            self.summary_text.insert(tk.END, f"Type: Macroeconomic Data\n")
            self.summary_text.insert(tk.END, f"Directory: {repo_config['directory']}\n")
            self.summary_text.insert(tk.END, f"Format: {repo_config.get('format', 'csv')}\n")
            self.summary_text.insert(tk.END, f"Last Updated: {repo_config.get('last_updated', 'Unknown')}\n")
            self.summary_text.insert(tk.END, f"Available Indicators: {len(self.data.columns)}\n")
        
        # Add data statistics
        self.stats_text.insert(tk.END, f"Total Rows: {len(self.data)}\n")
        self.stats_text.insert(tk.END, f"Total Columns: {len(self.data.columns)}\n")
        
        # Handle index min/max safely
        try:
            min_date = self.data.index.min()
            max_date = self.data.index.max()
            self.stats_text.insert(tk.END, f"Date Range: {min_date} to {max_date}\n")
        except Exception as e:
            self.stats_text.insert(tk.END, f"Date Range: Could not determine ({str(e)})\n")
        
        # Add column statistics if not too many columns
        if len(self.data.columns) <= 20:  # Limit to avoid overwhelming display
            self.stats_text.insert(tk.END, "\nColumn Statistics:\n")
            
            # Use a set to track columns we've already processed to avoid duplicates
            processed_columns = set()
            
            for col in self.data.columns:
                # Skip duplicate columns
                if col in processed_columns:
                    continue
                processed_columns.add(col)
                
                self.stats_text.insert(tk.END, f"\n{col}:\n")
                
                # Only process numeric columns for statistics
                if pd.api.types.is_numeric_dtype(self.data[col]):
                    try:
                        # Get the data as a numpy array, removing NaN values
                        values = self.data[col].dropna().values
                        
                        if len(values) > 0:
                            # Calculate statistics using numpy directly to avoid pandas formatting issues
                            min_val = np.min(values)
                            max_val = np.max(values)
                            mean_val = np.mean(values)
                            std_val = np.std(values)
                            
                            # Format using Python's string formatting
                            self.stats_text.insert(tk.END, f"  Min: {min_val:.4f}\n")
                            self.stats_text.insert(tk.END, f"  Max: {max_val:.4f}\n")
                            self.stats_text.insert(tk.END, f"  Mean: {mean_val:.4f}\n")
                            self.stats_text.insert(tk.END, f"  Std Dev: {std_val:.4f}\n")
                        else:
                            self.stats_text.insert(tk.END, "  No valid numeric data to calculate statistics\n")
                    except Exception as e:
                        print(f"Error calculating statistics for column {col}: {e}")
                        self.stats_text.insert(tk.END, f"  Could not calculate statistics: {str(e)}\n")
                else:
                    self.stats_text.insert(tk.END, "  Non-numeric column (no statistics available)\n")
                
                # Count missing values (this should work for any column type)
                try:
                    missing = self.data[col].isna().sum()
                    total = len(self.data)
                    if total > 0:
                        pct = (missing / total) * 100
                        self.stats_text.insert(tk.END, f"  Missing Values: {missing} ({pct:.1f}%)\n")
                    else:
                        self.stats_text.insert(tk.END, "  Missing Values: N/A (empty column)\n")
                except Exception as e:
                    print(f"Error calculating missing values for column {col}: {e}")
                    self.stats_text.insert(tk.END, f"  Could not calculate missing values: {str(e)}\n")
        
        # Disable text widgets again
        self.summary_text.config(state=tk.DISABLED)
        self.stats_text.config(state=tk.DISABLED)
    
    def update_data_view(self, event=None):
        """Update data table view"""
        if self.data is None:
            return
        
        # Clear existing tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Reset columns
        self.tree['columns'] = ['index'] + list(self.data.columns)
        
        # Configure column headings
        self.tree.column('index', width=150, anchor='w')
        self.tree.heading('index', text='Date/Time')
        
        for col in self.data.columns:
            self.tree.column(col, width=100, anchor='e')
            self.tree.heading(col, text=col)
        
        # Determine number of rows to display
        rows_str = self.rows_var.get()
        if rows_str == 'All':
            rows_to_display = len(self.data)
        else:
            rows_to_display = min(int(rows_str), len(self.data))
        
        # Insert data rows
        for i, (idx, row) in enumerate(self.data.head(rows_to_display).iterrows()):
            values = [idx.strftime('%Y-%m-%d %H:%M:%S')] + [f"{v:.4f}" if isinstance(v, float) else v for v in row]
            self.tree.insert("", tk.END, values=values)
    
    def update_chart(self, event=None):
        """Update chart view"""
        if self.data is None:
            print("No data available for charting")
            return
        
        print(f"Updating chart view with chart type: {self.chart_type_var.get()}")
        
        # Clear existing chart
        for widget in self.chart_container.winfo_children():
            widget.destroy()
        
        chart_type = self.chart_type_var.get()
        
        try:
            if self.repo_type == 'price':
                # Get price type for title display
                price_type = ""
                if hasattr(self, 'data_format') and self.data_format == "bid_ask":
                    price_type = f" ({self.price_type_var.get()})"
                
                chart_title = f"{self.pair_var.get()}{price_type} Price Chart"
                print(f"Creating price chart: {chart_title}")
                
                fig, ax = plt.subplots(figsize=(10, 6))
                
                if chart_type == 'Line':
                    print("Generating line chart")
                    # Ensure we have 'close' column
                    if 'close' in self.data.columns:
                        ax.plot(self.data.index, self.data['close'], label='Close')
                    else:
                        print("Warning: 'close' column not found")
                        error_label = ttk.Label(self.chart_container, 
                                              text="Error: Required columns not found for this chart type")
                        error_label.pack(expand=True)
                        return
                        
                elif chart_type == 'Candlestick':
                    print("Generating candlestick chart")
                    # Import mplfinance for candlestick charts
                    try:
                        import mplfinance as mpf
                        # Create a new figure for mplfinance
                        fig.clear()
                        plt.close(fig)
                        
                        # Make sure we have all required columns
                        required_columns = ['open', 'high', 'low', 'close']
                        if not all(col in self.data.columns for col in required_columns):
                            print(f"Missing required columns. Available: {self.data.columns}")
                            error_label = ttk.Label(self.chart_container, 
                                                 text="Error: Missing required OHLC columns for candlestick chart")
                            error_label.pack(expand=True)
                            return
                        
                        # Prepare data in OHLC format mplfinance expects
                        ohlc_data = self.data[required_columns].copy()
                        
                        # Make sure the index is datetime
                        if not isinstance(ohlc_data.index, pd.DatetimeIndex):
                            print("Converting index to DatetimeIndex")
                            ohlc_data.index = pd.to_datetime(ohlc_data.index)
                        
                        # Use mplfinance to create candlestick chart
                        mpf_fig, axlist = mpf.plot(
                            ohlc_data, 
                            type='candle', 
                            style='yahoo',
                            title=chart_title,
                            ylabel='Price',
                            returnfig=True
                        )
                        
                        # Embed in UI
                        canvas = FigureCanvasTkAgg(mpf_fig, master=self.chart_container)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        
                        # Add toolbar
                        toolbar_frame = ttk.Frame(self.chart_container)
                        toolbar_frame.pack(fill=tk.X)
                        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                        toolbar.update()
                        
                        print("Candlestick chart created successfully")
                        return
                    except ImportError:
                        print("mplfinance package not available, falling back to line chart")
                        # Create installation instructions
                        info_frame = ttk.Frame(self.chart_container)
                        info_frame.pack(fill=tk.X, pady=5)
                        ttk.Label(info_frame, text="For candlestick charts, install mplfinance package:").pack(anchor=tk.W)
                        ttk.Label(info_frame, text="pip install mplfinance", font=("Courier", 10)).pack(anchor=tk.W, padx=10)
                        
                        # Fallback to basic plot
                        if 'close' in self.data.columns:
                            ax.plot(self.data.index, self.data['close'], label='Close')
                            ax.set_title(f"{chart_title} (Candlestick view requires mplfinance)")
                        else:
                            error_label = ttk.Label(self.chart_container, 
                                                  text="Error: Required columns not found for this chart type")
                            error_label.pack(expand=True)
                            return
                            
                elif chart_type == 'OHLC':
                    print("Generating OHLC chart")
                    # Try to use mplfinance for OHLC
                    try:
                        import mplfinance as mpf
                        # Create a new figure for mplfinance
                        fig.clear()
                        plt.close(fig)
                        
                        # Make sure we have all required columns
                        required_columns = ['open', 'high', 'low', 'close']
                        if not all(col in self.data.columns for col in required_columns):
                            print(f"Missing required columns. Available: {self.data.columns}")
                            error_label = ttk.Label(self.chart_container, 
                                                 text="Error: Missing required OHLC columns for OHLC chart")
                            error_label.pack(expand=True)
                            return
                        
                        # Prepare data in OHLC format
                        ohlc_data = self.data[required_columns].copy()
                        
                        # Make sure the index is datetime
                        if not isinstance(ohlc_data.index, pd.DatetimeIndex):
                            print("Converting index to DatetimeIndex")
                            ohlc_data.index = pd.to_datetime(ohlc_data.index)
                        
                        # Use mplfinance to create OHLC chart
                        mpf_fig, axlist = mpf.plot(
                            ohlc_data, 
                            type='ohlc', 
                            style='yahoo',
                            title=chart_title,
                            ylabel='Price',
                            returnfig=True
                        )
                        
                        # Embed in UI
                        canvas = FigureCanvasTkAgg(mpf_fig, master=self.chart_container)
                        canvas.draw()
                        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
                        
                        # Add toolbar
                        toolbar_frame = ttk.Frame(self.chart_container)
                        toolbar_frame.pack(fill=tk.X)
                        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
                        toolbar.update()
                        
                        print("OHLC chart created successfully")
                        return
                    except ImportError:
                        print("mplfinance package not available, falling back to basic OHLC")
                        # Create installation instructions
                        info_frame = ttk.Frame(self.chart_container)
                        info_frame.pack(fill=tk.X, pady=5)
                        ttk.Label(info_frame, text="For better OHLC charts, install mplfinance package:").pack(anchor=tk.W)
                        ttk.Label(info_frame, text="pip install mplfinance", font=("Courier", 10)).pack(anchor=tk.W, padx=10)
                        
                        # Make sure we have all required columns
                        required_columns = ['open', 'high', 'low', 'close']
                        if not all(col in self.data.columns for col in required_columns):
                            print(f"Missing required columns. Available: {self.data.columns}")
                            error_label = ttk.Label(self.chart_container, 
                                                 text="Error: Missing required OHLC columns for OHLC chart")
                            error_label.pack(expand=True)
                            return
                        
                        # Create basic OHLC visualization
                        ax.plot(self.data.index, self.data['high'], color='green', alpha=0.5, label='High')
                        ax.plot(self.data.index, self.data['low'], color='red', alpha=0.5, label='Low')
                        ax.plot(self.data.index, self.data['open'], color='blue', label='Open')
                        ax.plot(self.data.index, self.data['close'], color='black', label='Close')
                
                ax.set_title(chart_title)
                ax.grid(True, alpha=0.3)
                ax.legend()
                
                # Additional data to display for bid/ask format
                if hasattr(self, 'data_format') and self.data_format == "bid_ask" and 'Spread' in self.data.columns:
                    # Add spread info
                    info_frame = ttk.Frame(self.chart_container)
                    info_frame.pack(fill=tk.X, pady=5, before=canvas.get_tk_widget())
                    
                    avg_spread = self.data['Spread'].mean()
                    max_spread = self.data['Spread'].max()
                    min_spread = self.data['Spread'].min()
                    
                    ttk.Label(info_frame, 
                            text=f"Spread Info: Avg: {avg_spread:.1f} | Min: {min_spread:.1f} | Max: {max_spread:.1f}",
                            font=("Helvetica", 10)).pack(anchor=tk.W, padx=10)
                
            elif self.repo_type == 'macro':
                # For macro data, plot selected column
                column = self.column_var.get()
                print(f"Creating macro chart for {column}")
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(self.data.index, self.data[column])
                ax.set_title(f"{column} Chart")
                ax.grid(True, alpha=0.3)
            
            # Configure date formatting
            ax.xaxis.set_major_formatter(DateFormatter('%Y-%m-%d'))
            plt.xticks(rotation=45)
            
            print("Embedding chart in UI")
            # Embed in UI
            canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
            canvas.draw()
            canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            
            # Add toolbar
            toolbar_frame = ttk.Frame(self.chart_container)
            toolbar_frame.pack(fill=tk.X)
            toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
            toolbar.update()
            print("Chart updated successfully")
            
        except Exception as e:
            print(f"Error creating chart: {str(e)}")
            error_label = ttk.Label(self.chart_container, 
                                   text=f"Error creating chart: {str(e)}")
            error_label.pack(expand=True)
    
    def validate_ohlc_data(self):
        """Special validation for OHLC data to help debug mplfinance issues"""
        if self.data is None:
            print("No data available for validation")
            return
        
        required_columns = ['open', 'high', 'low', 'close']
        
        # Enable text widget for editing
        self.validation_text.config(state=tk.NORMAL)
        self.validation_text.delete(1.0, tk.END)
        
        self.validation_text.insert(tk.END, f"OHLC Data Validation for mplfinance\n")
        self.validation_text.insert(tk.END, f"===============================\n\n")
        
        # Check if required columns exist
        missing_columns = [col for col in required_columns if col not in self.data.columns]
        if missing_columns:
            self.validation_text.insert(tk.END, f"❌ Missing required columns: {', '.join(missing_columns)}\n")
            self.validation_text.insert(tk.END, f"Available columns: {', '.join(self.data.columns)}\n\n")
            
            # Check for similar columns with different names
            for missing_col in missing_columns:
                similar_cols = [col for col in self.data.columns if missing_col.lower() in col.lower()]
                if similar_cols:
                    self.validation_text.insert(tk.END, f"Found similar columns to '{missing_col}': {', '.join(similar_cols)}\n")
            
            self.validation_text.insert(tk.END, "\nRecommendation: Rename columns or use detect_and_normalize_price_format()\n")
        else:
            self.validation_text.insert(tk.END, f"✓ All required OHLC columns are present\n\n")
            
            # Check column types
            self.validation_text.insert(tk.END, f"Column Types:\n")
            for col in required_columns:
                dtype = self.data[col].dtype
                is_numeric = pd.api.types.is_numeric_dtype(dtype)
                if is_numeric:
                    self.validation_text.insert(tk.END, f"✓ {col}: {dtype} (numeric)\n")
                else:
                    self.validation_text.insert(tk.END, f"❌ {col}: {dtype} (not numeric)\n")
                    
                    # Check for non-numeric values
                    non_numeric_count = pd.to_numeric(self.data[col], errors='coerce').isna().sum()
                    if non_numeric_count > 0:
                        self.validation_text.insert(tk.END, f"   Found {non_numeric_count} non-numeric values\n")
                        
                        # Show examples of non-numeric values
                        non_numeric_examples = self.data[pd.to_numeric(self.data[col], errors='coerce').isna()][col].head(3)
                        self.validation_text.insert(tk.END, f"   Examples: {', '.join(map(str, non_numeric_examples))}\n")
            
            # Check index
            self.validation_text.insert(tk.END, f"\nIndex Type: {type(self.data.index)}\n")
            if isinstance(self.data.index, pd.DatetimeIndex):
                self.validation_text.insert(tk.END, f"✓ Index is DatetimeIndex\n")
            else:
                self.validation_text.insert(tk.END, f"❌ Index is not DatetimeIndex\n")
            
            # Check for duplicate indices
            dup_count = self.data.index.duplicated().sum()
            if dup_count > 0:
                self.validation_text.insert(tk.END, f"❌ Found {dup_count} duplicate indices\n")
            else:
                self.validation_text.insert(tk.END, f"✓ No duplicate indices found\n")
            
            # Check for NaN values
            nan_counts = self.data[required_columns].isna().sum()
            total_nans = nan_counts.sum()
            if total_nans > 0:
                self.validation_text.insert(tk.END, f"\n❌ Found {total_nans} NaN values in OHLC columns:\n")
                for col, count in nan_counts.items():
                    if count > 0:
                        self.validation_text.insert(tk.END, f"   {col}: {count} NaN values\n")
            else:
                self.validation_text.insert(tk.END, f"\n✓ No NaN values found in OHLC columns\n")
            
            # Add recommendations
            self.validation_text.insert(tk.END, f"\nRecommendations for mplfinance:\n")
            if not all(pd.api.types.is_numeric_dtype(self.data[col].dtype) for col in required_columns):
                self.validation_text.insert(tk.END, f"- Convert all OHLC columns to numeric types\n")
            if not isinstance(self.data.index, pd.DatetimeIndex):
                self.validation_text.insert(tk.END, f"- Convert index to DatetimeIndex\n")
            if dup_count > 0:
                self.validation_text.insert(tk.END, f"- Remove duplicate indices\n")
            if total_nans > 0:
                self.validation_text.insert(tk.END, f"- Drop rows with NaN values\n")
            
            # Sample data before conversion
            self.validation_text.insert(tk.END, f"\nSample data (first 5 rows):\n")
            for i, (idx, row) in enumerate(self.data[required_columns].head(5).iterrows()):
                self.validation_text.insert(tk.END, f"{idx}: {dict(row)}\n")
            
            # Try converting and show the result
            self.validation_text.insert(tk.END, f"\nAttempting to convert data to mplfinance format...\n")
            try:
                ohlc_data = self.data[required_columns].copy()
                
                # Convert columns to numeric
                for col in required_columns:
                    ohlc_data[col] = pd.to_numeric(ohlc_data[col], errors='coerce')
                
                # Drop NaN values
                nan_count = ohlc_data.isna().sum().sum()
                if nan_count > 0:
                    pre_drop_len = len(ohlc_data)
                    ohlc_data.dropna(inplace=True)
                    post_drop_len = len(ohlc_data)
                    self.validation_text.insert(tk.END, f"Dropped {pre_drop_len - post_drop_len} rows with NaN values\n")
                
                # Convert index if needed
                if not isinstance(ohlc_data.index, pd.DatetimeIndex):
                    ohlc_data.index = pd.to_datetime(ohlc_data.index)
                    self.validation_text.insert(tk.END, f"Converted index to DatetimeIndex\n")
                
                # Remove duplicates
                dup_count = ohlc_data.index.duplicated().sum()
                if dup_count > 0:
                    pre_drop_len = len(ohlc_data)
                    ohlc_data = ohlc_data[~ohlc_data.index.duplicated()]
                    post_drop_len = len(ohlc_data)
                    self.validation_text.insert(tk.END, f"Removed {pre_drop_len - post_drop_len} duplicate indices\n")
                
                # Show final sample
                self.validation_text.insert(tk.END, f"\nConverted data (first 5 rows):\n")
                for i, (idx, row) in enumerate(ohlc_data.head(5).iterrows()):
                    self.validation_text.insert(tk.END, f"{idx}: {dict(row)}\n")
                
                # Check if data is suitable for mplfinance
                is_valid = True
                for col in required_columns:
                    if not pd.api.types.is_numeric_dtype(ohlc_data[col].dtype):
                        is_valid = False
                        self.validation_text.insert(tk.END, f"\n❌ Column {col} is still not numeric after conversion\n")
                
                if is_valid:
                    self.validation_text.insert(tk.END, f"\n✓ Data should now be compatible with mplfinance\n")
                    
                    # Test creating a small sample figure with mplfinance
                    try:
                        import mplfinance as mpf
                        self.validation_text.insert(tk.END, f"Testing with mplfinance...\n")
                        
                        # Try with just 50 rows to keep it simple
                        test_data = ohlc_data.head(50)
                        mpf.plot(test_data, type='candle', style='yahoo', returnfig=True)
                        
                        self.validation_text.insert(tk.END, f"✓ Successfully created test chart with mplfinance!\n")
                    except ImportError:
                        self.validation_text.insert(tk.END, f"⚠️ Could not test with mplfinance: Package not installed\n")
                    except Exception as e:
                        self.validation_text.insert(tk.END, f"❌ Error when testing with mplfinance: {str(e)}\n")
                        
            except Exception as e:
                self.validation_text.insert(tk.END, f"❌ Error during conversion: {str(e)}\n")
        
        # Disable text widget again
        self.validation_text.config(state=tk.DISABLED)
        
    def run_validation(self):
        """Run data validation check"""
        if self.data is None:
            print("No data available for validation")
            return
        
        validation_type = self.validation_type_var.get()
        print(f"Running data validation: {validation_type}")
        
        # Enable text widget for editing
        self.validation_text.config(state=tk.NORMAL)
        self.validation_text.delete(1.0, tk.END)
        
        try:
            if validation_type == "Missing Values":
                print("Checking for missing values")
                self.check_missing_values()
            elif validation_type == "Outliers":
                print("Checking for outliers")
                self.check_outliers()
            elif validation_type == "Duplicates":
                print("Checking for duplicates")
                self.check_duplicates()
            elif validation_type == "Gaps":
                print("Checking for time gaps")
                self.check_time_gaps()
            elif validation_type == "Data Types":
                print("Checking data types")
                self.check_data_types()
            
            print("Validation completed")
        except Exception as e:
            print(f"Error during validation: {str(e)}")
            print(f"Error traceback: {traceback.format_exc()}")
            self.validation_text.insert(tk.END, f"Error during validation: {str(e)}\n")
        
        # Disable text widget again
        self.validation_text.config(state=tk.DISABLED)
        
    def check_data_types(self):
        """Check data types in the dataset"""
        self.validation_text.insert(tk.END, f"Data Type Check\n")
        self.validation_text.insert(tk.END, f"==============\n\n")
        
        self.validation_text.insert(tk.END, f"Column Types:\n")
        for col in self.data.columns:
            dtype = self.data[col].dtype
            sample = str(self.data[col].iloc[0] if len(self.data) > 0 else "N/A")
            if len(sample) > 30:
                sample = sample[:30] + "..."
            
            is_numeric = pd.api.types.is_numeric_dtype(dtype)
            is_datetime = pd.api.types.is_datetime64_any_dtype(dtype)
            
            if is_numeric:
                self.validation_text.insert(tk.END, f"✓ {col}: {dtype} (numeric)\n")
                self.validation_text.insert(tk.END, f"   Sample: {sample}\n")
            elif is_datetime:
                self.validation_text.insert(tk.END, f"✓ {col}: {dtype} (datetime)\n")
                self.validation_text.insert(tk.END, f"   Sample: {sample}\n")
            else:
                self.validation_text.insert(tk.END, f"ℹ️ {col}: {dtype} (not numeric or datetime)\n")
                self.validation_text.insert(tk.END, f"   Sample: {sample}\n")
                
                # Check for potential numeric values stored as strings
                if dtype == 'object':
                    numeric_conversion = pd.to_numeric(self.data[col], errors='coerce')
                    non_numeric = numeric_conversion.isna().sum()
                    
                    if non_numeric == 0:
                        self.validation_text.insert(tk.END, f"   ⚠️ Column appears to contain only numeric values stored as strings\n")
                    elif non_numeric < len(self.data):
                        self.validation_text.insert(tk.END, f"   ⚠️ Column contains {len(self.data) - non_numeric} numeric values and {non_numeric} non-numeric values\n")
        
        # Check index
        idx_type = type(self.data.index)
        self.validation_text.insert(tk.END, f"\nIndex Type: {idx_type}\n")
        
        if isinstance(self.data.index, pd.DatetimeIndex):
            self.validation_text.insert(tk.END, f"✓ Index is DatetimeIndex\n")
        elif pd.api.types.is_numeric_dtype(self.data.index.dtype):
            self.validation_text.insert(tk.END, f"ℹ️ Index is numeric\n")
        else:
            self.validation_text.insert(tk.END, f"ℹ️ Index is not DatetimeIndex or numeric\n")
            # Check if it could be converted to datetime
            try:
                pd.to_datetime(self.data.index)
                self.validation_text.insert(tk.END, f"   ⚠️ Index could be converted to DatetimeIndex\n")
            except:
                self.validation_text.insert(tk.END, f"   ❌ Index cannot be converted to DatetimeIndex\n")
    
    def check_missing_values(self):
        """Check for missing values in the data"""
        print("Starting missing values analysis")
        missing = self.data.isna().sum()
        total_missing = missing.sum()
        
        self.validation_text.insert(tk.END, f"Missing Values Check\n")
        self.validation_text.insert(tk.END, f"===================\n\n")
        
        if total_missing == 0:
            print("No missing values found")
            self.validation_text.insert(tk.END, "✓ No missing values found in the dataset.\n")
            return
        
        print(f"Found {total_missing} missing values")
        self.validation_text.insert(tk.END, f"❌ Found {total_missing} missing values in the dataset.\n\n")
        self.validation_text.insert(tk.END, "Breakdown by column:\n")
        
        for col, count in missing.items():
            if count > 0:
                percentage = count / len(self.data) * 100
                print(f"Column {col}: {count} missing values ({percentage:.1f}%)")
                self.validation_text.insert(tk.END, f"  {col}: {count} missing values ({percentage:.1f}%)\n")
        
        # Add recommendation
        self.validation_text.insert(tk.END, "\nRecommendation:\n")
        self.validation_text.insert(tk.END, "- For price data, consider using forward fill ('ffill') to handle missing values\n")
        self.validation_text.insert(tk.END, "- For macro data, consider using interpolation methods\n")
        self.validation_text.insert(tk.END, "- For gaps in time series, ensure proper reindexing\n")
    
    def check_outliers(self):
        """Check for outliers in the data"""
        print("Starting outlier detection analysis")
        self.validation_text.insert(tk.END, f"Outlier Detection\n")
        self.validation_text.insert(tk.END, f"================\n\n")
        
        outliers_found = False
        
        for col in self.data.select_dtypes(include=[np.number]).columns:
            # Skip columns that are clearly not appropriate for outlier detection
            if col in ['volume', 'pip_factor']:
                continue
                
            try:
                # Make sure we have valid numeric data for z-score calculation
                series = self.data[col].copy()
                series = series.replace([np.inf, -np.inf], np.nan).dropna()
                
                if len(series) == 0:
                    self.validation_text.insert(tk.END, f"⚠️ {col}: No valid numeric data for outlier detection\n")
                    continue
                
                # Calculate mean and std safely
                mean_val = float(series.mean())
                std_val = float(series.std())
                
                # Skip if std is 0 (no variation) or very small
                if std_val < 1e-10:
                    self.validation_text.insert(tk.END, f"⚠️ {col}: No variation in data (std ≈ 0)\n")
                    continue
                
                # Use Z-score method to detect outliers
                z_scores = np.abs((series - mean_val) / std_val)
                outliers = z_scores > 3  # Z-score > 3 standard deviations
                
                outlier_count = outliers.sum()
                if outlier_count > 0:
                    outliers_found = True
                    percentage = outlier_count / len(series) * 100
                    print(f"Found {outlier_count} outliers in {col} ({percentage:.1f}%)")
                    self.validation_text.insert(tk.END, f"❌ {col}: {outlier_count} potential outliers ({percentage:.1f}%)\n")
                    
                    # Show some example outliers
                    if outlier_count > 0:
                        self.validation_text.insert(tk.END, "  Examples:\n")
                        outlier_indices = series.index[outliers]
                        for idx in outlier_indices[:3]:  # Show up to 3 examples
                            value = float(series.loc[idx])
                            self.validation_text.insert(tk.END, f"    {idx}: {value:.4f}\n")
            except Exception as e:
                print(f"Error in outlier detection for column {col}: {e}")
                self.validation_text.insert(tk.END, f"⚠️ {col}: Error in outlier detection: {str(e)}\n")
        
        if not outliers_found:
            self.validation_text.insert(tk.END, "✓ No significant outliers detected using Z-score method.\n")
        
        # Add recommendation
        self.validation_text.insert(tk.END, "\nRecommendation:\n")
        self.validation_text.insert(tk.END, "- Investigate potential outliers to determine if they are data errors\n")
        self.validation_text.insert(tk.END, "- For price data, outliers may represent market gaps or extreme moves\n")
        self.validation_text.insert(tk.END, "- Consider using winsorization or capping methods if appropriate\n")
    
    def check_duplicates(self):
        """Check for duplicate timestamps in the data"""
        self.validation_text.insert(tk.END, f"Duplicate Detection\n")
        self.validation_text.insert(tk.END, f"===================\n\n")
        
        # Check for duplicate indices
        duplicate_indices = self.data.index.duplicated()
        duplicate_count = duplicate_indices.sum()
        
        if duplicate_count == 0:
            self.validation_text.insert(tk.END, "✓ No duplicate timestamps found in the dataset.\n")
        else:
            self.validation_text.insert(tk.END, f"❌ Found {duplicate_count} duplicate timestamps in the dataset.\n\n")
            
            # Show examples
            self.validation_text.insert(tk.END, "Examples of duplicates:\n")
            duplicated_times = self.data.index[duplicate_indices]
            for idx in duplicated_times[:5]:  # Show up to 5 examples
                self.validation_text.insert(tk.END, f"  {idx}\n")
            
            # Add recommendation
            self.validation_text.insert(tk.END, "\nRecommendation:\n")
            self.validation_text.insert(tk.END, "- Keep only the first or last occurrence of each timestamp\n")
            self.validation_text.insert(tk.END, "- Investigate why duplicates exist (data quality issue)\n")
    
    def check_time_gaps(self):
        """Check for gaps in time series data"""
        self.validation_text.insert(tk.END, f"Time Series Gap Detection\n")
        self.validation_text.insert(tk.END, f"=======================\n\n")
        
        # Determine expected frequency
        freq = self._detect_frequency()
        
        if not freq:
            self.validation_text.insert(tk.END, "❓ Could not determine the time series frequency.\n")
            return
        
        self.validation_text.insert(tk.END, f"Detected frequency: {freq}\n\n")
        
        # Create a complete time index
        if freq == 'business day' or freq == 'day':
            freq = 'B' if freq == 'business day' else 'D'
            expected_index = pd.date_range(start=self.data.index.min(), end=self.data.index.max(), freq=freq)
        elif freq in ['hour', 'minute']:
            # For higher frequency data, check consecutive differences
            time_diffs = self.data.index.to_series().diff().dropna()
            most_common_diff = time_diffs.mode()[0]
            self.validation_text.insert(tk.END, f"Most common time difference: {most_common_diff}\n\n")
            
            # Check if there are any gaps larger than the most common difference
            large_gaps = time_diffs[time_diffs > most_common_diff * 2]
            if len(large_gaps) > 0:
                self.validation_text.insert(tk.END, f"❌ Found {len(large_gaps)} large gaps in the time series.\n\n")
                
                # Show examples
                self.validation_text.insert(tk.END, "Examples of large gaps:\n")
                for i, (idx, gap) in enumerate(large_gaps.items()):
                    if i >= 5:  # Limit to 5 examples
                        break
                    prev_idx = self.data.index[self.data.index.get_loc(idx) - 1]
                    self.validation_text.insert(tk.END, f"  Gap of {gap} between {prev_idx} and {idx}\n")
            else:
                self.validation_text.insert(tk.END, "✓ No significant gaps found in the time series.\n")
            
            return
        
        # Check for missing dates in the expected index
        missing_dates = expected_index.difference(self.data.index)
        
        if len(missing_dates) == 0:
            self.validation_text.insert(tk.END, "✓ No gaps found in the time series.\n")
        else:
            self.validation_text.insert(tk.END, f"❌ Found {len(missing_dates)} missing dates in the time series.\n\n")
            
            # Group missing dates into ranges
            ranges = []
            current_range = []
            
            for date in missing_dates:
                if not current_range or (date - current_range[-1]).days == 1:
                    current_range.append(date)
                else:
                    ranges.append(current_range)
                    current_range = [date]
            
            if current_range:
                ranges.append(current_range)
            
            # Show examples of gaps
            self.validation_text.insert(tk.END, "Examples of gaps:\n")
            for i, date_range in enumerate(ranges):
                if i >= 5:  # Limit to 5 examples
                    break
                if len(date_range) == 1:
                    self.validation_text.insert(tk.END, f"  Missing: {date_range[0]}\n")
                else:
                    self.validation_text.insert(tk.END, f"  Missing range: {date_range[0]} to {date_range[-1]} ({len(date_range)} days)\n")
        
        # Add recommendation
        self.validation_text.insert(tk.END, "\nRecommendation:\n")
        self.validation_text.insert(tk.END, "- For price data, consider reindexing and filling gaps appropriately\n")
        self.validation_text.insert(tk.END, "- For macro data, consider using a lower frequency or interpolation\n")
    
    def _detect_frequency(self):
        """Attempt to detect the time series frequency"""
        # Calculate time differences
        time_diffs = self.data.index.to_series().diff().dropna()
        
        # Check most common difference
        try:
            most_common = time_diffs.mode()[0]
            
            if most_common.days == 0:
                # Hourly or minute data
                if most_common.seconds == 3600:
                    return 'hour'
                elif most_common.seconds in [60, 300, 900, 1800]:
                    return 'minute'
            elif most_common.days == 1:
                return 'day'
            elif most_common.days >= 1 and most_common.days <= 3:
                # Check if weekdays only
                weekdays = [idx.weekday() < 5 for idx in self.data.index]
                if all(weekdays):
                    return 'business day'
                else:
                    return 'day'
            elif most_common.days >= 28 and most_common.days <= 31:
                return 'month'
        except:
            pass
        
        return None