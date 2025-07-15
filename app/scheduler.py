import asyncio
import os
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
from typing import List, Dict, Any
import re
from pymongo.errors import DuplicateKeyError
from pymongo import UpdateOne
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scheduler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ContentScheduler:
    def __init__(self):
        self.source_uri = os.getenv('MONGODB_URL')
        self.target_uri = os.getenv('TARGET_DB_URI')
        self.source_db = os.getenv('SOURCE_DB', 'scraper_db')
        self.target_db = os.getenv('TARGET_DB', 'CRM')
        self.source_collection = os.getenv('SOURCE_COLLECTION', 'generated_content')
        self.target_collection = os.getenv('TARGET_COLLECTION', 'posts')
        self.publish_interval_minutes = int(os.getenv('PUBLISH_INTERVAL_MINUTES', '150'))
        
        # Initialize database connections
        self.source_client = None
        self.target_client = None
        self.source_db_instance = None
        self.target_db_instance = None
        self.is_running = False

    async def initialize_connections(self):
        """Initialize database connections"""
        try:
            self.source_client = AsyncIOMotorClient(self.source_uri)
            self.target_client = AsyncIOMotorClient(self.target_uri)
            
            self.source_db_instance = self.source_client[self.source_db]
            self.target_db_instance = self.target_client[self.target_db]
            
            logger.info(f"✅ Database connections initialized")
            logger.info(f"📊 Source: {self.source_db}.{self.source_collection}")
            logger.info(f"📊 Target: {self.target_db}.{self.target_collection}")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connections: {str(e)}")
            raise

    async def close_connections(self):
        """Close database connections"""
        try:
            if self.source_client:
                self.source_client.close()
            if self.target_client:
                self.target_client.close()
            logger.info("✅ Database connections closed")
        except Exception as e:
            logger.error(f"❌ Error closing connections: {str(e)}")

    async def start_scheduler(self):
        """Start the scheduler loop, publishing one post every X minutes."""
        try:
            await self.initialize_connections()
            
            self.is_running = True
            empty_checks = 0
            max_empty_checks = 5  # Stop after 5 empty checks
            
            logger.info(f"🚀 Starting scheduler ({self.publish_interval_minutes} min interval)...")
            logger.info(f"✅ Scheduler initialized: {self.source_db}.{self.source_collection} -> {self.target_db}.{self.target_collection}")

            while self.is_running:
                try:
                    # Check for scheduled content
                    await self.check_scheduled_content()
                    logger.info(f"⏰ Next check in {self.publish_interval_minutes} minutes...")
                    await asyncio.sleep(self.publish_interval_minutes * 60)
                except Exception as e:
                    logger.error(f"❌ Scheduler error: {str(e)}")
                    await asyncio.sleep(self.publish_interval_minutes * 60)
                    
        except Exception as e:
            logger.error(f"❌ Fatal scheduler error: {str(e)}")
        finally:
            await self.close_connections()

    async def check_scheduled_content(self):
        """Publish the oldest pending post, regardless of scheduled time."""
        try:
            # Find the oldest pending post
            content = await self.source_db_instance[self.source_collection].find_one(
                {"status": "pending"},
                sort=[("createdAt", 1)]  # Use createdAt to determine order
            )
            if content:
                logger.info(f"✅ READY TO PUBLISH: {content.get('title', content.get('content', '')[:30])}...")
                await self.publish_content(content)
            else:
                logger.info(f"ℹ️ No pending content found")
        except Exception as e:
            logger.error(f"❌ Error in check_scheduled_content: {str(e)}")
            raise

    async def publish_content(self, content: dict):
        """Publish content to target database (strip scheduling fields, insert as-is, set status to published in both DBs)"""
        try:
            # Remove MongoDB _id to avoid duplicate key error
            content_to_publish = dict(content)
            content_to_publish.pop("_id", None)
            # Set status to published
            content_to_publish["status"] = "published"

            # Log the publish attempt with timestamp
            publish_time = datetime.now(timezone.utc)
            logger.info(f"[PUBLISH LOG] {publish_time.strftime('%Y-%m-%d %H:%M:%S %Z')} - Attempting to publish: {content_to_publish.get('title', str(content_to_publish)[:30])}")

            logger.info("\n📤 CONTENT BEING PUSHED TO DATABASE:")
            logger.info("=" * 80)
            logger.info(f"Content: {str(content_to_publish)[:200]}{'...' if len(str(content_to_publish)) > 200 else ''}")
            logger.info("=" * 80)

            duplicate = False
            try:
                result = await self.target_db_instance[self.target_collection].insert_one(content_to_publish)
                if result.inserted_id:
                    logger.info(f"✅ Content saved with ID: {result.inserted_id}")
            except Exception as e:
                # Check for duplicate key error (slug)
                if hasattr(e, 'details') and e.details and e.details.get('code') == 11000:
                    logger.warning(f"⚠️ Duplicate slug detected. Marking as published without inserting.")
                    duplicate = True
                else:
                    logger.error(f"❌ Error publishing content: {e}")
                    # Still update status below

            # Update status in source collection regardless of duplicate or other errors
            utc_timestamp = publish_time.timestamp()

            await self.source_db_instance[self.source_collection].update_one(
                {"_id": content["_id"]},
                {"$set": {
                    "status": "published",
                    "createdAt": utc_timestamp,
                    "updatedAt": utc_timestamp
                }}
            )
            logger.info(f"✅ Published content (status updated in source DB).{' (Duplicate slug)' if duplicate else ''} (Used UTC now) [PUBLISHED AT: {publish_time.strftime('%Y-%m-%d %H:%M:%S %Z')}]\n")

        except Exception as e:
            logger.error(f"❌ Error publishing content: {str(e)}")

    async def stop_scheduler(self):
        """Stop the scheduler"""
        self.is_running = False
        logger.info("🛑 Scheduler stop requested")

# Global scheduler instance
scheduler = None
scheduler_task = None

async def start_scheduler_background():
    """Start the scheduler in the background"""
    global scheduler, scheduler_task
    
    try:
        scheduler = ContentScheduler()
        scheduler_task = asyncio.create_task(scheduler.start_scheduler())
        logger.info("🚀 Background scheduler started")
        return scheduler_task
    except Exception as e:
        logger.error(f"❌ Failed to start background scheduler: {str(e)}")
        raise

async def stop_scheduler_background():
    """Stop the background scheduler"""
    global scheduler, scheduler_task
    
    try:
        if scheduler:
            await scheduler.stop_scheduler()
        if scheduler_task and not scheduler_task.done():
            scheduler_task.cancel()
            try:
                await scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Background scheduler stopped")
    except Exception as e:
        logger.error(f"❌ Error stopping background scheduler: {str(e)}")

# For standalone execution
async def main():
    """Main function for standalone execution"""
    try:
        await start_scheduler_background()
        # Keep the scheduler running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Received interrupt signal")
    except Exception as e:
        logger.error(f"❌ Main scheduler error: {str(e)}")
    finally:
        await stop_scheduler_background()

if __name__ == "__main__":
    asyncio.run(main()) 