from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseIntegration(ABC):
    """Base class for all integrations."""
    
    def __init__(self):
        """Initialize the integration."""
        pass
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the integration."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to the integration."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the integration is healthy and working."""
        pass
    
    @abstractmethod
    async def publish(self, data: Dict[str, Any]) -> bool:
        """Publish data to the integration."""
        pass
    
    @abstractmethod
    async def get_status(self, reference_id: str) -> Optional[Dict[str, Any]]:
        """Get status of a published item."""
        pass 