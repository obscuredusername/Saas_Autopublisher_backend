import os
import asyncio
import aiohttp
import re
import random
import requests
from PIL import Image
from io import BytesIO
from typing import Optional

class ImageGenerator:
    image_semaphore = asyncio.Semaphore(2)

    def __init__(self):
        self.prompts = self.load_prompts()

    def load_prompts(self):
        prompts = {}
        prompts_dir = os.path.join(os.path.dirname(__file__), '../prompts')
        for fname in os.listdir(prompts_dir):
            if fname.endswith('.txt'):
                with open(os.path.join(prompts_dir, fname), 'r', encoding='utf-8') as f:
                    prompts[fname.replace('_prompt.txt', '')] = f.read()
        return prompts

    def get_prompt(self, prompt_type: str) -> str:
        return self.prompts.get(prompt_type, "")

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> str:
        """
        Generate an image using BFL.ml and upload to IMGBB
        This replaces both your existing functions
        """
        async with self.image_semaphore:
            try:
                image_url = await self.generate_image_bfl(prompt, size)
                if image_url:
                    print(f"✅ Image generation successful")
                    return image_url
                else:
                    print("❌ Image generation failed")
                    return None
            except Exception as e:
                print(f"❌ Error in image generation: {str(e)}")
                return None

    async def generate_image_bfl(self, prompt: str, size: str = "1024x1024") -> str:
        """
        Generate image using BFL.ml API with correct authentication format
        Then upload to IMGBB and return the IMGBB URL
        """
        try:
            BFL_API_KEY = os.getenv("BFL_API_KEY")
            if not BFL_API_KEY:
                print("❌ BFL_API_KEY not found in environment variables")
                return None

            print(f"🎨 Generating image with BFL.ai: {prompt}")

            # Parse size string to get dimensions, with error handling
            try:
                width, height = map(int, size.lower().replace(' ', '').split('x'))
            except Exception as e:
                print(f"⚠️ Invalid size format '{size}', using default 1024x1024. Error: {e}")
                width, height = 1024, 1024

            # Correct headers format based on working curl command
            headers = {
                "x-key": BFL_API_KEY,  # Use lowercase 'x-key' as in curl
                "Content-Type": "application/json"
            }

            # Request payload (match curl example)
            payload = {
                "prompt": prompt,
                "width": width,
                "height": height,
                "prompt_upsampling": False,
                "safety_tolerance": 2,
                "output_format": "png"
            }

            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
                # Submit the generation request
                async with session.post("https://api.bfl.ai/v1/flux-kontext-pro", headers=headers, json=payload) as response:
                    if response.status != 200:
                        response_text = await response.text()
                        print(f"❌ BFL API error {response.status}: {response_text}")
                        return None
                    
                    result = await response.json()
                    request_id = result.get("id")
                    polling_url = result.get("polling_url")
                    
                    if not request_id:
                        print("❌ No request ID received from BFL API")
                        return None
                    
                    print(f"📋 Request ID: {request_id}")
                    print("⏳ Polling for result...")
                    
                    # Poll for the result using the provided polling URL or construct it
                    poll_url = polling_url or f"https://api.bfl.ai/v1/get_result?id={request_id}"
                    
                    max_attempts = 30  # 30 attempts * 3 seconds = 90 seconds max wait
                    for attempt in range(max_attempts):
                        await asyncio.sleep(3)  # Wait 3 seconds between polls
                        
                        async with session.get(poll_url, headers=headers) as poll_response:
                            if poll_response.status != 200:
                                print(f"❌ Poll error {poll_response.status}")
                                continue
                            
                            poll_result = await poll_response.json()
                            status = poll_result.get("status")
                            
                            if status == "Ready":
                                # Get the image URL from the result
                                result_data = poll_result.get("result", {})
                                image_url = result_data.get("sample") or result_data.get("url")
                                
                                if image_url:
                                    print(f"✅ BFL image generated: {image_url}")
                                    # Now upload to FastAPI server
                                    # Use the keyword and a random number for the name
                                    fastapi_url = await self.upload_to_fastapi(image_url, prompt)
                                    if fastapi_url:
                                        return fastapi_url
                                    else:
                                        # Return BFL URL as fallback
                                        return image_url
                                else:
                                    print("❌ No image URL in ready result")
                                    return None
                                    
                            elif status == "Error":
                                error_msg = poll_result.get("result", {}).get("error", "Unknown error")
                                print(f"❌ Generation failed: {error_msg}")
                                return None
                                
                            elif status in ["Pending", "Request Moderated"]:
                                print(f"⏳ Still processing... ({status}) - Attempt {attempt + 1}/{max_attempts}")
                                continue
                            else:
                                print(f"⚠️ Unknown status: {status}")
                                continue
                    
                    print("❌ Timeout waiting for image generation")
                    return None

        except Exception as e:
            print(f"❌ BFL generation error: {str(e)}")
            return None

    async def upload_to_fastapi(self, image_url: str, keyword: str) -> Optional[str]:
        """
        Save image to disk in /images and return the public URL.
        The name is the keyword (no spaces, a-zA-Z0-9 only) merged with a random 2- or 3-digit number.
        """
        base_name = re.sub(r'[^a-zA-Z0-9]', '', keyword.replace(' ', ''))[:20]
        rand_num = str(random.randint(100, 999))
        safe_name = f"{base_name}{rand_num}"
        filename = f"{safe_name}.webp"
        save_dir = "/var/www/images"
        os.makedirs(save_dir, exist_ok=True)
        filepath = os.path.join(save_dir, filename)
        try:
            response = requests.get(image_url, timeout=30)
            if response.status_code != 200:
                print(f"❌ Failed to download image: {image_url}")
                return None
            try:
                img = Image.open(BytesIO(response.content)).convert("RGB")
            except Exception:
                print(f"❌ Invalid image format for: {image_url}")
                return None
            img.save(filepath, "WEBP", quality=65)
            # Return the public URL (adjust domain as needed)
            public_url = f"https://handicap-internatioanl.fr/images/{filename}"
            return public_url
        except Exception as e:
            print(f"❌ Image save failed: {e}")
            return None 