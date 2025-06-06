import asyncio
import os
import json
import sys

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.scraper_service import ScrapingService
from app.content_generator import ContentGenerator

async def test_social_media_search():
    print("🔍 Starting Social Media Search Test")
    
    # Initialize services
    scraper = ScrapingService()
    
    # Test cases
    test_cases = [
        {"keyword": "Tesla", "category": "company"},
        {"keyword": "Elon Musk", "category": "person"},
        {"keyword": "Microsoft", "category": "company"},
        {"keyword": "Bill Gates", "category": "person"}
    ]
    
    for test in test_cases:
        print(f"\n📌 Testing: {test['keyword']} ({test['category']})")
        
        # Search for social media profiles
        result = scraper.find_social_media_and_website(
            keyword=test['keyword'],
            category=test['category']
        )
        
        if result['success']:
            print(f"✅ Found {result['links_found']} links for {test['keyword']}")
            print("\nFound Links:")
            for platform, link in result['data']['links'].items():
                if link:
                    print(f"- {platform}: {link}")
        else:
            print(f"❌ Failed to find links: {result['message']}")
        
        # Save results to file
        if result['success']:
            output_dir = "test_results"
            os.makedirs(output_dir, exist_ok=True)
            
            filename = os.path.join(output_dir, f"social_media_{test['keyword'].replace(' ', '_').lower()}.json")
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(result['data'], f, indent=2, ensure_ascii=False)
            print(f"\n💾 Results saved to: {filename}")
        
        print("-" * 80)

async def test_content_generation_with_socials():
    print("\n🚀 Testing Content Generation with Social Media Integration")
    
    # Initialize services
    scraper = ScrapingService()
    content_gen = ContentGenerator()
    
    # Test case
    keyword = "Tesla"
    
    print(f"\n📌 Testing content generation for: {keyword}")
    
    # First get social media info
    social_result = scraper.find_social_media_and_website(keyword, "company")
    
    if not social_result['success']:
        print(f"❌ Failed to get social media info: {social_result['message']}")
        return
    
    # Then get regular content
    scrape_result = scraper.scrape_content(keyword)
    
    if not scrape_result['success']:
        print(f"❌ Failed to scrape content: {scrape_result['message']}")
        return
    
    # Combine the results
    combined_data = {
        'search_info': scrape_result['data']['search_info'],
        'scraped_content': scrape_result['data']['scraped_content'],
        'social_media': social_result['data']['links']
    }
    
    # Save combined results
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    filename = os.path.join(output_dir, f"combined_{keyword.lower()}.json")
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(combined_data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Combined results saved to: {filename}")
    print("-" * 80)

if __name__ == "__main__":
    # Create an event loop and run the tests
    loop = asyncio.get_event_loop()
    try:
        print("🧪 Starting Tests")
        
        # Run tests
        loop.run_until_complete(test_social_media_search())
        loop.run_until_complete(test_content_generation_with_socials())
        
        print("\n✨ Tests completed!")
    finally:
        loop.close() 