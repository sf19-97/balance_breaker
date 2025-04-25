"""
Repository Dialog Base Class
Provides a foundation for repository configuration dialogs
with robust error handling and UI management
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox
import traceback

class RepositoryDialog:
    """Base class for repository dialogs with improved error handling"""
    
    def __init__(self, parent, repo_manager, repo_type="price", on_save=None, edit_repo=None):
        """Initialize dialog with repository manager and settings
        
        Parameters:
        -----------
        parent : tk.Tk or tk.Toplevel
            Parent window
        repo_manager : RepositoryManager
            Repository manager instance
        repo_type : str
            Repository type ('price' or 'macro')
        on_save : callable, optional
            Callback function to execute after saving
        edit_repo : str, optional
            Repository name if editing existing repo
        """
        # Store parameters
        self.parent = parent
        self.repo_manager = repo_manager
        self.repo_type = repo_type
        self.on_save = on_save
        self.edit_repo = edit_repo
        
        # Initialize dialog components to None
        self.dialog = None
        self.status_var = None
        self.status_bar = None
        
        # Create the dialog
        self.create_dialog()
    
    def create_dialog(self):
        """Create the base dialog window with frame structure"""
        try:
            # Create dialog window
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title(f"{'Edit' if self.edit_repo else 'Add'} {self.repo_type.title()} Repository")
            self.dialog.geometry("700x600")
            self.dialog.minsize(700, 600)
            self.dialog.transient(self.parent)
            self.dialog.grab_set()  # Make dialog modal
            
            # Status variable for messages
            self.status_var = tk.StringVar(value="Ready")
            
            # Create main container frame with padding
            main_frame = ttk.Frame(self.dialog, padding="10 10 10 10")
            main_frame.pack(fill=tk.BOTH, expand=True)
            
            # Add dialog content to the main frame
            self.create_dialog_content(main_frame)
            
            # Status bar for feedback
            self.status_bar = ttk.Label(self.dialog, textvariable=self.status_var, 
                                       relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
            
            # Button frame with padding
            btn_frame = ttk.Frame(self.dialog)
            btn_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=(0, 10))
            
            ttk.Button(btn_frame, text="Cancel", 
                      command=self.dialog.destroy).pack(side=tk.RIGHT, padx=5)
            ttk.Button(btn_frame, text="Save", 
                      command=self.save_repository).pack(side=tk.RIGHT, padx=5)
            
            # Handle dialog close events
            self.dialog.protocol("WM_DELETE_WINDOW", self.dialog.destroy)
            
            # Center dialog on parent
            self.center_dialog()
            
        except Exception as e:
            self.show_error("Error creating dialog", e)
    
    def create_dialog_content(self, parent_frame):
        """Create dialog content - override in subclasses"""
        # This method should be overridden by subclasses
        pass
    
    def save_repository(self):
        """Save repository configuration - override in subclasses"""
        # This method should be overridden by subclasses
        pass
    
    def update_status(self, message, is_error=False):
        """Update status bar with message and optional error formatting
        
        Parameters:
        -----------
        message : str
            Message to display in status bar
        is_error : bool
            Whether to format as error message
        """
        try:
            # Update status text if status_var exists
            if hasattr(self, 'status_var') and self.status_var is not None:
                self.status_var.set(message)
            
            # Update status bar formatting if it exists
            if hasattr(self, 'status_bar') and self.status_bar is not None:
                self.status_bar.config(foreground='red' if is_error else 'black')
                
                # Update immediately (for smoother UI feedback)
                self.status_bar.update_idletasks()
        except Exception as e:
            # Silently handle errors updating status
            # (avoid recursive error reporting)
            print(f"Error updating status: {e}")
    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if not self.dialog or not self.parent:
            return
            
        try:
            # Update dialog geometry to ensure proper dimensions
            self.dialog.update_idletasks()
            
            # Get parent and dialog dimensions
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            
            dialog_width = self.dialog.winfo_width()
            dialog_height = self.dialog.winfo_height()
            
            # Calculate position
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2
            
            # Position dialog
            self.dialog.geometry(f"+{x}+{y}")
        except Exception as e:
            # Non-critical function, just print error
            print(f"Error centering dialog: {e}")
    
    def show_error(self, title, exception):
        """Show error message with details
        
        Parameters:
        -----------
        title : str
            Error message title
        exception : Exception
            Exception object
        """
        error_msg = f"{title}: {str(exception)}"
        print(error_msg)
        print(traceback.format_exc())
        messagebox.showerror("Error", error_msg)
    
    def validate_required_input(self, input_dict):
        """Validate required input fields
        
        Parameters:
        -----------
        input_dict : dict
            Dictionary of {field_name: value} pairs
            
        Returns:
        --------
        bool
            True if all required fields have valid values, False otherwise
        """
        for field, value in input_dict.items():
            if not value or (isinstance(value, str) and value.strip() == ""):
                self.update_status(f"{field} is required", is_error=True)
                messagebox.showerror("Validation Error", f"{field} is required")
                return False
        return True
    
    def is_valid_directory(self, directory):
        """Check if directory exists and is valid
        
        Parameters:
        -----------
        directory : str
            Directory path to validate
            
        Returns:
        --------
        bool
            True if directory is valid, False otherwise
        """
        if not directory or not os.path.isdir(directory):
            self.update_status("Invalid directory", is_error=True)
            messagebox.showerror("Error", "Please select a valid directory")
            return False
        return True