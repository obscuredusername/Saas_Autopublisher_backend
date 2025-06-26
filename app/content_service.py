# content_service.py - Enhanced version with all DB operations and content matching

from fastapi import HTTPException
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.scraper_service import ScrapingService
from app.content_generator import ContentGenerator
from app.models import KeywordRequest, ScrapingResponse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from bson.objectid import ObjectId
import re
import os
import json
from motor.motor_asyncio import AsyncIOMotorClient
import asyncio
import threading
import time
import sys

class ContentService:
    def __init__(self, db):
        self.db = db
        self.scraping_service = ScrapingService()
        self.scraping_service.db = db
        self.content_generator = ContentGenerator()  # No db dependency
        
        # Initialize target DB connection using global variables from routes
        from app.routes import TARGET_DB_URI, TARGET_DB
        self.target_db = AsyncIOMotorClient(TARGET_DB_URI)[TARGET_DB]
        
        # Track unprocessed keywords
        self.unprocessed_keywords = []

    def generate_slug(self, title: str) -> str:
        """Generate a URL-friendly slug from the title"""
        # Convert to lowercase and replace spaces with hyphens
        slug = title.lower()
        # Remove special characters
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        # Replace multiple spaces or hyphens with single hyphen
        slug = re.sub(r'[\s-]+', '-', slug)
        # Remove leading/trailing hyphens
        slug = slug.strip('-')
        
        return f"{slug}"

    def run_scrape_and_generate_content(self, *args, **kwargs):
        # Sync wrapper for async scrape_and_generate_content
        asyncio.run(self.scrape_and_generate_content(*args, **kwargs))

    async def process_keywords(self, keyword_request: KeywordRequest) -> ScrapingResponse:
        try:
            # Reset unprocessed keywords list for new batch
            self.unprocessed_keywords = []
            
            tasks = []
            all_unique_links = []
            categories = await self.get_all_categories()
            subcategories = [cat for cat in categories if cat.get('parentId')]
            category_names = [cat['name'] for cat in categories]
            
            print(f"🚀 Starting processing of {len(keyword_request.keywords)} keywords")
            
            for idx, keyword_item in enumerate(keyword_request.keywords):
                print(f"📝 Processing keyword {idx + 1}/{len(keyword_request.keywords)}: '{keyword_item.text}'")
                tasks.append(asyncio.create_task(
                    self.orchestrate_keyword_pipeline(
                        keyword_item,
                        keyword_request,
                        categories,
                        subcategories,
                        category_names
                    )
                ))
                if idx < len(keyword_request.keywords) - 1:
                    print("⏳ Waiting 10 seconds before starting next task...")
                    await asyncio.sleep(10)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # Log processing summary
            print(f"📊 Processing Summary:")
            print(f"   Total keywords: {len(keyword_request.keywords)}")
            print(f"   Unprocessed keywords: {len(self.unprocessed_keywords)}")
            
            if self.unprocessed_keywords:
                print(f"❌ Unprocessed keywords: {[kw['keyword'] for kw in self.unprocessed_keywords]}")
                print(f"🔄 Starting automatic retry of unprocessed keywords...")
                
                # Automatically retry unprocessed keywords
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

    async def auto_retry_unprocessed_keywords(self, keyword_request: KeywordRequest, categories, subcategories, category_names):
        """Automatically retry unprocessed keywords with different strategies"""
        try:
            print(f"🔄 Auto-retry: Processing {len(self.unprocessed_keywords)} failed keywords")
            
            # Create a copy of unprocessed keywords for retry
            retry_keywords = self.unprocessed_keywords.copy()
            self.unprocessed_keywords = []  # Reset for retry results
            
            for idx, failed_keyword in enumerate(retry_keywords):
                keyword = failed_keyword['keyword']
                stage = failed_keyword['stage']
                error = failed_keyword['error']
                
                print(f"🔄 Auto-retry {idx + 1}/{len(retry_keywords)}: '{keyword}' (Failed at: {stage})")
                
                # Different retry strategies based on failure stage
                if stage in ['search', 'link_extraction']:
                    # For search/link failures, try with different search parameters
                    success = await self.retry_with_different_search_params(
                        keyword, keyword_request, categories, subcategories, category_names
                    )
                elif stage in ['blog_plan', 'content_generation']:
                    # For content generation failures, try with simplified approach
                    success = await self.retry_with_simplified_generation(
                        keyword, keyword_request, categories, subcategories, category_names
                    )
                elif stage in ['scraping', 'data_preparation']:
                    # For scraping failures, try with fewer links
                    success = await self.retry_with_fewer_links(
                        keyword, keyword_request, categories, subcategories, category_names
                    )
                else:
                    # For other failures, try standard retry
                    success = await self.retry_with_standard_approach(
                        keyword, keyword_request, categories, subcategories, category_names
                    )
                
                if success:
                    print(f"✅ Auto-retry successful for '{keyword}'")
                else:
                    print(f"❌ Auto-retry failed for '{keyword}'")
                    # Store in database for manual review
                    await self.store_single_unprocessed_keyword(failed_keyword, keyword_request)
            
            # Final summary
            successful_retries = len(retry_keywords) - len(self.unprocessed_keywords)
            print(f"📊 Auto-retry Summary:")
            print(f"   Total retried: {len(retry_keywords)}")
            print(f"   Successful retries: {successful_retries}")
            print(f"   Still failed: {len(self.unprocessed_keywords)}")
            
        except Exception as e:
            print(f"❌ Error in auto-retry process: {str(e)}")

    async def retry_with_different_search_params(self, keyword, keyword_request, categories, subcategories, category_names):
        """Retry with different search parameters"""
        try:
            print(f"   🔍 Retrying '{keyword}' with different search parameters...")
            
            # Try with different search terms
            search_variations = [
                keyword,
                f"{keyword} biography",
                f"{keyword} profile",
                f"{keyword} information"
            ]
            
            for search_term in search_variations:
                print(f"   🔍 Trying search term: '{search_term}'")
                
                loop = asyncio.get_running_loop()
                search_results = await loop.run_in_executor(None, lambda: 
                    self.scraping_service.scraper.search_duckduckgo(
                        keyword=search_term,
                        country_code=keyword_request.country.lower(),
                        language=keyword_request.language.lower(),
                        max_results=15  # Reduced for retry
                    )
                )
                
                if search_results:
                    unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=5)  # Reduced count
                    if unique_links:
                        print(f"   ✅ Found links with search term: '{search_term}'")
                        return await self.process_with_links(keyword, unique_links, keyword_request, categories, subcategories, category_names)
                
                await asyncio.sleep(2)  # Brief pause between attempts
            
            return False
            
        except Exception as e:
            print(f"   ❌ Error in search retry: {str(e)}")
            return False

    async def retry_with_simplified_generation(self, keyword, keyword_request, categories, subcategories, category_names):
        """Retry with simplified content generation"""
        try:
            print(f"   🤖 Retrying '{keyword}' with simplified generation...")
            
            # Try to get at least some search results
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(None, lambda: 
                self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword,
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=10
                )
            )
            
            if not search_results:
                return False
            
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=3)  # Very few links
            if not unique_links:
                return False
            
            # Try simplified content generation
            return await self.process_with_simplified_generation(keyword, unique_links, keyword_request, categories, subcategories, category_names)
            
        except Exception as e:
            print(f"   ❌ Error in simplified generation retry: {str(e)}")
            return False

    async def retry_with_fewer_links(self, keyword, keyword_request, categories, subcategories, category_names):
        """Retry with fewer links to scrape"""
        try:
            print(f"   🕷️ Retrying '{keyword}' with fewer links...")
            
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(None, lambda: 
                self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword,
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=10
                )
            )
            
            if not search_results:
                return False
            
            unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=2)  # Very few links
            if not unique_links:
                return False
            
            return await self.process_with_links(keyword, unique_links, keyword_request, categories, subcategories, category_names)
            
        except Exception as e:
            print(f"   ❌ Error in fewer links retry: {str(e)}")
            return False

    async def retry_with_standard_approach(self, keyword, keyword_request, categories, subcategories, category_names):
        """Standard retry approach"""
        try:
            print(f"   🔄 Retrying '{keyword}' with standard approach...")
            
            # Create a keyword item for retry
            from app.models import KeywordItem
            keyword_item = KeywordItem(
                text=keyword,
                scheduledDate=keyword_request.keywords[0].scheduledDate if keyword_request.keywords else "2024-01-01",
                scheduledTime=keyword_request.keywords[0].scheduledTime if keyword_request.keywords else "10:00",
                minLength=0
            )
            
            # Try the standard pipeline
            await self.orchestrate_keyword_pipeline(
                keyword_item,
                keyword_request,
                categories,
                subcategories,
                category_names
            )
            
            # Check if it succeeded (no new unprocessed keywords for this keyword)
            return len([kw for kw in self.unprocessed_keywords if kw['keyword'] == keyword]) == 0
            
        except Exception as e:
            print(f"   ❌ Error in standard retry: {str(e)}")
            return False

    async def process_with_links(self, keyword, unique_links, keyword_request, categories, subcategories, category_names):
        """Process keyword with given links"""
        try:
            # Create keyword item
            from app.models import KeywordItem
            keyword_item = KeywordItem(
                text=keyword,
                scheduledDate=keyword_request.keywords[0].scheduledDate if keyword_request.keywords else "2024-01-01",
                scheduledTime=keyword_request.keywords[0].scheduledTime if keyword_request.keywords else "10:00",
                minLength=0
            )
            
            # Use the existing pipeline logic but with provided links
            return await self.orchestrate_keyword_pipeline_with_links(
                keyword_item, unique_links, keyword_request, categories, subcategories, category_names
            )
            
        except Exception as e:
            print(f"   ❌ Error processing with links: {str(e)}")
            return False

    def clean_content_and_title(self, title: str, content: str):
        """
        - Removes <img> tags whose src does NOT start with 'https://autopublisher-crm'
        - If title is '[Reference in fr]', replaces it with the first <h1>...</h1> in content and removes that <h1> from content
        Returns: (new_title, cleaned_content)
        """
        def img_replacer(match):
            src = match.group(1)
            if src.startswith("https://autopublisher-crm"):
                return match.group(0)  # keep the tag
            return ""  # remove the tag

        img_pattern = re.compile(r'<img\s+[^>]*src="([^"]+)"[^>]*>', re.IGNORECASE)
        cleaned_content = img_pattern.sub(img_replacer, content)

        # 2. If title is [Reference in fr], extract first <h1>...</h1>
        if title.strip().lower() == "[reference in fr]":
            h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', cleaned_content, re.IGNORECASE | re.DOTALL)
            if h1_match:
                new_title = h1_match.group(1).strip()
                # Remove the first <h1>...</h1> from content
                cleaned_content = cleaned_content[:h1_match.start()] + cleaned_content[h1_match.end():]
                return new_title, cleaned_content
        return title, cleaned_content

    async def process_with_simplified_generation(self, keyword, unique_links, keyword_request, categories, subcategories, category_names):
        """Process keyword with simplified content generation"""
        try:
            # Create keyword item
            from app.models import KeywordItem
            keyword_item = KeywordItem(
                text=keyword,
                scheduledDate=keyword_request.keywords[0].scheduledDate if keyword_request.keywords else "2024-01-01",
                scheduledTime=keyword_request.keywords[0].scheduledTime if keyword_request.keywords else "10:00",
                minLength=0
            )
            # Use the existing pipeline logic but with provided links
            content_result = await self.orchestrate_keyword_pipeline_with_links(
                keyword_item, unique_links, keyword_request, categories, subcategories, category_names
            )
            if content_result and content_result.get('success'):
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
                # Clean content and title before saving
                cleaned_title, cleaned_content = self.clean_content_and_title(content_result['title'], content_result['content'])
                tags = await self.get_all_tags()
                tag_ids = await self.match_content_tags(cleaned_content, tags)
                return await self.save_generated_content(
                    keyword=keyword,
                    content=cleaned_content,
                    word_count=content_result['word_count'],
                    language=keyword_request.language.lower(),
                    category_ids=category_ids,
                    tag_ids=tag_ids,
                    image_urls=content_result.get('image_urls', []),
                    metadata={},
                    scheduled_date=keyword_item.scheduledDate,
                    scheduled_time=keyword_item.scheduledTime,
                    user_email=keyword_request.user_email,
                    content_type="biography"
                )
            else:
                print(f"❌ Content generation failed or returned no result.")
                return False
        except Exception as e:
            print(f"   ❌ Error processing with links: {str(e)}")
            return False

    async def orchestrate_keyword_pipeline_with_links(self, keyword_item, unique_links, keyword_request, categories, subcategories, category_names):
        """Orchestrate pipeline with pre-provided links"""
        keyword = keyword_item.text.strip()
        print(f"   🎯 Processing '{keyword}' with provided links...")
        
        try:
            # Skip search step since we have links
            print(f"   📋 Generating blog plan for '{keyword}'...")
            blog_plan = await self.content_generator.generate_blog_plan(keyword, keyword_request.language)
            if not blog_plan:
                return False
            
            # Scrape the provided links
            loop = asyncio.get_running_loop()
            scraped_data = await loop.run_in_executor(None, lambda: 
                self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=len(unique_links))
            )
            
            if not scraped_data:
                return False
            
            # Continue with content generation
            final_data = {
                'search_info': {
                    'keyword': keyword,
                    'country': keyword_request.country.lower(),
                    'language': keyword_request.language.lower(),
                    'timestamp': datetime.now().isoformat(),
                    'total_results_found': len(scraped_data),
                    'scheduledDate': keyword_item.scheduledDate,
                    'scheduledTime': keyword_item.scheduledTime,
                    'user_email': keyword_request.user_email
                },
                'scraped_content': scraped_data,
                'blog_plan': blog_plan,
                'video_info': None,  # Skip video for retry
                'subcategories': subcategories,
                'category_names': category_names
            }
            
            content_result = await self.content_generator.generate_content_with_plan(final_data, "biography")
            
            if content_result and content_result.get('success'):
                # Save to database
                selected_category_name = content_result.get('selected_category_name')
                category_ids = []
                if selected_category_name:
                    for cat in categories:
                        if cat['name'].strip().lower() == selected_category_name.strip().lower():
                            category_ids = [str(cat['_id'])]
                            break
                
                if not category_ids:
                    category_ids = await self.match_content_categories(content_result['content'], categories)
                
                tags = await self.get_all_tags()
                tag_ids = await self.match_content_tags(content_result['content'], tags)
                
                save_success = await self.save_generated_content(
                    keyword=keyword,
                    content=content_result['content'],
                    word_count=content_result['word_count'],
                    language=keyword_request.language.lower(),
                    category_ids=category_ids,
                    tag_ids=tag_ids,
                    image_urls=content_result.get('image_urls', []),
                    metadata={},
                    scheduled_date=keyword_item.scheduledDate,
                    scheduled_time=keyword_item.scheduledTime,
                    user_email=keyword_request.user_email,
                    content_type="biography"
                )
                
                return save_success
            
            return False
            
        except Exception as e:
            print(f"   ❌ Error in pipeline with links: {str(e)}")
            return False

    async def store_single_unprocessed_keyword(self, failed_keyword, keyword_request):
        """Store a single unprocessed keyword in database"""
        try:
            unprocessed_doc = {
                "keyword": failed_keyword['keyword'],
                "error": failed_keyword['error'],
                "stage": failed_keyword['stage'],
                "country": keyword_request.country.lower(),
                "language": keyword_request.language.lower(),
                "user_email": keyword_request.user_email,
                "created_at": datetime.now(),
                "status": "failed",
                "retry_count": 1  # Mark as already retried
            }
            
            result = await self.db.unprocessed_keywords.insert_one(unprocessed_doc)
            print(f"💾 Stored unprocessed keyword '{failed_keyword['keyword']}' in database (ID: {result.inserted_id})")
            
        except Exception as e:
            print(f"❌ Error storing unprocessed keyword: {str(e)}")

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
            if not blog_plan:
                error_msg = f"Failed to generate blog plan for '{keyword}'"
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
                # Prepare final_data as before
                final_data = {
                    'search_info': {
                        'keyword': keyword,
                        'country': keyword_request.country.lower(),
                        'language': keyword_request.language.lower(),
                        'timestamp': datetime.now().isoformat(),
                        'total_results_found': len(scraped_data),
                        'scheduledDate': keyword_item.scheduledDate,
                        'scheduledTime': keyword_item.scheduledTime,
                        'user_email': keyword_request.user_email
                    },
                    'scraped_content': scraped_data,
                    'blog_plan': blog_plan,
                    'video_info': self.scraping_service.scraper.video_link_scraper(keyword),
                    'subcategories': subcategories,
                    'category_names': category_names
                }
                
                # Start main content generation (handles image generation internally)
                print(f"🤖 Generating content for '{keyword}'...")
                content_result = await self.content_generator.generate_content_with_plan(final_data, "biography")
                
                # Check for image generation failure
                image_urls = content_result.get('image_urls', []) if content_result else []
                if not image_urls or (len(image_urls) < 2 and len(blog_plan.get('image_prompts', [])) >= 2):
                    error_msg = f"Image generation failed for '{keyword}'"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'image_generation'
                    })
                    # --- PAUSE SCRIPT IF CRITICAL ERROR ---
                    critical_keywords = ['cannot generate', 'balance', 'token', 'insufficient']
                    if any(kw in error_msg.lower() for kw in critical_keywords):
                        print(f"🛑 Critical error detected ('{error_msg}'). Pausing script.")
                        sys.exit(1)
                    return

                # Save to DB if content_result is successful
                if content_result and content_result.get('success'):
                    print(f"✅ Content generation successful for '{keyword}' ({content_result['word_count']} words)")
                    
                    # (category/tag matching logic as before)
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
                    
                    # Save to database with detailed logging
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
                        scheduled_date=keyword_item.scheduledDate,
                        scheduled_time=keyword_item.scheduledTime,
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
                    error_msg = f"Content generation failed for '{keyword}': {content_result.get('message', 'Unknown error') if content_result else 'No result'}"
                    print(f"❌ {error_msg}")
                    self.unprocessed_keywords.append({
                        'keyword': keyword,
                        'error': error_msg,
                        'stage': 'content_generation'
                    })
                    # --- PAUSE SCRIPT IF CRITICAL ERROR ---
                    critical_keywords = ['cannot generate', 'balance', 'token', 'insufficient']
                    if any(kw in error_msg.lower() for kw in critical_keywords):
                        print(f"🛑 Critical error detected ('{error_msg}'). Pausing script.")
                        sys.exit(1)
            else:
                error_msg = f"Skipping content generation for '{keyword}' due to missing blog plan or scraped data"
                print(f"❌ {error_msg}")
                self.unprocessed_keywords.append({
                    'keyword': keyword,
                    'error': error_msg,
                    'stage': 'data_preparation'
                })
                
        except Exception as e:
            error_msg = f"Unexpected error processing '{keyword}': {str(e)}"
            print(f"❌ {error_msg}")
            self.unprocessed_keywords.append({
                'keyword': keyword,
                'error': error_msg,
                'stage': 'pipeline'
            })
            # --- PAUSE SCRIPT IF CRITICAL ERROR ---
            critical_keywords = ['cannot generate', 'balance', 'token', 'insufficient']
            if any(kw in error_msg.lower() for kw in critical_keywords):
                print(f"🛑 Critical error detected ('{error_msg}'). Pausing script.")
                sys.exit(1)

    async def scrape_and_generate_content(
        self,
        unique_links: List[str],
        keyword: str,
        country: str,
        language: str,
        scheduled_date: str,
        scheduled_time: str,
        user_email: str,
        content_type: str,
        selected_category_id: str = None,
        selected_tag_id: str = None,
        categories: List[Dict[str, Any]] = None,
        subcategories: List[Dict[str, Any]] = None,
        category_names: List[str] = None
    ) -> None:
        try:
            # Use passed categories, subcategories, and category_names
            if categories is None:
                categories = []
            if subcategories is None:
                subcategories = [cat for cat in categories if cat.get('parentId')]
            if category_names is None:
                category_names = [cat['name'] for cat in categories]
            # Now proceed with scraping
            print(f"🕷️ Starting content scraping for '{keyword}' ({len(unique_links)} links)")
            def scrape_with_retry():
                scraped_data = self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
                if not scraped_data:
                    print(f"🔄 Scraping failed for '{keyword}', retrying in 5 seconds...")
                    time.sleep(5)
                    scraped_data = self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
                return scraped_data
            scraped_data = scrape_with_retry()
            if not scraped_data:
                print(f"❌ No content scraped for '{keyword}' after retry")
                return
            # Restore real content generation with blog plan
            final_data = {
                'search_info': {
                    'keyword': keyword,
                    'country': country,
                    'language': language,
                    'timestamp': datetime.now().isoformat(),
                    'total_results_found': len(scraped_data),
                    'scheduledDate': scheduled_date,
                    'scheduledTime': scheduled_time,
                    'user_email': user_email
                },
                'scraped_content': scraped_data,
                'blog_plan': await self.content_generator.generate_blog_plan(keyword, language),
                'video_info': self.scraping_service.scraper.video_link_scraper(keyword),
                'subcategories': subcategories,
                'category_names': category_names
            }
            def generate_with_retry():
                try:
                    return asyncio.run(self.content_generator.generate_content_with_plan(final_data, content_type))
                except Exception as e:
                    print(f"🔄 Content generation failed for '{keyword}', retrying in 5 seconds... Error: {e}")
                    time.sleep(5)
                    try:
                        return asyncio.run(self.content_generator.generate_content_with_plan(final_data, content_type))
                    except Exception as e2:
                        print(f"❌ Content generation failed for '{keyword}' after retry. Error: {e2}")
                        return None
            result = await self.content_generator.generate_content_with_plan(final_data, content_type)
            if not result or not result.get('success'):
                print(f"🔄 Content generation failed for '{keyword}', retrying in 5 seconds...")
                time.sleep(5)
                result = await self.content_generator.generate_content_with_plan(final_data, content_type)
                if not result or not result.get('success'):
                    print(f"❌ Content generation failed for '{keyword}' after retry.")
                    return
            
            if result['success']:
                print(f"✅ Generated content in {language}: {result['word_count']} words")
                # If GPT selected a category, use its ID
                selected_category_name = result.get('selected_category_name')
                category_ids = []
                if selected_category_name:
                    for cat in categories:
                        if cat['name'].strip().lower() == selected_category_name.strip().lower():
                            category_ids = [str(cat['_id'])]
                            print(f"GPT selected category: {selected_category_name} (ID: {cat['_id']})")
                            break
                # Fallback to previous logic if not found
                if not category_ids:
                    if selected_category_id:
                        category_ids = [selected_category_id]
                    else:
                        category_ids = await self.match_content_categories(result['content'], categories)
                # Handle tags
                tag_ids = []
                if selected_tag_id:
                    tag_ids = [selected_tag_id]
                else:
                    tags = await self.get_all_tags()
                    tag_ids = await self.match_content_tags(result['content'], tags)
                print(f"Content details:\n"
                      f"Keyword: {keyword}\n"
                      f"Word count: {result['word_count']}\n"
                      f"Language: {language}\n"
                      f"Categories: {category_ids}\n"
                      f"Tags: {tag_ids}\n"
                      f"Image URLs: {result.get('image_urls', [])}\n"
                      f"Scheduled: {scheduled_date} {scheduled_time}\n"
                      f"User: {user_email}\n"
                      f"Type: {content_type}")
                # Save the content with proper payload
                success = await self.save_generated_content(
                    keyword=keyword,
                    content=result['content'],
                    word_count=result['word_count'],
                    language=language,
                    category_ids=category_ids,
                    tag_ids=tag_ids,
                    image_urls=result.get('image_urls', []),
                    metadata={},  # No metadata from generator
                    scheduled_date=scheduled_date,
                    scheduled_time=scheduled_time,
                    user_email=user_email,
                    content_type=content_type
                )
                
                if success:
                    print(f"✅ Content saved successfully to database")
                else:
                    print(f"❌ Failed to save content to database")
            else:
                print(f"❌ Content generation failed: {result['message']}")
                
        except Exception as e:
            print(f"❌ Error processing '{keyword}': {str(e)}")

    async def get_all_categories(self) -> List[Dict[str, Any]]:
        """Fetch all categories from the target database"""
        try:
            print(f"🔍 Fetching categories from target DB...")
            print(f"   - Target DB URI: {os.getenv('TARGET_DB_URI')}")
            print(f"   - Target DB Name: {os.getenv('TARGET_DB', 'CRM')}")
            
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

    async def get_all_tags(self) -> List[Dict[str, Any]]:
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

    async def get_default_category(self, content_type: str) -> Optional[str]:
        """Get default category based on content type"""
        try:
            # Map content types to category names
            category_mapping = {
                'biography': 'Biography',
                'news': 'News',
                'article': 'Articles',
                'blog': 'Blog',
                'review': 'Reviews'
            }
            
            category_name = category_mapping.get(content_type.lower(), 'General')
            
            # Find the category in target DB
            category = await self.target_db.categories.find_one(
                {'name': {'$regex': f'^{category_name}$', '$options': 'i'}}
            )
            
            return str(category['_id']) if category else None
            
        except Exception as e:
            print(f"Error getting default category: {str(e)}")
            return None

    async def match_content_categories(self, content: str, categories: List[Dict]) -> List[str]:
        """Match content with relevant categories and return their IDs"""
        try:
            if not categories:
                return []

            # Prepare text for matching
            category_texts = []
            for cat in categories:
                cat_text = f"{cat.get('name', '')} {cat.get('description', '')}"
                category_texts.append(cat_text)
            
            # Use TF-IDF to find most relevant categories
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(category_texts + [content])
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            
            # Get top 2 most relevant categories
            top_indices = np.argsort(similarities)[-2:][::-1]
            
            # Get the actual category IDs
            category_ids = []
            for idx in top_indices:
                if similarities[idx] > 0.1:  # Only include if similarity is meaningful
                    cat_id = categories[idx].get('_id')
                    if cat_id:
                        category_ids.append(str(cat_id))
            
            print(f"Selected categories: {[categories[i].get('name') for i in top_indices if similarities[i] > 0.1]}")
            return category_ids
            
        except Exception as e:
            print(f"Error matching categories: {str(e)}")
            return []

    async def match_content_tags(self, content: str, tags: List[Dict]) -> List[str]:
        """Match content with relevant tags and return their IDs"""
        try:
            if not tags:
                return []

            # Prepare text for matching
            tag_texts = []
            for tag in tags:
                tag_text = f"{tag.get('name', '')} {tag.get('description', '')}"
                tag_texts.append(tag_text)
            
            # Use TF-IDF to find most relevant tags
            vectorizer = TfidfVectorizer(stop_words='english')
            tfidf_matrix = vectorizer.fit_transform(tag_texts + [content])
            similarities = cosine_similarity(tfidf_matrix[-1:], tfidf_matrix[:-1])[0]
            
            # Get top tag
            top_index = np.argmax(similarities)
            
            # Get the actual tag ID if similarity is meaningful
            if similarities[top_index] > 0.1:
                tag_id = tags[top_index].get('_id')
                if tag_id:
                    print(f"Selected tag: {tags[top_index].get('name')}")
                    return [str(tag_id)]
        except Exception as e:
            print(f"Error matching tags: {str(e)}")
            return []

    async def save_generated_content(
        self,
        keyword: str,
        content: str,
        word_count: int,
        language: str,
        category_ids: List[str],
        tag_ids: List[str],
        image_urls: List[str],
        metadata: Dict[str, Any],
        scheduled_date: str,
        scheduled_time: str,
        user_email: str,
        content_type: str
    ) -> bool:
        """Save generated content to the database"""
        try:
            print(f"💾 Starting database save operation for keyword: '{keyword}'")
            print(f"   📊 Content details:")
            print(f"      - Word count: {word_count}")
            print(f"      - Language: {language}")
            print(f"      - Categories: {category_ids}")
            print(f"      - Tags: {tag_ids}")
            print(f"      - Image URLs: {len(image_urls)} images")
            print(f"      - Scheduled: {scheduled_date} {scheduled_time}")
            print(f"      - User: {user_email}")
            print(f"      - Content type: {content_type}")
            
            # Ensure category_ids and tag_ids are lists
            if category_ids is None:
                category_ids = []
            if tag_ids is None:
                tag_ids = []
            
            # If no categories were matched, try to get default category
            if not category_ids:
                print(f"   ⚠️ No categories matched, trying to get default category...")
                default_category = await self.get_default_category(content_type)
                if default_category:
                    category_ids = [default_category]
                    print(f"   ✅ Using default category: {default_category}")
                else:
                    print(f"   ⚠️ No default category found for content type: {content_type}")
            
            # Convert string IDs to ObjectId, handling empty lists
            category_object_ids = [ObjectId(cat_id) for cat_id in category_ids if cat_id]
            tag_object_ids = [ObjectId(tag_id) for tag_id in tag_ids if tag_id]
            
            print(f"   🔄 Converted IDs:")
            print(f"      - Category ObjectIds: {category_object_ids}")
            print(f"      - Tag ObjectIds: {tag_object_ids}")
            
            # Extract title from content if available
            title = None
            title_match = re.search(r'<h2>(.*?)</h2>', content)
            if title_match:
                title = title_match.group(1)
                print(f"   📝 Extracted title from content: {title}")
            if not title:
                title = keyword  # Fallback to keyword
                print(f"   📝 Using keyword as title: {title}")
            
            # Generate slug
            slug = self.generate_slug(title)
            print(f"   🔗 Generated slug: {slug}")
            
            # Prepare content document
            content_doc = {
                "title": title,  # Use extracted title
                "content": content,
                "slug": slug,  # Use slug from title
                "excerpt": title,  # Use title as excerpt
                "status": "pending",  # Set initial status as pending
                "categoryIds": category_object_ids,
                "tagIds": tag_object_ids,
                "authorId": ObjectId("683b3771a6b031d7d73735d7"),
                "createdAt": datetime.now(),
                "updatedAt": datetime.now(),
                "__v": 0,
                "canonicalUrl": "",
                "featured": False,
                "focusKeyword": keyword,
                "metaDescription": title,  # Use title as meta description
                "metaImage": image_urls[0] if image_urls else "http://localhost:3000/dashboard/posts/new",
                "metaKeywords": keyword,
                "metaTitle": title,  # Use title as meta title
                "ogDescription": title,  # Use title as og description
                "ogTitle": title,  # Use title as og title
                "ogType": "article",
                "readingTime": word_count // 200,
                "twitterCard": "summary_large_image",
                "twitterDescription": title,
                "scheduled_date": scheduled_date,  # Add scheduled date
                "scheduled_time": scheduled_time,  # Add scheduled time
                "user_email": user_email,  # Add user email
                "content_type": content_type,  # Add content type
                "image_urls": image_urls,  # Add image URLs
                "metadata": metadata  # No generator metadata
            }
            
            print(f"   📄 Content document prepared, attempting database insertion...")
            
            # Insert into database
            result = await self.db.generated_content.insert_one(content_doc)
            
            if result.inserted_id:
                print(f"   ✅ Content successfully inserted into database!")
                print(f"      - Document ID: {result.inserted_id}")
                print(f"      - Collection: generated_content")
                print(f"      - Status: pending")
                print(f"   🎉 Database save operation completed successfully for '{keyword}'")
                return True
            else:
                print(f"   ❌ Database insertion failed - no document ID returned")
                return False
                
        except Exception as e:
            print(f"   ❌ Error saving generated content to database: {str(e)}")
            print(f"   📍 Error occurred while processing keyword: '{keyword}'")
            print(f"   🔍 Error details: {type(e).__name__}: {str(e)}")
            return False