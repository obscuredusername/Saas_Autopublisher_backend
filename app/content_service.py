from fastapi import HTTPException
from datetime import datetime
from typing import List, Dict, Any
from app.scraper_service import ScrapingService
from app.content_generator import ContentGenerator
from app.models import KeywordRequest, ScrapingResponse

class ContentService:
    def __init__(self, db):
        self.db = db
        self.scraping_service = ScrapingService()
        self.scraping_service.db = db
        self.content_generator = ContentGenerator(db=db)

    async def process_keywords(self, keyword_request: KeywordRequest) -> ScrapingResponse:
        try:
            tasks = []
            all_unique_links = []

            for keyword_item in keyword_request.keywords:
                print(f"🔍 Processing keyword: '{keyword_item.text}'")
                
                search_results = self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword_item.text.strip(),
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=25
                )
                
                if search_results:
                    unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=10)
                    
                    if unique_links:
                        all_unique_links.extend(unique_links)
                        tasks.append({
                            "keyword": keyword_item.text,
                            "scheduledDate": keyword_item.scheduledDate,
                            "scheduledTime": keyword_item.scheduledTime,
                            "minLength": keyword_item.minLength,
                            "links_found": len(unique_links),
                            "status": "scheduled"
                        })
                    else:
                        tasks.append({
                            "keyword": keyword_item.text,
                            "links_found": 0,
                            "status": "no_links_found"
                        })
            
            return ScrapingResponse(
                success=True,
                message=f"Found {len(all_unique_links)} unique links across {len(tasks)} keywords",
                tasks=tasks,
                country=keyword_request.country.lower(),
                language=keyword_request.language.lower(),
                status="processing",
                unique_links=list(set(all_unique_links))
            )
                
        except Exception as e:
            print(f"Error in process_keywords: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    async def scrape_and_generate_content(
        self,
        unique_links: List[str],
        keyword: str,
        country: str,
        language: str,
        min_length: int,
        user_email: str,
        scheduled_date: str,
        scheduled_time: str
    ) -> None:
        try:
            print(f"🕷️ Starting content scraping for '{keyword}' ({len(unique_links)} links)")
            scraped_data = self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
            
            if not scraped_data:
                print(f"❌ No content scraped for '{keyword}'")
                return
                
            final_data = {
                'search_info': {
                    'keyword': keyword,
                    'country': country,
                    'language': language,
                    'timestamp': datetime.now().isoformat(),
                    'total_results_found': len(scraped_data),
                    'min_length': min_length,
                    'scheduledDate': scheduled_date,
                    'scheduledTime': scheduled_time
                },
                'scraped_content': scraped_data
            }
            
            result = await self.content_generator.generate_content(final_data, user_email)
            
            if result['success']:
                print(f"✅ Generated content in {language}: {result['file_path']}")
            else:
                print(f"❌ Content generation failed: {result['message']}")
                
        except Exception as e:
            print(f"❌ Error processing '{keyword}': {str(e)}")

    async def get_scheduled_content(self, status: str = None, date: str = None) -> Dict[str, Any]:
        try:
            query = {}
            
            if status:
                query["status"] = status
            if date:
                query["scheduled_date"] = date
                
            cursor = self.db.generated_content.find(query)
            content_list = await cursor.to_list(length=None)
            
            return {
                "success": True,
                "content_count": len(content_list),
                "content": [
                    {
                        "keyword": item["keyword"],
                        "language": item["language"],
                        "scheduled_date": item["scheduled_date"],
                        "scheduled_time": item["scheduled_time"],
                        "status": item["status"],
                        "word_count": item["word_count"],
                        "file_path": item["file_path"]
                    }
                    for item in content_list
                ]
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) 