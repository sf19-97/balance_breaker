# src/data_pipeline/validators/base.py

import logging
from typing import Dict, Any, Optional, List
from ..components.base import PipelineComponent

class BaseValidator(PipelineComponent):
    """Base class for data validators"""
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    def component_type(self) -> str:
        return 'validator'
    
    @abstractmethod
    def validate(self, data: Any, context: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the data
        
        Args:
            data: Input data to validate
            context: Pipeline context
            
        Returns:
            Validation results
        """
        pass
    
    def process(self, data: Any, context: Dict[str, Any]) -> Any:
        """Process by validating data
        
        Args:
            data: Input data
            context: Pipeline context information
            
        Returns:
            Original data with validation results added to context
        """
        validation_results = self.validate(data, context)
        
        # Add validation results to context
        if 'validation' not in context:
            context['validation'] = {}
        
        context['validation'].update(validation_results)
        
        # Return original data
        return data