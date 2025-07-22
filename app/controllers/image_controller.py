from app.services.blog_service import *
from app.services.image_service import ImageService

class ImageController:
    def __init__(self):
        self.image_service = ImageService()

    async def generate_image(self, prompt: str, size: str = "1024x1024"):
        return await self.image_service.generate_image(prompt, size)

    # Add image-related methods here 