# src/data_pipeline/processors/base.py

import logging
from typing import Dict, Any, Optional
from ..components.base import PipelineComponent

class BaseProcessor(PipelineComponent):
    """Base class for data processors"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    def component_type(self) -> str:
        return 'processor'
    
    @abstractmethod
    def process_data(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process the data
        
        Args:
            data: Input data to process
            context: Pipeline context
            
        Returns:
            Processed data
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process data using process_data method
        
        Args:
            data: Input data
            context: Pipeline context information
            
        Returns:
            Processed data
        """
        return self.process_data(data, context)