from app.scraper import *
from app.scraper_service import *
from app.services.scraper_service import ScrapingService

class ScraperController:
    def __init__(self):
        self.scraping_service = ScrapingService()

    def scrape_content(self, keyword, country='us', language='en'):
        return self.scraping_service.scrape_content(keyword, country, language)

    # Add methods here to use scraper and scraper_service functions as needed 