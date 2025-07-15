from app.services.blog_service import *

class ContentController:
    def __init__(self, db):
        self.content_service = BlogService(db)

    async def process_keywords(self, keyword_request):
        return await self.content_service.process_keywords(keyword_request)

    async def generate_content(self, scraped_data, content_type="biography"):
        return await self.content_service.generate_content_with_plan(scraped_data, content_type)

    async def get_all_categories(self):
        return await self.content_service.get_all_categories()

    # Add methods here to use content_generator and content_service functions as needed 