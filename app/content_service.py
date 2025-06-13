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

class ContentService:
    def __init__(self, db):
        self.db = db
        self.scraping_service = ScrapingService()
        self.scraping_service.db = db
        self.content_generator = ContentGenerator()  # No db dependency
        
        # Initialize target DB connection
        self.target_db = AsyncIOMotorClient(os.getenv('TARGET_DB_URI'))[os.getenv('TARGET_DB')]

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

    async def process_keywords(self, keyword_request: KeywordRequest) -> ScrapingResponse:
        try:
            tasks = []
            all_unique_links = []

            for keyword_item in keyword_request.keywords:
                print(f"🔍 Processing keyword: '{keyword_item.text}'")
                
                search_results = self.scraping_service.scraper.search_duckduckgo(
                    keyword=keyword_item.text.strip(),
                    country_code=keyword_request.country.lower(),
                    language=keyword_request.language.lower(),
                    max_results=25
                )
                
                if search_results:
                    unique_links = self.scraping_service.scraper.get_unique_links(search_results, count=10)
                    
                    if unique_links:
                        all_unique_links.extend(unique_links)
                        tasks.append({
                            "keyword": keyword_item.text,
                            "scheduledDate": keyword_item.scheduledDate,
                            "scheduledTime": keyword_item.scheduledTime,
                            "minLength": keyword_item.minLength,
                            "links_found": len(unique_links),
                            "status": "scheduled"
                        })
                    else:
                        tasks.append({
                            "keyword": keyword_item.text,
                            "links_found": 0,
                            "status": "no_links_found"
                        })
            
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
            # Generate blog plan first
            print(f"📝 Generating blog plan for: {keyword}")
            blog_plan = await self.content_generator.generate_blog_plan(keyword, language)
            if not blog_plan:
                print(f"❌ Failed to generate blog plan for '{keyword}'")
                return
                
            print(f"✅ Blog plan generated successfully")
            print(json.dumps(blog_plan, indent=2))
            
            # Get video information
            print(f"🎥 Searching for video content for: {keyword}")
            video_info = self.scraping_service.scraper.video_link_scraper(keyword)
            if video_info:
                print(f"✅ Found video: {video_info['title']}")
            else:
                print("❌ No video found")
            
            # Now proceed with scraping
            print(f"🕷️ Starting content scraping for '{keyword}' ({len(unique_links)} links)")
            scraped_data = self.scraping_service.scraper.scrape_multiple_urls(unique_links, target_count=5)
            
            if not scraped_data:
                print(f"❌ No content scraped for '{keyword}'")
                return
                
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
                'blog_plan': blog_plan,  # Pass the blog plan to content generation
                'video_info': video_info  # Pass video information to content generation
            }
            
            # Generate content using the generator with blog plan
            result = await self.content_generator.generate_content_with_plan(final_data, content_type)
            
            if not result.get('success'):
                print(f"❌ Content generation failed for '{keyword}': {result.get('message')}")
                return
            
            if result['success']:
                print(f"✅ Generated content in {language}: {result['word_count']} words")
                print(f"📝 Blog Plan Used:")
                print(json.dumps(result.get('metadata', {}).get('headings', []), indent=2))
                
                # Use category from blog plan if available
                category_ids = []
                if selected_category_id:
                    category_ids = [selected_category_id]
                else:
                    blog_plan_category = result.get('category')
                    if blog_plan_category:
                        # Try to find matching category
                        categories = await self.get_all_categories()
                        for cat in categories:
                            if cat['name'].lower() == blog_plan_category.lower():
                                category_ids = [str(cat['_id'])]
                                break
                    
                    # If no category found from blog plan, try auto-matching
                    if not category_ids:
                        categories = await self.get_all_categories()
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
                      f"Blog Plan: {json.dumps(result.get('metadata', {}).get('headings', []), indent=2)}\n"
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
                    metadata=result.get('metadata', {}),
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
            
            # Get the content_for_db from metadata if available
            content_for_db = metadata.get('content_for_db', {})
            
            # Extract title from content if available
            title = content_for_db.get('title')
            if not title:
                # Try to extract from content
                title_match = re.search(r'<h2>(.*?)</h2>', content)
                if title_match:
                    title = title_match.group(1)
                else:
                    title = keyword  # Fallback to keyword
            
            # Use content_for_db values if available, otherwise use provided values
            content_doc = {
                "title": title,  # Use extracted title
                "content": content_for_db.get('content', content),
                "slug": content_for_db.get('slug', self.generate_slug(title)),  # Use slug from title
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
                "metadata": content_for_db.get('metadata', metadata)  # Use metadata from content_for_db if available
            }
            
            result = await self.db.generated_content.insert_one(content_doc)
            return bool(result.inserted_id)
            
        except Exception as e:
            print(f"Error saving generated content: {str(e)}")
            return False