"""
Utility functions for repository dialogs
"""

import os
import pandas as pd
import numpy as np
import traceback

def scan_directory_for_files(directory, format_type='csv', file_pattern=None):
    """Scan directory for files matching the format type and pattern
    
    Parameters:
    -----------
    directory : str
        Directory path to scan
    format_type : str
        File format to scan for ('csv' or 'excel')
    file_pattern : str, optional
        Pattern to match in filenames
        
    Returns:
    --------
    list
        List of file paths matching criteria
    """
    extensions = {
        'csv': ['.csv', '.CSV', '.txt', '.TXT'],
        'excel': ['.xlsx', '.xls', '.XLSX', '.XLS']
    }
    
    file_extensions = extensions.get(format_type, ['.csv', '.CSV'])
    
    found_files = []
    
    try:
        for root, _, files in os.walk(directory):
            for file in files:
                if any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                    # Check pattern if provided
                    if file_pattern is None or file_pattern in file:
                        file_path = os.path.join(root, file)
                        found_files.append(file_path)
        
        return found_files
    except Exception as e:
        print(f"Error scanning directory: {e}")
        print(traceback.format_exc())
        return []

def load_sample_data(file_path, format_type='csv'):
    """Load sample data with robust error handling
    
    Parameters:
    -----------
    file_path : str
        Path to the data file
    format_type : str
        File format ('csv' or 'excel')
        
    Returns:
    --------
    DataFrame or None
        Loaded data or None if loading failed
    """
    data = None
    
    try:
        # Try standard approach first
        if format_type == 'csv':
            data = pd.read_csv(file_path)
        else:
            data = pd.read_excel(file_path)
            
    except Exception as first_error:
        print(f"Standard loading failed: {first_error}, trying alternatives...")
        
        try:
            # Alternative loading approaches
            if format_type == 'csv':
                # Try different separators
                for sep in [',', ';', '\t', '|']:
                    try:
                        data = pd.read_csv(file_path, sep=sep)
                        if len(data.columns) > 1:
                            print(f"Successfully loaded with separator: {sep}")
                            break
                    except:
                        continue
            else:
                # For Excel, try with explicit sheet index
                data = pd.read_excel(file_path, sheet_name=0)
                
        except Exception as e:
            print(f"All loading attempts failed: {e}")
            print(traceback.format_exc())
            return None
    
    return data

def detect_file_format(data):
    """Detect the file format based on column names
    
    Parameters:
    -----------
    data : DataFrame
        Data to analyze
        
    Returns:
    --------
    tuple
        (format_type, format_notes) where format_type is a string describing the format
        and format_notes is a list of additional format observations
    """
    if data is None:
        return "Unknown Format", []
    
    try:
        columns = [str(col).lower() for col in data.columns]
        
        # Check for common format patterns
        has_bid = any('bid' in col for col in columns)
        has_ask = any('ask' in col for col in columns)
        has_ohlc = all(term in ' '.join(columns) for term in ['open', 'high', 'low', 'close'])
        has_datetime = any(term in ' '.join(columns) for term in ['date', 'time', 'datetime'])
        
        format_notes = []
        
        if has_bid and has_ask:
            format_type = "Bid/Ask Format"
            format_notes.append("Contains both Bid and Ask prices")
        elif has_ohlc:
            format_type = "Standard OHLC Format"
            format_notes.append("Contains standard OHLC columns")
        elif has_bid:
            format_type = "Bid Only Format"
            format_notes.append("Contains only Bid prices")
        elif has_ask:
            format_type = "Ask Only Format"
            format_notes.append("Contains only Ask prices")
        else:
            format_type = "Custom Format"
            format_notes.append("Column pattern not recognized")
        
        if has_datetime:
            format_notes.append("Contains DateTime column")
        else:
            format_notes.append("No DateTime column detected")
            
        return format_type, format_notes
        
    except Exception as e:
        print(f"Error detecting format: {e}")
        return "Unknown Format", [f"Error: {str(e)}"]

def detect_currency_pairs(file_paths):
    """Detect currency pairs from filenames
    
    Parameters:
    -----------
    file_paths : list
        List of file paths to analyze
        
    Returns:
    --------
    set
        Set of detected currency pairs
    """
    # Common pairs to look for
    common_pairs = ['USDJPY', 'EURUSD', 'GBPUSD', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD']
    detected_pairs = set()
    
    for file_path in file_paths:
        file_name = os.path.basename(file_path).lower()
        for pair in common_pairs:
            if pair.lower() in file_name:
                detected_pairs.add(pair)
                break
                
    return detected_pairs