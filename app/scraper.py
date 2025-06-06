import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import re
import random

class WebContentScraper:
    def __init__(self):
        self.session = requests.Session()
        # Rotate between different user agents to avoid blocking
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/91.0.864.59',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        ]
        self.session.headers.update({
            'User-Agent': random.choice(self.user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.default_timeout = (10, 20)  # (connect timeout, read timeout)
    
    def search_duckduckgo(self, keyword, country_code='us', language='en', max_results=25):
        """
        Search using DuckDuckGo with country and language parameters
        """
        try:
            # Use DuckDuckGo's search API endpoint
            search_url = "https://duckduckgo.com/"
            params = {
                'q': keyword,
                't': 'h_',  # HTML endpoint
                'ia': 'web'  # Web search
            }
            
            print(f"Sending request to DuckDuckGo for '{keyword}'...")
            # First, get the search token
            self.session.headers.update({
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            })
            
            # Get the token first
            response = self.session.get(
                search_url,
                params={'q': keyword},
                timeout=self.default_timeout
            )
            
            if response.status_code == 200:
                # Now perform the actual search
                search_params = {
                    'q': keyword,
                    'kl': f'{country_code}-{language}',
                    't': 'h_',
                    'ia': 'web',
                    's': '0'
                }
                
                time.sleep(1)  # Small delay between requests
                
                response = self.session.get(
                    'https://duckduckgo.com/html/',
                    params=search_params,
                    timeout=self.default_timeout,
                    headers={
                        'User-Agent': random.choice(self.user_agents),
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5',
                        'Accept-Encoding': 'gzip, deflate',
                        'Referer': 'https://duckduckgo.com',
                        'DNT': '1',
                        'Connection': 'keep-alive',
                        'Upgrade-Insecure-Requests': '1'
                    }
                )
                
                print(f"Response status code: {response.status_code}")
                print(f"Response URL: {response.url}")
                
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = []
                    
                    # Find all result divs
                    results = soup.find_all('div', class_='result')
                    print(f"Found {len(results)} result divs")
                    
                    for result in results:
                        # Look for the main result link
                        link = result.find('a', class_='result__a')
                        if not link:
                            continue
                            
                        href = link.get('href', '')
                        
                        # Handle relative URLs
                        if href.startswith('/'):
                            href = 'https://duckduckgo.com' + href
                            
                        # Extract actual URL from DuckDuckGo redirect
                        if 'duckduckgo.com/l/?uddg=' in href:
                            try:
                                from urllib.parse import unquote
                                href = unquote(href.split('uddg=')[-1].split('&')[0])
                            except:
                                continue
                                
                        if href and href.startswith('http') and not any(x in href.lower() for x in ['duckduckgo.com', 'duck.co']):
                            if href not in links:
                                links.append(href)
                                print(f"Found link: {href}")
                                
                                if len(links) >= max_results:
                                    break
                    
                    print(f"Successfully extracted {len(links)} links")
                    return links
                    
            return []
            
        except requests.Timeout:
            print(f"Timeout while searching DuckDuckGo for '{keyword}' - Request took longer than {self.default_timeout} seconds")
            return []
        except requests.ConnectionError as e:
            print(f"Connection error while searching DuckDuckGo for '{keyword}': {str(e)}")
            return []
        except Exception as e:
            print(f"Error searching DuckDuckGo: {str(e)}")
            print(f"Error type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return []
    
    def get_unique_links(self, links, count=15):
        """
        Get unique links by domain to ensure diversity
        Also handles subdomain variations (e.g., en.wikipedia.org vs fr.wikipedia.org)
        """
        unique_links = []
        seen_base_domains = set()
        
        for link in links:
            try:
                domain = urlparse(link).netloc.lower()
                
                # Extract base domain (e.g., wikipedia.org from en.wikipedia.org)
                domain_parts = domain.split('.')
                if len(domain_parts) >= 2:
                    base_domain = '.'.join(domain_parts[-2:])  # Get last two parts
                else:
                    base_domain = domain
                
                # Skip if we already have a link from this base domain
                if base_domain not in seen_base_domains and self.is_valid_url(link):
                    unique_links.append(link)
                    seen_base_domains.add(base_domain)
                    if len(unique_links) >= count:
                        break
            except:
                continue
        
        return unique_links
    
    def is_valid_url(self, url):
        """
        Check if URL is valid and scrapeable
        """
        try:
            parsed = urlparse(url)
            # Skip social media, video sites, and file downloads
            skip_domains = ['youtube.com', 'facebook.com', 'twitter.com', 'instagram.com', 
                          'linkedin.com', 'tiktok.com', 'pinterest.com']
            skip_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx']
            
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            
            if any(skip in domain for skip in skip_domains):
                return False
            if any(path.endswith(ext) for ext in skip_extensions):
                return False
            
            return True
        except:
            return False
    
    def extract_main_content(self, html_content, url):
        """
        Extract main content from HTML using various strategies
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 
                           'aside', 'advertisement', 'ads', 'comment']):
            element.decompose()
        
        # Try different content extraction strategies
        content = ""
        title = ""
        
        # Extract title
        title_tag = soup.find('title')
        if title_tag:
            title = title_tag.get_text().strip()
        
        # Strategy 1: Look for common content containers
        content_selectors = [
            'article', 'main', '.content', '#content', '.post', '.entry',
            '.article-body', '.post-content', '.entry-content', 
            '[role="main"]', '.main-content'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                content = content_elem.get_text(separator=' ', strip=True)
                if len(content) > 200:  # Minimum content length
                    break
        
        # Strategy 2: If no content found, look for largest text block
        if not content or len(content) < 200:
            text_elements = soup.find_all(['p', 'div', 'section'])
            largest_text = ""
            
            for elem in text_elements:
                text = elem.get_text(separator=' ', strip=True)
                if len(text) > len(largest_text):
                    largest_text = text
            
            if len(largest_text) > len(content):
                content = largest_text
        
        # Strategy 3: Fallback to body text
        if not content or len(content) < 100:
            body = soup.find('body')
            if body:
                content = body.get_text(separator=' ', strip=True)
        
        # Clean up content
        content = re.sub(r'\s+', ' ', content).strip()
        
        return {
            'title': title,
            'content': content[:5000],  # Limit content length
            'url': url,
            'content_length': len(content)
        }
    
    def scrape_url(self, url, timeout=None):
        """
        Scrape content from a single URL
        """
        try:
            print(f"Scraping: {url}")
            timeout = timeout or self.default_timeout
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type:
                return None
            
            return self.extract_main_content(response.content, url)
            
        except requests.Timeout:
            print(f"Timeout while scraping {url}")
            return None
        except requests.ConnectionError:
            print(f"Connection error while scraping {url}")
            return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None
    
    def scrape_multiple_urls(self, urls, target_count=5, delay=2):
        """
        Scrape multiple URLs with delay between requests
        Ensures exactly target_count successful scrapes by using backup URLs
        """
        results = []
        processed_urls = set()
        
        for i, url in enumerate(urls):
            if len(results) >= target_count:
                break
                
            if url in processed_urls:
                continue
                
            processed_urls.add(url)
            print(f"Processing {len(results)+1}/{target_count}: {url}")
            
            result = self.scrape_url(url)
            if result and result['content_length'] > 100:
                results.append(result)
                print(f"✅ Successfully scraped ({len(results)}/{target_count})")
            else:
                print(f"❌ Failed to scrape or insufficient content")
            
            # Add delay between requests to be respectful
            if i < len(urls) - 1 and len(results) < target_count:
                time.sleep(delay)
        
        return results

    def search_social_media(self, keyword):
        """
        Search for a keyword on different social media platforms and return first link for each
        """
        social_platforms = ['instagram', 'linkedin', 'twitter']
        results = {}
        
        for platform in social_platforms:
            search_query = f"{keyword} {platform}"
            print(f"\nSearching for: {search_query}")
            
            links = self.search_duckduckgo(search_query, max_results=1)
            if links:
                results[platform] = links[0]
                print(f"{platform.capitalize()} Link: {links[0]}")
            else:
                results[platform] = None
                print(f"No {platform} link found")
            
            # Add delay between searches
            time.sleep(2)
        
        return results