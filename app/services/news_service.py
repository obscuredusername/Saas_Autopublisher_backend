import os
import json
from newsapi import NewsApiClient
import datetime
import sys
from bson import ObjectId
import math

# Add the parent directory to the path so we can import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.scraper import WebContentScraper
from app.services.image_generator import ImageGenerator
from app.services.blog_service import BlogService
from motor.motor_asyncio import AsyncIOMotorClient
import openai
import re

def insert_natural_backlink(html_content, url, title):
    paragraphs = html_content.split('</p>')
    if len(paragraphs) < 3:
        anchor = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
        paragraphs[0] += f' ({anchor})'
    else:
        mid = len(paragraphs) // 2
        anchor = f'<a href="{url}" target="_blank" rel="noopener">{title}</a>'
        paragraphs[mid] += f' According to {anchor},'
    return '</p>'.join(paragraphs)

# Utility function for rotating schedule
def generate_rotating_schedule(start_time, category_limits, default_gap_minutes=60):
    categories = list(category_limits.keys())
    total_posts = sum(category_limits.values())
    schedule = []
    counters = {cat: 0 for cat in categories}
    current_time = start_time
    # Calculate minimum gap to fit all posts in the window (assume 12 hours)
    total_minutes = 12 * 60
    min_gap = max(default_gap_minutes, math.floor(total_minutes / (total_posts - 1))) if total_posts > 1 else 0
    while sum(counters.values()) < total_posts:
        for cat in categories:
            if counters[cat] < category_limits[cat]:
                schedule.append((cat, current_time))
                counters[cat] += 1
                current_time += datetime.timedelta(minutes=min_gap)
                if sum(counters.values()) >= total_posts:
                    break
    return schedule

class NewsService:
    def __init__(self):
        # Use the provided NewsAPI key directly or from env
        self.api_key = os.getenv('NEWSAPI_KEY', '9ce3da83f5584df594b4154bf8ca49f9')
        self.newsapi = NewsApiClient(api_key=self.api_key)
        
        # Supported countries by NewsAPI (ISO 3166-1 alpha-2 codes)
        # These are the exact country codes that NewsAPI accepts
        self.supported_countries = [
            'ae', 'ar', 'at', 'au', 'be', 'bg', 'br', 'ca', 'ch', 'cn', 'co', 'cu', 'cz', 'de', 'eg', 'fr', 'gb', 'gr', 'hk', 'hu', 'id', 'ie', 'il', 'in', 'it', 'jp', 'kr', 'lt', 'lv', 'ma', 'mx', 'my', 'ng', 'nl', 'no', 'nz', 'ph', 'pl', 'pt', 'ro', 'rs', 'ru', 'sa', 'se', 'sg', 'si', 'sk', 'th', 'tr', 'tw', 'ua', 'us', 've', 'za'
        ]

    async def get_news_scrapped(self, country, language, category, db=None, user_email="news@system.com"):
        # NewsAPI supports: country, category, language, q
        try:
            print(f"Fetching news: country={country}, language={language}, category={category}")
            
            # Validate country code - NewsAPI is very strict about country codes
            is_valid, validated_country = self.validate_country(country)
            if not is_valid:
                print(f"⚠️ Using fallback country: {validated_country}")
                country = validated_country
            
            # First try the requested combination
            response = self.newsapi.get_top_headlines(
                category=category,
                language=language,
                country=country
            )
            print(f"NewsAPI Response: {response}")
            articles = response.get('articles', [])
            print(f"Found {len(articles)} articles from NewsAPI")
            
            # If no articles found, try fallback combinations
            if not articles:
                print(f"No articles found for {country}/{language}/{category}, trying fallbacks...")
                
                # Fallback 1: Try with English language
                if language != 'en':
                    print(f"Trying fallback: country={country}, language=en, category={category}")
                    response = self.newsapi.get_top_headlines(
                        category=category,
                        language='en',
                        country=country
                    )
                    articles = response.get('articles', [])
                    print(f"Fallback 1 found {len(articles)} articles")
                
                # Fallback 2: Try with US country if still no results
                if not articles and country != 'us':
                    print(f"Trying fallback: country=us, language=en, category={category}")
                    response = self.newsapi.get_top_headlines(
                        category=category,
                        language='en',
                        country='us'
                    )
                    articles = response.get('articles', [])
                    print(f"Fallback 2 found {len(articles)} articles")
                
                # Fallback 3: Try general category if still no results
                if not articles and category != 'general':
                    print(f"Trying fallback: country=us, language=en, category=general")
                    response = self.newsapi.get_top_headlines(
                        category='general',
                        language='en',
                        country='us'
                    )
                    articles = response.get('articles', [])
                    print(f"Fallback 3 found {len(articles)} articles")
            
            # Extract URLs from articles
            urls = [a.get('url') for a in articles if a.get('url')]
            print(f"Found {len(urls)} article URLs from NewsAPI")
            
            if not urls:
                print("No URLs found, returning empty results")
                return [], "success"
                
            # Scrape all working links
            scraper = WebContentScraper()
            scraped_results = scraper.scrape_multiple_urls(urls, target_count=len(urls))
            
            # Save to JSON file
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
            filename = f"scraped_news_{country}_{language}_{category}_{timestamp}.json"
            output_dir = "scraped_data"
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(scraped_results, f, indent=2, ensure_ascii=False)
            print(f"✅ Saved scraped news to {filepath}")
            
            # Generate blog posts from scraped content
            generated_posts = []
            if scraped_results:
                generated_posts = await self.generate_blog_posts_from_news(scraped_results, category, language, db, user_email, save_to_db=True)
                # Manual scheduling removed - now handled by Celery Beat based on scheduledAt field
            
            # Delete the scraped JSON file since it's not needed
            try:
                os.remove(filepath)
                print(f"🗑️ Deleted scraped JSON file: {filepath}")
            except Exception as e:
                print(f"⚠️ Could not delete scraped JSON file: {e}")
            
            return generated_posts, "success"
        except Exception as e:
            import traceback
            print(f"Error fetching or scraping news: {e} ({type(e).__name__})")
            traceback.print_exc()
            return None, "1.1"

    async def generate_blog_posts_from_news(self, scraped_results, category, language, db, user_email, save_to_db=True):
        """Generate blog posts from scraped news articles using direct content rephrasing and image generation."""
        try:
            print(f"🤖 Starting blog generation for {len(scraped_results)} news articles...")
            
            # Create news directory for storing rephrased content
            news_dir = "news"
            os.makedirs(news_dir, exist_ok=True)
            print(f"📁 Created/using news directory: {news_dir}")
            
            # Initialize OpenAI client for direct content generation
            client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            
            # Initialize image generator
            image_generator = ImageGenerator()
            
            generated_posts = []
            
            # --- NEW ROTATION LOGIC ---
            category_limits = {'finance': 4, 'business': 2, 'fashion': 3}
            start_time = datetime.datetime.now(datetime.timezone.utc).replace(hour=8, minute=0, second=0, microsecond=0)
            schedule = generate_rotating_schedule(start_time, category_limits, default_gap_minutes=60)
            # Only use as many scraped_results as needed
            schedule = schedule[:len(scraped_results)]
            for i, (cat, scheduled_time) in enumerate(schedule):
                article = scraped_results[i]
                try:
                    print(f"📝 Generating blog post {i+1}/{len(scraped_results)} from: {article.get('title', 'No title')}")
                    
                    # Get original content
                    original_title = article.get('title', 'Technology News')
                    original_content = article.get('content', '')
                    original_length = len(original_content)
                    
                    # Generate rephrased title and content using GPT-4o-mini
                    rephrase_prompt = f"""
Rephrase and extensively expand this news article in {language}. Make it comprehensive, detailed, and at least 1000 words long.

Original Title: {original_title}
Original Content: {original_content}

Requirements:
1. Rephrase EVERY SINGLE SENTENCE completely
2. Expand each point with additional details, context, and explanations
3. Add relevant background information, statistics, and expert insights
4. Make the content at least 1000 words long
5. Structure with proper HTML headings (h2, h3) and paragraphs
6. Make it engaging and informative

IMPORTANT: Your response MUST start with 'TITLE:' on the very first line, and 'CONTENT:' on the very next line. Do NOT include anything else before, between, or after these sections. Do NOT include explanations, notes, or any other text. Only output:
TITLE: [rephrased title here]
CONTENT: [detailed rephrased content in HTML format here]
"""

                    response = await client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "You are a professional content writer who creates comprehensive, detailed news articles. Always rephrase every sentence completely and expand content to be at least 1000 words. Use proper HTML formatting with h2, h3, p tags. Make content engaging and informative."},
                            {"role": "user", "content": rephrase_prompt}
                        ],
                        temperature=0.8,
                        max_tokens=6000
                    )
                    
                    response_text = response.choices[0].message.content
                    
                    # Parse the response to extract title and content
                    title_match = re.search(r'TITLE:\s*(.+)', response_text, re.IGNORECASE)
                    content_match = re.search(r'CONTENT:\s*(.+)', response_text, re.IGNORECASE | re.DOTALL)
                    
                    if title_match and content_match:
                        rephrased_title = title_match.group(1).strip()
                        rephrased_content = content_match.group(1).strip()
                        
                        print(f"✅ Generated rephrased title: {rephrased_title}")
                        
                        # Generate two images: one for original title, one for rephrased title
                        image_urls = []
                        
                        # Image 1: Based on original title (Featured Image)
                        print(f"🎨 Generating featured image for original title...")
                        image1_prompt = f"Professional featured image for news article about {original_title}, high quality, editorial style, breaking news concept, modern design"
                        image1_url = await image_generator.generate_image(image1_prompt)
                        public_url1 = await image_generator.upload_to_fastapi(image1_url, original_title) if image1_url else None
                        if public_url1:
                            image_urls.append(public_url1)
                            print(f"✅ Uploaded featured image: {public_url1}")
                        elif image1_url:
                            image_urls.append(image1_url)
                            print(f"✅ Generated featured image: {image1_url}")
                        
                        # Image 2: Based on rephrased title (Mid-content image)
                        print(f"🎨 Generating mid-content image for rephrased title...")
                        image2_prompt = f"Professional editorial image representing {rephrased_title}, high quality, modern design, relevant to the topic, infographic style"
                        image2_url = await image_generator.generate_image(image2_prompt)
                        public_url2 = await image_generator.upload_to_fastapi(image2_url, rephrased_title) if image2_url else None
                        if public_url2:
                            image_urls.append(public_url2)
                            print(f"✅ Uploaded mid-content image: {public_url2}")
                        elif image2_url:
                            image_urls.append(image2_url)
                            print(f"✅ Generated mid-content image: {image2_url}")
                        
                        # Insert images strategically in the content
                        # Split content into paragraphs to find a good insertion point
                        paragraphs = rephrased_content.split('</p>')
                        
                        # Insert featured image at the very beginning
                        featured_image_html = f'<img src="{image_urls[0]}" alt="Featured Image" style="max-width:100%;margin:20px 0;display:block;"/>' if image_urls else ""
                        
                        # Insert mid-content image after the first few paragraphs
                        mid_content_image_html = ""
                        if len(image_urls) > 1 and len(paragraphs) > 3:
                            # Insert after 2-3 paragraphs
                            insert_position = min(3, len(paragraphs) // 3)
                            mid_content_image_html = f'<img src="{image_urls[1]}" alt="Mid-content Image" style="max-width:100%;margin:30px 0;display:block;"/>'
                            
                            # Reconstruct content with images
                            content_with_images = featured_image_html + paragraphs[0] + '</p>'
                            for i, para in enumerate(paragraphs[1:], 1):
                                content_with_images += para + '</p>'
                                if i == insert_position and mid_content_image_html:
                                    content_with_images += mid_content_image_html
                        else:
                            # If not enough paragraphs, just add images at beginning
                            content_with_images = featured_image_html + rephrased_content
                            if len(image_urls) > 1:
                                content_with_images += f'<img src="{image_urls[1]}" alt="Additional Image" style="max-width:100%;margin:20px 0;display:block;"/>'
                        
                        # Insert natural backlink
                        content_with_images = insert_natural_backlink(content_with_images, article.get('url', ''), original_title)

                        # Save to file
                        safe_title = re.sub(r'[^a-zA-Z0-9\s-]', '', original_title)[:50]
                        timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d_%H%M%S')
                        filename = f"news_{i+1}_{safe_title}_{timestamp}.html"
                        filepath = os.path.join(news_dir, filename)
                        
                        # Create clean HTML content without metadata
                        html_content = f"""
<!DOCTYPE html>
<html lang="{language}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{rephrased_title}</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 40px; }}
        img {{ max-width: 100%; height: auto; margin: 20px 0; }}
        h1, h2, h3 {{ color: #333; }}
        p {{ margin-bottom: 15px; }}
    </style>
</head>
<body>
    {content_with_images}
</body>
</html>
"""
                        
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                        print(f"💾 Saved rephrased content to: {filepath}")
                        
                        # Save to database if requested
                        db_id = None
                        if save_to_db:
                            print(f"[DEBUG] Attempting to save generated news post to database for article: {original_title}")
                            print(f"[DEBUG] Target DB: CRM, Collection: posts (news always goes to CRM.posts)")
                            blog_service = BlogService(db)
                            # Always use CRM database and posts collection for news
                            target_db_name = "CRM"  # News always goes to CRM database
                            target_collection = "posts"  # Collection is always posts
                            author_id = ObjectId('6872543bb13173a4a942d3c4')
                            # Find category ID for cat
                            categories = await blog_service.get_all_categories()
                            cat_id = None
                            for c in categories:
                                if c['name'].strip().lower() == cat:
                                    cat_id = ObjectId(c['_id'])
                                    break
                            db_id = await blog_service.save_generated_content(
                                keyword=article.get('title', ''),
                                content=content_with_images,
                                word_count=len(rephrased_content.split()),
                                language=language,
                                category_ids=[cat_id] if cat_id else [],
                                tag_ids=[],
                                image_urls=image_urls,
                                metadata={
                                    'source_article': article.get('url', ''),
                                    'original_title': article.get('title', ''),
                                    'rephrased_title': rephrased_title,
                                    'news_category': cat,
                                    'generated_from_news': True,
                                    'original_content_length': original_length,
                                    'generated_content_length': len(rephrased_content),
                                    'generated_images_count': len(image_urls)
                                },
                                user_email=user_email,
                                content_type="news_article",
                                post_index=0,  # Not used for scheduling now
                                target_db=target_db_name,
                                target_collection=target_collection,
                                author_id=author_id,
                                scheduled_at=scheduled_time
                            )
                            print(f"[DEBUG] Save to database result for article '{original_title}': db_id={db_id}")
                            if db_id:
                                print(f"✅ Saved to database successfully (ID: {db_id})")
                            else:
                                print(f"❌ Failed to save to database for news post: {original_title}")
                        
                        generated_posts.append({
                            'title': rephrased_title,
                            'word_count': len(rephrased_content.split()),
                            'url': article.get('url', ''),
                            'images_generated': len(image_urls),
                            'original_length': original_length,
                            'generated_length': len(rephrased_content),
                            'status': 'success',
                            'content': content_with_images,
                            'image_urls': image_urls,
                            'file_path': filepath,
                            'db_id': str(db_id) if db_id else None
                        })
                        
                        print(f"✅ Generated blog post: {rephrased_title}")
                        print(f"   📊 Length: {len(rephrased_content)} chars ({len(rephrased_content.split())} words)")
                        print(f"   🖼️  Images: {len(image_urls)} generated")
                        print(f"   💾 Saved to: {filepath}")
                        
                    else:
                        print(f"[ERROR] Failed to parse rephrased content for: {original_title}")
                        print(f"[ERROR] Full OpenAI response was:\n{response_text}\n---END RESPONSE---")
                        
                except Exception as e:
                    print(f"❌ Error generating blog post {i+1}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    continue
            
            print(f"🎉 Successfully generated {len(generated_posts)} blog posts from news articles")
            return generated_posts
            
        except Exception as e:
            print(f"❌ Error in generate_blog_posts_from_news: {str(e)}")
            import traceback
            traceback.print_exc()
            return []

    def get_supported_countries(self):
        """Get list of supported countries"""
        return self.supported_countries

    def validate_country(self, country):
        """Validate if a country code is supported by NewsAPI"""
        if country in self.supported_countries:
            return True, country
        else:
            print(f"⚠️ Invalid country code '{country}'. Supported countries: {', '.join(self.supported_countries)}")
            return False, 'us'  # Default fallback

    def get_country_info(self):
        """Get information about supported countries"""
        country_names = {
            'ae': 'United Arab Emirates', 'ar': 'Argentina', 'at': 'Austria', 'au': 'Australia',
            'be': 'Belgium', 'bg': 'Bulgaria', 'br': 'Brazil', 'ca': 'Canada', 'ch': 'Switzerland',
            'cn': 'China', 'co': 'Colombia', 'cu': 'Cuba', 'cz': 'Czech Republic', 'de': 'Germany',
            'eg': 'Egypt', 'fr': 'France', 'gb': 'United Kingdom', 'gr': 'Greece', 'hk': 'Hong Kong',
            'hu': 'Hungary', 'id': 'Indonesia', 'ie': 'Ireland', 'il': 'Israel', 'in': 'India',
            'it': 'Italy', 'jp': 'Japan', 'kr': 'South Korea', 'lt': 'Lithuania', 'lv': 'Latvia',
            'ma': 'Morocco', 'mx': 'Mexico', 'my': 'Malaysia', 'ng': 'Nigeria', 'nl': 'Netherlands',
            'no': 'Norway', 'nz': 'New Zealand', 'ph': 'Philippines', 'pl': 'Poland', 'pt': 'Portugal',
            'ro': 'Romania', 'rs': 'Serbia', 'ru': 'Russia', 'sa': 'Saudi Arabia', 'se': 'Sweden',
            'sg': 'Singapore', 'si': 'Slovenia', 'sk': 'Slovakia', 'th': 'Thailand', 'tr': 'Turkey',
            'tw': 'Taiwan', 'ua': 'Ukraine', 'us': 'United States', 've': 'Venezuela', 'za': 'South Africa'
        }
        
        return {code: country_names.get(code, code) for code in self.supported_countries}

# For testing as a script
if __name__ == "__main__":
    import asyncio
    import dotenv
    dotenv.load_dotenv()
    service = NewsService()
    async def test():
        # Test with different combinations to see what works
        test_cases = [
            ('us', 'en', 'technology'),
            ('fr', 'fr', 'technology'),  # French language (will fallback)
            ('fr', 'en', 'technology'),  # French country, English language
            ('gb', 'en', 'technology'),  # UK
            ('ca', 'en', 'technology'),  # Canada
        ]
        
        for country, language, category in test_cases:
            print(f"\n{'='*50}")
            print(f"Testing: country={country}, language={language}, category={category}")
            print(f"{'='*50}")
            articles, status = await service.get_news_scrapped(country, language, category)
            print(f"Status: {status}")
            print(f"Articles count: {len(articles) if articles else 0}")
            if articles:
                print(f"First article title: {articles[0].get('title', 'No title')}")
    
    asyncio.run(test()) 