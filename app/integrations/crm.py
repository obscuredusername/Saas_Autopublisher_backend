from datetime import datetime
from typing import Any, Dict, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from ..config.settings import get_settings
from .base import BaseIntegration

class CRMIntegration(BaseIntegration):
    """Integration with CRM system."""
    
    def __init__(self):
        """Initialize CRM integration."""
        super().__init__()
        self.settings = get_settings()
        self.client = None
        self.db = None
        self.collection = None
        
    async def connect(self) -> bool:
        """Connect to CRM database."""
        try:
            self.client = AsyncIOMotorClient(self.settings.CRM_DB_URI)
            self.db = self.client[self.settings.CRM_DB_NAME]
            self.collection = self.db[self.settings.CRM_COLLECTION_NAME]
            return True
        except Exception as e:
            print(f"❌ CRM connection error: {str(e)}")
            return False
            
    async def disconnect(self) -> bool:
        """Disconnect from CRM database."""
        try:
            if self.client:
                self.client.close()
            return True
        except Exception as e:
            print(f"❌ CRM disconnect error: {str(e)}")
            return False
            
    async def health_check(self) -> bool:
        """Check CRM connection health."""
        try:
            if not self.client:
                await self.connect()
            await self.collection.find_one()
            return True
        except Exception as e:
            print(f"❌ CRM health check error: {str(e)}")
            return False
            
    async def publish(self, data: Dict[str, Any]) -> bool:
        """Publish content to CRM."""
        try:
            if not self.client:
                await self.connect()
                
            # Get current timestamp in local timezone and format it properly
            current_time = datetime.now()
            formatted_timestamp = current_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00"
            
            # Create formatted content with EXACT structure matching requirements
            crm_data = {
                "_id": ObjectId(),  # Generate a proper ObjectId
                "title": data.get('title', ''),
                "content": data.get('content', ''),
                "slug": data.get('slug', ''),
                "excerpt": data.get('excerpt', data.get('title', '')[:150]),
                "status": "published",
                "categoryIds": data.get('categoryIds', [ObjectId("683b3aa5a6b031d7d737362d")]),  # Default category
                "tagIds": data.get('tagIds', [ObjectId("683b3ab8a6b031d7d7373637")]),  # Default tag
                "authorId": ObjectId("683b3771a6b031d7d73735d7"),  # Author ID
                "createdAt": formatted_timestamp,  # ISO format with T and timezone
                "updatedAt": formatted_timestamp,  # Same timestamp for both fields
                "__v": 0  # Version field as integer
            }
            
            print(f"📤 Publishing: {data.get('keyword', 'Unknown')}")
            
            # Print the formatted content being pushed to database
            print("🔍 DATA BEING PUSHED TO TARGET DB:")
            print("=" * 50)
            for key, value in crm_data.items():
                print(f"{key}: {value}")
            print("=" * 50)
            
            result = await self.collection.insert_one(crm_data)
            return bool(result.inserted_id)
            
        except Exception as e:
            print(f"❌ CRM publish error: {str(e)}")
            return False
            
    async def get_status(self, reference_id: str) -> Optional[Dict[str, Any]]:
        """Get status of published content in CRM."""
        try:
            if not self.client:
                await self.connect()
                
            result = await self.collection.find_one({"_id": ObjectId(reference_id)})
            if result:
                return {
                    "status": result.get("status", "unknown"),
                    "published_at": result.get("createdAt"),
                    "url": result.get("url")
                }
            return None
            
        except Exception as e:
            print(f"❌ CRM status check error: {str(e)}")
            return None 