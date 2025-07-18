from fastapi import HTTPException
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from app.services.scraper_service import ScrapingService
from app.services.image_generator import ImageGenerator
from app.services.content_generator import ContentGenerator
from app.models.schemas import KeywordRequest, ScrapingResponse, KeywordItem
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from bson.objectid import ObjectId
import re
import os
import json
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import time
import sys
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.retrievers import TFIDFRetriever

class BlogService:
    def __init__(self, db, target_db=None, target_db_name=None):
        self.db = db
        self.scraping_service = ScrapingService()
        self.scraping_service.db = db
        self.image_service = ImageGenerator()
        self.content_generator = ContentGenerator()
        self.target_db = target_db
        self.target_db_name = target_db_name
        self.unprocessed_keywords = []
        self.intermediate_results = {}  # Store intermediate results per keyword
        self.chunk_size = 1000
        self.max_chunks = 10

    @classmethod
    async def create(cls, db, target_db_name=None):
        target_db = None
        if target_db_name:
            config = await db["db_configs"].find_one({"name": target_db_name})
            if not config:
                raise RuntimeError(f"No DB config found for name: {target_db_name}")
            uri = config["target_db_uri"]
            dbname = config["target_db"]
            target_db = AsyncIOMotorClient(uri)[dbname]
        return cls(db, target_db=target_db, target_db_name=target_db_name)

    def get_most_relevant_chunks(self, chunks: list, query: str, top_k: int = 5) -> list:
        if not chunks:
            return []
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = vectorizer.fit_transform(chunks + [query])
        similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
        top_indices = similarities.argsort()[-top_k:][::-1]
        return [chunks[i] for i in top_indices if similarities[i] > 0.1]

    def get_most_relevant_chunks_langchain(self, chunks: list, query: str, top_k: int = 5) -> list:
        """
        Use LangChain's TFIDFRetriever to get the most relevant chunks for a query.
        """
        if not chunks:
            return []
        # LangChain expects documents as strings
        retriever = TFIDFRetriever.from_texts(chunks)
        results = retriever.get_relevant_documents(query)
        # Return the top_k most relevant chunks
        return [doc.page_content for doc in results[:top_k]]

    def chunk_text(self, text: str) -> list:
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

    def wrap_content_in_html(self, title: str, content: str) -> str:
        html_template = f"""
        <!DOCTYPE html>
        <html lang=\"en\">
        <head>
            <meta charset=\"UTF-8\">
            <title>{title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                h1, h2, h3, h4 {{ color: #2c3e50; }}
                img {{ max-width: 100%; height: auto; }}
                .video-container {{ margin: 20px 0; }}
            </style>
        </head>
        <body>
            <h1>{title}</h1>
            {content}
        </body>
        </html>
        """
        return html_template

    async def generate_content_with_plan(self, scraped_data: dict, content_type: str = "biography") -> dict:
        print("DEBUG: Entered generate_content_with_plan")
        search_info = scraped_data.get("search_info", {})
        keyword = search_info.get("keyword", "")
        language = search_info.get("language", "en")
        category_names = scraped_data.get("category_names", [])
        blog_plan = scraped_data.get("blog_plan")
        video_info = scraped_data.get("video_info")
        print("DEBUG: Using blog plan from scraped_data")
        if not isinstance(blog_plan, dict) or "headings" not in blog_plan or not isinstance(blog_plan["headings"], list):
            blog_plan = {"title": keyword, "category": "", "headings": [], "image_prompts": []}
        print("\n===== GENERATED BLOG PLAN =====\n", json.dumps(blog_plan, indent=2), "\n==============================\n")
        all_chunks = []
        references = []
        for item in scraped_data.get("scraped_content", []):
            title = item.get('title', '')
            content = item.get('content', '')
            url = item.get('url', '')
            if url and url.startswith(('http://', 'https://')):
                references.append({'title': title, 'url': url})
            context_block = f"SOURCE: {url}\nTITLE: {title}\nCONTENT: {content}"
            chunks = self.chunk_text(context_block)
            all_chunks.extend(chunks)
        section_chunks = {}
        for heading in blog_plan["headings"]:
            section_title = heading["title"]
            section_query = f"{keyword} {section_title}"
            # Use LangChain RAG retrieval
            relevant_chunks = self.get_most_relevant_chunks_langchain(all_chunks, query=section_query, top_k=self.max_chunks)
            # Add Chain-of-Thought reasoning step as context for each section
            cot_reasoning = (
                f"Let's think step by step about how to write the section '{section_title}'. "
                f"First, consider what information is needed for this section, then use the following context to write a detailed, logical answer."
            )
            section_chunks[section_title] = [cot_reasoning] + relevant_chunks
        if not category_names:
            category_selection_instruction = ""
        else:
            category_selection_instruction = None
        video_section = ""
        if video_info:
            video_section = f"""
VIDEO INFORMATION:
Title: {video_info['title']}
URL: {video_info['url']}
Please include this video in the content with proper HTML embedding using the following format:
<div class=\"video-container\" style=\"position: relative; padding-bottom: 56.25%; height: 0; overflow: hidden; max-width: 100%; margin: 20px 0;\">
    <iframe src=\"{video_info['url'].replace('watch?v=', 'embed/')}\" style=\"position: absolute; top: 0; left: 0; width: 100%; height: 100%; border: 0;\" allow=\"accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>
</div>
<p class=\"video-caption\" style=\"text-align: center; font-style: italic; margin-top: 10px;\">{video_info['title']}</p>
IMPORTANT: Do not create any image tags or references to images that don't exist. Only use the images that will be generated by the system.
"""
        # Generate images from blog plan prompts using image service
        image_urls = []
        if blog_plan.get("image_prompts"):
            for idx, img_prompt in enumerate(blog_plan["image_prompts"]):
                prompt_text = img_prompt.get("prompt")
                if prompt_text:
                    # Generate image using image service
                    image_url = await self.image_service.generate_image(prompt_text, keyword)
                    # Upload to FastAPI and get public URL
                    public_url = await self.image_service.upload_to_fastapi(image_url, keyword) if image_url else None
                    if public_url:
                        image_urls.append(public_url)
                    elif image_url:
                        image_urls.append(image_url)
        
        # Get custom length prompt if provided
        custom_length_prompt = scraped_data.get('custom_length_prompt', '')
        target_word_count = scraped_data.get('target_word_count', 2000)
        
        # Generate content using content generator service
        content_result = await self.content_generator.generate_blog_content(
            keyword=keyword,
            language=language,
            blog_plan=blog_plan,
            video_info=video_info,
            category_names=category_names,
            section_chunks=section_chunks,
            custom_length_prompt=custom_length_prompt,
            target_word_count=target_word_count
        )
        
        if not content_result or not content_result.get('success'):
            return {
                "success": False,
                "content": "",
                "word_count": 0,
                "image_urls": image_urls,
                "selected_category_name": None,
                "html": ""
            }
        
        generated_content = content_result['content']
        word_count = content_result['word_count']
        selected_category_name = content_result['selected_category_name']
        
        # Insert images at the top of the content
        images_html = ''.join([f'<img src="{url}" alt="Blog Image {i+1}" style="max-width:100%;margin:20px 0;"/>' for i, url in enumerate(image_urls)])
        generated_content = images_html + generated_content
        
        # Wrap content in HTML for viewing
        html_content = self.wrap_content_in_html(blog_plan.get('title', keyword), generated_content)
        
        # Automatically save to file
        safe_keyword = re.sub(r'[^a-zA-Z0-9_\-]', '', keyword.replace(' ', '_'))
        html_filename = f"output_blog_{safe_keyword}.html"
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        
        return {
            "success": True,
            "content": generated_content,
            "word_count": word_count,
            "image_urls": image_urls,
            "selected_category_name": selected_category_name,
            "html": html_content
        }

    def extract_json_from_text(self, text):
        match = re.search(r'(\{.*?\}|\[.*?\])', text, re.DOTALL)
        if match:
            return match.group(1)
        return None

    async def get_all_categories(self) -> list:
        """Fetch all categories from the target database"""
        try:
            print(f"🔍 Fetching categories from target DB...")
            categories = await self.target_db.categories.find({}, {
                '_id': 1,
                'name': 1,
                'description': 1
            }).to_list(length=None)
            print(f"   - Found {len(categories)} categories")
            if categories:
                print(f"   - Category names: {[cat.get('name', 'N/A') for cat in categories]}")
            else:
                print(f"   - No categories found in target database")
            return categories
        except Exception as e:
            print(f"❌ Error fetching categories from target DB: {str(e)}")
            return []

    async def process_keywords(self, keyword_request: KeywordRequest) -> ScrapingResponse:
        try:
            # Reset unprocessed keywords list for new batch
            self.unprocessed_keywords = []
            post_ids = []
            tasks = []
            all_unique_links = []
            categories = await self.get_all_categories()
            subcategories = [cat for cat in categories if cat.get('parentId')]
            category_names = [cat['name'] for cat in categories]
            print(f"🚀 Starting processing of {len(keyword_request.keywords)} keywords")
            for idx, keyword_item in enumerate(keyword_request.keywords):
                print(f"📝 Processing keyword {idx + 1}/{len(keyword_request.keywords)}: '{keyword_item.text}'")
                # Instead of async task, process sequentially to collect post IDs
                post_id = await self.orchestrate_keyword_pipeline_collect_id(
                    keyword_item,
                    keyword_request,
                    categories,
                    subcategories,
                    category_names,
                    post_index=idx  # Pass the index for staggered scheduling
                )
                if post_id:
                    post_ids.append(post_id)
            # After all keywords are processed, schedule publish tasks for successful posts
            if post_ids:
                print(f"📅 Scheduling publish tasks for {len(post_ids)} posts...")
                # Manual scheduling removed - now handled by Celery Beat based on scheduledAt field
                print(f"✅ All posts will be published automatically by Celery Beat scheduler")
            else:
                print(f"⚠️ No posts to schedule for publishing")
            # Log processing summary
            print(f"📊 Processing Summary:")
            print(f"   Total keywords: {len(keyword_request.keywords)}")
            print(f"   Unprocessed keywords: {len(self.unprocessed_keywords)}")
            if self.unprocessed_keywords:
                print(f"❌ Unprocessed keywords: {[kw['keyword'] for kw in self.unprocessed_keywords]}")
                print(f"🔄 Starting automatic retry of unprocessed keywords...")
                await self.auto_retry_unprocessed_keywords(keyword_request, categories, subcategories, category_names)
            return ScrapingResponse(
                success=True,
                message=f"Started processing {len(keyword_request.keywords)} keywords.",
                tasks=[{"keyword": k.text, "status": "scheduled"} for k in keyword_request.keywords],
                country=keyword_request.country.lower(),
                language=keyword_request.language.lower(),
                status="processing",
                unique_links=[]
            )
        except Exception as e:
            print(f"Error in process_keywords: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    async def orchestrate_keyword_pipeline(
        self,
        keyword_item,
        keyword_request,
        categories,
        subcategories,
        category_names
    ):
        keyword = keyword_item.text.strip()
        print(f"🎯 Starting pipeline for keyword: '{keyword}'")
        # Debug: Print category information
        print(f"📋 Category Debug Info:")
        print(f"   - Total categories: {len(categories)}")
        print(f"   - Category names: {category_names}")
        print(f"   - Subcategories: {len(subcategories)}")
        try:
            loop = asyncio.get_running_loop()
            # 1. Get links (blocking)
            print(f"🔍 Searching for links for '{keyword}'...")
            def search_with_retry():
                search_results = self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword,
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=25
                )
                if not search_results:
                    print(f"🔄 No search results for '{keyword}', retrying in 5 seconds...")
                    time.sleep(5)
                    search_results = self.scraping_service.scraper.search_duckduckgo(
                        keyword=keyword,
                        country_code=keyword_request.country.lower(),
                        language=keyword_request.language.lower(),
                        max_results=25
                    )
                return search_results
            search_results = await loop.run_in_executor(None, search_with_retry)
            if not search_results:
                error_msg = f"No search results for '{keyword}' after retry"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'search'
                })
                return
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=10)
            if not unique_links:
                error_msg = f"No unique links found for '{keyword}'"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'link_extraction'
                })
                return
            print(f"✅ Found {len(unique_links)} unique links for '{keyword}'")
            # Store scraped links
            self.intermediate_results.setdefault(keyword, {})['scraped_links'] = unique_links
            # 2. Start blog plan generation (async)
            print(f"📋 Generating blog plan for '{keyword}'...")
            blog_plan_task = asyncio.create_task(
                self.content_generator.generate_blog_plan(keyword, keyword_request.language)
            )
            # 3. Start scraping links (blocking, in executor)
            print(f"🕷️ Starting content scraping for '{keyword}'...")
            def scrape_links():
                return self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
            scraping_task = loop.run_in_executor(None, scrape_links)
            # 4. As soon as blog plan is ready, start first image generation (async)
            blog_plan = await blog_plan_task
            # Store blog plan
            self.intermediate_results.setdefault(keyword, {})['blog_plan'] = blog_plan
            # Fallback logic to ensure blog_plan is always valid and not an error dict
            retry_attempts = 0
            while (not blog_plan or not isinstance(blog_plan, dict) or not blog_plan.get("headings") or not blog_plan.get("image_prompts")) and retry_attempts < 2:
                print(f"❌ Blog plan is empty or missing image prompts/headings for '{keyword}'. Retrying blog plan generation (attempt {retry_attempts+2})...")
                blog_plan = await self.content_generator.generate_blog_plan(keyword, keyword_request.language)
                self.intermediate_results[keyword]['blog_plan'] = blog_plan
                retry_attempts += 1
            if (not blog_plan or not isinstance(blog_plan, dict) or blog_plan.get("success") is False or
                "headings" not in blog_plan or not isinstance(blog_plan["headings"], list)):
                blog_plan = {"title": keyword, "category": "", "headings": [], "image_prompts": []}
            elif not blog_plan.get("title"):
                blog_plan["title"] = keyword
            if not blog_plan.get("headings"):
                blog_plan["headings"] = []
            if not blog_plan.get("image_prompts"):
                blog_plan["image_prompts"] = []
            if not blog_plan or not blog_plan.get("headings") or not blog_plan.get("image_prompts"):
                error_msg = f"Failed to generate valid blog plan for '{keyword}' after retries"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'blog_plan'
                })
                return
            print(f"✅ Blog plan generated for '{keyword}'")
            # 5. Await scraping
            scraped_data = await scraping_task
            # Store scraped data
            self.intermediate_results.setdefault(keyword, {})['scraped_data'] = scraped_data
            if not scraped_data:
                error_msg = f"Failed to scrape content for '{keyword}'"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'scraping'
                })
                return
            print(f"✅ Scraped {len(scraped_data)} content items for '{keyword}'")
            # 6. When both blog plan and scraping are ready, start main content generation
            if blog_plan and scraped_data:
                final_data = {
                    'search_info': {
                        'keyword': keyword,
                        'country': keyword_request.country.lower(),
                        'language': keyword_request.language.lower(),
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'total_results_found': len(scraped_data),
                        'user_email': keyword_request.user_email
                    },
                    'scraped_content': scraped_data,
                    'blog_plan': blog_plan,
                    'video_info': self.scraping_service.scraper.video_link_scraper(keyword),
                    'subcategories': subcategories,
                    'category_names': category_names
                }
                print(f"🤖 Generating content for '{keyword}'...")
                content_result = await self.generate_content_with_plan(final_data, "biography")
                # Store content result
                self.intermediate_results.setdefault(keyword, {})['content_result'] = content_result
                image_urls = content_result.get('image_urls', []) if content_result else []
                if not image_urls or (len(image_urls) < 2 and len(blog_plan.get('image_prompts', [])) >= 2):
                    error_msg = f"Image generation failed for '{keyword}'"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'image_generation'
                    })
                    critical_keywords = ['cannot generate', 'balance', 'token', 'insufficient']
                    if any(kw in error_msg.lower() for kw in critical_keywords):
                        print(f"🛑 Critical error detected ('{error_msg}'). Pausing script.")
                        sys.exit(1)
                    return
                if content_result and content_result.get('success'):
                    print(f"✅ Content generation successful for '{keyword}' ({content_result['word_count']} words)")
                    selected_category_name = content_result.get('selected_category_name')
                    category_ids = []
                    print(f"🎯 Processing selected category: {selected_category_name}")
                    if selected_category_name:
                        for cat in categories:
                            if cat['name'].strip().lower() == selected_category_name.strip().lower():
                                category_ids = [str(cat['_id'])]
                                print(f"GPT selected category: {selected_category_name} (ID: {cat['_id']})")
                                break
                        else:
                            print(f"❌ Selected category '{selected_category_name}' not found in available categories")
                    if not category_ids:
                        print(f"🔄 No GPT category selected, using content matching...")
                        category_ids = await self.match_content_categories(content_result['content'], categories)
                    tags = await self.get_all_tags()
                    tag_ids = await self.match_content_tags(content_result['content'], tags)
                    print(f"💾 Saving content to database for '{keyword}'...")
                    save_success = await self.save_generated_content(
                        keyword=keyword,
                        content=content_result['content'],
                        word_count=content_result['word_count'],
                        language=keyword_request.language.lower(),
                        category_ids=category_ids,
                        tag_ids=tag_ids,
                        image_urls=image_urls,
                        metadata={},
                        user_email=keyword_request.user_email,
                        content_type="biography"
                    )
                    if save_success:
                        print(f"✅ Content for '{keyword}' successfully saved to database")
                    else:
                        error_msg = f"Failed to save content to database for '{keyword}'"
                        print(f"❌ {error_msg}")
                        self.unprocessed_keywords.append({
                            'keyword': keyword,
                            'error': error_msg,
                            'stage': 'database_save'
                        })
                else:
                    error_msg = f"Content generation failed for '{keyword}'"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'content_generation'
                    })
        except Exception as e:
            print(f"❌ Error in orchestrate_keyword_pipeline for '{keyword}': {str(e)}")
            self.unprocessed_keywords.append({
                'keyword': keyword,
                'error': str(e),
                'stage': 'pipeline_exception'
            })
        # Store all intermediate results after pipeline
        # (already done after each step above)

    async def orchestrate_keyword_pipeline_collect_id(
        self,
        keyword_item,
        keyword_request,
        categories,
        subcategories,
        category_names,
        post_index: int = 0
    ):
        # This is a copy of orchestrate_keyword_pipeline, but returns the post_id if successful
        keyword = keyword_item.text.strip()
        print(f"🎯 Starting pipeline for keyword: '{keyword}' (collecting post ID)")
        print(f"📋 Category Debug Info:")
        print(f"   - Total categories: {len(categories)}")
        print(f"   - Category names: {category_names}")
        print(f"   - Subcategories: {len(subcategories)}")
        try:
            loop = asyncio.get_running_loop()
            def search_with_retry():
                search_results = self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword,
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=25
                )
                if not search_results:
                    print(f"🔄 No search results for '{keyword}', retrying in 5 seconds...")
                    time.sleep(5)
                    search_results = self.scraping_service.scraper.search_duckduckgo(
                        keyword=keyword,
                        country_code=keyword_request.country.lower(),
                        language=keyword_request.language.lower(),
                        max_results=25
                    )
                return search_results
            search_results = await loop.run_in_executor(None, search_with_retry)
            if not search_results:
                error_msg = f"No search results for '{keyword}' after retry"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'search'
                })
                return None
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=10)
            if not unique_links:
                error_msg = f"No unique links found for '{keyword}'"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'link_extraction'
                })
                return None
            print(f"✅ Found {len(unique_links)} unique links for '{keyword}'")
            self.intermediate_results.setdefault(keyword, {})['scraped_links'] = unique_links
            print(f"📋 Generating blog plan for '{keyword}'...")
            blog_plan_task = asyncio.create_task(
                self.content_generator.generate_blog_plan(keyword, keyword_request.language)
            )
            print(f"🕷️ Starting content scraping for '{keyword}'...")
            def scrape_links():
                return self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
            scraping_task = loop.run_in_executor(None, scrape_links)
            blog_plan = await blog_plan_task
            self.intermediate_results.setdefault(keyword, {})['blog_plan'] = blog_plan
            retry_attempts = 0
            while (not blog_plan or not isinstance(blog_plan, dict) or not blog_plan.get("headings") or not blog_plan.get("image_prompts")) and retry_attempts < 2:
                print(f"❌ Blog plan is empty or missing image prompts/headings for '{keyword}'. Retrying blog plan generation (attempt {retry_attempts+2})...")
                blog_plan = await self.content_generator.generate_blog_plan(keyword, keyword_request.language)
                self.intermediate_results[keyword]['blog_plan'] = blog_plan
                retry_attempts += 1
            if (not blog_plan or not isinstance(blog_plan, dict) or blog_plan.get("success") is False or
                "headings" not in blog_plan or not isinstance(blog_plan["headings"], list)):
                blog_plan = {"title": keyword, "category": "", "headings": [], "image_prompts": []}
            elif not blog_plan.get("title"):
                blog_plan["title"] = keyword
            if not blog_plan.get("headings"):
                blog_plan["headings"] = []
            if not blog_plan.get("image_prompts"):
                blog_plan["image_prompts"] = []
            if not blog_plan or not blog_plan.get("headings") or not blog_plan.get("image_prompts"):
                error_msg = f"Failed to generate valid blog plan for '{keyword}' after retries"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'blog_plan'
                })
                return None
            print(f"✅ Blog plan generated for '{keyword}'")
            scraped_data = await scraping_task
            self.intermediate_results.setdefault(keyword, {})['scraped_data'] = scraped_data
            if not scraped_data:
                error_msg = f"Failed to scrape content for '{keyword}'"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'scraping'
                })
                return None
            print(f"✅ Scraped {len(scraped_data)} content items for '{keyword}'")
            if blog_plan and scraped_data:
                final_data = {
                    'search_info': {
                        'keyword': keyword,
                        'country': keyword_request.country.lower(),
                        'language': keyword_request.language.lower(),
                        'timestamp': datetime.now(timezone.utc).isoformat(),
                        'total_results_found': len(scraped_data),
                        'user_email': keyword_request.user_email
                    },
                    'scraped_content': scraped_data,
                    'blog_plan': blog_plan,
                    'video_info': self.scraping_service.scraper.video_link_scraper(keyword),
                    'subcategories': subcategories,
                    'category_names': category_names
                }
                print(f"🤖 Generating content for '{keyword}'...")
                content_result = await self.generate_content_with_plan(final_data, "biography")
                self.intermediate_results.setdefault(keyword, {})['content_result'] = content_result
                image_urls = content_result.get('image_urls', []) if content_result else []
                if not image_urls or (len(image_urls) < 2 and len(blog_plan.get('image_prompts', [])) >= 2):
                    error_msg = f"Image generation failed for '{keyword}'"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'image_generation'
                    })
                    critical_keywords = ['cannot generate', 'balance', 'token', 'insufficient']
                    if any(kw in error_msg.lower() for kw in critical_keywords):
                        print(f"🛑 Critical error detected ('{error_msg}'). Pausing script.")
                        sys.exit(1)
                    return None
                if content_result and content_result.get('success'):
                    print(f"✅ Content generation successful for '{keyword}' ({content_result['word_count']} words)")
                    selected_category_name = content_result.get('selected_category_name')
                    category_ids = []
                    print(f"🎯 Processing selected category: {selected_category_name}")
                    if selected_category_name:
                        for cat in categories:
                            if cat['name'].strip().lower() == selected_category_name.strip().lower():
                                category_ids = [str(cat['_id'])]
                                print(f"GPT selected category: {selected_category_name} (ID: {cat['_id']})")
                                break
                        else:
                            print(f"❌ Selected category '{selected_category_name}' not found in available categories")
                    if not category_ids:
                        print(f"🔄 No GPT category selected, using content matching...")
                        category_ids = await self.match_content_categories(content_result['content'], categories)
                    tags = await self.get_all_tags()
                    tag_ids = await self.match_content_tags(content_result['content'], tags)
                    print(f"💾 Saving content to database for '{keyword}'...")
                    post_id = await self.save_generated_content(
                        keyword=keyword,
                        content=content_result['content'],
                        word_count=content_result['word_count'],
                        language=keyword_request.language.lower(),
                        category_ids=category_ids,
                        tag_ids=tag_ids,
                        image_urls=image_urls,
                        metadata={},
                        user_email=keyword_request.user_email,
                        content_type="biography",
                        post_index=post_index
                    )
                    if post_id:
                        print(f"✅ Content for '{keyword}' successfully saved to database (ID: {post_id})")
                        return post_id
                    else:
                        error_msg = f"Failed to save content to database for '{keyword}'"
                        print(f"❌ {error_msg}")
                        self.unprocessed_keywords.append({
                            'keyword': keyword,
                            'error': error_msg,
                            'stage': 'database_save'
                        })
                        return None
                else:
                    error_msg = f"Content generation failed for '{keyword}'"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'content_generation'
                    })
                    return None
        except Exception as e:
            print(f"❌ Error in orchestrate_keyword_pipeline for '{keyword}': {str(e)}")
            self.unprocessed_keywords.append({
                'keyword': keyword,
                'error': str(e),
                'stage': 'pipeline_exception'
            })
            return None

    async def auto_retry_unprocessed_keywords(self, keyword_request, categories, subcategories, category_names):
        """Automatically retry unprocessed keywords with different strategies, only retrying the failed step and reusing previous results."""
        try:
            print(f"🔄 Auto-retry: Processing {len(self.unprocessed_keywords)} failed keywords")
            retry_keywords = self.unprocessed_keywords.copy()
            self.unprocessed_keywords = []
            for idx, failed_keyword in enumerate(retry_keywords):
                keyword = failed_keyword['keyword']
                stage = failed_keyword['stage']
                error = failed_keyword['error']
                print(f"🔄 Auto-retry {idx + 1}/{len(retry_keywords)}: '{keyword}' (Failed at: {stage})")
                results = self.intermediate_results.get(keyword, {})
                # Step-wise retry logic
                if stage == 'image_generation':
                    print(f"🔁 Retrying only image generation for '{keyword}'...")
                    blog_plan = results.get('blog_plan')
                    scraped_data = results.get('scraped_data')
                    if blog_plan and scraped_data:
                        image_urls = []
                        for img_prompt in blog_plan.get('image_prompts', []):
                            prompt_text = img_prompt.get('prompt')
                            if prompt_text:
                                image_url = await self.image_service.generate_image(prompt_text, keyword)
                                # Upload to FastAPI and get public URL
                                public_url = await self.image_service.upload_to_fastapi(image_url, keyword) if image_url else None
                                if public_url:
                                    image_urls.append(public_url)
                                elif image_url:
                                    image_urls.append(image_url)
                        self.intermediate_results[keyword]['image_urls'] = image_urls
                        # Optionally, retry content generation if needed
                        content_result = results.get('content_result')
                        if not content_result or not content_result.get('success'):
                            print(f"🔁 Retrying content generation for '{keyword}' after image generation...")
                            final_data = {
                                'search_info': scraped_data['search_info'],
                                'scraped_content': scraped_data['scraped_content'],
                                'blog_plan': blog_plan,
                                'video_info': scraped_data.get('video_info'),
                                'subcategories': subcategories,
                                'category_names': category_names
                            }
                            content_result = await self.generate_content_with_plan(final_data, "biography")
                            self.intermediate_results[keyword]['content_result'] = content_result
                    continue
                elif stage == 'content_generation':
                    print(f"🔁 Retrying only content generation for '{keyword}'...")
                    blog_plan = results.get('blog_plan')
                    scraped_data = results.get('scraped_data')
                    image_urls = results.get('image_urls', [])
                    if blog_plan and scraped_data:
                        final_data = {
                            'search_info': scraped_data['search_info'],
                            'scraped_content': scraped_data['scraped_content'],
                            'blog_plan': blog_plan,
                            'video_info': scraped_data.get('video_info'),
                            'subcategories': subcategories,
                            'category_names': category_names
                        }
                        content_result = await self.generate_content_with_plan(final_data, "biography")
                        self.intermediate_results[keyword]['content_result'] = content_result
                    continue
                elif stage == 'blog_plan':
                    print(f"🔁 Retrying only blog plan for '{keyword}'...")
                    blog_plan = await self.content_generator.generate_blog_plan(keyword, keyword_request.language)
                    self.intermediate_results[keyword]['blog_plan'] = blog_plan
                    # Optionally, retry image generation if needed
                    scraped_data = results.get('scraped_data')
                    if blog_plan and scraped_data:
                        image_urls = []
                        for img_prompt in blog_plan.get('image_prompts', []):
                            prompt_text = img_prompt.get('prompt')
                            if prompt_text:
                                image_url = await self.image_service.generate_image(prompt_text, keyword)
                                # Upload to FastAPI and get public URL
                                public_url = await self.image_service.upload_to_fastapi(image_url, keyword) if image_url else None
                                if public_url:
                                    image_urls.append(public_url)
                                elif image_url:
                                    image_urls.append(image_url)
                        self.intermediate_results[keyword]['image_urls'] = image_urls
                    continue
                elif stage == 'scraping':
                    print(f"🔁 Retrying only scraping for '{keyword}'...")
                    unique_links = results.get('scraped_links')
                    if not unique_links:
                        print(f"⚠️ No scraped_links found for '{keyword}', cannot retry scraping.")
                        continue
                    loop = asyncio.get_running_loop()
                    def scrape_links():
                        return self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
                    scraped_data = await loop.run_in_executor(None, scrape_links)
                    self.intermediate_results[keyword]['scraped_data'] = scraped_data
                    # Optionally, retry content generation if needed
                    blog_plan = results.get('blog_plan')
                    if blog_plan and scraped_data:
                        final_data = {
                            'search_info': scraped_data['search_info'],
                            'scraped_content': scraped_data['scraped_content'],
                            'blog_plan': blog_plan,
                            'video_info': scraped_data.get('video_info'),
                            'subcategories': subcategories,
                            'category_names': category_names
                        }
                        content_result = await self.generate_content_with_plan(final_data, "biography")
                        self.intermediate_results[keyword]['content_result'] = content_result
                    continue
                else:
                    print(f"🔁 Fallback: standard retry for '{keyword}'...")
                    # Only retry the failed step, do not redo everything
                    # If we don't know the stage, just skip for now
                    continue
            successful_retries = len(retry_keywords) - len(self.unprocessed_keywords)
            print(f"📊 Auto-retry Summary:")
            print(f"   Total retried: {len(retry_keywords)}")
            print(f"   Successful retries: {successful_retries}")
            print(f"   Still failed: {len(self.unprocessed_keywords)}")
        except Exception as e:
            print(f"❌ Error in auto-retry process: {str(e)}")

    async def retry_with_different_search_params(self, keyword, keyword_request, categories, subcategories, category_names):
        try:
            print(f"   🔍 Retrying '{keyword}' with different search parameters...")
            search_variations = [keyword, f"{keyword} biography", f"{keyword} profile", f"{keyword} information"]
            for search_term in search_variations:
                print(f"   🔍 Trying search term: '{search_term}'")
                loop = asyncio.get_running_loop()
                search_results = await loop.run_in_executor(None, lambda: self.scraping_service.scraper.search_duckduckgo(
                    keyword=search_term,
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=15
                ))
                if search_results:
                    unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=5)
                    if unique_links:
                        print(f"   ✅ Found links with search term: '{search_term}'")
                        return await self.process_with_links(keyword, unique_links, keyword_request, categories, subcategories, category_names)
                await asyncio.sleep(2)
            return False
        except Exception as e:
            print(f"   ❌ Error in search retry: {str(e)}")
            return False

    async def retry_with_simplified_generation(self, keyword, keyword_request, categories, subcategories, category_names):
        try:
            print(f"   🤖 Retrying '{keyword}' with simplified generation...")
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(None, lambda: self.scraping_service.scraper.search_duckduckgo(
                keyword=keyword,
                country_code=keyword_request.country.lower(),
                language=keyword_request.language.lower(),
                max_results=10
            ))
            if not search_results:
                return False
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=3)
            if not unique_links:
                return False
            return await self.process_with_simplified_generation(keyword, unique_links, keyword_request, categories, subcategories, category_names)
        except Exception as e:
            print(f"   ❌ Error in simplified generation retry: {str(e)}")
            return False

    async def retry_with_fewer_links(self, keyword, keyword_request, categories, subcategories, category_names):
        try:
            print(f"   🕷️ Retrying '{keyword}' with fewer links...")
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(None, lambda: self.scraping_service.scraper.search_duckduckgo(
                keyword=keyword,
                country_code=keyword_request.country.lower(),
                language=keyword_request.language.lower(),
                max_results=10
            ))
            if not search_results:
                return False
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=2)
            if not unique_links:
                return False
            return await self.process_with_links(keyword, unique_links, keyword_request, categories, subcategories, category_names)
        except Exception as e:
            print(f"   ❌ Error in fewer links retry: {str(e)}")
            return False

    async def retry_with_standard_approach(self, keyword, keyword_request, categories, subcategories, category_names):
        try:
            print(f"   🔄 Retrying '{keyword}' with standard approach...")
            keyword_item = KeywordItem(text=keyword, minLength=0)
            await self.orchestrate_keyword_pipeline(
                keyword_item,
                keyword_request,
                categories,
                subcategories,
                category_names
            )
            return len([kw for kw in self.unprocessed_keywords if kw['keyword'] == keyword]) == 0
        except Exception as e:
            print(f"   ❌ Error in standard retry: {str(e)}")
            return False

    async def process_with_links(self, keyword, unique_links, keyword_request, categories, subcategories, category_names):
        try:
            keyword_item = KeywordItem(text=keyword, minLength=0)
            return await self.orchestrate_keyword_pipeline_with_links(
                keyword_item, unique_links, keyword_request, categories, subcategories, category_names
            )
        except Exception as e:
            print(f"   ❌ Error processing with links: {str(e)}")
            return False

    async def process_with_simplified_generation(self, keyword, unique_links, keyword_request, categories, subcategories, category_names):
        try:
            keyword_item = KeywordItem(text=keyword, minLength=0)
            return await self.orchestrate_keyword_pipeline_with_links(
                keyword_item, unique_links, keyword_request, categories, subcategories, category_names
            )
        except Exception as e:
            print(f"   ❌ Error processing with links: {str(e)}")
            return False

    async def get_all_tags(self) -> list:
        """Fetch all tags from the target database"""
        try:
            tags = await self.target_db.tags.find({}, {
                '_id': 1,
                'name': 1,
                'description': 1
            }).to_list(length=None)
            return tags
        except Exception as e:
            print(f"Error fetching tags from target DB: {str(e)}")
            return []

    async def match_content_tags(self, content: str, tags: list) -> list:
        """Match content with relevant tags and return their IDs"""
        try:
            if not tags:
                return []
            tag_texts = [f"{tag.get('name', '')} {tag.get('description', '')}" for tag in tags]
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(tag_texts + [content])
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            top_index = np.argmax(similarities)
            if similarities[top_index] > 0.1:
                tag_id = tags[top_index].get('_id')
                if tag_id:
                    print(f"Selected tag: {tags[top_index].get('name')}")
                    return [str(tag_id)]
            return []
        except Exception as e:
            print(f"Error matching tags: {str(e)}")
            return []

    async def match_content_categories(self, content: str, categories: list) -> list:
        """Match content with relevant categories and return their IDs"""
        try:
            if not categories:
                return []
            category_texts = [f"{cat.get('name', '')} {cat.get('description', '')}" for cat in categories]
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(category_texts + [content])
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            top_index = np.argmax(similarities)
            if similarities[top_index] > 0.1:
                cat_id = categories[top_index].get('_id')
                if cat_id:
                    print(f"Selected category: {categories[top_index].get('name')}")
                    return [str(cat_id)]
            return []
        except Exception as e:
            print(f"Error matching categories: {str(e)}")
            return []

    async def get_default_category(self, content_type: str) -> Optional[str]:
        """Get default category for content type"""
        try:
            # Try to find a default category based on content type
            if content_type == "biography":
                # Look for a biography or people category
                categories = await self.get_all_categories()
                for cat in categories:
                    if any(keyword in cat.get('name', '').lower() for keyword in ['biography', 'people', 'person', 'profile']):
                        return str(cat['_id'])
            
            # If no specific category found, return the first available category
            categories = await self.get_all_categories()
            if categories:
                return str(categories[0]['_id'])
            
            return None
        except Exception as e:
            print(f"Error getting default category: {str(e)}")
            return None

    async def save_generated_content(
        self,
        keyword: str,
        content: str,
        word_count: int,
        language: str,
        category_ids: list,
        tag_ids: list,
        image_urls: list,
        metadata: dict,
        user_email: str,
        content_type: str,
        post_index: int = 0,
        target_db: str = None,
        target_collection: str = None,
        author_id: ObjectId = None,
        scheduled_at: Optional[datetime] = None
    ) -> bool:
        """Save generated content to the database"""
        try:
            # Always use CRM for all content types
            target_db = "CRM"
            target_collection = "posts"
            target_db_uri = os.getenv('NEWS_TARGET_DB_URI', 'mongodb+srv://cryptoanalysis45:Zz5e0HLdDoF9SJXA@cluster0.zqdhkxn.mongodb.net/CRM')
            author_id = author_id or ObjectId('683b3771a6b031d7d73735d7')

            print(f"💾 Starting database save operation for keyword: '{keyword}'")
            print(f"   📊 Content details:")
            print(f"      - Word count: {word_count}")
            print(f"      - Language: {language}")
            print(f"      - Categories: {category_ids}")
            print(f"      - Tags: {tag_ids}")
            print(f"      - Image URLs: {len(image_urls)} images")
            print(f"      - User: {user_email}")
            print(f"      - Content type: {content_type}")
            print(f"      - Target DB: {target_db}")
            print(f"      - Target Collection: {target_collection}")
            print(f"      - Target URI: {target_db_uri}")
            print(f"      - Author ID: {author_id}")
            print(f"      - Post index: {post_index}")
            
            # Calculate scheduledAt time (staggered by 10 minutes per post for news, 5 minutes for keywords)
            now = datetime.now(timezone.utc)
            if scheduled_at is not None:
                scheduled_at_time = scheduled_at
            elif content_type == "news_article":
                scheduled_at_time = now + timedelta(minutes=post_index * 10)  # 10 minutes apart for news
            else:
                scheduled_at_time = now + timedelta(minutes=post_index * 5)  # 5 minutes apart for keywords
            
            print(f"   ⏰ Scheduled for publishing at: {scheduled_at_time}")
            
            if category_ids is None:
                category_ids = []
            if tag_ids is None:
                tag_ids = []
            if not category_ids:
                print(f"   ⚠️ No categories matched, trying to get default category...")
                default_category = await self.get_default_category(content_type)
                if default_category:
                    category_ids = [default_category]
                    print(f"   ✅ Using default category: {default_category}")
                else:
                    print(f"   ⚠️ No default category found for content type: {content_type}")
            category_object_ids = [ObjectId(cat_id) for cat_id in category_ids if cat_id]
            tag_object_ids = [ObjectId(tag_id) for tag_id in tag_ids if tag_id]
            print(f"   🔄 Converted IDs:")
            print(f"      - Category ObjectIds: {category_object_ids}")
            print(f"      - Tag ObjectIds: {tag_object_ids}")
            
            # Extract title from content
            title = None
            title_match = re.search(r'<h2>(.*?)</h2>', content)
            if title_match:
                title = title_match.group(1)
                print(f"   📝 Extracted title from content: {title}")
            if not title:
                title = keyword
                print(f"   📝 Using keyword as title: {title}")
            
            # Generate slug
            slug = self.generate_slug(title)
            print(f"   🔗 Generated slug: {slug}")
            
            # Create content document with new fields
            content_doc = {
                "title": title,
                "content": content,
                "slug": slug,
                "excerpt": title,
                "status": "pending",
                "categoryIds": category_object_ids,
                "tagIds": tag_object_ids,
                "authorId": author_id,
                "createdAt": now,
                "updatedAt": now,
                "__v": 0,
                "canonicalUrl": "",
                "featured": False,
                "focusKeyword": keyword,
                "metaDescription": title,
                "metaImage": image_urls[0] if image_urls else "http://localhost:3000/dashboard/posts/new",
                "metaKeywords": keyword,
                "metaTitle": title,
                "ogDescription": title,
                "ogTitle": title,
                "ogType": "article",
                "readingTime": word_count // 200,
                "twitterCard": "summary_large_image",
                "twitterDescription": title,
                "user_email": user_email,
                "content_type": content_type,
                "image_urls": image_urls,
                "metadata": metadata,
                "word_count": word_count,
                "language": language,
                "scheduledAt": scheduled_at_time,  # When to publish
                "target_db": target_db,  # Which database to publish to
                "target_collection": target_collection,
                "target_url": target_db_uri  # Store the target URL for publishing
            }
            
            print(f"   📄 Content document prepared, attempting database insertion...")
            # Save to broker.posts collection
            from motor.motor_asyncio import AsyncIOMotorClient
            mongo_url = 'mongodb+srv://zubairisworking:Ki66bNWmpi70Y9Ql@cluster0.dtdmgdx.mongodb.net/broker?retryWrites=true&w=majority'
            client = AsyncIOMotorClient(mongo_url)
            db = client['broker']
            collection = db['posts']
            result = await collection.insert_one(content_doc)
            
            if result.inserted_id:
                print(f"   ✅ Content saved successfully to broker.posts with ID: {result.inserted_id}")
                print(f"   📅 Will be published to {target_db}.{target_collection} at: {scheduled_at_time}")
                print(f"   🔗 Target URL: {target_db_uri}")
                client.close()
                return str(result.inserted_id)
            else:
                print(f"   ❌ Failed to save content to broker database")
                client.close()
                return None
                
        except Exception as e:
            print(f"   ❌ Error saving generated content to database: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def schedule_publish_tasks(self, post_ids, delay_minutes=5):
        """Schedule publish_post_task for each post ID, staggered by delay_minutes."""
        from app.services.tasks import publish_post_task
        for i, post_id in enumerate(post_ids):
            countdown = i * delay_minutes * 60
            print(f"Scheduling publish for post {post_id} in {countdown//60} minutes...")
            publish_post_task.apply_async((post_id,), countdown=countdown)

    def generate_slug(self, title: str) -> str:
        """Generate a URL-friendly slug from title"""
        slug = title.lower().strip()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        return slug 