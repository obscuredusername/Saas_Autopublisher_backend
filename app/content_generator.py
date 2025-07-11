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
import random
import requests
from PIL import Image
from io import BytesIO

load_dotenv()

class ContentGenerator:
    image_semaphore = asyncio.Semaphore(2)  # Limit to 2 concurrent image generations
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
                
                "user": """Create a comprehensive biography about {keyword} in {language}. Use the source material below as reference but COMPLETELY REWRITE everything in your own words. The content must be at least 1500 words.\n\nREQUIREMENTS:\n- Language: {language}\n- Minimum length: 1500 words\n- Paraphrase all information (no direct copying)\n- Use proper HTML structure as shown below\n- Include detailed analysis and context\n- Expand on key events with historical background\n- Add multiple sections covering different aspects of life\n- IMPORTANT: When referencing a source, always embed the hyperlink contextually within the paragraph using a natural phrase (anchor tags, not at the end of paragrpahs source please) such as: 'We can understand the situation better from the words of <a href=\"[URL]\" target=\"_blank\">[valuable anchor]</a>'. Do NOT list sources at the end or outside the main text. Hyperlinks must be part of the narrative, not a separate source list.\n\nHTML Structure Required:\n<article class=\"biography\">\n    <h1 class=\"person-name\">{keyword}</h1>\n    
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
                "system": """You are an expert content writer specializing in comprehensive how-to guides. Create detailed, practical guides that are:\n                - MINIMUM 1500 words long\n                - Written in the specified language\n                - Thoroughly paraphrased from source material\n                - Structured with proper HTML formatting\n                - Rich in practical examples and tips\n                - Easy to follow and actionable""",
                
                "user": """Create a comprehensive how-to guide about {keyword} in {language}. Use the source material as reference but completely rewrite in your own words. Minimum 1500 words.\n\nRequirements: Same HTML structure principles as biography but adapted for how-to content.\n- IMPORTANT: When referencing a source, always embed the hyperlink contextually within the paragraph using a natural phrase such as: 'We can understand the situation better from the words of <a href=\"[URL]\" target=\"_blank\">[valuable anchor]</a>'. Do NOT list sources at the end or outside the main text. Hyperlinks must be part of the narrative, not a separate source list.\n\nSOURCE MATERIAL:\n{scraped_data}"""
            },
            
            "company": {
                "system": """You are a business analyst specializing in comprehensive company profiles. Create detailed company analyses that are:\n                - MINIMUM 1500 words long\n                - Written in the specified language\n                - Thoroughly paraphrased from source material\n                - Rich in business insights and analysis""",
                
                "user": """Create a comprehensive company profile about {keyword} in {language}. Use the source material as reference but completely rewrite in your own words. Minimum 1500 words.\n\n- IMPORTANT: When referencing a source, always embed the hyperlink contextually within the paragraph using a natural phrase such as: 'We can understand the situation better from the words of <a href=\"[URL]\" target=\"_blank\">[valuable anchor]</a>'. Do NOT list sources at the end or outside the main text. Hyperlinks must be part of the narrative, not a separate source list.\n\nSOURCE MATERIAL:\n{scraped_data}"""
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

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
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

    async def upload_to_fastapi(self, image_url: str, keyword: str) -> Optional[str]:
        """
        Save image to disk in /var/www/images and return the public URL.
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

    async def generate_image_bfl(self, prompt: str, size: str = "1024x1024") -> Optional[str]:
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
                        "prompt": "Detailed prompt for first image (should be realistic matching the blog)",
                        "purpose": "Purpose of this image in the blog"
                    }},
                    {{
                        "prompt": "Detailed prompt for second image (should be realistic matching the blog)",
                        "purpose": "Purpose of this image in the blog"
                    }}
                ]
            }}

            Requirements:
            - Title should be creative and attention-grabbing
            - Category should be specific and relevant
            - Headings should cover all important aspects of the topic
            - Image prompts should be detailed and specific
            - Images should not be more than two, so please egenrate two prompts only
            - All content should be in {language}
            
            Return ONLY the JSON structure, nothing else."""

            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional blog planner and content strategist. You excel at creating comprehensive blog structures and creative content plans. Always respond with valid JSON only."},
                    {"role": "user", "content": blog_plan_prompt}
                ],
                temperature=0.7
            )
            
            # Parse the response as JSON
            try:
                blog_plan = json.loads(response.choices[0].message.content.strip())
                print(f"\n📝 Generated Blog Plan for '{keyword}' in '{language}':\n{json.dumps(blog_plan, indent=2)}\n")
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
                # Add non-vulgarity requirement to image prompt
                safe_img_prompt = img_prompt["prompt"] + " (Generate image with conservative, loose-fitting clothing only. High necklines, long sleeves, full coverage. Professional modest attire like business suits, sweaters, or conservative dresses. No form-fitting or revealing clothing whatsoever. Family-friendly and appropriate.)"
                task = asyncio.create_task(self.generate_image(safe_img_prompt))
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
            print(f"🎯 Category Selection Debug:")
            print(f"   - Available categories: {category_names}")
            print(f"   - Category list string: {category_list_str}")
            
            # If no categories available, use a default
            if not category_names:
                print(f"   ⚠️ No categories available, using default")
                category_selection_instruction = ""
            else:
                category_selection_instruction = f"""
CRITICAL INSTRUCTION - YOU MUST FOLLOW THIS EXACTLY:

You are writing content about "{keyword}". 

AVAILABLE CATEGORIES (YOU MUST CHOOSE ONE OF THESE EXACT NAMES):
{chr(10).join([f"- {cat}" for cat in category_names])}

BEFORE writing any content, you MUST select the most appropriate category from the list above.

YOUR RESPONSE MUST START WITH THIS EXACT LINE:
SELECTED_CATEGORY: [EXACT category name from the list above]

IMPORTANT RULES:
- You can ONLY use categories from the list above
- You CANNOT create new category names
- You CANNOT use variations or synonyms
- You MUST use the EXACT category name as shown above
- If none seem perfect, choose the closest one

DO NOT write any content until you have selected a category.
DO NOT skip the category selection.

After the SELECTED_CATEGORY line, then write your full content.

EXAMPLE FORMAT:
SELECTED_CATEGORY: SCI-TECH

<article>
[Your full content here]
</article>
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
- DO NOT include any h1 tags in the content (title is separate)
- Include anchor tags to sources (dont qoute them as source, and please dont use one link twice for anchor tags) contextually within the content, using a natural phrase such as: 'We can understand the situation better from the words of <a href=\"[URL]\" target=\"_blank\">[valuable anchor]</a>'. Anchor Tag must be part of the narrative, not a separate source list. And do not repeat links in anchor tags

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
   - Include Anchor tags \
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
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a professional content writer specializing in creating comprehensive, well-researched blog posts. You MUST ALWAYS start your response with a category selection in the format 'SELECTED_CATEGORY: [category name]' before writing any content. DO NOT include any h1 tags in your content - the title is provided separately."},
                    {"role": "user", "content": content_prompt}
                ],
                temperature=0.7,
                max_tokens=3000
            )
            
            generated_content = response.choices[0].message.content.strip()

            # --- Parse selected category from the top of the response ---
            selected_category_name = None
            lines = generated_content.splitlines()
            print(f"🔍 Category Selection Response Debug:")
            print(f"   - First line: {lines[0] if lines else 'No lines'}")
            print(f"   - Total lines: {len(lines)}")
            
            # Try to find SELECTED_CATEGORY in the first few lines
            for i, line in enumerate(lines[:5]):  # Check first 5 lines
                if line.strip().startswith("SELECTED_CATEGORY:"):
                    selected_category_name = line.replace("SELECTED_CATEGORY:", "").strip()
                    print(f"   ✅ Selected category: {selected_category_name}")
                    # Remove the category line from content
                    lines.pop(i)
                    generated_content = "\n".join(lines).lstrip()
                    break
            else:
                print(f"   ❌ No SELECTED_CATEGORY found in first 5 lines")
                # Try to find any category-like line
                for i, line in enumerate(lines[:3]):
                    line_stripped = line.strip()
                    if line_stripped and not line_stripped.startswith('<') and len(line_stripped.split()) <= 3:
                        # This might be a category name
                        potential_category = line_stripped
                        if potential_category in category_names:
                            selected_category_name = potential_category
                            print(f"   ✅ Found potential category: {selected_category_name}")
                            lines.pop(i)
                            generated_content = "\n".join(lines).lstrip()
                            break
                
                # Fallback: Auto-select category based on keyword
                if not selected_category_name and category_names:
                    print(f"   🔄 Auto-selecting category based on keyword...")
                    keyword_lower = keyword.lower()
                    
                    # Simple keyword-based category selection
                    if any(word in keyword_lower for word in ['elon', 'musk', 'bill', 'gates', 'person', 'biography', 'bio']):
                        selected_category_name = 'bio broly'
                    elif any(word in keyword_lower for word in ['tech', 'technology', 'ai', 'software', 'computer', 'science', 'space', 'astronomy']):
                        selected_category_name = 'SCI-TECH'
                    elif any(word in keyword_lower for word in ['health', 'medical', 'doctor', 'hospital', 'medicine']):
                        selected_category_name = 'SANTE'
                    elif any(word in keyword_lower for word in ['politics', 'government', 'election', 'president', 'political']):
                        selected_category_name = 'POLITIQUE'
                    elif any(word in keyword_lower for word in ['economy', 'business', 'finance', 'money', 'economic']):
                        selected_category_name = 'ECONOMIE'
                    elif any(word in keyword_lower for word in ['world', 'international', 'global', 'country']):
                        selected_category_name = 'MONDE'
                    elif any(word in keyword_lower for word in ['entertainment', 'movie', 'music', 'celebrity', 'art', 'culture']):
                        selected_category_name = 'DIVERTISSEMENT'
                    elif any(word in keyword_lower for word in ['sport', 'football', 'basketball', 'athlete', 'game']):
                        selected_category_name = 'SPORT'
                    elif any(word in keyword_lower for word in ['cook', 'food', 'recipe', 'kitchen', 'culinary']):
                        selected_category_name = 'DIVERTISSEMENT'  # Map cooking to entertainment
                    else:
                        selected_category_name = 'A LA UNE'  # Default to main category
                    
                    print(f"   ✅ Auto-selected category: {selected_category_name}")
            # --- End parse ---
            
            # Always use the blog plan title, don't extract from content
            title = blog_plan["title"]
            
            # Remove any h1 tags from content (title should be separate)
            generated_content = re.sub(r'<h1>.*?</h1>', '', generated_content, flags=re.DOTALL)
            
            # Calculate word count
            word_count = len(generated_content.split())
            print(f"📝 Generated content: {word_count} words")
            
            # Verify word count is within target range (changed from 1500 to 800)
            if word_count < 800:
                print(f"⚠️ Warning: Word count ({word_count}) is below target range (800-2000)")
                # If content is too short, try to expand it
                expansion_prompt = f"""Expand the following content to at least 800 words by adding more details and context.
                Maintain the same language ({language}) and HTML structure.
                Use the source material for additional information.

                Current content:
                {generated_content}

                Source material:
                {json.dumps(section_chunks, indent=2)}"""

                expansion_response = await self.client.chat.completions.create(
                    model="gpt-4o-mini",
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
            # Enforce a maximum of two image URLs
            image_urls = image_urls[:2]
            print(f"Image URLs to be returned: {image_urls}")
            
            # Insert images into the content
            if image_urls:
                for i, image_url in enumerate(image_urls):
                    img_tag = f'<img src="{image_url}" alt="{keyword} - {blog_plan["image_prompts"][i]["purpose"]}" rel ="nofollow" class="blog-image" style="max-width: 100%; height: auto; margin: 20px 0;" />'
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
                'image_urls': image_urls,  # Always a list of up to 2 URLs
                'word_count': word_count,
                'selected_category_name': selected_category_name
            }
            
        except Exception as e:
            print(f"❌ Error generating content with plan: {str(e)}")
            return {
                'success': False,
                'message': f'Error generating content: {str(e)}'
            }