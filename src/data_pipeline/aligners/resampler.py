# src/data_pipeline/aligners/resampler.py

import pandas as pd
import numpy as np
from typing import Dict, Any, Union, List, Optional
from .base import BaseAligner

class TimeResampler(BaseAligner):
    """Resamples time series data to different frequencies"""
    
    def align_data(self, data: Any, context: Dict[str, Any]) -> Any:
        """Resample time series data to target frequency
        
        Args:
            data: Input data (Dict[str, pd.DataFrame] or pd.DataFrame)
            context: Pipeline context with parameters:
                - target_timeframe: Target timeframe (e.g., '1H', '4H', 'D')
                
        Returns:
            Resampled data
        """
        target_timeframe = context.get('target_timeframe')
        if not target_timeframe:
            self.logger.warning("No target timeframe specified for resampling")
            return data
            
        self.logger.info(f"Resampling data to {target_timeframe}")
        
        if isinstance(data, dict):
            # Process dictionary of dataframes
            result = {}
            for key, df in data.items():
                try:
                    result[key] = self._resample_dataframe(df, target_timeframe, context)
                    self.logger.info(f"Resampled {key} to {target_timeframe}: {len(result[key])} rows")
                except Exception as e:
                    self.logger.error(f"Error resampling {key}: {str(e)}")
                    result[key] = df  # Keep original on error
            return result
            
        elif isinstance(data, pd.DataFrame):
            # Process single dataframe
            return self._resample_dataframe(data, target_timeframe, context)
            
        else:
            self.logger.warning(f"Unsupported data type for resampling: {type(data)}")
            return data
    
    def _resample_dataframe(self, df: pd.DataFrame, target_timeframe: str, 
                          context: Dict[str, Any]) -> pd.DataFrame:
        """Resample a single dataframe
        
        Args:
            df: Input dataframe
            target_timeframe: Target timeframe
            context: Pipeline context
            
        Returns:
            Resampled dataframe
        """
        # Make sure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        # Detect price data based on columns
        is_price_data = all(col in df.columns for col in ['open', 'high', 'low', 'close'])
        
        if is_price_data:
            return self._resample_ohlc(df, target_timeframe, context)
        else:
            # For non-OHLC data, use standard resampling
            return self._resample_standard(df, target_timeframe, context)
    
    def _resample_ohlc(self, df: pd.DataFrame, target_timeframe: str, 
                      context: Dict[str, Any]) -> pd.DataFrame:
        """Resample OHLC price data
        
        Args:
            df: Price dataframe with OHLC columns
            target_timeframe: Target timeframe
            context: Pipeline context
            
        Returns:
            Resampled OHLC dataframe
        """
        # OHLC resampling rules
        resampler = df.resample(target_timeframe)
        
        result = pd.DataFrame({
            'open': resampler['open'].first(),
            'high': resampler['high'].max(),
            'low': resampler['low'].min(),
            'close': resampler['close'].last(),
        })
        
        # Handle volume if present
        if 'volume' in df.columns:
            result['volume'] = resampler['volume'].sum()
        
        # Handle pip_factor if present
        if 'pip_factor' in df.columns:
            result['pip_factor'] = df['pip_factor'].iloc[0]  # Take first value
        
        # Carry forward any other columns with last value
        for col in df.columns:
            if col not in result.columns:
                result[col] = resampler[col].last()
        
        return result
    
    def _resample_standard(self, df: pd.DataFrame, target_timeframe: str, 
                         context: Dict[str, Any]) -> pd.DataFrame:
        """Resample standard (non-OHLC) data
        
        Args:
            df: Non-OHLC dataframe
            target_timeframe: Target timeframe
            context: Pipeline context
            
        Returns:
            Resampled dataframe
        """
        # Determine appropriate method based on data and context
        method = context.get('resample_method', 'last')
        
        if method == 'last':
            return df.resample(target_timeframe).last()
        elif method == 'mean':
            return df.resample(target_timeframe).mean()
        elif method == 'sum':
            return df.resample(target_timeframe).sum()
        elif method == 'interpolate':
            # Resample with last and then interpolate
            resampled = df.resample(target_timeframe).last()
            return resampled.interpolate(method='time')
        else:
            # Default to last value
            return df.resample(target_timeframe).last()
    
    def downsample(self, data: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """Convenience method for downsampling (e.g., 1H -> 4H)
        
        Args:
            data: Input dataframe
            target_timeframe: Target timeframe
            
        Returns:
            Downsampled dataframe
        """
        return self._resample_dataframe(data, target_timeframe, {'resample_method': 'last'})
    
    def upsample(self, data: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """Convenience method for upsampling (e.g., D -> 1H)
        
        Args:
            data: Input dataframe
            target_timeframe: Target timeframe
            
        Returns:
            Upsampled dataframe
        """
        return self._resample_dataframe(data, target_timeframe, {'resample_method': 'interpolate'})