#!/usr/bin/env python3
"""
Test script to debug category selection issues
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

async def test_category_selection():
    """Test category selection functionality"""
    
    print("🧪 Testing Category Selection Functionality")
    print("=" * 60)
    
    async with aiohttp.ClientSession() as session:
        
        # 1. Test processing a simple keyword to see category selection
        print("\n1. 🚀 Testing keyword processing with category selection...")
        test_keywords = [
            {"text": "elon musk", "minLength": 0}
        ]
        
        test_request = {
            "keywords": test_keywords,
            "country": "us",
            "language": "en",
            "user_email": "test@example.com"
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/keywords", json=test_request) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Keyword processing initiated: {result['message']}")
                    print(f"   - Tasks scheduled: {len(result['tasks'])}")
                else:
                    print(f"❌ Failed to process keywords: {response.status}")
                    return
        except Exception as e:
            print(f"❌ Error processing keywords: {str(e)}")
            return
        
        # 2. Wait for processing to complete
        print("\n2. ⏳ Waiting for processing to complete...")
        print("   This may take 1-2 minutes...")
        await asyncio.sleep(120)  # 2 minutes
        
        # 3. Check the generated content to see if categories were selected
        print("\n3. 📊 Checking generated content for category selection...")
        try:
            async with session.get(f"{API_BASE_URL}/scheduled-content") as response:
                if response.status == 200:
                    content_data = await response.json()
                    print(f"✅ Retrieved {len(content_data)} content items")
                    
                    for item in content_data:
                        print(f"\n📄 Content Item:")
                        print(f"   - Title: {item.get('title', 'N/A')}")
                        print(f"   - Keyword: {item.get('focusKeyword', 'N/A')}")
                        print(f"   - Categories: {item.get('categoryIds', [])}")
                        print(f"   - Tags: {item.get('tagIds', [])}")
                        print(f"   - Status: {item.get('status', 'N/A')}")
                        print(f"   - Word Count: {item.get('readingTime', 'N/A')} (estimated)")
                        
                        # Check if categories were assigned
                        category_ids = item.get('categoryIds', [])
                        if category_ids:
                            print(f"   ✅ Categories assigned: {len(category_ids)} categories")
                        else:
                            print(f"   ❌ No categories assigned!")
                            
                else:
                    print(f"❌ Failed to get scheduled content: {response.status}")
        except Exception as e:
            print(f"❌ Error getting scheduled content: {str(e)}")
        
        # 4. Test the processing statistics to see success rate
        print("\n4. 📈 Checking processing statistics...")
        try:
            async with session.get(f"{API_BASE_URL}/processing-stats?days=1") as response:
                if response.status == 200:
                    stats = await response.json()
                    print("✅ Processing statistics:")
                    print(f"   - Successful content: {stats['statistics']['successful_content']}")
                    print(f"   - Failed keywords: {stats['statistics']['failed_keywords']}")
                    print(f"   - Success rate: {stats['statistics']['success_rate']}%")
                    
                    if stats['statistics']['failure_breakdown']:
                        print(f"   - Failure breakdown:")
                        for failure in stats['statistics']['failure_breakdown']:
                            print(f"     * {failure['_id']}: {failure['count']} failures")
                else:
                    print(f"❌ Failed to get processing statistics: {response.status}")
        except Exception as e:
            print(f"❌ Error getting processing statistics: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting Category Selection Test")
    print(f"📅 Test started at: {datetime.now()}")
    print("=" * 60)
    print("This test will:")
    print("1. Process a simple keyword")
    print("2. Wait for processing to complete")
    print("3. Check if categories were selected")
    print("4. Show processing statistics")
    print("=" * 60)
    
    try:
        asyncio.run(test_category_selection())
        print("\n✅ Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
    
    print(f"📅 Test ended at: {datetime.now()}") 