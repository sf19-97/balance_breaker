# src/data_pipeline/indicators/base.py

import logging
from typing import Dict, Any, Optional, List, Union
from ..components.base import PipelineComponent

class BaseIndicator(PipelineComponent):
    """Base class for indicators"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._parameters = {}
    
    @property
    def component_type(self) -> str:
        return 'indicator'
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get indicator parameters"""
        return self._parameters
    
    @parameters.setter
    def parameters(self, params: Dict[str, Any]) -> None:
        """Set indicator parameters"""
        self._parameters = params
    
    @abstractmethod
    def calculate(self, data: Any, context: Dict[str, Any]) -> Any:
        """Calculate indicator values
        
        Args:
            data: Input data
            context: Pipeline context
            
        Returns:
            Data with indicator values added
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process by calculating indicators
        
        Args:
            data: Input data
            context: Pipeline context information
            
        Returns:
            Data with indicator values added
        """
        return self.calculate(data, context)