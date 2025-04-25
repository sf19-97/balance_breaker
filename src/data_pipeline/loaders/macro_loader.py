# src/data_pipeline/loaders/macro_loader.py

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from .base import BaseLoader

class MacroLoader(BaseLoader):
    """Loader for macroeconomic data"""
    
    def __init__(self, repository_path: Optional[str] = None):
        super().__init__()
        self.repository_path = repository_path
    
    def load_data(self, context: Dict[str, Any]) -> pd.DataFrame:
        """Load macroeconomic data
        
        Args:
            context: Pipeline context with parameters:
                - start_date: Start date (YYYY-MM-DD)
                - end_date: End date (YYYY-MM-DD)
                - repository: Repository name (optional)
                
        Returns:
            DataFrame with macroeconomic indicators
        """
        start_date = context.get('start_date')
        end_date = context.get('end_date')
        repository = context.get('repository')
        
        # Determine repository path
        repo_path = self.repository_path
        if repository:
            # Use repository from context if specified
            if 'repository_config' in context and repository in context['repository_config'].get('macro', {}):
                repo_config = context['repository_config']['macro'][repository]
                repo_path = repo_config.get('directory')
        
        if not repo_path:
            # Default to data/macro if no path specified
            repo_path = os.path.join('data', 'macro')
            self.logger.info(f"Using default repository path: {repo_path}")
        
        # Check if directory exists
        if not os.path.exists(repo_path):
            self.logger.error(f"Repository directory not found: {repo_path}")
            return pd.DataFrame()
        
        # Look for derived indicators first
        derived_path = os.path.join(repo_path, 'derived_indicators.csv')
        if os.path.exists(derived_path):
            self.logger.info(f"Loading derived indicators from {derived_path}")
            try:
                macro_df = pd.read_csv(derived_path, index_col=0, parse_dates=True)
                
                # Apply date filtering
                if start_date:
                    macro_df = macro_df[macro_df.index >= start_date]
                if end_date:
                    macro_df = macro_df[macro_df.index <= end_date]
                
                return macro_df
            except Exception as e:
                self.logger.error(f"Error loading derived indicators: {str(e)}")
        
        # If derived indicators not found, load individual files
        all_data = {}
        
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith('.csv') and 'macro_' in file:
                    file_path = os.path.join(root, file)
                    try:
                        # Extract indicator name from filename
                        indicator = os.path.splitext(file)[0].split('_')[-1]
                        
                        # Load data
                        self.logger.debug(f"Loading macro data from {file_path}")
                        df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                        
                        # If single column, use indicator as column name
                        if len(df.columns) == 1:
                            all_data[indicator] = df.iloc[:, 0]
                        else:
                            # Multiple columns, merge all
                            for col in df.columns:
                                all_data[f"{indicator}_{col}"] = df[col]
                    except Exception as e:
                        self.logger.error(f"Error loading {file}: {str(e)}")
        
        # Combine all series into a DataFrame
        if all_data:
            macro_df = pd.DataFrame(all_data)
            
            # Fill NaN values
            self.logger.info("Filling NaN values in macro data")
            macro_df = macro_df.fillna(method='ffill').fillna(method='bfill')
            
            # Check for infinite values and replace with NaN, then fill
            self.logger.info("Checking for infinite values")
            macro_df = macro_df.replace([np.inf, -np.inf], np.nan)
            macro_df = macro_df.fillna(method='ffill').fillna(method='bfill')
            
            # Apply date filtering
            if start_date:
                macro_df = macro_df[macro_df.index >= start_date]
            if end_date:
                macro_df = macro_df[macro_df.index <= end_date]
            
            self.logger.info(f"Loaded macro data with {len(macro_df.columns)} indicators")
            return macro_df
        else:
            self.logger.warning(f"No valid macro data found in {repo_path}")
            return pd.DataFrame()