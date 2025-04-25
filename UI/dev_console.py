# New file: balance_breaker/UI/dev_console.py
import tkinter as tk
from tkinter import ttk
import code
import sys
import io
import threading
import queue

class ConsoleOutput(io.StringIO):
    """Redirects stdout to the console widget"""
    def __init__(self, console_widget, queue):
        self.console = console_widget
        self.queue = queue
        super().__init__()
        
    def write(self, text):
        self.queue.put(text)

class DevConsole:
    """Interactive Python console with access to application state"""
    def __init__(self, parent, app):
        """Initialize dev console
        
        Parameters:
        -----------
        parent : tk.Toplevel
            Parent window
        app : BalanceBreakerApp
            Reference to main application
        """
        self.parent = parent
        self.app = app
        self.queue = queue.Queue()
        self.create_console_window()
        
    def create_console_window(self):
        """Create the console UI"""
        # Frame for console output
        output_frame = ttk.LabelFrame(self.parent, text="Console Output")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Console output area
        self.console_output = tk.Text(output_frame, wrap=tk.WORD, bg='black', fg='lime green')
        self.console_output.pack(fill=tk.BOTH, expand=True)
        
        # Command input
        input_frame = ttk.LabelFrame(self.parent, text="Command Input")
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.command_input = tk.Text(input_frame, height=3, bg='black', fg='white')
        self.command_input.pack(fill=tk.X, pady=5)
        self.command_input.bind("<Return>", self.on_enter_pressed)
        
        # Button frame
        button_frame = ttk.Frame(self.parent)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Execute", command=self.execute_command).pack(side=tk.RIGHT, padx=5)
        ttk.Button(button_frame, text="Clear", command=self.clear_console).pack(side=tk.RIGHT, padx=5)
        
        # Start output checking
        self.parent.after(100, self.check_output_queue)
        
        # Set up interpreter with access to the app
        self.locals = {
            'app': self.app,
            'strategy': self.app.strategy if hasattr(self.app, 'strategy') else None,
            'backtest': self.app.backtest_engine if hasattr(self.app, 'backtest_engine') else None,
            'tk': tk,
            'ttk': ttk,
        }
        self.interpreter = code.InteractiveInterpreter(self.locals)
        
        # Redirect stdout to our console
        self.old_stdout = sys.stdout
        sys.stdout = ConsoleOutput(self.console_output, self.queue)
        
        # Welcome message
        self.write_to_console("Balance Breaker Developer Console\n")
        self.write_to_console("Available objects: app, strategy, backtest\n")
        self.write_to_console(">>> ")
    
    def on_enter_pressed(self, event):
        """Handle Enter key in command input"""
        if not event.state & 0x4:  # No Ctrl key
            self.execute_command()
            return "break"  # Prevent default newline
        
    def execute_command(self):
        """Execute the Python command"""
        command = self.command_input.get("1.0", tk.END).strip()
        self.command_input.delete("1.0", tk.END)
        
        # Write command to console
        self.write_to_console(f"{command}\n")
        
        # Execute the command
        self.interpreter.runsource(command)
        
        # Add prompt
        self.write_to_console(">>> ")
    
    def write_to_console(self, text):
        """Write text to the console output"""
        self.console_output.configure(state=tk.NORMAL)
        self.console_output.insert(tk.END, text)
        self.console_output.see(tk.END)
        self.console_output.configure(state=tk.DISABLED)
    
    def clear_console(self):
        """Clear the console output"""
        self.console_output.configure(state=tk.NORMAL)
        self.console_output.delete("1.0", tk.END)
        self.console_output.configure(state=tk.DISABLED)
        self.write_to_console(">>> ")
    
    def check_output_queue(self):
        """Check if there's any output to display"""
        try:
            while True:
                text = self.queue.get_nowait()
                self.write_to_console(text)
                self.queue.task_done()
        except queue.Empty:
            pass
        
        # Schedule next check
        self.parent.after(100, self.check_output_queue)
    
    def destroy(self):
        """Clean up when console is closed"""
        # Restore stdout
        sys.stdout = self.old_stdout