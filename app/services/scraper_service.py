import json
import os
from datetime import datetime, timezone
from app.services.scraper import WebContentScraper
# You can now use the scraper service functions here

class ScrapingService:
    def __init__(self):
        self.scraper = WebContentScraper()
        self.output_dir = "scraped_data"
        self._ensure_output_dir()
    
    def _ensure_output_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
    
    def scrape_content(self, keyword, country='us', language='en'):
        try:
            print(f"🔍 Starting scrape for keyword: '{keyword}' in {country}-{language}")
            print("\n🎥 Searching for relevant video...")
            # video_info = self.scraper.video_link_scraper(keyword)  # Uncomment if implemented
            video_info = None
            if video_info:
                print(f"\n✅ Found video for content generation:")
                print(f"📺 Title: {video_info['title']}")
                print(f"🔗 URL: {video_info['url']}")
            else:
                print("\n❌ No relevant video found for content generation")
            print("📡 Searching for links...")
            search_results = self.scraper.search_duckduckgo(
                keyword=keyword, 
                country_code=country, 
                language=language, 
                max_results=25
            )
            if not search_results:
                return {
                    'success': False,
                    'error': 'No search results found',
                    'message': f'No results found for keyword "{keyword}" in {country}-{language}'
                }
            print(f"✅ Found {len(search_results)} initial results")
            unique_links = self.scraper.get_unique_links(search_results, count=15)
            if len(unique_links) < 5:
                print(f"⚠️  Warning: Only found {len(unique_links)} unique links")
                if len(unique_links) == 0:
                    return {
                        'success': False,
                        'error': 'No valid links found',
                        'message': 'All search results were filtered out (social media, PDFs, etc.)'
                    }
            print(f"🔗 Selected {len(unique_links)} unique links for scraping")
            print("🕷️  Starting content scraping...")
            # scraped_data = self.scraper.scrape_multiple_urls(unique_links, target_count=5)  # Uncomment if implemented
            scraped_data = []
            if not scraped_data:
                return {
                    'success': False,
                    'error': 'No content could be scraped',
                    'message': 'All selected URLs failed to scrape or had insufficient content'
                }
            final_data = {
                'search_info': {
                    'keyword': keyword,
                    'country': country,
                    'language': language,
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'total_results_found': len(scraped_data)
                },
                'scraped_content': scraped_data,
                'video_info': video_info
            }
            filename = f"scraped_content_{keyword.replace(' ', '_')}_{country}_{language}.json"
            filepath = os.path.join(self.output_dir, filename)
            success = self._save_to_json(final_data, filepath)
            if success:
                print(f"✅ Successfully scraped {len(scraped_data)} pages")
                if video_info:
                    print(f"✅ Found video: {video_info['title']}")
                print(f"📁 Data saved as: {filepath}")
                return {
                    'success': True,
                    'scraped_count': len(scraped_data),
                    'filename': filename,
                    'data': final_data,
                    'message': f'Successfully scraped {len(scraped_data)} pages and saved to {filename}'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to save data',
                    'message': 'Scraping completed but failed to save JSON file'
                }
        except Exception as e:
            print(f"❌ Error in scraping service: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f'Scraping service failed: {str(e)}'
            }
    def _save_to_json(self, data, filepath):
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving to JSON: {e}")
            return False 