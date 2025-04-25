# src/data_pipeline/loaders/base.py

import logging
from typing import Dict, Any, Optional
from ..components.base import PipelineComponent

class BaseLoader(PipelineComponent):
    """Base class for data loaders"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    def component_type(self) -> str:
        return 'loader'
    
    @abstractmethod
    def load_data(self, context: Dict[str, Any]) -> Any:
        """Load data from source
        
        Args:
            context: Pipeline context with loading parameters
            
        Returns:
            Loaded data
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process by loading data
        
        Args:
            data: Input data (ignored for loaders)
            context: Pipeline context information
            
        Returns:
            Loaded data
        """
        return self.load_data(context)