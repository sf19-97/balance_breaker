"""
Balance Breaker Repository Manager
Handles data repository configurations and loading
"""

import os
import pandas as pd
import numpy as np
import json
from datetime import datetime

class RepositoryManager:
    def __init__(self, config_path='repository_config.json'):
        self.config_path = config_path
        self.repositories = {
            'price': {},
            'macro': {}
        }
        self.load_config()
    
    def load_config(self):
        """Load repositories configuration"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    self.repositories = json.load(f)
                print(f"Loaded {len(self.repositories['price'])} price repositories")
                print(f"Loaded {len(self.repositories['macro'])} macro repositories")
            except Exception as e:
                print(f"Error loading repository config: {e}")
    
    def save_config(self):
        """Save repositories configuration"""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.repositories, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving repository config: {e}")
            return False
    
    def add_repository(self, repo_type, name, config):
        """Add a new repository configuration"""
        if repo_type not in ['price', 'macro']:
            raise ValueError("Repository type must be 'price' or 'macro'")
        
        self.repositories[repo_type][name] = config
        return self.save_config()
    
    def remove_repository(self, repo_type, name):
        """Remove a repository configuration"""
        if repo_type not in ['price', 'macro']:
            raise ValueError("Repository type must be 'price' or 'macro'")
        
        if name in self.repositories[repo_type]:
            del self.repositories[repo_type][name]
            return self.save_config()
        return False
    
    def get_repository_list(self, repo_type):
        """Get list of repository names for the specified type"""
        if repo_type not in ['price', 'macro']:
            raise ValueError("Repository type must be 'price' or 'macro'")
        
        return list(self.repositories[repo_type].keys())
    
    def load_price_data(self, repo_name, pair, start_date=None, end_date=None):
        """Load price data from repository for a specific pair"""
        if repo_name not in self.repositories['price']:
            raise ValueError(f"Price repository '{repo_name}' not found")
        
        repo_config = self.repositories['price'][repo_name]
        directory = repo_config['directory']
        format_type = repo_config.get('format', 'csv')
        column_map = repo_config.get('columns', {})
        
        # Determine file path based on pair and directory
        file_path = self._find_pair_file(directory, pair, format_type)
        if not file_path:
            raise FileNotFoundError(f"No data file found for {pair} in repository {repo_name}")
        
        print(f"Loading price data from: {file_path}")
        
        # Load data based on format
        if format_type == 'csv':
            try:
                df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            except Exception as e:
                # Try alternative approaches if first attempt fails
                try:
                    print(f"First attempt failed ({e}), trying with auto-detection...")
                    df = pd.read_csv(file_path, parse_dates=True)
                    
                    # Look for potential datetime column
                    date_cols = [col for col in df.columns if any(term in col.lower() for term in ['date', 'time'])]
                    if date_cols:
                        print(f"Setting index to column: {date_cols[0]}")
                        df = df.set_index(date_cols[0])
                except Exception as e2:
                    raise ValueError(f"Failed to load CSV file: {e2}")
        elif format_type == 'excel':
            df = pd.read_excel(file_path, index_col=0, parse_dates=True)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        # Debug output of original data
        print(f"Original data columns: {df.columns.tolist()}")
        print(f"Original data shape: {df.shape}")
        
        # Check if index is datetime, if not try to convert
        if not isinstance(df.index, pd.DatetimeIndex):
            print("Converting index to DatetimeIndex")
            try:
                df.index = pd.to_datetime(df.index)
            except:
                print("Warning: Could not convert index to datetime")
        
        # Normalize column names
        df = self._normalize_columns(df, column_map)
        
        # Filter by date range
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        # Calculate pip factor
        df['pip_factor'] = 100.0 if 'JPY' in pair else 10000.0
        
        # Final data debug
        print(f"Normalized data columns: {df.columns.tolist()}")
        print(f"Normalized data shape: {df.shape}")
        
        # Verify no duplicate columns
        if len(df.columns) != len(set(df.columns)):
            print("Warning: Duplicate columns detected, fixing...")
            # Get list of columns with duplicates
            seen = set()
            dupes = [x for x in df.columns if x in seen or seen.add(x)]
            print(f"Duplicate columns: {dupes}")
            
            # Create clean dataframe
            clean_df = pd.DataFrame(index=df.index)
            for col in set(df.columns):
                try:
                    # Get first occurrence
                    clean_df[col] = df[col].iloc[:, 0] if isinstance(df[col], pd.DataFrame) else df[col]
                except:
                    print(f"Error accessing column {col}, skipping")
            df = clean_df
            print(f"Fixed columns: {df.columns.tolist()}")
        
        return df
    
    def _find_pair_file(self, directory, pair, format_type):
        """Find data file for the specified pair"""
        extensions = {
            'csv': ['.csv', '.CSV', '.txt', '.TXT'],
            'excel': ['.xlsx', '.xls', '.XLSX', '.XLS']
        }
        
        file_extensions = extensions.get(format_type, ['.csv'])
        
        # Track all candidate files
        candidates = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if filename contains pair name and has correct extension
                if pair.lower() in file.lower() and any(file.lower().endswith(ext.lower()) for ext in file_extensions):
                    candidates.append(file_path)
                    
                    # Exact match prioritization
                    if file.lower() == f"{pair.lower()}.{file_extensions[0].lower().strip('.')}" or \
                       file.lower() == f"{pair.lower()}_h1.{file_extensions[0].lower().strip('.')}":
                        print(f"Found exact match for {pair}: {file}")
                        return file_path
        
        # Return first candidate if any found
        if candidates:
            print(f"Found candidate match for {pair}: {os.path.basename(candidates[0])}")
            return candidates[0]
        
        # No candidates found
        return None
    
    def _normalize_columns(self, df, column_map):
        """Normalize column names based on mapping"""
        print("Normalizing columns...")
        
        # Default column mapping
        default_map = {
            'date': 'datetime',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        }
        
        # Update with custom mapping
        mapping = {**default_map, **column_map}
        
        # Create a reverse mapping to look up columns
        reverse_map = {}
        for std_name, custom_name in mapping.items():
            reverse_map[custom_name.lower()] = std_name
        
        # Try to match columns (case insensitive)
        new_names = {}
        for col in df.columns:
            col_lower = col.lower()
            if col_lower in reverse_map:
                new_names[col] = reverse_map[col_lower]
            elif 'open' in col_lower:
                new_names[col] = 'open'
            elif 'high' in col_lower:
                new_names[col] = 'high'
            elif 'low' in col_lower:
                new_names[col] = 'low'
            elif 'close' in col_lower:
                new_names[col] = 'close'
            elif 'volume' in col_lower or 'vol' in col_lower:
                new_names[col] = 'volume'
        
        # Debug column mapping
        print(f"Column mapping: {new_names}")
        
        # Check for potential bid/ask format
        has_bid_cols = any('bid' in col.lower() for col in df.columns)
        has_ask_cols = any('ask' in col.lower() for col in df.columns)
        
        # Create a clean DataFrame to avoid duplicates
        clean_df = pd.DataFrame(index=df.index)
        
        # Handle bid/ask format if both bid and ask columns exist
        if has_bid_cols and has_ask_cols:
            print("Detected bid/ask format, creating mid-price columns")
            
            # Find the actual column names
            bid_cols = [col for col in df.columns if 'bid' in col.lower()]
            ask_cols = [col for col in df.columns if 'ask' in col.lower()]
            
            print(f"Bid columns: {bid_cols}")
            print(f"Ask columns: {ask_cols}")
            
            # Extract the price component (open, high, low, close)
            price_types = ['open', 'high', 'low', 'close']
            
            # Create OHLC from bid/ask
            for price_type in price_types:
                bid_col = next((col for col in bid_cols if price_type in col.lower()), None)
                ask_col = next((col for col in ask_cols if price_type in col.lower()), None)
                
                if bid_col and ask_col:
                    print(f"Creating {price_type} column from {bid_col} and {ask_col}")
                    # First rename original columns to avoid later conflicts
                    new_bid_col = f"Bid{price_type.capitalize()}"
                    new_ask_col = f"Ask{price_type.capitalize()}"
                    
                    # Add both bid and ask as separate columns
                    clean_df[new_bid_col] = df[bid_col]
                    clean_df[new_ask_col] = df[ask_col]
                    
                    # Create mid price
                    clean_df[price_type] = (df[bid_col] + df[ask_col]) / 2.0
                    
                    # Also capture spread
                    if price_type == 'close':
                        clean_df['Spread'] = df[ask_col] - df[bid_col]
                else:
                    print(f"Missing bid or ask column for {price_type}")
            
            # Add volume if present
            vol_col = next((col for col in df.columns if 'volume' in col.lower() or 'vol' in col.lower()), None)
            if vol_col:
                clean_df['volume'] = df[vol_col]
            else:
                clean_df['volume'] = 1  # Default volume
        else:
            # Standard format, just rename columns
            print("Detected standard format, renaming columns")
            
            # Rename and add to clean dataframe (handling duplicates)
            seen_std_names = set()
            for col, std_name in new_names.items():
                if std_name not in seen_std_names:
                    seen_std_names.add(std_name)
                    clean_df[std_name] = df[col]
            
            # Add other columns that weren't renamed
            for col in df.columns:
                if col not in new_names and col not in clean_df.columns:
                    clean_df[col] = df[col]
        
        # Ensure we have the required columns
        required = ['open', 'high', 'low', 'close']
        for col in required:
            if col not in clean_df.columns:
                if 'close' in clean_df.columns:
                    print(f"Adding missing {col} column (derived from close)")
                    clean_df[col] = clean_df['close']
                else:
                    raise ValueError(f"Required column '{col}' not found and could not be derived")
        
        # Add volume if missing
        if 'volume' not in clean_df.columns:
            print("Adding default volume column")
            clean_df['volume'] = 1
        
        print(f"Normalization complete, final columns: {clean_df.columns.tolist()}")
        return clean_df
    
    def load_macro_data(self, repo_name, start_date=None, end_date=None):
        """Load macro economic data from repository"""
        if repo_name not in self.repositories['macro']:
            raise ValueError(f"Macro repository '{repo_name}' not found")
        
        repo_config = self.repositories['macro'][repo_name]
        directory = repo_config['directory']
        format_type = repo_config.get('format', 'csv')
        
        # Load all macro data files and merge them
        all_data = {}
        
        for root, _, files in os.walk(directory):
            for file in files:
                if format_type == 'csv' and file.endswith('.csv'):
                    file_path = os.path.join(root, file)
                    try:
                        # Extract indicator name from filename
                        indicator = os.path.splitext(file)[0].split('_')[-1]
                        
                        # Load data
                        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                        
                        # If single column, use filename as column name
                        if len(df.columns) == 1:
                            all_data[indicator] = df.iloc[:, 0]
                        else:
                            # Multiple columns, merge all
                            for col in df.columns:
                                all_data[f"{indicator}_{col}"] = df[col]
                    except Exception as e:
                        print(f"Error loading {file}: {e}")
        
        # Combine all series into a DataFrame
        if all_data:
            macro_df = pd.DataFrame(all_data)
            
            # Fill NaN values - important for PCA to work properly
            print("Filling NaN values in macro data")
            macro_df = macro_df.fillna(method='ffill').fillna(method='bfill')
            
            # Check for infinite values and replace with NaN, then fill
            print("Checking for infinite values")
            macro_df = macro_df.replace([np.inf, -np.inf], np.nan)
            macro_df = macro_df.fillna(method='ffill').fillna(method='bfill')
            
            # Filter by date range
            if start_date:
                macro_df = macro_df[macro_df.index >= start_date]
            if end_date:
                macro_df = macro_df[macro_df.index <= end_date]
            
            print(f"Loaded macro data with {len(macro_df.columns)} indicators")
            return macro_df
        else:
            raise ValueError(f"No valid data found in macro repository {repo_name}")