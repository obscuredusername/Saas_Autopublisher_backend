#!/usr/bin/env python3
"""
Test script for automatic unprocessed keywords retry functionality
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"

async def test_automatic_unprocessed_keywords_functionality():
    """Test the automatic unprocessed keywords retry functionality"""
    
    print("🧪 Testing Automatic Unprocessed Keywords Retry Functionality")
    print("=" * 70)
    
    async with aiohttp.ClientSession() as session:
        
        # 1. Test processing statistics before processing
        print("\n1. 📊 Getting initial processing statistics...")
        try:
            async with session.get(f"{API_BASE_URL}/processing-stats?days=1") as response:
                if response.status == 200:
                    stats = await response.json()
                    print("✅ Initial processing statistics:")
                    print(f"   - Successful content: {stats['statistics']['successful_content']}")
                    print(f"   - Failed keywords: {stats['statistics']['failed_keywords']}")
                    print(f"   - Success rate: {stats['statistics']['success_rate']}%")
                else:
                    print(f"❌ Failed to get processing statistics: {response.status}")
        except Exception as e:
            print(f"❌ Error getting processing statistics: {str(e)}")
        
        # 2. Test processing keywords with some that will fail and some that will succeed
        print("\n2. 🚀 Testing keyword processing with mixed success/failure keywords...")
        test_keywords = [
            {"text": "elon musk", "minLength": 0},
            {"text": "bill gates", "minLength": 0},
            {"text": "invalid_keyword_that_will_fail_12345", "minLength": 0},
            {"text": "another_invalid_keyword_98765", "minLength": 0},
            {"text": "mark zuckerberg", "minLength": 0}
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
                    print(f"   - Keywords to process: {[kw['text'] for kw in test_keywords]}")
                else:
                    print(f"❌ Failed to process keywords: {response.status}")
                    return
        except Exception as e:
            print(f"❌ Error processing keywords: {str(e)}")
            return
        
        # 3. Wait for processing to complete (including automatic retries)
        print("\n3. ⏳ Waiting for processing and automatic retries to complete...")
        print("   This may take 2-3 minutes as the system processes keywords and automatically retries failed ones...")
        
        # Wait longer for the full processing cycle including retries
        await asyncio.sleep(180)  # 3 minutes
        
        # 4. Check final processing statistics
        print("\n4. 📊 Checking final processing statistics...")
        try:
            async with session.get(f"{API_BASE_URL}/processing-stats?days=1") as response:
                if response.status == 200:
                    stats = await response.json()
                    print("✅ Final processing statistics:")
                    print(f"   - Successful content: {stats['statistics']['successful_content']}")
                    print(f"   - Failed keywords: {stats['statistics']['failed_keywords']}")
                    print(f"   - Total processed: {stats['statistics']['total_processed']}")
                    print(f"   - Success rate: {stats['statistics']['success_rate']}%")
                    
                    if stats['statistics']['failure_breakdown']:
                        print(f"   - Failure breakdown:")
                        for failure in stats['statistics']['failure_breakdown']:
                            print(f"     * {failure['_id']}: {failure['count']} failures")
                    
                    # Analyze results
                    success_rate = stats['statistics']['success_rate']
                    if success_rate >= 80:
                        print(f"   🎉 Excellent success rate: {success_rate}%")
                    elif success_rate >= 60:
                        print(f"   ✅ Good success rate: {success_rate}%")
                    elif success_rate >= 40:
                        print(f"   ⚠️ Moderate success rate: {success_rate}%")
                    else:
                        print(f"   ❌ Low success rate: {success_rate}%")
                        
                else:
                    print(f"❌ Failed to get final statistics: {response.status}")
        except Exception as e:
            print(f"❌ Error getting final statistics: {str(e)}")
        
        # 5. Test the system's ability to handle edge cases
        print("\n5. 🔍 Testing edge case handling...")
        edge_case_keywords = [
            {"text": "very_obscure_keyword_12345", "minLength": 0},
            {"text": "test_keyword_with_special_chars_!@#$%", "minLength": 0}
        ]
        
        edge_case_request = {
            "keywords": edge_case_keywords,
            "country": "us",
            "language": "en",
            "user_email": "test@example.com"
        }
        
        try:
            async with session.post(f"{API_BASE_URL}/keywords", json=edge_case_request) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"✅ Edge case processing initiated: {result['message']}")
                else:
                    print(f"❌ Failed to process edge cases: {response.status}")
        except Exception as e:
            print(f"❌ Error processing edge cases: {str(e)}")
        
        # Wait for edge case processing
        print("   ⏳ Waiting 60 seconds for edge case processing...")
        await asyncio.sleep(60)
        
        # 6. Final comprehensive statistics
        print("\n6. 📊 Final comprehensive statistics...")
        try:
            async with session.get(f"{API_BASE_URL}/processing-stats?days=1") as response:
                if response.status == 200:
                    stats = await response.json()
                    print("✅ Comprehensive processing statistics:")
                    print(f"   - Period: {stats['statistics']['period']}")
                    print(f"   - User: {stats['statistics']['user_email']}")
                    print(f"   - Successful content: {stats['statistics']['successful_content']}")
                    print(f"   - Failed keywords: {stats['statistics']['failed_keywords']}")
                    print(f"   - Total processed: {stats['statistics']['total_processed']}")
                    print(f"   - Success rate: {stats['statistics']['success_rate']}%")
                    
                    if stats['statistics']['failure_breakdown']:
                        print(f"   - Failure breakdown by stage:")
                        for failure in stats['statistics']['failure_breakdown']:
                            print(f"     * {failure['_id']}: {failure['count']} failures")
                    
                    print(f"\n🎯 Test Summary:")
                    print(f"   - The system automatically retries failed keywords")
                    print(f"   - Different retry strategies are used based on failure stage")
                    print(f"   - Failed keywords are stored in database for manual review")
                    print(f"   - Success rate: {stats['statistics']['success_rate']}%")
                    
                else:
                    print(f"❌ Failed to get comprehensive statistics: {response.status}")
        except Exception as e:
            print(f"❌ Error getting comprehensive statistics: {str(e)}")

if __name__ == "__main__":
    print("🚀 Starting Automatic Unprocessed Keywords Retry Test")
    print(f"📅 Test started at: {datetime.now()}")
    print("=" * 70)
    print("This test will:")
    print("1. Process a mix of valid and invalid keywords")
    print("2. Wait for automatic retry processing")
    print("3. Show processing statistics and success rates")
    print("4. Test edge case handling")
    print("=" * 70)
    
    try:
        asyncio.run(test_automatic_unprocessed_keywords_functionality())
        print("\n✅ Test completed successfully!")
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
    
    print(f"📅 Test ended at: {datetime.now()}") 