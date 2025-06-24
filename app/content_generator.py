# content_generator.py - Simplified version focused only on content generation

from openai import AsyncOpenAI
from typing import List, Dict, Optional, Any
import os
from dotenv import load_dotenv
import re
import aiohttp
import base64
import asyncio
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import time
import json
import boto3
from botocore.exceptions import BotoCoreError, NoCredentialsError
from uuid import uuid4
import tempfile
from PIL import Image

load_dotenv()

class ContentGenerator:
    def __init__(self, api_key: str = None):
        """
        Initialize the content generator with OpenAI client only
        """
        self.client = AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY")
        )
        self.chunk_size = 800  # Reduced chunk size for better token management
        self.max_chunks = 3  # Reduced number of chunks per section
        
        # Enhanced content type prompts for longer generation
        self.content_prompts = {
            "biography": {
                "system": """You are a professional biographer and content writer with expertise in creating comprehensive, well-researched biographical content. Your task is to create detailed, engaging biographies that are:
                - MINIMUM 1500 words long
                - Written in the specified language
                - Thoroughly paraphrased from source material (never copy-paste)
                - Structured with proper HTML formatting
                - Rich in detail and context
                - Historically accurate and well-researched
                
                IMPORTANT GUIDELINES:
                1. Always write in the language specified in the metadata
                2. Paraphrase all information - never copy text directly
                3. Expand on facts with historical context and analysis
                4. Use varied sentence structures and vocabulary
                5. Include multiple perspectives and interpretations
                6. Add transitional phrases and explanatory content
                7. Ensure content flows naturally and reads like original writing""",
                
                "user": """Create a comprehensive biography about {keyword} in {language}. Use the source material below as reference but COMPLETELY REWRITE everything in your own words. The content must be at least 1500 words.

REQUIREMENTS:
- Language: {language}
- Minimum length: 1500 words
- Paraphrase all information (no direct copying)
- Use proper HTML structure as shown below
- Include detailed analysis and context
- Expand on key events with historical background
- Add multiple sections covering different aspects of life

HTML Structure Required:
<article class="biography">
    <h1 class="person-name">{keyword}</h1>
    
    <div class="bio-meta">
        <p class="bio-intro">
            [Comprehensive introduction paragraph - 100+ words]
        </p>
        
        <table class="quick-facts">
            <caption>[Quick Facts in {language}]</caption>
            <tbody>
                <tr><th>[Born in {language}]</th><td>[Birth details]</td></tr>
                <tr><th>[Died in {language}]</th><td>[Death details if applicable]</td></tr>
                <tr><th>[Nationality in {language}]</th><td>[Nationality]</td></tr>
                <tr><th>[Known for in {language}]</th><td>[Major achievements]</td></tr>
                <tr><th>[Active period in {language}]</th><td>[Active period]</td></tr>
            </tbody>
        </table>
    </div>

    <div class="table-of-contents">
        <h2>[Contents in {language}]</h2>
        <ul>
            <li><a href="#early-life">[Early Life and Education in {language}]</a></li>
            <li><a href="#political-rise">[Political Rise in {language}]</a></li>
            <li><a href="#in-power">[In Power in {language}]</a></li>
            <li><a href="#wars-conflicts">[Wars and Conflicts in {language}]</a></li>
            <li><a href="#downfall-end">[Downfall and End in {language}]</a></li>
            <li><a href="#legacy-impact">[Legacy and Impact in {language}]</a></li>
        </ul>
    </div>

    <div class="bio-content">
        <section id="early-life">
            <h2>[Early Life and Education in {language}]</h2>
            [Detailed section - 250+ words about early life, family background, education, formative experiences]
            
            <h3>[Family and Social Background in {language}]</h3>
            [Subsection about family and social context - 150+ words]
            
            <h3>[Early Political Influences in {language}]</h3>
            [Subsection about early political influences - 150+ words]
        </section>

        <section id="political-rise">
            <h2>[Political Rise in {language}]</h2>
            [Detailed section - 300+ words about political rise, key events, strategies used]
            
            <h3>[Party Involvement in {language}]</h3>
            [Subsection about party involvement - 200+ words]
            
            <h3>[Coups and Political Maneuvering in {language}]</h3>
            [Subsection about coups and political maneuvering - 200+ words]
        </section>

        <section id="in-power">
            <h2>[In Power in {language}]</h2>
            [Detailed section - 300+ words about time in power, policies, governance style]
            
            <h3>[Power Consolidation in {language}]</h3>
            [Subsection about power consolidation - 200+ words]
            
            <h3>[Domestic Policies in {language}]</h3>
            [Subsection about domestic policies - 200+ words]
        </section>

        <section id="wars-conflicts">
            <h2>[Wars and Conflicts in {language}]</h2>
            [Detailed section - 400+ words about wars, conflicts, military campaigns]
            
            <h3>[Iran-Iraq War in {language}]</h3>
            [Subsection about Iran-Iraq war - 250+ words]
            
            <h3>[Gulf War in {language}]</h3>
            [Subsection about Gulf War - 250+ words]
        </section>

        <section id="downfall-end">
            <h2>[Downfall and End in {language}]</h2>
            [Detailed section - 300+ words about downfall, capture, trial, execution]
            
            <h3>[2003 Invasion in {language}]</h3>
            [Subsection about 2003 invasion - 200+ words]
            
            <h3>[Trial and Execution in {language}]</h3>
            [Subsection about trial and execution - 200+ words]
        </section>

        <section id="legacy-impact">
            <h2>[Legacy and Impact in {language}]</h2>
            [Detailed section - 250+ words about legacy, impact on region, historical assessment]
            
            <h3>[Impact on the Middle East in {language}]</h3>
            [Subsection about regional impact - 150+ words]
            
            <h3>[Historical Assessment in {language}]</h3>
            [Subsection about historical evaluation - 150+ words]
        </section>
    </div>
</article>

SOURCE MATERIAL FOR REFERENCE (PARAPHRASE COMPLETELY):
{scraped_data}

Remember: Write everything in {language} and ensure the content is at least 1500 words with rich detail and analysis."""
            },
            
            "how_to": {
                "system": """You are an expert content writer specializing in comprehensive how-to guides. Create detailed, practical guides that are:
                - MINIMUM 1500 words long
                - Written in the specified language
                - Thoroughly paraphrased from source material
                - Structured with proper HTML formatting
                - Rich in practical examples and tips
                - Easy to follow and actionable""",
                
                "user": """Create a comprehensive how-to guide about {keyword} in {language}. Use the source material as reference but completely rewrite in your own words. Minimum 1500 words.

Requirements: Same HTML structure principles as biography but adapted for how-to content.

SOURCE MATERIAL:
{scraped_data}"""
            },
            
            "company": {
                "system": """You are a business analyst specializing in comprehensive company profiles. Create detailed company analyses that are:
                - MINIMUM 1500 words long
                - Written in the specified language
                - Thoroughly paraphrased from source material
                - Rich in business insights and analysis""",
                
                "user": """Create a comprehensive company profile about {keyword} in {language}. Use the source material as reference but completely rewrite in your own words. Minimum 1500 words.

SOURCE MATERIAL:
{scraped_data}"""
            }
        }

    def chunk_text(self, text: str) -> List[str]:
        """Split text into smaller chunks for better context management."""
        chunks = []
        current_chunk = ""
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= self.chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks

    def get_most_relevant_chunks(self, chunks: List[str], query: str, top_k: int = 5) -> List[str]:
        """Get the most relevant chunks using TF-IDF and cosine similarity."""
        if not chunks:
            return []
            
        try:
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(chunks + [query])
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            return [chunks[i] for i in top_indices]
        except Exception as e:
            print(f"Error in relevance calculation: {str(e)}")
            return chunks[:top_k]

    async def generate_content(self, scraped_data: Dict[str, Any], content_type: str = "biography") -> Dict[str, Any]:
        """
        Generate comprehensive content based on scraped data
        Only handles content generation - no database operations
        """
        try:
            if content_type not in self.content_prompts:
                return {
                    'success': False,
                    'message': f"Invalid content type: {content_type}"
                }

            # Extract metadata
            search_info = scraped_data.get("search_info", {})
            keyword = search_info.get("keyword", "")
            language = search_info.get("language", "en")
            min_length = search_info.get("min_length", 1500)
            
            if not keyword:
                return {'success': False, 'message': "No keyword found"}

            print(f"🎯 Generating {content_type} content for: {keyword} in {language}")
            print(f"📏 Target length: {min_length} words")

            # First, generate an attention-catching title
            title_prompt = f"""Create a highly creative and engaging title for a {content_type} about {keyword} in {language}. 
            The title should be:
            - Extremely creative and unique
            - Attention-grabbing and memorable
            - Include a creative metaphor, play on words, or political slogan
            - 5-10 words long
            - Include the keyword {keyword} in a creative way
            - Be appropriate for the content type
            - Written in {language}
            - Avoid generic or boring titles
            - Use literary devices like alliteration, metaphors, or wordplay
            - For political figures, consider using political slogans or campaign themes
            - Make it controversial or thought-provoking when appropriate
            
            Examples of creative titles for political figures:
            - "Bill Clinton: Making America Great Again Before It Was Cool"
            - "The Comeback Kid: Bill Clinton's Political Odyssey"
            - "From Arkansas to the White House: The Bill Clinton Revolution"
            - "The Charismatic Commander: Bill Clinton's Presidential Legacy"
            - "Clinton's America: The 90s Renaissance"
            
            Examples of creative titles for other figures:
            - "The Digital Alchemist: How {keyword} Transformed Technology"
            - "{keyword}: The Architect of Tomorrow's World"
            - "From Vision to Reality: The {keyword} Revolution"
            - "The Untold Saga of {keyword}: A Modern Epic"
            - "{keyword}: Where Innovation Meets Imagination"
            
            Return ONLY the creative title, nothing else."""

            title_response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a creative content writer specializing in crafting unique, attention-grabbing titles that stand out and engage readers. You excel at creating titles that are both memorable and thought-provoking, especially for political and historical figures."},
                    {"role": "user", "content": title_prompt}
                ],
                temperature=0.95,  # Increased temperature for more creativity
                max_tokens=100
            )
            
            title = title_response.choices[0].message.content.strip()
            
            # Create slug from keyword instead of title
            clean_keyword = keyword.lower()
            clean_keyword = re.sub(r'[^a-z0-9\s-]', '', clean_keyword)
            clean_keyword = re.sub(r'\s+', '-', clean_keyword)
            clean_keyword = re.sub(r'-+', '-', clean_keyword)
            clean_keyword = clean_keyword.strip('-')
            slug = clean_keyword
            
            print(f"📝 Extracted title: {title}")
            print(f"🔗 Generated slug from keyword: {slug}")

            # Process scraped content
            if not scraped_data.get("scraped_content"):
                return {'success': False, 'message': "No scraped content found"}

            # Create comprehensive content chunks and collect references
            all_chunks = []
            references = []
            for item in scraped_data.get("scraped_content", []):
                title = item.get('title', '')
                content = item.get('content', '')
                url = item.get('url', '')
                
                # Add to references if it's a valid URL
                if url and url.startswith(('http://', 'https://')):
                    references.append({
                        'title': title,
                        'url': url
                    })
                
                # Create rich context block
                context_block = f"""
TITLE: {title}
SOURCE: {url}
CONTENT: {content}
---
"""
                chunks = self.chunk_text(context_block)
                all_chunks.extend(chunks)

            # Get most relevant chunks
            relevant_chunks = self.get_most_relevant_chunks(
                all_chunks, 
                query=f"{keyword} {language}",
                top_k=self.max_chunks
            )

            content_text = "\n\n=== SOURCE EXCERPT ===\n".join(relevant_chunks)

            if not content_text.strip():
                return {'success': False, 'message': "No relevant content found"}

            # Get prompts
            prompts = self.content_prompts[content_type]

            # --- Start image generation tasks in parallel ---
            print(f"🎨 Starting image generation tasks for: {keyword}")
            image_prompt1 = f"Professional high-quality image of {keyword}, detailed and realistic"
            image_prompt2 = f"{keyword} in action or in context, a photo of {keyword} in a scenario"
            image_task1 = asyncio.create_task(self.generate_image(image_prompt1))
            image_task2 = asyncio.create_task(self.generate_image(image_prompt2))
            # --- End image generation task start ---

            print(f"🤖 Generating content with GPT-4...")
            
            # First generation attempt
            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": prompts["system"]},
                    {"role": "user", "content": prompts["user"].format(
                        keyword=keyword,
                        language=language,
                        scraped_data=content_text
                    )}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            generated_content = response.choices[0].message.content.strip()
            
            # Extract title from content (looking for h2 tag)
            title_match = re.search(r'<h2>(.*?)</h2>', generated_content)
            if title_match:
                title = title_match.group(1)
                # Remove the h2 tag from content
                generated_content = generated_content.replace(f'<h2>{title}</h2>', '')
            else:
                title = title_match.group(1)  # Fallback to blog plan title
            
            word_count = len(generated_content.split())
            
            print(f"📝 Initial generation: {word_count} words")
            
            # Calculate minimum acceptable word count (75% of target)
            min_acceptable_words = int(min_length * 0.75)
            print(f"📏 Minimum acceptable words: {min_acceptable_words}")
            
            # If content is still too short, expand it
            attempts = 0
            while word_count < min_acceptable_words and attempts < 3:
                print(f"⚠️ Content too short ({word_count}/{min_acceptable_words} words). Expanding... (Attempt {attempts + 1})")
                
                expansion_prompt = f"""
The following content is too short ({word_count} words). Please expand it to at least {min_acceptable_words} words by:
1. Adding more detailed explanations
2. Including additional historical context
3. Expanding on key points with examples
4. Adding more subsections where appropriate
5. Providing deeper analysis and insights

MAINTAIN the same language ({language}) and HTML structure. DO NOT repeat information, but ADD NEW relevant details.

Current content to expand:
{generated_content}

Additional source material for reference:
{content_text}
"""
                
                expansion_response = await self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": prompts["system"]},
                        {"role": "user", "content": expansion_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=4000
                )
                
                generated_content = expansion_response.choices[0].message.content.strip()
                word_count = len(generated_content.split())
                attempts += 1
                
                print(f"📝 Expanded to: {word_count} words")

            # Add word count status to metadata
            word_count_status = "optimal" if word_count >= min_length else "acceptable" if word_count >= min_acceptable_words else "below_minimum"
            print(f"📊 Word count status: {word_count_status} ({word_count} words)")

            # --- Await image generation results ---
            image_url1 = await image_task1
            image_url2 = await image_task2
            # --- End image await ---

            if image_url1 or image_url2:
                print(f"✅ Generated images successfully")
                
                # Insert images into the content
                # Find the first paragraph tag to insert the first image
                if image_url1:
                    img_tag1 = f'<img src="{image_url1}" alt="{keyword}" class="main-image" style="max-width: 100%; height: auto; margin: 20px 0;" />'
                    if '<p>' in generated_content:
                        generated_content = generated_content.replace('<p>', f'<p>{img_tag1}', 1)
                    else:
                        generated_content = img_tag1 + generated_content
                
                # Insert second image roughly in the middle of the content
                if image_url2:
                    img_tag2 = f'<img src="{image_url2}" alt="{keyword} in context" class="context-image" style="max-width: 100%; height: auto; margin: 20px 0;" />'
                    content_parts = generated_content.split('</p>')
                    if len(content_parts) > 2:
                        middle_index = len(content_parts) // 2
                        content_parts.insert(middle_index, img_tag2)
                        generated_content = '</p>'.join(content_parts)
                    else:
                        generated_content += img_tag2

            # Add references section
            if references:
                references_section = f"""
<section class="references">
    <h2>[References in {language}]</h2>
    <ul class="reference-list">
"""
                for ref in references:
                    references_section += f'        <li><a href="{ref["url"]}" target="_blank" rel="noopener noreferrer">{ref["title"]}</a></li>\n'
                
                references_section += """    </ul>
</section>"""
                
                # Add references section at the end of the content
                generated_content += references_section

            return {
                'success': True,
                'message': f'Generated {content_type} content: {word_count} words in {language}',
                'title': title,
                'content': generated_content,
                'image_urls': [url for url in [image_url1, image_url2] if url],
                'word_count': word_count
            }
            
        except Exception as e:
            print(f"❌ Error generating content: {str(e)}")
            return {
                'success': False,
                'message': f'Error generating content: {str(e)}'
            }

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
        """
        Generate an image using BFL.ml and upload to IMGBB
        This replaces both your existing functions
        """
        try:
            print(f"🎨 Generating image: {prompt}")
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

    async def generate_image_bfl(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
        """
        Generate image using BFL.ml API with correct authentication format
        Then upload to IMGBB and return the IMGBB URL
        """
        try:
            BFL_API_KEY = os.getenv("BFL_API_KEY")
            print(f"[DEBUG] BFL_API_KEY: {BFL_API_KEY}")  # Debug print
            if not BFL_API_KEY:
                print("❌ BFL API key not found in environment variables")
                return None

            print(f"🎨 Generating image with BFL.ai: {prompt}")

            # Parse size string to get dimensions
            width, height = map(int, size.split('x'))

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
                                    
                                    # Now upload to S3
                                    s3_url = await self.upload_to_s3(image_url, session)
                                    if s3_url:
                                        return s3_url
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

    async def upload_to_s3(self, image_url: str, session: aiohttp.ClientSession) -> Optional[str]:
        """
        Download image from BFL and upload to AWS S3 bucket, returning the public URL.
        Convert the image to JPG before upload.
        """
        try:
            print("AWS_ACCESS_KEY_ID:", os.getenv("AWS_ACCESS_KEY_ID"))
            print("AWS_SECRET_ACCESS_KEY:", os.getenv("AWS_SECRET_ACCESS_KEY"))
            print("S3_BUCKET_NAME:", os.getenv("S3_BUCKET_NAME"))
            print("S3_REGION:", os.getenv("S3_REGION"))
            aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
            aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
            bucket_name = os.getenv("S3_BUCKET_NAME")
            region = os.getenv("S3_REGION", "eu-north-1")
            if not all([aws_access_key, aws_secret_key, bucket_name, region]):
                print("⚠️ AWS S3 credentials or bucket info missing in environment variables")
                return None

            print(f"📥 Downloading image from BFL...")
            async with session.get(image_url) as response:
                if response.status != 200:
                    print(f"❌ Failed to download image from BFL: {response.status}")
                    return None
                image_data = await response.read()

            # Save to a temporary PNG file first
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp_png_file:
                tmp_png_file.write(image_data)
                png_file_path = tmp_png_file.name

            # Convert PNG to JPG using PIL
            jpg_file_path = png_file_path.replace('.png', '.jpg')
            try:
                with Image.open(png_file_path) as im:
                    rgb_im = im.convert('RGB')
                    rgb_im.save(jpg_file_path, 'JPEG', quality=95)
            except Exception as e:
                print(f"❌ Error converting PNG to JPG: {str(e)}")
                os.remove(png_file_path)
                return None
            finally:
                os.remove(png_file_path)  # Remove the PNG file after conversion

            s3_key = f"bfl-images/{uuid4().hex}.jpg"
            print(f"📤 Uploading to S3 bucket {bucket_name} as {s3_key}...")
            s3 = boto3.client(
                "s3",
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=region
            )
            try:
                s3.upload_file(
                    Filename=jpg_file_path,
                    Bucket=bucket_name,
                    Key=s3_key,
                    ExtraArgs={'ContentType': 'image/jpeg'}
                )
            except (BotoCoreError, NoCredentialsError) as e:
                print(f"❌ S3 upload failed: {str(e)}")
                return None
            finally:
                os.remove(jpg_file_path)

            url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
            print(f"✅ Image uploaded to S3: {url}")
            return url
        except Exception as e:
            print(f"❌ S3 upload error: {str(e)}")
            return None

    async def generate_blog_plan(self, keyword: str, language: str = "en") -> Dict[str, Any]:
        """
        Generate a comprehensive blog plan including title, headings, category, and image prompts
        """
        try:
            blog_plan_prompt = f"""Create a comprehensive blog plan for {keyword} in {language}. 
            Return the response in JSON format with the following structure:
            {{
                "title": "Creative and engaging title",
                "category": "Main category for the blog",
                "headings": [
                    {{
                        "title": "Heading title",
                        "description": "Brief description of what this section will cover"
                    }}
                ],
                "image_prompts": [
                    {{
                        "prompt": "Detailed prompt for first image",
                        "purpose": "Purpose of this image in the blog"
                    }},
                    {{
                        "prompt": "Detailed prompt for second image",
                        "purpose": "Purpose of this image in the blog"
                    }}
                ]
            }}

            Requirements:
            - Title should be creative and attention-grabbing
            - Category should be specific and relevant
            - Headings should cover all important aspects of the topic
            - Image prompts should be detailed and specific
            - All content should be in {language}
            
            Return ONLY the JSON structure, nothing else."""

            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional blog planner and content strategist. You excel at creating comprehensive blog structures and creative content plans. Always respond with valid JSON only."},
                    {"role": "user", "content": blog_plan_prompt}
                ],
                temperature=0.7
            )
            
            # Parse the response as JSON
            try:
                blog_plan = json.loads(response.choices[0].message.content.strip())
                return blog_plan
            except json.JSONDecodeError as e:
                print(f"❌ Error parsing blog plan JSON: {str(e)}")
                print(f"Raw response: {response.choices[0].message.content}")
                return None
            
        except Exception as e:
            print(f"❌ Error generating blog plan: {str(e)}")
            return None

    async def generate_content_with_plan(self, scraped_data: Dict[str, Any], content_type: str = "biography") -> Dict[str, Any]:
        """
        Generate content using a structured blog plan and optimized RAG approach
        """
        try:
            # Extract metadata
            search_info = scraped_data.get("search_info", {})
            keyword = search_info.get("keyword", "")
            language = search_info.get("language", "en")
            category_names = scraped_data.get("category_names", [])
            
            if not keyword:
                return {'success': False, 'message': "No keyword found"}

            # Get the blog plan from the data
            blog_plan = scraped_data.get("blog_plan")
            if not blog_plan:
                return {'success': False, 'message': "No blog plan found"}
            
            # Get video information
            video_info = scraped_data.get("video_info")
            
            # Start image generation tasks immediately after getting blog plan
            print("🎨 Starting image generation tasks...")
            image_tasks = []
            # Take only the first two image prompts
            for img_prompt in blog_plan["image_prompts"][:2]:
                task = asyncio.create_task(self.generate_image(img_prompt["prompt"]))
                image_tasks.append(task)
            
            # Process scraped content for RAG
            all_chunks = []
            references = []
            for item in scraped_data.get("scraped_content", []):
                title = item.get('title', '')
                content = item.get('content', '')
                url = item.get('url', '')
                
                if url and url.startswith(('http://', 'https://')):
                    references.append({
                        'title': title,
                        'url': url
                    })
                
                # Create concise context block
                context_block = f"SOURCE: {url}\nTITLE: {title}\nCONTENT: {content}"
                chunks = self.chunk_text(context_block)
                all_chunks.extend(chunks)

            # Get most relevant chunks for each section
            section_chunks = {}
            for heading in blog_plan["headings"]:
                section_title = heading["title"]
                section_query = f"{keyword} {section_title}"
                relevant_chunks = self.get_most_relevant_chunks(
                    all_chunks, 
                    query=section_query,
                    top_k=self.max_chunks
                )
                section_chunks[section_title] = relevant_chunks

            # Add video information to the content prompt if available
            video_section = ""
            if video_info:
                video_section = f"""
VIDEO INFORMATION:
Title: {video_info['title']}
URL: {video_info['url']}

Please include this video in the content with proper HTML embedding using the following format:
<div class=\"video-container\" style=\"position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;\">
    <iframe src=\"{video_info['url'].replace('watch?v=', 'embed/')}\" 
            style=\"position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;\" 
            allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" 
            allowfullscreen></iframe>
</div>
<p class=\"video-caption\" style=\"text-align: center; font-style: italic; margin-top: 10px;\">{video_info['title']}</p>

IMPORTANT: Do not create any image tags or references to images that don't exist. Only use the images that will be generated by the system.
"""

            # --- CATEGORY SELECTION PROMPT ---
            category_list_str = ', '.join(category_names)
            category_selection_instruction = f"""
Here is a list of available categories: [{category_list_str}].
Select the most relevant category for this content and return ONLY the category name as:
SELECTED_CATEGORY: <category name>
Place this line at the very top of your response, then provide the full content below.
"""
            # --- END CATEGORY SELECTION PROMPT ---

            # Generate content based on the plan and RAG
            content_prompt = f"""{category_selection_instruction}
Create a comprehensive blog post about {keyword} in {language}.

BLOG PLAN:
{json.dumps(blog_plan, indent=2)}

{video_section}

REQUIREMENTS:
- Follow the exact headings and structure provided
- Use the source material as reference but rewrite in your own words
- Include proper HTML formatting
- Add relevant quotes and citations from sources
- Target word count: 1500-2000 words
- Use the exact title provided in the blog plan

STRUCTURED CONTENT REQUIREMENTS:
1. For biographies/people:
   - Create a "Quick Facts" table with:
     * Full Name
     * Birth Date/Place
     * Nationality
     * Occupation
     * Net Worth (if available)
     * Notable Works
   - Create an "Awards & Achievements" table with:
     * Year
     * Award Name
     * Category
     * Work/Project
   - Use bullet points for:
     * Early Life & Education
     * Career Highlights
     * Personal Life
     * Philanthropy/Charity Work
     * Interesting Facts

2. For topics/events:
   - Create a "Key Information" table with:
     * Date/Period
     * Location
     * Significance
     * Key Figures
     * Impact
   - Use bullet points for:
     * Main Points
     * Key Statistics
     * Important Facts
     * Related Events
     * Future Implications

3. For products/technology:
   - Create a "Specifications" table with:
     * Features
     * Technical Details
     * Requirements
     * Pricing (if applicable)
   - Use bullet points for:
     * Key Benefits
     * Use Cases
     * Pros and Cons
     * Comparison Points

4. For all content types:
   - Include at least 2 data tables with relevant information
   - Use bullet points for lists and key points
   - Format important statistics in tables
   - Use blockquotes for important quotes
   - Each section should be 200-300 words minimum
   - If video information is provided, include it in a relevant section with proper HTML embedding
   - DO NOT create any image tags or references to images that don't exist
   - Only use the images that will be provided by the system
   - Ensure all HTML is clean and valid
   - Do not include any placeholder or non-existent image URLs

SOURCE MATERIAL BY SECTION:
{json.dumps(section_chunks, indent=2)}

Return the complete blog post with proper HTML formatting, including all tables and bullet points as specified above."""

            response = await self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a professional content writer specializing in creating comprehensive, well-researched blog posts."},
                    {"role": "user", "content": content_prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            generated_content = response.choices[0].message.content.strip()

            # --- Parse selected category from the top of the response ---
            selected_category_name = None
            lines = generated_content.splitlines()
            if lines and lines[0].startswith("SELECTED_CATEGORY:"):
                selected_category_name = lines[0].replace("SELECTED_CATEGORY:", "").strip()
                # Remove the first line from the content
                generated_content = "\n".join(lines[1:]).lstrip()
            # --- End parse ---
            
            # Extract title from content (looking for h2 tag)
            title_match = re.search(r'<h2>(.*?)</h2>', generated_content)
            if title_match:
                title = title_match.group(1)
                # Remove the h2 tag from content
                generated_content = generated_content.replace(f'<h2>{title}</h2>', '')
            else:
                title = blog_plan["title"]  # Fallback to blog plan title
            
            # Calculate word count
            word_count = len(generated_content.split())
            print(f"📝 Generated content: {word_count} words")
            
            # Verify word count is within target range
            if word_count < 1500:
                print(f"⚠️ Warning: Word count ({word_count}) is below target range (1500-2000)")
                # If content is too short, try to expand it
                expansion_prompt = f"""Expand the following content to at least 1500 words by adding more details and context.
                Maintain the same language ({language}) and HTML structure.
                Use the source material for additional information.

                Current content:
                {generated_content}

                Source material:
                {json.dumps(section_chunks, indent=2)}"""

                expansion_response = await self.client.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a professional content writer specializing in expanding content while maintaining quality."},
                        {"role": "user", "content": expansion_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=3000
                )
                generated_content = expansion_response.choices[0].message.content.strip()
                word_count = len(generated_content.split())
                print(f"📝 Expanded content: {word_count} words")

            # Create slug from keyword instead of title
            clean_keyword = keyword.lower()
            clean_keyword = re.sub(r'[^a-z0-9\s-]', '', clean_keyword)
            clean_keyword = re.sub(r'\s+', '-', clean_keyword)
            clean_keyword = re.sub(r'-+', '-', clean_keyword)
            clean_keyword = clean_keyword.strip('-')
            slug = clean_keyword
            
            print(f"📝 Extracted title: {title}")
            print(f"🔗 Generated slug from keyword: {slug}")

            # Await image generation results
            print("⏳ Waiting for image generation to complete...")
            image_urls = []
            for task in image_tasks:
                image_url = await task
                if image_url:
                    image_urls.append(image_url)
            
            # Insert images into the content
            if image_urls:
                for i, image_url in enumerate(image_urls):
                    img_tag = f'<img src="{image_url}" alt="{keyword} - {blog_plan["image_prompts"][i]["purpose"]}" class="blog-image" style="max-width: 100%; height: auto; margin: 20px 0;" />'
                    if i == 0:
                        if '<p>' in generated_content:
                            generated_content = generated_content.replace('<p>', f'<p>{img_tag}', 1)
                        else:
                            generated_content = img_tag + generated_content
                    else:
                        content_parts = generated_content.split('</p>')
                        if len(content_parts) > 2:
                            middle_index = len(content_parts) // 2
                            content_parts.insert(middle_index, img_tag)
                            generated_content = '</p>'.join(content_parts)
                        else:
                            generated_content += img_tag

            # Add references section
            if references:
                references_section = f"""
<section class="references">
    <h2>[References in {language}]</h2>
    <ul class="reference-list">
"""
                for ref in references:
                    references_section += f'        <li><a href="{ref["url"]}" target="_blank" rel="noopener noreferrer">{ref["title"]}</a></li>\n'
                
                references_section += """    </ul>
</section>"""
                
                generated_content += references_section

            # Add video information to metadata
            metadata = {
                'headings': blog_plan["headings"],
                'image_prompts': blog_plan["image_prompts"][:2],  # Only include the first two prompts
                'sources_used': len(references),
                'references': references
            }
            
            if video_info:
                metadata['video'] = video_info

            return {
                'success': True,
                'message': f'Generated blog content for: {keyword}',
                'title': blog_plan["title"],
                'content': generated_content,
                'image_urls': image_urls,
                'word_count': word_count,
                'selected_category_name': selected_category_name
            }
            
        except Exception as e:
            print(f"❌ Error generating content with plan: {str(e)}")
            return {
                'success': False,
                'message': f'Error generating content: {str(e)}'
            }

    async def generate_dummy_content(self, title="Dummy Title", content_type="biography") -> dict:
        """
        Dummy content generator for testing. Returns static data in the new minimal format.
        """
        dummy_content = f"""
        <article>
            <h2>{title}</h2>
            <p>This is dummy generated content for testing purposes only.</p>
            <img src=\"https://placehold.co/600x400\" alt=\"Dummy Image\" />
        </article>
        """
        return {
            "success": True,
            "message": f"Dummy {content_type} content generated.",
            "title": title,
            "content": dummy_content,
            "image_urls": ["https://placehold.co/600x400"],
            "word_count": 12
        }

def test_bfl_image_generation(api_key: str, prompt: str, width: int = 1024, height: int = 1024):
    """
    Standalone test function to generate an image using BFL API and poll for the result, mimicking the curl commands.
    Usage:
        test_bfl_image_generation('your-api-key', 'beautiful sunset')
    """
    async def run():
        headers = {
            "x-key": api_key,
            "Content-Type": "application/json"
        }
        payload = {
            "output_format": "png",
            "prompt_upsampling": False,
            "safety_tolerance": 2,
            "prompt": prompt,
            "width": width,
            "height": height
        }
        async with aiohttp.ClientSession() as session:
            # Step 1: POST to generate
            print("Sending image generation request...")
            async with session.post("https://api.bfl.ai/v1/flux-kontext-pro", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    print(f"Error: {resp.status}")
                    print(await resp.text())
                    return
                data = await resp.json()
                print("Generation response:", data)
                polling_url = data.get("polling_url")
                if not polling_url:
                    # fallback to id
                    id_ = data.get("id")
                    if not id_:
                        print("No polling URL or id returned!")
                        return
                    polling_url = f"https://api.bfl.ai/v1/get_result?id={id_}"

            # Step 2: Poll for result
            print(f"Polling for result at: {polling_url}")
            for attempt in range(30):
                await asyncio.sleep(3)
                async with session.get(polling_url, headers={"x-key": api_key}) as poll_resp:
                    poll_data = await poll_resp.json()
                    print(f"Attempt {attempt+1}: status={poll_data.get('status')}")
                    if poll_data.get("status") == "Ready":
                        result = poll_data.get("result", {})
                        image_url = result.get("sample") or result.get("url")
                        print(f"Image ready! URL: {image_url}")
                        return image_url
                    elif poll_data.get("status") == "Error":
                        print(f"Generation failed: {poll_data}")
                        return None
            print("Timeout waiting for image generation.")
            return None

    asyncio.run(run())

if __name__ == "__main__":
    import asyncio
    import sys

    async def main():
        # Prompt user for a keyword or use a default
        prompt = input("Enter a prompt for the image (or leave blank for default): ")
        if not prompt:
            prompt = "A futuristic city skyline at sunset, ultra-realistic"
        print(f"\nGenerating image for prompt: '{prompt}'\n")
        
        # Create ContentGenerator instance
        generator = ContentGenerator()
        # Generate image and upload to S3
        image_url = await generator.generate_image(prompt)
        if image_url:
            print(f"\n✅ Image uploaded to S3: {image_url}\n")
        else:
            print("\n❌ Image generation or upload failed.\n")

    asyncio.run(main())