# src/data_pipeline/loaders/price_loader.py

import os
import pandas as pd
from typing import Dict, Any, List, Optional
from datetime import datetime
from .base import BaseLoader

class PriceLoader(BaseLoader):
    """Loader for price data from repositories"""
    
    def __init__(self, repository_path: Optional[str] = None):
        super().__init__()
        self.repository_path = repository_path
    
    def load_data(self, context: Dict[str, Any]) -> Dict[str, pd.DataFrame]:
        """Load price data from repository
        
        Args:
            context: Pipeline context with parameters:
                - pairs: List of currency pairs
                - start_date: Start date (YYYY-MM-DD)
                - end_date: End date (YYYY-MM-DD)
                - repository: Repository name (optional)
                
        Returns:
            Dictionary of DataFrames with pair as key
        """
        pairs = context.get('pairs', [])
        start_date = context.get('start_date')
        end_date = context.get('end_date')
        repository = context.get('repository')
        
        if not pairs:
            self.logger.warning("No pairs specified for loading")
            return {}
        
        # Determine repository path
        repo_path = self.repository_path
        if repository:
            # Use repository from context if specified
            if 'repository_config' in context and repository in context['repository_config'].get('price', {}):
                repo_config = context['repository_config']['price'][repository]
                repo_path = repo_config.get('directory')
        
        if not repo_path:
            # Default to data/price if no path specified
            repo_path = os.path.join('data', 'price')
            self.logger.info(f"Using default repository path: {repo_path}")
        
        # Load each pair
        data = {}
        for pair in pairs:
            try:
                # Find file for pair
                file_path = self._find_pair_file(repo_path, pair)
                if not file_path:
                    self.logger.warning(f"No file found for pair {pair} in {repo_path}")
                    continue
                
                # Load the data
                self.logger.info(f"Loading price data for {pair} from {file_path}")
                df = pd.read_csv(file_path, index_col=0, parse_dates=True)
                
                # Apply date filtering
                if start_date:
                    df = df[df.index >= start_date]
                if end_date:
                    df = df[df.index <= end_date]
                
                # Store in result dictionary
                data[pair] = df
                self.logger.info(f"Loaded {len(df)} rows for {pair}")
                
            except Exception as e:
                self.logger.error(f"Error loading data for {pair}: {str(e)}")
        
        return data
    
    def _find_pair_file(self, directory: str, pair: str) -> Optional[str]:
        """Find data file for the specified pair"""
        # Common extensions to check
        extensions = ['.csv', '.CSV', '.txt', '.TXT']
        
        if not os.path.exists(directory):
            self.logger.error(f"Repository directory not found: {directory}")
            return None
        
        # Track all candidate files
        candidates = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                file_path = os.path.join(root, file)
                
                # Check if filename contains pair name and has correct extension
                if pair.lower() in file.lower() and any(file.lower().endswith(ext.lower()) for ext in extensions):
                    candidates.append(file_path)
                    
                    # Exact match prioritization
                    if file.lower() == f"{pair.lower()}.csv" or file.lower() == f"{pair.lower()}_h1.csv":
                        self.logger.debug(f"Found exact match for {pair}: {file}")
                        return file_path
        
        # Return first candidate if any found
        if candidates:
            self.logger.debug(f"Found candidate match for {pair}: {os.path.basename(candidates[0])}")
            return candidates[0]
        
        # No candidates found
        return None