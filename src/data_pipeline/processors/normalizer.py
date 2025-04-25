# src/data_pipeline/processors/normalizer.py

import pandas as pd
import numpy as np
from typing import Dict, Any, Union, List
from .base import BaseProcessor

class DataNormalizer(BaseProcessor):
    """Normalizer for price and macro data"""
    
    def process_data(self, data: Any, context: Dict[str, Any]) -> Any:
        """Normalize data format
        
        Args:
            data: Input data (Dict[str, pd.DataFrame] for price, pd.DataFrame for macro)
            context: Pipeline context
            
        Returns:
            Normalized data
        """
        data_type = context.get('data_type', 'price')
        
        if data_type == 'price':
            return self._normalize_price_data(data, context)
        elif data_type == 'macro':
            return self._normalize_macro_data(data, context)
        else:
            self.logger.warning(f"Unknown data type for normalization: {data_type}")
            return data
    
    def _normalize_price_data(self, data: Dict[str, pd.DataFrame], context: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Normalize price data format
        
        Args:
            data: Dictionary of price DataFrames
            context: Pipeline context
            
        Returns:
            Dictionary of normalized DataFrames
        """
        normalized_data = {}
        
        for pair, df in data.items():
            self.logger.info(f"Normalizing price data for {pair}")
            
            # Create a copy to avoid modifying original
            normalized = df.copy()
            
            # Check column names
            columns = df.columns.str.lower() if hasattr(df.columns, 'str') else [str(c).lower() for c in df.columns]
            
            # If we have separate bid/ask columns
            if 'bidclose' in columns and 'askclose' in columns:
                self.logger.info(f"Detected Bid/Ask format for {pair}, converting to OHLC format")
                
                # Find bid/ask columns
                bid_cols = [col for col in df.columns if 'bid' in str(col).lower()]
                ask_cols = [col for col in df.columns if 'ask' in str(col).lower()]
                
                # Calculate mid prices
                # Find open, high, low, close in both bid and ask
                for price_type in ['open', 'high', 'low', 'close']:
                    bid_col = next((col for col in bid_cols if price_type in str(col).lower()), None)
                    ask_col = next((col for col in ask_cols if price_type in str(col).lower()), None)
                    
                    if bid_col and ask_col:
                        normalized[price_type] = (df[bid_col] + df[ask_col]) / 2
                    elif bid_col:
                        normalized[price_type] = df[bid_col]
                    elif ask_col:
                        normalized[price_type] = df[ask_col]
                    else:
                        self.logger.warning(f"Missing {price_type} price for {pair}")
                
                # Add spread if not present
                if 'bidclose' in df.columns and 'askclose' in df.columns and 'spread' not in df.columns:
                    normalized['spread'] = df['askclose'] - df['bidclose']
                
                # Add volume if missing
                if 'volume' not in df.columns and 'volume' not in normalized.columns:
                    # Check for tick volume or similar
                    vol_col = next((col for col in df.columns if 'vol' in str(col).lower() or 'tick' in str(col).lower()), None)
                    if vol_col:
                        normalized['volume'] = df[vol_col]
                    else:
                        normalized['volume'] = 1  # Default value
            
            # If we have Close but not close (case sensitivity)
            elif 'close' not in columns and any(c == 'close' for c in [str(c).lower() for c in df.columns]):
                self.logger.info(f"Detected capitalized column names for {pair}, converting to lowercase")
                
                # Find columns by lowercase matches
                column_mapping = {}
                for col in df.columns:
                    col_lower = str(col).lower()
                    if col_lower in ['open', 'high', 'low', 'close', 'volume']:
                        column_mapping[col] = col_lower
                
                # Rename columns
                renamed = df.rename(columns=column_mapping)
                
                # Add missing columns with reasonable defaults
                required_columns = ['open', 'high', 'low', 'close', 'volume']
                for col in required_columns:
                    if col not in renamed.columns:
                        if col == 'volume':
                            renamed[col] = 1
                        elif col == 'open' and 'close' in renamed.columns:
                            renamed[col] = renamed['close'].shift(1)
                        elif 'close' in renamed.columns:
                            renamed[col] = renamed['close']
                
                normalized = renamed
            
            # Ensure all required columns exist
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            for col in required_columns:
                if col not in normalized.columns:
                    self.logger.warning(f"Missing required column '{col}' for {pair}, using defaults")
                    if col == 'volume':
                        normalized[col] = 1
                    elif col == 'open' and 'close' in normalized.columns:
                        normalized[col] = normalized['close'].shift(1)
                    elif 'close' in normalized.columns:
                        normalized[col] = normalized['close']
                    else:
                        normalized[col] = 0
            
            # Add pip factor if not present
            if 'pip_factor' not in normalized.columns:
                normalized['pip_factor'] = 100.0 if 'JPY' in pair else 10000.0
            
            # Store the normalized DataFrame
            normalized_data[pair] = normalized[required_columns + ['pip_factor']]
            
            self.logger.info(f"Normalized {pair} price data: {normalized_data[pair].shape}")
        
        return normalized_data
    
    def _normalize_macro_data(self, data: pd.DataFrame, context: Dict[str, Any]) -> pd.DataFrame:
        """Normalize macro data format
        
        Args:
            data: Macro data DataFrame
            context: Pipeline context
            
        Returns:
            Normalized DataFrame
        """
        if not isinstance(data, pd.DataFrame) or data.empty:
            self.logger.warning("No macro data to normalize")
            return pd.DataFrame()
        
        self.logger.info("Normalizing macro data")
        
        # Create a copy to avoid modifying original
        normalized = data.copy()
        
        # Handle missing values
        self.logger.info("Handling missing values in macro data")
        normalized = normalized.fillna(method='ffill').fillna(method='bfill')
        
        # Handle infinite values
        self.logger.info("Checking for infinite values")
        normalized = normalized.replace([np.inf, -np.inf], np.nan)
        normalized = normalized.fillna(method='ffill').fillna(method='bfill')
        
        # Ensure consistent frequency (if daily data)
        if isinstance(normalized.index, pd.DatetimeIndex) and len(normalized) > 1:
            # Check if index is approximately daily
            time_diffs = normalized.index.to_series().diff().dropna()
            median_diff = time_diffs.median()
            
            # If close to daily, resample to daily
            if pd.Timedelta(hours=20) < median_diff < pd.Timedelta(hours=28):
                self.logger.info("Resampling macro data to daily frequency")
                normalized = normalized.resample('D').asfreq()
                normalized = normalized.fillna(method='ffill').fillna(method='bfill')
        
        self.logger.info(f"Normalized macro data: {normalized.shape}")
        return normalized