#!/usr/bin/env python3
"""
Script to check how many categories exist in the database
"""

import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

async def check_categories():
    """Check categories in the database"""
    
    print("🔍 Checking Categories in Database")
    print("=" * 50)
    
    # Get database connection details
    target_db_uri = os.getenv('TARGET_DB_URI')
    target_db_name = os.getenv('TARGET_DB', 'CRM')
    
    print(f"📊 Database Info:")
    print(f"   - URI: {target_db_uri}")
    print(f"   - Database: {target_db_name}")
    
    if not target_db_uri:
        print("❌ TARGET_DB_URI not found in environment variables")
        return
    
    try:
        # Connect to the target database
        client = AsyncIOMotorClient(target_db_uri)
        db = client[target_db_name]
        
        # Test connection
        await client.admin.command('ping')
        print("✅ Database connection successful")
        
        # Get categories count
        categories_count = await db.categories.count_documents({})
        print(f"📈 Total categories: {categories_count}")
        
        if categories_count > 0:
            # Get all categories
            categories = await db.categories.find({}, {
                '_id': 1,
                'name': 1,
                'description': 1
            }).to_list(length=None)
            
            print(f"\n📋 Categories List:")
            for i, cat in enumerate(categories, 1):
                print(f"   {i}. {cat.get('name', 'N/A')} (ID: {cat.get('_id')})")
                if cat.get('description'):
                    print(f"      Description: {cat.get('description')}")
            
            # Get category names for content generator
            category_names = [cat.get('name', '') for cat in categories if cat.get('name')]
            print(f"\n🎯 Category Names for Content Generator:")
            print(f"   {category_names}")
            
        else:
            print("❌ No categories found in database!")
            print("   You need to add categories to the 'categories' collection.")
        
        # Check if there are any subcategories
        subcategories_count = await db.categories.count_documents({"parentId": {"$exists": True}})
        print(f"\n📊 Subcategories: {subcategories_count}")
        
        # Close connection
        client.close()
        
    except Exception as e:
        print(f"❌ Error connecting to database: {str(e)}")

if __name__ == "__main__":
    asyncio.run(check_categories()) 