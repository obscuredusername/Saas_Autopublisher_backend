import os
import requests
import httpx
import datetime
import json
from app.services.scraper import WebContentScraper
from app.services.news_service import NewsService
from app.services.news_service import insert_natural_backlink

class DedicatedNewsService:
    def __init__(self):
        self.gnews_api_key = os.getenv("SCRAP_API_KEY_GNEWS", "c3064f083b58fc9b4ab20a19cfe2aebf")
        print("DEBUG: Using GNews API key:", self.gnews_api_key)  # Debug print
        self.bing_api_key = os.getenv("SCRAP_API_KEY_BNEWS", "your_bing_api_key")
        self.scraper = WebContentScraper()

    async def fetch_google_news(self, category, max_results, language, country):
        url = "https://gnews.io/api/v4/top-headlines"
        params = {
            "topic": category,
            "token": self.gnews_api_key,
            "lang": language,
            "country": country,
            "max": max_results
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            try:
                data = response.json()
                # Save to file
                folder = "google_news"
                os.makedirs(folder, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"google_{category}_{language}_{country}_{timestamp}.json"
                filepath = os.path.join(folder, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print(f"Saved Google News data to {filepath}")
                return data
            except Exception as e:
                return {"error": str(e), "status_code": response.status_code}

    async def fetch_bing_news(self, category, max_results, language, country):
        url = "https://api.bing.microsoft.com/v7.0/news/search"
        params = {
            "q": category,
            "count": max_results,
            "mkt": f"{language}-{country.upper()}"
        }
        headers = {
            "Ocp-Apim-Subscription-Key": self.bing_api_key
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, headers=headers)
            try:
                return response.json()
            except Exception as e:
                return {"error": str(e), "status_code": response.status_code}

    async def fetch_yahoo_news(self, category, max_results, language, country, db=None, user_email="news@system.com"):
        # Map category to Yahoo News URL
        base_url = f"https://www.yahoo.com/news/{category}/"
        print(f"Fetching Yahoo News links from: {base_url}")
        links = self.scraper.get_yahoo_news_links(base_url)
        if not links:
            return {"error": "No Yahoo news links found for category.", "category": category}
        # Limit to max_results
        links = links[:max_results]
        print(f"Scraping {len(links)} Yahoo news articles...")
        scraped = self.scraper.scrape_multiple_urls(links, target_count=len(links))
        # Pass to GPT rewriting pipeline
        news_service = NewsService()
        rewritten = await news_service.generate_blog_posts_from_news(scraped, category, language, db, user_email, save_to_db=True)
        return {"category": category, "rewritten": rewritten}

    async def fetch_all(self, category, max_results, language, country, db=None, user_email="news@system.com"):
        google = await self.fetch_google_news(category, max_results, language, country)
        bing = await self.fetch_bing_news(category, max_results, language, country)
        yahoo = await self.fetch_yahoo_news(category, max_results, language, country, db=db, user_email=user_email)
        return {"google": google, "bing": bing, "yahoo": yahoo} 