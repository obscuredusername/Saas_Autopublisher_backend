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

class ContentService:
    def __init__(self, db):
        self.db = db
        self.scraping_service = ScrapingService()
        self.scraping_service.db = db
        self.content_generator = ContentGenerator()  # No db dependency
        
        # Initialize target DB connection using global variables from routes
        from app.routes import TARGET_DB_URI, TARGET_DB
        self.target_db = AsyncIOMotorClient(TARGET_DB_URI)[TARGET_DB]

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
            tasks = []
            all_unique_links = []
            threads = []
            # WARNING: Spawning 300 threads is not recommended for production. Use a thread pool or queue for better resource management.
            for idx, keyword_item in enumerate(keyword_request.keywords):
                print(f"🔍 Processing keyword: '{keyword_item.text}'")
                search_results = self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword_item.text.strip(),
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=25
                )
                if search_results:
                    unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=10)
                    min_length = getattr(keyword_item, 'minLength', None)
                    if min_length is None:
                        min_length = 7500
                    if unique_links:
                        thread = threading.Thread(
                            target=self.run_scrape_and_generate_content,
                            args=(unique_links, keyword_item.text, keyword_request.country.lower(), keyword_request.language.lower(), min_length, keyword_request.user_email, keyword_item.scheduledDate, keyword_item.scheduledTime, "biography")
                        )
                        thread.start()
                        threads.append(thread)
                        print(f"🧵 Started thread for keyword '{keyword_item.text}'")
                        tasks.append({
                            "keyword": keyword_item.text,
                            "scheduledDate": keyword_item.scheduledDate,
                            "scheduledTime": keyword_item.scheduledTime,
                            "minLength": min_length,
                            "links_found": len(unique_links),
                            "status": "scheduled"
                        })
                        if idx < len(keyword_request.keywords) - 1:
                            print("⏳ Waiting 10 seconds before starting next thread...")
                            time.sleep(10)
                    else:
                        tasks.append({
                            "keyword": keyword_item.text,
                            "links_found": 0,
                            "status": "no_links_found"
                        })
            # Optionally, join threads here if you want to wait for all to finish
            # for thread in threads:
            #     thread.join()
            return ScrapingResponse(
                success=True,
                message=f"Found {len(all_unique_links)} unique links across {len(tasks)} keywords",
                tasks=tasks,
                country=keyword_request.country.lower(),
                language=keyword_request.language.lower(),
                status="processing",
                unique_links=list(set(all_unique_links))
            )
        except Exception as e:
            print(f"Error in process_keywords: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

    async def scrape_and_generate_content(
        self,
        unique_links: List[str],
        keyword: str,
        country: str,
        language: str,
        min_length: int,
        user_email: str,
        scheduled_date: str,
        scheduled_time: str,
        content_type: str,
        selected_category_id: str = None,
        selected_tag_id: str = None
    ) -> None:
        try:
            # Fetch all categories from target DB and filter subcategories
            categories = await self.get_all_categories()
            print("All categories fetched from target DB:", categories)
            subcategories = [cat for cat in categories if cat.get('parentId')]
            print("Filtered subcategories:", subcategories)
            # Extract category names for GPT prompt
            category_names = [cat['name'] for cat in categories]
            # Now proceed with scraping
            print(f"🕷️ Starting content scraping for '{keyword}' ({len(unique_links)} links)")
            scraped_data = self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5, min_length=min_length)
            
            if not scraped_data:
                print(f"❌ No content scraped for '{keyword}'")
                return
            
            # Restore real content generation with blog plan
            final_data = {
                'search_info': {
                    'keyword': keyword,
                    'country': country,
                    'language': language,
                    'timestamp': datetime.now().isoformat(),
                    'total_results_found': len(scraped_data),
                    'min_length': min_length,
                    'scheduledDate': scheduled_date,
                    'scheduledTime': scheduled_time,
                    'user_email': user_email
                },
                'scraped_content': scraped_data,
                'blog_plan': await self.content_generator.generate_blog_plan(keyword, language),
                'video_info': self.scraping_service.scraper.video_link_scraper(keyword),
                'subcategories': subcategories,  # Pass subcategories to content generator
                'category_names': category_names  # Pass category names to content generator
            }
            # Debug print to confirm subcategories being sent
            print("Subcategories being sent to content generator:", subcategories)
            result = await self.content_generator.generate_content_with_plan(final_data, content_type)
            
            if not result.get('success'):
                print(f"❌ Content generation failed for '{keyword}': {result.get('message')}")
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
            categories = await self.target_db.categories.find({}, {
                '_id': 1,
                'name': 1,
                'description': 1
            }).to_list(length=None)
            return categories
        except Exception as e:
            print(f"Error fetching categories from target DB: {str(e)}")
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
            # Ensure category_ids and tag_ids are lists
            if category_ids is None:
                category_ids = []
            if tag_ids is None:
                tag_ids = []
            # If no categories were matched, try to get default category
            if not category_ids:
                default_category = await self.get_default_category(content_type)
                if default_category:
                    category_ids = [default_category]
            # Convert string IDs to ObjectId, handling empty lists
            category_object_ids = [ObjectId(cat_id) for cat_id in category_ids if cat_id]
            tag_object_ids = [ObjectId(tag_id) for tag_id in tag_ids if tag_id]
            # Extract title from content if available
            title = None
            title_match = re.search(r'<h2>(.*?)</h2>', content)
            if title_match:
                title = title_match.group(1)
            if not title:
                title = keyword  # Fallback to keyword
            content_doc = {
                "title": title,  # Use extracted title
                "content": content,
                "slug": self.generate_slug(title),  # Use slug from title
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
            result = await self.db.generated_content.insert_one(content_doc)
            return bool(result.inserted_id)
        except Exception as e:
            print(f"Error saving generated content: {str(e)}")
            return False