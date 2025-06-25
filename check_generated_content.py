#!/usr/bin/env python3
"""
Script to check generated content in the database
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

async def check_generated_content():
    """Check generated content in the database"""
    
    print("🔍 Checking Generated Content in Database")
    print("=" * 50)
    
    # Get database connection details
    db_uri = os.getenv('MONGODB_URI')
    db_name = os.getenv('MONGODB_DB', 'saas_autopublisher')
    
    print(f"📊 Database Info:")
    print(f"   - URI: {db_uri}")
    print(f"   - Database: {db_name}")
    
    if not db_uri:
        print("❌ MONGODB_URI not found in environment variables")
        return
    
    try:
        # Connect to the database
        client = AsyncIOMotorClient(db_uri)
        db = client[db_name]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Database connection successful")
        
        # Get recent generated content (last 24 hours)
        yesterday = datetime.now() - timedelta(days=1)
        
        # Check generated_content collection
        generated_count = await db.generated_content.count_documents({
            "createdAt": {"$gte": yesterday}
        })
        print(f"📈 Recent generated content (last 24h): {generated_count}")
        
        if generated_count > 0:
            # Get recent content
            recent_content = await db.generated_content.find({
                "createdAt": {"$gte": yesterday}
            }, {
                '_id': 1,
                'title': 1,
                'focusKeyword': 1,
                'categoryIds': 1,
                'tagIds': 1,
                'status': 1,
                'createdAt': 1,
                'user_email': 1
            }).sort("createdAt", -1).limit(10).to_list(length=None)
            
            print(f"\n📋 Recent Generated Content:")
            for i, content in enumerate(recent_content, 1):
                print(f"\n   {i}. Content Item:")
                print(f"      - ID: {content.get('_id')}")
                print(f"      - Title: {content.get('title', 'N/A')}")
                print(f"      - Keyword: {content.get('focusKeyword', 'N/A')}")
                print(f"      - Categories: {content.get('categoryIds', [])}")
                print(f"      - Tags: {content.get('tagIds', [])}")
                print(f"      - Status: {content.get('status', 'N/A')}")
                print(f"      - User: {content.get('user_email', 'N/A')}")
                print(f"      - Created: {content.get('createdAt', 'N/A')}")
                
                # Check if categories were assigned
                category_ids = content.get('categoryIds', [])
                if category_ids:
                    print(f"      ✅ Categories assigned: {len(category_ids)} categories")
                else:
                    print(f"      ❌ No categories assigned!")
        
        # Check unprocessed_keywords collection
        unprocessed_count = await db.unprocessed_keywords.count_documents({
            "created_at": {"$gte": yesterday}
        })
        print(f"\n📊 Recent unprocessed keywords (last 24h): {unprocessed_count}")
        
        if unprocessed_count > 0:
            unprocessed_keywords = await db.unprocessed_keywords.find({
                "created_at": {"$gte": yesterday}
            }, {
                'keyword': 1,
                'error': 1,
                'stage': 1,
                'created_at': 1
            }).sort("created_at", -1).limit(5).to_list(length=None)
            
            print(f"\n❌ Recent Unprocessed Keywords:")
            for i, keyword in enumerate(unprocessed_keywords, 1):
                print(f"   {i}. {keyword.get('keyword', 'N/A')} - Failed at: {keyword.get('stage', 'N/A')} - Error: {keyword.get('error', 'N/A')}")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_generated_content()) 