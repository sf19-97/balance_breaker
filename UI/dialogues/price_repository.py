"""
Price repository dialog for Balance Breaker
Handles price data repository configuration
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import numpy as np
import os
import traceback
from datetime import datetime

from .repository_base import RepositoryDialog

class PriceRepositoryDialog(RepositoryDialog):
    """Enhanced dialog for price data repository configuration"""
    def __init__(self, parent, repo_manager, on_save=None, edit_repo=None):
        self.edit_repo = edit_repo  # Repository name if editing existing
        self.detected_format = None  # To store detected file format
        self.sample_data = None     # To store sample data for preview
        self.sample_file_path = None  # Path to the current sample file
        super().__init__(parent, repo_manager, "price", on_save)
    
    def create_dialog_content(self, parent_frame):
        """Create price repository dialog content with enhanced features"""
        # Repository name
        name_frame = ttk.Frame(parent_frame)
        name_frame.pack(fill=tk.X, padx=0, pady=5)
        ttk.Label(name_frame, text="Repository Name:").pack(side=tk.LEFT)
        self.name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.name_var, width=30).pack(side=tk.LEFT, padx=5)
        
        # Directory selection
        dir_frame = ttk.Frame(parent_frame)
        dir_frame.pack(fill=tk.X, padx=0, pady=5)
        ttk.Label(dir_frame, text="Data Directory:").pack(side=tk.LEFT)
        self.dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.dir_var, width=40).pack(side=tk.LEFT, padx=5)
        ttk.Button(dir_frame, text="Browse...", 
                  command=self.browse_directory).pack(side=tk.LEFT)
        
        # Create a notebook for tabs
        notebook = ttk.Notebook(parent_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)
        
        # Tab 1: Basic Configuration
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Configuration")
        
        # File format selection
        format_frame = ttk.LabelFrame(basic_frame, text="File Format")
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV Files", variable=self.format_var, value="csv").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="Excel Files", variable=self.format_var, value="excel").pack(anchor=tk.W)
        
        # Detected format display with more detailed info
        format_detail_frame = ttk.Frame(format_frame)
        format_detail_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(format_detail_frame, text="Detected Format:").grid(row=0, column=0, sticky=tk.W)
        self.format_detect_var = tk.StringVar(value="Not detected yet")
        ttk.Label(format_detail_frame, textvariable=self.format_detect_var).grid(row=0, column=1, sticky=tk.W)
        
        ttk.Label(format_detail_frame, text="Found Files:").grid(row=1, column=0, sticky=tk.W)
        self.found_files_var = tk.StringVar(value="None")
        ttk.Label(format_detail_frame, textvariable=self.found_files_var).grid(row=1, column=1, sticky=tk.W)
        
        ttk.Label(format_detail_frame, text="Sample File:").grid(row=2, column=0, sticky=tk.W)
        self.sample_file_var = tk.StringVar(value="None")
        ttk.Label(format_detail_frame, textvariable=self.sample_file_var).grid(row=2, column=1, sticky=tk.W)
        
        # Action buttons
        action_frame = ttk.Frame(basic_frame)
        action_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(action_frame, text="Scan Directory", 
                  command=self.scan_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Test Connection", 
                  command=self.test_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Load Sample", 
                  command=self.load_sample_file).pack(side=tk.LEFT, padx=5)
        
        # Tab 2: Column Mapping
        mapping_frame = ttk.Frame(notebook)
        notebook.add(mapping_frame, text="Column Mapping")
        
        # Column mapping with preview of actual values
        mapping_config_frame = ttk.LabelFrame(mapping_frame, text="Column Mapping")
        mapping_config_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.column_vars = {}
        self.column_preview_vars = {}
        standard_columns = [
            ("date/time", "DateTime/Date column for index"),
            ("open", "Opening price column"),
            ("high", "Highest price column"),
            ("low", "Lowest price column"),
            ("close", "Closing price column"),
            ("volume", "Volume column (optional)")
        ]
        
        # Create a scrollable frame for column mappings
        mapping_canvas = tk.Canvas(mapping_config_frame)
        scrollbar = ttk.Scrollbar(mapping_config_frame, orient=tk.VERTICAL, command=mapping_canvas.yview)
        scrollable_frame = ttk.Frame(mapping_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: mapping_canvas.configure(scrollregion=mapping_canvas.bbox("all"))
        )
        
        mapping_canvas.create_window((0, 0), window=scrollable_frame, anchor=tk.NW)
        mapping_canvas.configure(yscrollcommand=scrollbar.set)
        
        mapping_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Column headers
        ttk.Label(scrollable_frame, text="Standard Name", font=('', 10, 'bold')).grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        ttk.Label(scrollable_frame, text="File Column", font=('', 10, 'bold')).grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        ttk.Label(scrollable_frame, text="Description", font=('', 10, 'bold')).grid(row=0, column=2, padx=5, pady=2, sticky=tk.W)
        ttk.Label(scrollable_frame, text="Sample Value", font=('', 10, 'bold')).grid(row=0, column=3, padx=5, pady=2, sticky=tk.W)
        
        for i, (col, desc) in enumerate(standard_columns, 1):
            ttk.Label(scrollable_frame, text=col).grid(row=i, column=0, padx=5, pady=2, sticky=tk.W)
            
            col_var = tk.StringVar(value=col.lower())
            self.column_vars[col.lower()] = col_var
            ttk.Entry(scrollable_frame, textvariable=col_var, width=20).grid(row=i, column=1, padx=5, pady=2, sticky=tk.W)
            
            ttk.Label(scrollable_frame, text=desc).grid(row=i, column=2, padx=5, pady=2, sticky=tk.W)
            
            preview_var = tk.StringVar(value="")
            self.column_preview_vars[col.lower()] = preview_var
            ttk.Label(scrollable_frame, textvariable=preview_var, width=20).grid(row=i, column=3, padx=5, pady=2, sticky=tk.W)
        
        # Auto-detect button for columns with improved UI feedback
        ttk.Button(mapping_frame, text="Auto-detect Columns", 
                  command=self.auto_detect_columns).pack(anchor=tk.W, padx=5, pady=5)
        
        # Tab 3: Data Preview
        preview_frame = ttk.Frame(notebook)
        notebook.add(preview_frame, text="Data Preview")
        
        # Sample data preview area
        preview_controls = ttk.Frame(preview_frame)
        preview_controls.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(preview_controls, text="Preview Rows:").pack(side=tk.LEFT, padx=5)
        self.preview_rows_var = tk.StringVar(value="10")
        ttk.Combobox(preview_controls, textvariable=self.preview_rows_var, 
                    values=["5", "10", "20", "50"], width=5).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(preview_controls, text="Refresh Preview", 
                  command=self.refresh_preview).pack(side=tk.LEFT, padx=5)
        
        # Create preview area
        self.preview_frame = ttk.Frame(preview_frame)
        self.preview_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Fill with existing data if editing
        if self.edit_repo:
            self.load_existing_config()
    
    def browse_directory(self):
        """Browse for data directory"""
        directory = filedialog.askdirectory(title="Select Data Directory")
        if directory:
            self.dir_var.set(directory)
            self.update_status(f"Selected directory: {directory}")
            # Auto-scan the directory after selection
            self.scan_directory()
    
    def scan_directory(self):
        """Scan directory for price data files"""
        directory = self.dir_var.get()
        if not directory or not os.path.isdir(directory):
            self.update_status("Please select a valid directory first", is_error=True)
            return
            
        self.update_status(f"Scanning directory: {directory}...")
        
        try:
            # Get file list
            format_type = self.format_var.get()
            extensions = {
                'csv': ['.csv', '.CSV', '.txt', '.TXT'],
                'excel': ['.xlsx', '.xls', '.XLSX', '.XLS']
            }
            
            file_extensions = extensions.get(format_type, ['.csv', '.CSV'])
            
            # Find all matching files
            found_files = []
            detected_pairs = set()
            
            # Common pairs to look for
            common_pairs = ['USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD']
            
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                        file_path = os.path.join(root, file)
                        found_files.append(file_path)
                        
                        # Try to detect currency pair from filename
                        for pair in common_pairs:
                            if pair.lower() in file.lower():
                                detected_pairs.add(pair)
                                break
            
            if not found_files:
                self.update_status(f"No {format_type} files found in directory", is_error=True)
                return
            
            # Update UI with results
            self.found_files_var.set(f"{len(found_files)} files found")
            if detected_pairs:
                self.update_status(f"Found {len(found_files)} files with {len(detected_pairs)} currency pairs")
            else:
                self.update_status(f"Found {len(found_files)} files, but couldn't detect currency pairs")
            
            # Try to load the first file as sample
            if found_files:
                self.sample_file_path = found_files[0]
                self.sample_file_var.set(os.path.basename(self.sample_file_path))
                self.load_sample_file()
        
        except Exception as e:
            error_msg = f"Error scanning directory: {str(e)}"
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def load_sample_file(self):
        """Load a sample file for column detection and preview"""
        if not self.sample_file_path:
            self.update_status("No sample file available", is_error=True)
            return
        
        try:
            self.update_status(f"Loading sample file: {os.path.basename(self.sample_file_path)}...")
            
            # Determine file type from extension
            format_type = self.format_var.get()
            
            # Try multiple approaches to load the file
            try:
                # Approach 1: Standard read with auto index detection
                if format_type == 'csv':
                    self.sample_data = pd.read_csv(self.sample_file_path)
                else:
                    self.sample_data = pd.read_excel(self.sample_file_path)
                
                # Check if we found a date/time column to use as index
                date_cols = [col for col in self.sample_data.columns 
                            if any(term.lower() in str(col).lower() 
                                  for term in ['date', 'time', 'datetime'])]
                
                if date_cols:
                    date_col = date_cols[0]
                    # Try to convert to datetime
                    try:
                        self.sample_data[date_col] = pd.to_datetime(self.sample_data[date_col])
                        print(f"Converted {date_col} to datetime")
                    except:
                        print(f"Could not convert {date_col} to datetime")
            
            except Exception as e:
                print(f"First loading approach failed: {e}, trying alternative...")
                
                # Approach 2: Try with different separators for CSV
                if format_type == 'csv':
                    for sep in [',', ';', '\t', '|']:
                        try:
                            self.sample_data = pd.read_csv(self.sample_file_path, sep=sep)
                            if len(self.sample_data.columns) > 1:
                                print(f"Successfully loaded with separator: {sep}")
                                break
                        except:
                            continue
                else:
                    # For Excel, try specifying sheet index
                    self.sample_data = pd.read_excel(self.sample_file_path, sheet_name=0)
            
            # Check if we successfully loaded the data
            if self.sample_data is None or len(self.sample_data) == 0:
                self.update_status("Could not load sample file data", is_error=True)
                return
            
            # Detect file format based on columns
            self.detect_file_format()
            
            # Update column preview values
            self.update_column_previews()
            
            # Refresh data preview
            self.refresh_preview()
            
            self.update_status(f"Successfully loaded sample file with {len(self.sample_data)} rows and {len(self.sample_data.columns)} columns")
            
        except Exception as e:
            error_msg = f"Error loading sample file: {str(e)}"
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def detect_file_format(self):
        """Detect the file format with improved robustness"""
        if self.sample_data is None:
            return
        
        try:
            columns = [str(col).lower() for col in self.sample_data.columns]
            print(f"Detected columns: {columns}")
            
            # Check for common format patterns
            has_bid = any('bid' in col for col in columns)
            has_ask = any('ask' in col for col in columns)
            has_ohlc = all(term in ' '.join(columns) for term in ['open', 'high', 'low', 'close'])
            has_datetime = any(term in ' '.join(columns) for term in ['date', 'time', 'datetime'])
            
            format_notes = []
            
            if has_bid and has_ask:
                self.detected_format = "Bid/Ask Format"
                format_notes.append("Contains both Bid and Ask prices")
            elif has_ohlc:
                self.detected_format = "Standard OHLC Format"
                format_notes.append("Contains standard OHLC columns")
            elif has_bid:
                self.detected_format = "Bid Only Format"
                format_notes.append("Contains only Bid prices")
            elif has_ask:
                self.detected_format = "Ask Only Format"
                format_notes.append("Contains only Ask prices")
            else:
                self.detected_format = "Custom Format"
                format_notes.append("Column pattern not recognized")
            
            if has_datetime:
                format_notes.append("Contains DateTime column")
            else:
                format_notes.append("No DateTime column detected")
            
            # Update UI
            format_description = f"{self.detected_format} ({', '.join(format_notes)})"
            self.format_detect_var.set(format_description)
            
            # Auto detect columns if format is recognized
            if self.detected_format != "Custom Format":
                self.auto_detect_columns()
                
        except Exception as e:
            print(f"Error in format detection: {e}")
            self.detected_format = "Unknown Format"
            self.format_detect_var.set(f"Unknown Format (Error: {str(e)})")
    
    def update_column_previews(self):
        """Update the preview values for mapped columns"""
        if self.sample_data is None or len(self.sample_data) == 0:
            return
            
        try:
            # For each mapping, try to get a sample value
            for std_name, col_var in self.column_vars.items():
                col_name = col_var.get()
                preview_var = self.column_preview_vars.get(std_name)
                
                if not preview_var or not col_name:
                    continue
                    
                # Try to find the column in the data
                if col_name in self.sample_data.columns:
                    # Get first non-null value
                    values = self.sample_data[col_name].dropna()
                    if len(values) > 0:
                        sample_value = str(values.iloc[0])
                        # Truncate if too long
                        if len(sample_value) > 20:
                            sample_value = sample_value[:17] + "..."
                        preview_var.set(sample_value)
                    else:
                        preview_var.set("(No values)")
                else:
                    preview_var.set("(Column not found)")
        
        except Exception as e:
            print(f"Error updating column previews: {e}")
    
    def refresh_preview(self):
        """Refresh the data preview area"""
        # Clear existing preview
        for widget in self.preview_frame.winfo_children():
            widget.destroy()
            
        if self.sample_data is None or len(self.sample_data) == 0:
            ttk.Label(self.preview_frame, text="No data to preview").pack(pady=10)
            return
            
        try:
            # Get number of rows to preview
            try:
                preview_rows = int(self.preview_rows_var.get())
            except:
                preview_rows = 10
                
            # Create a frame with scrollbars for the data preview
            preview_container = ttk.Frame(self.preview_frame)
            preview_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # Add horizontal and vertical scrollbars
            h_scrollbar = ttk.Scrollbar(preview_container, orient=tk.HORIZONTAL)
            v_scrollbar = ttk.Scrollbar(preview_container, orient=tk.VERTICAL)
            
            # Create Treeview
            cols = list(self.sample_data.columns)
            tree = ttk.Treeview(preview_container, columns=cols, show="headings",
                              xscrollcommand=h_scrollbar.set, yscrollcommand=v_scrollbar.set)
            
            # Configure scrollbars
            h_scrollbar.config(command=tree.xview)
            h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
            
            v_scrollbar.config(command=tree.yview)
            v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            
            tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            
            # Set column headings
            for col in cols:
                tree.heading(col, text=str(col))
                tree.column(col, width=100, stretch=tk.YES)
            
            # Add data rows
            for i, row in self.sample_data.head(preview_rows).iterrows():
                values = [str(row[col]) for col in cols]
                tree.insert("", tk.END, values=values)
                
        except Exception as e:
            error_msg = f"Error creating preview: {str(e)}"
            ttk.Label(self.preview_frame, text=error_msg, foreground="red").pack(pady=10)
            print(f"Error details: {traceback.format_exc()}")
    
    def auto_detect_columns(self):
        """Try to auto-detect column mappings from sample data with improved robustness"""
        if self.sample_data is None:
            self.update_status("No sample data available, please load a sample file first", is_error=True)
            return
        
        try:
            # This will store our success rate for user feedback
            detected_count = 0
            total_mappings = len(self.column_vars)
            
            # Get lowercased column list for case-insensitive matching
            data_columns = [str(col) for col in self.sample_data.columns]
            lower_columns = [col.lower() for col in data_columns]
            
            # Mapping for common names based on detected format
            if self.detected_format == "Bid/Ask Format":
                mappings = {
                    'date/time': ['datetime', 'date', 'time', 'timestamp'],
                    'open': ['bidopen'],
                    'high': ['bidhigh'],
                    'low': ['bidlow'],
                    'close': ['bidclose'],
                    'volume': ['volume', 'tickqty']
                }
            else:
                mappings = {
                    'date/time': ['datetime', 'date', 'time', 'timestamp'],
                    'open': ['open', 'openingprice', 'openprice'],
                    'high': ['high', 'highprice', 'highest'],
                    'low': ['low', 'lowprice', 'lowest'],
                    'close': ['close', 'closingprice', 'closeprice'],
                    'volume': ['volume', 'vol', 'tickqty', 'quantity']
                }
            
            # Stores exact or best matches for each standard column
            matches = {}
            
            # First pass: Look for exact matches
            for std_name, possible_names in mappings.items():
                exact_match = None
                
                # Look for exact matches first
                for i, col in enumerate(lower_columns):
                    if col in possible_names:
                        exact_match = data_columns[i]
                        break
                
                # If exact match found, use it
                if exact_match:
                    matches[std_name] = exact_match
                    detected_count += 1
            
            # Second pass: Look for partial matches for any still unmapped
            for std_name, possible_names in mappings.items():
                if std_name in matches:
                    continue  # Already matched
                    
                best_match = None
                
                # Look for columns containing the terms
                for i, col in enumerate(lower_columns):
                    for name in possible_names:
                        if name in col:
                            best_match = data_columns[i]
                            break
                    if best_match:
                        break
                
                # If partial match found, use it
                if best_match:
                    matches[std_name] = best_match
                    detected_count += 1
            
            # Apply detected mappings
            for std_name, column in matches.items():
                if std_name in self.column_vars:
                    self.column_vars[std_name].set(column)
            
            # Update preview values
            self.update_column_previews()
            
            # Special handling for date/time if still not found
            if 'date/time' not in matches:
                # Try to find any column with date-like values
                for i, col in enumerate(data_columns):
                    try:
                        pd.to_datetime(self.sample_data[col])
                        self.column_vars['date/time'].set(col)
                        detected_count += 1
                        print(f"Detected date column by content: {col}")
                        break
                    except:
                        continue
            
            # Update status based on results
            if detected_count == total_mappings:
                self.update_status(f"Successfully detected all {detected_count} column mappings")
            elif detected_count > 0:
                self.update_status(f"Detected {detected_count} of {total_mappings} column mappings, please set the rest manually")
            else:
                self.update_status("Could not detect column mappings automatically, please set them manually", is_error=True)
                
        except Exception as e:
            error_msg = f"Error auto-detecting columns: {str(e)}"
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def test_connection(self):
        """Test the repository connection with improved error handling"""
        directory = self.dir_var.get().strip()
        if not directory or not os.path.isdir(directory):
            messagebox.showerror("Error", "Please select a valid directory")
            return
        
        self.update_status("Testing connection...")
        
        try:
            # Test if we can actually load data with the current settings
            format_type = self.format_var.get()
            column_map = {std: var.get() for std, var in self.column_vars.items()}
            
            # Get most recent sample file
            if not self.sample_file_path:
                messagebox.showinfo("Info", "No sample file available. Please scan directory first.")
                return
            
            # Try to load the file with specified columns
            date_col = column_map.get('date/time')
            
            try:
                if format_type == 'csv':
                    test_data = pd.read_csv(self.sample_file_path)
                else:
                    test_data = pd.read_excel(self.sample_file_path)
                
                # Verify required columns exist
                missing_cols = []
                for std_name, col_name in column_map.items():
                    if col_name and col_name not in test_data.columns:
                        missing_cols.append(f"{std_name} -> {col_name}")
                
                if missing_cols:
                    raise ValueError(f"Missing mapped columns: {', '.join(missing_cols)}")
                
                # Try to convert date column if specified
                if date_col and date_col in test_data.columns:
                    try:
                        test_data[date_col] = pd.to_datetime(test_data[date_col])
                    except Exception as e:
                        raise ValueError(f"Could not convert {date_col} to datetime: {str(e)}")
                
                # Check if we have price data
                price_cols = ['open', 'high', 'low', 'close']
                available_price_cols = [std for std in price_cols if column_map.get(std) in test_data.columns]
                if not available_price_cols:
                    raise ValueError("No price columns (open, high, low, close) found in mapped data")
                
                # If we get here, connection is successful
                messagebox.showinfo("Connection Test", 
                                  f"Connection test successful!\n\n"
                                  f"Loaded data from {os.path.basename(self.sample_file_path)}\n"
                                  f"Found {len(test_data)} rows with {len(test_data.columns)} columns\n"
                                  f"Successfully mapped {len(available_price_cols)} price columns")
                
                self.update_status("Connection test successful")
                
            except Exception as e:
                error_msg = f"Error testing connection: {str(e)}"
                messagebox.showerror("Connection Error", error_msg)
                self.update_status(error_msg, is_error=True)
        
        except Exception as e:
            error_msg = f"Error in test connection: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def load_existing_config(self):
        """Load existing repository configuration for editing"""
        if self.edit_repo in self.repo_manager.repositories['price']:
            config = self.repo_manager.repositories['price'][self.edit_repo]
            self.name_var.set(self.edit_repo)
            self.dir_var.set(config.get('directory', ''))
            self.format_var.set(config.get('format', 'csv'))
            
            # Set column mappings
            column_map = config.get('columns', {})
            for std_name, col_var in self.column_vars.items():
                if std_name in column_map:
                    col_var.set(column_map[std_name])
            
            # Try to scan the directory
            self.scan_directory()
            
            self.update_status(f"Loaded configuration for repository: {self.edit_repo}")
    
    def save_repository(self):
        """Save the repository configuration with validation"""
        name = self.name_var.get().strip()
        directory = self.dir_var.get().strip()
        
        # Validate inputs
        if not name:
            messagebox.showerror("Error", "Repository name is required")
            self.update_status("Repository name is required", is_error=True)
            return
        
        if not directory or not os.path.isdir(directory):
            messagebox.showerror("Error", "Please select a valid directory")
            self.update_status("Invalid directory", is_error=True)
            return
        
        try:
            # Validate that essential column mappings are provided
            essential_columns = ['date/time', 'open', 'high', 'low', 'close']
            missing_mappings = []
            
            # Create column mapping
            columns = {}
            for std_name, col_var in self.column_vars.items():
                col_value = col_var.get().strip()
                columns[std_name] = col_value
                
                # Check if essential columns are provided
                if std_name in essential_columns and not col_value:
                    missing_mappings.append(std_name)
            
            if missing_mappings:
                error_msg = f"Missing essential column mappings: {', '.join(missing_mappings)}"
                messagebox.showerror("Validation Error", error_msg)
                self.update_status(error_msg, is_error=True)
                return
            
            # Create repository configuration
            config = {
                'directory': directory,
                'format': self.format_var.get(),
                'columns': columns,
                'detected_format': self.detected_format,
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save to repository manager
            # If editing, remove old entry first
            if self.edit_repo and self.edit_repo != name:
                self.repo_manager.remove_repository('price', self.edit_repo)
            
            # Add the repository
            success = self.repo_manager.add_repository('price', name, config)
            
            if success:
                messagebox.showinfo("Success", f"Repository '{name}' saved successfully")
                self.update_status(f"Repository '{name}' saved successfully")
                self.dialog.destroy()
                
                # Call callback if provided
                if self.on_save:
                    self.on_save()
            else:
                messagebox.showerror("Error", "Failed to save repository configuration")
                self.update_status("Failed to save repository", is_error=True)
                
        except Exception as e:
            error_msg = f"Error saving repository: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")