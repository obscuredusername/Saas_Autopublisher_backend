import os
import requests
import httpx
import datetime
import json
import math
from app.services.scraper import WebContentScraper
from app.services.news_service import NewsService
from app.services.news_service import insert_natural_backlink
from app.services.news_service import generate_rotating_schedule
from app.controllers.yahoo_link import YahooLinkController

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
        yahoo_link = YahooLinkController().yahoo_link(category, language)
        base_url = yahoo_link
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
        rewritten = await news_service.generate_blog_posts_from_news(scraped, category, language, db, user_email)
        return {"category": category, "rewritten": rewritten}

    async def fetch_all(self, category, max_results, language, country, db=None, user_email="news@system.com"):
        google = await self.fetch_google_news(category, max_results, language, country)
        bing = await self.fetch_bing_news(category, max_results, language, country)
        yahoo = await self.fetch_yahoo_news(category, max_results, language, country, db=db, user_email=user_email)
        return {"google": google, "bing": bing, "yahoo": yahoo}

    async def schedule_rotating_yahoo_news(self, categories_dict, language, country, db=None, user_email="news@system.com"):
        """
        Schedule news posts for multiple categories in a rotating, interleaved fashion using Yahoo News.
        categories_dict: {"finance": 4, "business": 2, "fashion": 3}
        """
        import datetime
        start_time = datetime.datetime.now(datetime.timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
        schedule = generate_rotating_schedule(start_time, categories_dict, default_gap_minutes=60)
        news_service = NewsService()
        results = []
        from app.controllers.yahoo_link import YahooLinkController
        for i, (cat, scheduled_time) in enumerate(schedule):
            yahoo_url = await YahooLinkController().yahoo_link(cat, language)
            news_data = await self.fetch_yahoo_news_with_url(yahoo_url, cat, 1, language, country)
            articles = news_data.get('articles') or news_data.get('news') or []
            if not articles:
                results.append({"category": cat, "status": "no articles found"})
                continue
            url = articles[0].get('url')
            if not url:
                results.append({"category": cat, "status": "no url in article"})
                continue
            scraper = WebContentScraper()
            scraped = scraper.scrape_multiple_urls([url], target_count=1)
            generated = await news_service.generate_blog_posts_from_news(scraped, cat, language, db, user_email)
            results.append({"category": cat, "scheduledAt": str(scheduled_time), "result": generated})
        return {"scheduled": results}

    async def fetch_yahoo_news_with_url(self, yahoo_url, category, max_results, language, country, db=None, user_email="news@system.com"):
        # Map category to Yahoo News URL (already resolved)
        base_url = yahoo_url
        print(f"[YAHOO] Fetching Yahoo News links from: {base_url}")
        links = self.scraper.get_yahoo_news_links(base_url)
        print(f"[YAHOO] Found {len(links) if links else 0} links for category '{category}'")
        if not links:
            print(f"[YAHOO][ERROR] No Yahoo news links found for category '{category}' at {base_url}")
            return {"error": "No Yahoo news links found for category.", "category": category}
        # Limit to max_results
        links = links[:max_results]
        print(f"[YAHOO] Scraping {len(links)} Yahoo news articles...")
        scraped = self.scraper.scrape_multiple_urls(links, target_count=len(links))
        print(f"[YAHOO] Scraping complete. Scraped {len(scraped) if scraped else 0} articles.")
        if not scraped:
            print(f"[YAHOO][ERROR] Scraping failed for links: {links}")
            return {"error": "Failed to scrape Yahoo news articles.", "category": category}
        # Pass to GPT rewriting pipeline
        news_service = NewsService()
        print(f"[YAHOO] Starting rephrasing and image generation for {len(scraped)} articles...")
        rewritten = await news_service.generate_blog_posts_from_news(scraped, category, language, db, user_email)
        print(f"[YAHOO] Rephrasing and image generation complete for category '{category}'.")
        return {"category": category, "articles": [{"url": l} for l in links], "rewritten": rewritten}

    async def schedule_rotating_google_news(self, categories_dict, language, country, db=None, user_email="news@system.com"):
        """
        Schedule news posts for multiple categories in a rotating, interleaved fashion using Google News.
        categories_dict: {"finance": 4, "business": 2, "fashion": 3}
        """
        import datetime
        start_time = datetime.datetime.now(datetime.timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
        schedule = generate_rotating_schedule(start_time, categories_dict, default_gap_minutes=60)
        news_service = NewsService()
        results = []
        for i, (cat, scheduled_time) in enumerate(schedule):
            news_data = await self.fetch_google_news(cat, 1, language, country)
            articles = news_data.get('articles') or news_data.get('news') or []
            if not articles:
                results.append({"category": cat, "status": "no articles found"})
                continue
            url = articles[0].get('url')
            if not url:
                results.append({"category": cat, "status": "no url in article"})
                continue
            scraper = WebContentScraper()
            scraped = scraper.scrape_multiple_urls([url], target_count=1)
            generated = await news_service.generate_blog_posts_from_news(scraped, cat, language, db, user_email)
            results.append({"category": cat, "scheduledAt": str(scheduled_time), "result": generated})
        return {"scheduled": results} 