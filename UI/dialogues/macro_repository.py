"""
Macro repository dialog for Balance Breaker
Handles macroeconomic data repository configuration
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import pandas as pd
import numpy as np
import os
import traceback
from datetime import datetime

from .repository_base import RepositoryDialog

class MacroRepositoryDialog(RepositoryDialog):
    """Enhanced dialog for macroeconomic data repository configuration"""
    def __init__(self, parent, repo_manager, on_save=None, edit_repo=None):
        self.edit_repo = edit_repo  # Repository name if editing existing
        self.found_indicators = []  # Store found indicators
        super().__init__(parent, repo_manager, "macro", on_save)
    
    def create_dialog_content(self, parent_frame):
        """Create macro repository dialog content with improved features"""
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
        
        # Create notebook for tabs
        notebook = ttk.Notebook(parent_frame)
        notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=5)
        
        # Tab 1: Basic Settings
        basic_frame = ttk.Frame(notebook)
        notebook.add(basic_frame, text="Basic Settings")
        
        # File format selection
        format_frame = ttk.LabelFrame(basic_frame, text="File Format")
        format_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.format_var = tk.StringVar(value="csv")
        ttk.Radiobutton(format_frame, text="CSV Files", variable=self.format_var, value="csv").pack(anchor=tk.W)
        ttk.Radiobutton(format_frame, text="Excel Files", variable=self.format_var, value="excel").pack(anchor=tk.W)
        
        # File pattern settings
        pattern_frame = ttk.LabelFrame(basic_frame, text="File Naming Pattern")
        pattern_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(pattern_frame, text="Files should follow a consistent naming pattern:").pack(anchor=tk.W)
        example_frame = ttk.Frame(pattern_frame)
        example_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(example_frame, text="Examples:").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(example_frame, text="macro_DGS10.csv").grid(row=1, column=0, padx=10, sticky=tk.W)
        ttk.Label(example_frame, text="(where 'macro_' is the prefix, 'DGS10' is the indicator)").grid(row=1, column=1, sticky=tk.W)
        
        # Prefix setting
        prefix_frame = ttk.Frame(pattern_frame)
        prefix_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(prefix_frame, text="File Prefix:").pack(side=tk.LEFT)
        self.prefix_var = tk.StringVar(value="macro_")
        ttk.Entry(prefix_frame, textvariable=self.prefix_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(prefix_frame, text="(Optional, but helps identify indicator files)").pack(side=tk.LEFT, padx=5)
        
        # Tab 2: Found Indicators
        indicators_frame = ttk.Frame(notebook)
        notebook.add(indicators_frame, text="Indicators")
        
        # Create indicator list with scrollbar
        indicator_container = ttk.Frame(indicators_frame)
        indicator_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add vertical scrollbar
        scrollbar = ttk.Scrollbar(indicator_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Create listbox with indicators
        self.indicator_list = tk.Listbox(indicator_container, yscrollcommand=scrollbar.set)
        self.indicator_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.indicator_list.yview)
        
        # Add checkbutton for including all files (not just prefix-matched)
        self.include_all_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(indicators_frame, text="Include all files (not just those matching prefix)",
                      variable=self.include_all_var, command=self.scan_directory).pack(anchor=tk.W, padx=5, pady=5)
        
        # Action buttons
        action_frame = ttk.Frame(parent_frame)
        action_frame.pack(fill=tk.X, padx=0, pady=5)
        
        ttk.Button(action_frame, text="Scan Directory", 
                  command=self.scan_directory).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Test Connection", 
                  command=self.test_connection).pack(side=tk.LEFT, padx=5)
        ttk.Button(action_frame, text="Preview Indicator", 
                  command=self.preview_indicator).pack(side=tk.LEFT, padx=5)
        
        # Fill with existing data if editing
        if self.edit_repo:
            self.load_existing_config()
    
    def browse_directory(self):
        """Browse for data directory"""
        directory = filedialog.askdirectory(title="Select Data Directory")
        if directory:
            self.dir_var.set(directory)
            self.update_status(f"Selected directory: {directory}")
            # Auto-scan the directory
            self.scan_directory()
    
    def scan_directory(self):
        """Scan directory for macro data files with improved robustness"""
        directory = self.dir_var.get()
        if not directory or not os.path.isdir(directory):
            self.update_status("Please select a valid directory first", is_error=True)
            return
            
        try:
            # Clear current indicator list
            self.indicator_list.delete(0, tk.END)
            self.found_indicators = []
            
            # Get file list
            format_type = self.format_var.get()
            prefix = self.prefix_var.get()
            include_all = self.include_all_var.get()
            
            extensions = {
                'csv': ['.csv', '.CSV', '.txt', '.TXT'],
                'excel': ['.xlsx', '.xls', '.XLSX', '.XLS']
            }
            
            file_extensions = extensions.get(format_type, ['.csv', '.CSV'])
            
            # Find matching files
            matching_files = []
            indicators = []
            
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                        # Check prefix if not including all
                        if include_all or not prefix or file.startswith(prefix):
                            file_path = os.path.join(root, file)
                            matching_files.append(file_path)
                            
                            # Extract indicator name
                            if prefix and file.startswith(prefix):
                                indicator = file[len(prefix):].split('.')[0]
                            else:
                                indicator = file.split('.')[0]
                                
                            indicators.append((indicator, file_path))
            
            if not matching_files:
                message = f"No {format_type} files found"
                if prefix and not include_all:
                    message += f" matching prefix '{prefix}'"
                self.update_status(message, is_error=True)
                return
            
            # Store found indicators
            self.found_indicators = indicators
            
            # Update indicator list
            for indicator, file_path in indicators:
                display_text = f"{indicator} ({os.path.basename(file_path)})"
                self.indicator_list.insert(tk.END, display_text)
            
            self.update_status(f"Found {len(matching_files)} indicators")
            
        except Exception as e:
            error_msg = f"Error scanning directory: {str(e)}"
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def preview_indicator(self):
        """Preview selected indicator data"""
        selection = self.indicator_list.curselection()
        if not selection:
            self.update_status("Please select an indicator to preview", is_error=True)
            return
            
        try:
            # Get selected indicator info
            indicator, file_path = self.found_indicators[selection[0]]
            
            # Create preview dialog
            preview = tk.Toplevel(self.dialog)
            preview.title(f"Preview: {indicator}")
            preview.geometry("600x400")
            preview.transient(self.dialog)
            
            # Create frame for preview
            frame = ttk.Frame(preview, padding="10 10 10 10")
            frame.pack(fill=tk.BOTH, expand=True)
            
            try:
                # Load the data
                format_type = self.format_var.get()
                if format_type == 'csv':
                    data = pd.read_csv(file_path)
                else:
                    data = pd.read_excel(file_path)
                
                # Create a frame with scrollbars for the data preview
                preview_container = ttk.Frame(frame)
                preview_container.pack(fill=tk.BOTH, expand=True)
                
                # Add horizontal and vertical scrollbars
                h_scrollbar = ttk.Scrollbar(preview_container, orient=tk.HORIZONTAL)
                v_scrollbar = ttk.Scrollbar(preview_container, orient=tk.VERTICAL)
                
                # Create Treeview
                cols = list(data.columns)
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
                
                # Add data rows (limit to 20)
                max_rows = min(20, len(data))
                for i, row in data.head(max_rows).iterrows():
                    values = [str(row[col]) for col in cols]
                    tree.insert("", tk.END, values=values)
                
                # Add info label
                info_text = f"Showing {max_rows} of {len(data)} rows with {len(cols)} columns"
                ttk.Label(frame, text=info_text).pack(side=tk.BOTTOM, pady=5)
                
            except Exception as e:
                error_msg = f"Error loading indicator data: {str(e)}"
                ttk.Label(frame, text=error_msg, foreground="red").pack(pady=20)
                print(f"Error details: {traceback.format_exc()}")
            
        except Exception as e:
            error_msg = f"Error creating preview: {str(e)}"
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def test_connection(self):
        """Test the macro repository connection"""
        directory = self.dir_var.get().strip()
        if not directory or not os.path.isdir(directory):
            messagebox.showerror("Error", "Please select a valid directory")
            return
        
        try:
            # Scan directory if it hasn't been done yet
            if not self.found_indicators:
                self.scan_directory()
                if not self.found_indicators:
                    messagebox.showerror("Error", "No indicator files found. Please check directory and file pattern.")
                    return
            
            format_type = self.format_var.get()
            prefix = self.prefix_var.get()
            
            # Try to load a few sample indicators
            test_results = []
            
            for i, (indicator, file_path) in enumerate(self.found_indicators[:3]):  # Test first 3
                try:
                    if format_type == 'csv':
                        data = pd.read_csv(file_path)
                    else:
                        data = pd.read_excel(file_path)
                    
                    test_results.append(f"{indicator}: {len(data)} rows, {len(data.columns)} columns - SUCCESS")
                except Exception as e:
                    test_results.append(f"{indicator}: ERROR - {str(e)}")
            
            # Determine if tests were successful overall
            if any("SUCCESS" in result for result in test_results):
                result_text = "\n".join(test_results)
                messagebox.showinfo("Connection Test", 
                                  f"Connection test successful!\n\n"
                                  f"Found {len(self.found_indicators)} indicators\n\n"
                                  f"Sample tests:\n{result_text}")
                
                self.update_status("Connection test successful")
            else:
                messagebox.showerror("Connection Test Failed", 
                                    f"Could not load any indicator files.\n\n"
                                    f"Sample tests:\n{chr(10).join(test_results)}")
                
                self.update_status("Connection test failed", is_error=True)
            
        except Exception as e:
            error_msg = f"Error testing connection: {str(e)}"
            messagebox.showerror("Error", error_msg)
            self.update_status(error_msg, is_error=True)
            print(f"Error details: {traceback.format_exc()}")
    
    def load_existing_config(self):
        """Load existing repository configuration for editing"""
        if self.edit_repo in self.repo_manager.repositories['macro']:
            config = self.repo_manager.repositories['macro'][self.edit_repo]
            self.name_var.set(self.edit_repo)
            self.dir_var.set(config.get('directory', ''))
            self.format_var.set(config.get('format', 'csv'))
            self.prefix_var.set(config.get('prefix', 'macro_'))
            
            # Set include all if present
            if 'include_all' in config:
                self.include_all_var.set(config['include_all'])
            
            # Scan directory to show available indicators
            self.scan_directory()
            
            self.update_status(f"Loaded configuration for repository: {self.edit_repo}")
    
    def save_repository(self):
        """Save the repository configuration"""
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
        
        if not self.found_indicators:
            if messagebox.askyesno("Warning", "No indicators found. Scan directory now?"):
                self.scan_directory()
                if not self.found_indicators:
                    messagebox.showerror("Error", "Could not find any indicators. Please check directory and file pattern.")
                    return
            else:
                messagebox.showerror("Error", "Cannot save repository without indicators")
                return
        
        try:
            # Create repository configuration
            config = {
                'directory': directory,
                'format': self.format_var.get(),
                'prefix': self.prefix_var.get(),
                'include_all': self.include_all_var.get(),
                'indicators': [indicator for indicator, _ in self.found_indicators],
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Save to repository manager
            # If editing, remove old entry first
            if self.edit_repo and self.edit_repo != name:
                self.repo_manager.remove_repository('macro', self.edit_repo)
            
            # Add the repository
            success = self.repo_manager.add_repository('macro', name, config)
            
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