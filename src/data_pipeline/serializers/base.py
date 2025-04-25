# src/data_pipeline/serializers/base.py

import logging
from typing import Dict, Any, Optional
from ..components.base import PipelineComponent

class BaseSerializer(PipelineComponent):
    """Base class for data serializers"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    def component_type(self) -> str:
        return 'serializer'
    
    @abstractmethod
    def serialize(self, data: Any, context: Dict[str, Any]) -> Any:
        """Serialize data according to component logic
        
        Args:
            data: Input data to serialize
            context: Pipeline context
            
        Returns:
            Serialized data or original data with serialization results added to context
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process by serializing data
        
        Args:
            data: Input data
            context: Pipeline context information
            
        Returns:
            Serialized data or original data (with serialization results in context)
        """
        return self.serialize(data, context)