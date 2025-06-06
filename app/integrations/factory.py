from typing import Dict, Optional, Type
from .base import BaseIntegration
from .crm import CRMIntegration

class IntegrationFactory:
    """Factory class to manage all integrations."""
    
    _integrations: Dict[str, Type[BaseIntegration]] = {
        "crm": CRMIntegration
    }
    
    _instances: Dict[str, BaseIntegration] = {}
    
    @classmethod
    def get_integration(cls, integration_type: str) -> Optional[BaseIntegration]:
        """Get an integration instance by type."""
        integration_type = integration_type.lower()
        
        # Return existing instance if available
        if integration_type in cls._instances:
            return cls._instances[integration_type]
            
        # Create new instance if integration type exists
        if integration_type in cls._integrations:
            instance = cls._integrations[integration_type]()
            cls._instances[integration_type] = instance
            return instance
            
        return None
    
    @classmethod
    def register_integration(cls, name: str, integration_class: Type[BaseIntegration]) -> None:
        """Register a new integration type."""
        cls._integrations[name.lower()] = integration_class
        
    @classmethod
    async def close_all(cls) -> None:
        """Close all active integration connections."""
        for instance in cls._instances.values():
            await instance.disconnect()
        cls._instances.clear() 