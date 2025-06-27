import asyncio
import os
from app.content_generator import ContentGenerator

async def test_generate_and_upload_image():
    # Use a simple prompt for testing
    prompt = "A test image of a cat sitting on a laptop, digital art"
    generator = ContentGenerator()
    print("Generating and uploading image...")
    image_url = await generator.generate_image(prompt, size="512x512")
    if image_url:
        print(f"Image uploaded to: {image_url}")
    else:
        print("Image generation or upload failed.")

if __name__ == "__main__":
    asyncio.run(test_generate_and_upload_image()) 