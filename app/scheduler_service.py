from datetime import datetime
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from typing import List, Dict, Any
import re
from pymongo.errors import DuplicateKeyError
from pymongo import UpdateOne

class SchedulerService:
    def __init__(self, source_uri: str, source_db: str, source_collection: str,
                 target_uri: str = None, target_db: str = None, target_collection: str = "posts"):
        """Initialize scheduler service with database connections"""
        self.source_client = AsyncIOMotorClient(source_uri)
        
        # Use global variables for target database if not provided
        if target_uri is None or target_db is None:
            from app.routes import TARGET_DB_URI, TARGET_DB
            target_uri = TARGET_DB_URI
            target_db = TARGET_DB
        
        self.target_client = AsyncIOMotorClient(target_uri)
        
        self.source_db = self.source_client[source_db]
        self.target_db = self.target_client[target_db]
        
        self.source_collection = source_collection
        self.target_collection = target_collection
        
        self.is_running = False
        self.empty_checks = 0
        self.max_empty_checks = 5  # Stop after 5 empty checks
        self.categories_cache = None
        self.categories_cache_time = None

        print(f"✅ Scheduler initialized: {source_db}.{source_collection} -> {target_db}.{target_collection}")
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Fetch and cache categories from target database"""
        current_time = datetime.now()
        
        # Return cached categories if they're less than 1 hour old
        if self.categories_cache and self.categories_cache_time:
            age = (current_time - self.categories_cache_time).total_seconds()
            if age < 3600:  # 1 hour
                return self.categories_cache
        
        try:
            cursor = self.target_db.categories.find({})
            categories = await cursor.to_list(length=None)
            self.categories_cache = categories
            self.categories_cache_time = current_time
            return categories
        except Exception as e:
            print(f"❌ Error fetching categories: {str(e)}")
            return []

    def find_matching_categories(self, content: str, title: str, categories: List[Dict[str, Any]]) -> List[ObjectId]:
        """Find best matching categories based on content and title"""
        try:
            matched_categories = []
            content_lower = content.lower()
            title_lower = title.lower()
            
            for category in categories:
                category_name = category.get('name', '').lower()
                category_description = category.get('description', '').lower()
                
                # Check if category name or keywords appear in title or first 1000 chars of content
                if (category_name in title_lower or 
                    category_name in content_lower[:1000] or
                    any(keyword.lower() in title_lower for keyword in category.get('keywords', [])) or
                    any(keyword.lower() in content_lower[:1000] for keyword in category.get('keywords', []))):
                    matched_categories.append(ObjectId(category['_id']))
            
            # If no matches found, use default category
            if not matched_categories:
                matched_categories = [ObjectId("683b3aa5a6b031d7d737362d")]  # Default category
                
            return matched_categories
            
        except Exception as e:
            print(f"❌ Error matching categories: {str(e)}")
            return [ObjectId("683b3aa5a6b031d7d737362d")]  # Default category

    def generate_slug(self, title: str) -> str:
        """Generate a URL-friendly slug from title"""
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower().strip()
        # Remove special characters
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        # Replace spaces with hyphens
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug

    def format_datetime(self, dt: datetime) -> str:
        """Format datetime in the required format"""
        return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "+00:00"

    async def check_scheduled_content(self):
        """Check for content that needs to be published (date/time in the past and status 'pending')"""
        try:
            current_time = datetime.utcnow()
            current_date = current_time.strftime("%Y-%m-%d")
            current_time_str = current_time.strftime("%H:%M")

            print(f"🔍 Checking for content at (UTC): {current_date} {current_time_str}")

            published_count = 0

            # Query for content scheduled for now or in the past
            query = {
                "status": "pending",
                "$or": [
                    {"scheduled_date": {"$lt": current_date}},
                    {"scheduled_date": current_date, "scheduled_time": {"$lte": current_time_str}}
                ]
            }

            cursor = self.source_db[self.source_collection].find(query)
            async for content in cursor:
                print(f"✅ READY TO PUBLISH: {content.get('content', '')[:30]}... - {content.get('scheduled_date')} at {content.get('scheduled_time')}")
                await self.publish_content(content)
                published_count += 1

            if published_count == 0:
                self.empty_checks += 1
                print(f"ℹ️ No content ready for publishing")
            else:
                self.empty_checks = 0  # Reset counter when content is found
                print(f"📊 Published {published_count} items")

        except Exception as e:
            print(f"❌ Error in check_scheduled_content: {str(e)}")
            raise

    async def publish_content(self, content: dict):
        """Publish content to target database (strip scheduling fields, insert as-is, set status to published in both DBs)"""
        try:
            # Remove scheduling fields
            content_to_publish = dict(content)
            for key in ["scheduled_date", "scheduled_time"]:
                content_to_publish.pop(key, None)
            # Remove MongoDB _id to avoid duplicate key error
            content_to_publish.pop("_id", None)
            # Set status to published
            content_to_publish["status"] = "published"

            print("\n📦 CONTENT BEING PUSHED TO DATABASE:")
            print("=" * 80)
            print("Content:", str(content_to_publish)[:200] + ("..." if len(str(content_to_publish)) > 200 else ""))
            print("=" * 80)

            duplicate = False
            try:
                result = await self.target_db[self.target_collection].insert_one(content_to_publish)
                if result.inserted_id:
                    print(f"✅ Content saved with ID: {result.inserted_id}")
            except Exception as e:
                # Check for duplicate key error (slug)
                if hasattr(e, 'details') and e.details and e.details.get('code') == 11000:
                    print(f"⚠️ Duplicate slug detected. Marking as published without inserting.")
                    duplicate = True
                else:
                    print(f"❌ Error publishing content: {e}")
                    # Still update status below

            # Update status in source collection regardless of duplicate or other errors
            scheduled_date = content.get("scheduled_date")
            scheduled_time = content.get("scheduled_time")
            use_scheduled = False
            if scheduled_date and scheduled_time:
                try:
                    scheduled_dt = datetime.strptime(f"{scheduled_date} {scheduled_time}", "%Y-%m-%d %H:%M")
                    use_scheduled = True
                except Exception as e:
                    print(f"⚠️ Error parsing scheduled_date/time: {e}, using current UTC time.")
                    scheduled_dt = datetime.utcnow()
            else:
                scheduled_dt = datetime.utcnow()

            # Debug prints for createdAt, utcnow, and scheduled fields
            print(f"[SCHEDULER DEBUG] scheduled_date: {scheduled_date}")
            print(f"[SCHEDULER DEBUG] scheduled_time: {scheduled_time}")
            print(f"[SCHEDULER DEBUG] createdAt/updatedAt to be set: {scheduled_dt}")
            print(f"[SCHEDULER DEBUG] utcnow: {datetime.utcnow()}")

            await self.source_db[self.source_collection].update_one(
                {"_id": content["_id"]},
                {"$set": {
                    "status": "published",
                    "createdAt": scheduled_dt,
                    "updatedAt": scheduled_dt
                }}
            )
            print(f"✅ Published content (status updated in source DB).{' (Duplicate slug)' if duplicate else ''} {'(Used scheduled date/time)' if use_scheduled else '(Used UTC now)'}")

        except Exception as e:
            print(f"❌ Error publishing content: {str(e)}")
            
    async def start_scheduler(self):
        """Start the scheduler loop"""
        print("🚀 Starting scheduler...")
        self.is_running = True
        self.empty_checks = 0
        
        while self.is_running:
            try:
                await self.check_scheduled_content()
                await asyncio.sleep(300)
            except Exception as e:
                print(f"❌ Scheduler error: {str(e)}")
                await asyncio.sleep(300)

    def resume_scheduler(self):
        """Resume the scheduler"""
        if not self.is_running:
            print("▶️ Resuming scheduler...")
            self.empty_checks = 0  # Reset the counter when resuming
            asyncio.create_task(self.start_scheduler())
    
    def is_scheduler_running(self) -> bool:
        """Check if the scheduler is currently running"""
        return self.is_running

    async def test_connection(self):
        """Test database connections"""
        try:
            source_count = await self.source_db[self.source_collection].count_documents({})
            pending_count = await self.source_db[self.source_collection].count_documents({"status": "pending"})
            
            print(f"📊 Source collection has {source_count} documents ({pending_count} pending)")
            
            return True
        except Exception as e:
            print(f"❌ Connection test failed: {str(e)}")
            return False

    def update_target_connection(self, target_uri: str, target_db: str):
        """Update target database connection with new configuration"""
        try:
            # Close existing target connection
            if hasattr(self, 'target_client'):
                self.target_client.close()
            
            # Create new target connection
            self.target_client = AsyncIOMotorClient(target_uri)
            self.target_db = self.target_client[target_db]
            
            print(f"✅ Target database connection updated: {target_db}")
            return True
        except Exception as e:
            print(f"❌ Failed to update target database connection: {str(e)}")
            return False