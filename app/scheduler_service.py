from datetime import datetime
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

class SchedulerService:
    def __init__(self, source_uri: str, source_db: str, source_collection: str,
                 target_uri: str, target_db: str, target_collection: str):
        """Initialize scheduler service with database connections"""
        self.source_client = AsyncIOMotorClient(source_uri)
        self.target_client = AsyncIOMotorClient(target_uri)
        
        self.source_db = self.source_client[source_db]
        self.target_db = self.target_client[target_db]
        
        self.source_collection = source_collection
        self.target_collection = target_collection
        
        self.is_running = False
        self.empty_checks = 0
        self.max_empty_checks = 5  # Stop after 5 empty checks

        print(f"✅ Scheduler initialized: {source_db}.{source_collection} -> {target_db}.{target_collection}")
    
    async def check_scheduled_content(self):
        """Check for content that needs to be published"""
        try:
            current_time = datetime.now()
            current_date = current_time.strftime("%Y-%m-%d")
            current_time_str = current_time.strftime("%H:%M")
            
            print(f"🔍 Checking for content at: {current_date} {current_time_str}")
            
            published_count = 0
            
            # Query for exact date and time match
            exact_match_query = {
                "status": "pending",
                "scheduled_date": current_date,
                "scheduled_time": current_time_str
            }
            
            exact_matches = self.source_db[self.source_collection].find(exact_match_query)
            async for content in exact_matches:
                print(f"✅ EXACT MATCH: {content.get('keyword', 'Unknown')} - {content.get('scheduled_date')} at {content.get('scheduled_time')}")
                await self.publish_content(content)
                published_count += 1
            
            # Query for overdue content (past dates)
            overdue_query = {
                "status": "pending",
                "scheduled_date": {"$lt": current_date}
            }
            
            overdue_matches = self.source_db[self.source_collection].find(overdue_query)
            async for content in overdue_matches:
                print(f"✅ OVERDUE: {content.get('keyword', 'Unknown')} - {content.get('scheduled_date')} at {content.get('scheduled_time')}")
                await self.publish_content(content)
                published_count += 1
            
            # Query for content scheduled for today but past time
            past_time_today_query = {
                "status": "pending",
                "scheduled_date": current_date,
                "scheduled_time": {"$lt": current_time_str}
            }
            
            past_time_matches = self.source_db[self.source_collection].find(past_time_today_query)
            async for content in past_time_matches:
                print(f"✅ PAST TIME TODAY: {content.get('keyword', 'Unknown')} - {content.get('scheduled_date')} at {content.get('scheduled_time')}")
                await self.publish_content(content)
                published_count += 1
            
            if published_count == 0:
                self.empty_checks += 1
                print(f"ℹ️ No content ready for publishing (Check {self.empty_checks}/{self.max_empty_checks})")
                if self.empty_checks >= self.max_empty_checks:
                    print("🛑 Scheduler paused due to no content")
                    self.is_running = False
            else:
                self.empty_checks = 0  # Reset counter when content is found
                print(f"📊 Published {published_count} items")

        except Exception as e:
            print(f"❌ Error in check_scheduled_content: {str(e)}")
            raise

    async def publish_content(self, content: dict):
        """Publish content to target database"""
        try:
            # Create formatted content with required fields and structure
            current_time = datetime.now()
            formatted_content = {
                "title": content.get('title'),
                "content": content.get('content'),
                "slug": content.get('slug'),
                "excerpt": content.get('excerpt', content.get('title', '')[:150]),
                "status": "published",
                "categoryIds": content.get('categoryIds', [{"$oid": "683b3aa5a6b031d7d737362d"}]),
                "tagIds": content.get('tagIds', [{"$oid": "683b3ab8a6b031d7d7373637"}]),
                "authorId": {"$oid": "683b3771a6b031d7d73735d7"},  # Default author ID
                "createdAt": current_time,  # Store as native Python datetime
                "updatedAt": current_time,  # Store as native Python datetime
                "__v": {"$numberInt": "0"}
            }

            print(f"📤 Publishing: {content.get('keyword', 'Unknown')}")
            
            # Insert formatted content to target collection
            await self.target_db[self.target_collection].insert_one(formatted_content)
            
            # Update status in source collection
            await self.source_db[self.source_collection].update_one(
                {"_id": content["_id"]},
                {"$set": {
                    "status": "published",
                    "published_at": datetime.now()
                }}
            )
            
            print(f"✅ Published: {content.get('keyword', 'Unknown')}")
            
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
                await asyncio.sleep(60)
            except Exception as e:
                print(f"❌ Scheduler error: {str(e)}")
                await asyncio.sleep(60)

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