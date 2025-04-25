# src/data_pipeline/aligners/base.py

import logging
from typing import Dict, Any, Optional
from ..components.base import PipelineComponent

class BaseAligner(PipelineComponent):
    """Base class for data aligners"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    def component_type(self) -> str:
        return 'aligner'
    
    @abstractmethod
    def align_data(self, data: Any, context: Dict[str, Any]) -> Any:
        """Align data according to component logic
        
        Args:
            data: Input data to align
            context: Pipeline context
            
        Returns:
            Aligned data
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process by aligning data
        
        Args:
            data: Input data
            context: Pipeline context information
            
        Returns:
            Aligned data
        """
        return self.align_data(data, context)