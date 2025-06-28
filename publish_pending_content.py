#!/usr/bin/env python3
"""
Standalone script to change pending content status to published
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

async def publish_pending_content():
    """Change pending content status to published"""
    
    print("🚀 Starting Pending Content Publisher")
    print("=" * 50)
    
    # Database connection
    source_uri = os.getenv('MONGODB_URL')
    source_db = os.getenv('SOURCE_DB', 'scraper_db')
    source_collection = 'generated_content'
    
    if not source_uri:
        print("❌ MONGODB_URL not found in environment variables")
        return
    
    try:
        # Connect to source database
        client = AsyncIOMotorClient(source_uri)
        db = client[source_db]
        collection = db[source_collection]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Database connection successful")
        
        # Find pending content
        pending_content = await collection.find({"status": "pending"}).to_list(length=None)
        
        if not pending_content:
            print("ℹ️ No pending content found")
            return
        
        print(f"📝 Found {len(pending_content)} pending items")
        
        # Update all pending items to published
        result = await collection.update_many(
            {"status": "pending"},
            {"$set": {"status": "published", "published_at": datetime.now()}}
        )
        
        print(f"✅ Updated {result.modified_count} items from pending to published")
        print(f"✅ Processing complete!")
        
    except Exception as e:
        print(f"❌ Database error: {str(e)}")
    finally:
        client.close()

if __name__ == "__main__":
    asyncio.run(publish_pending_content()) 