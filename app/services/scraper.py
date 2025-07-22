import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote
import re
import random
import os

class WebContentScraper:
    def __init__(self):
        self.session = requests.Session()
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
        self.default_timeout = (10, 20)

    def search_duckduckgo(self, keyword, country_code='us', language='en', max_results=25):
        try:
            search_url = "https://duckduckgo.com/"
            params = {'q': keyword, 't': 'h_', 'ia': 'web'}
            self.session.headers.update({'User-Agent': random.choice(self.user_agents)})
            response = self.session.get(search_url, params={'q': keyword}, timeout=self.default_timeout)
            if response.status_code == 200:
                search_params = {
                    'q': keyword,
                    'kl': f'{country_code}-{language}',
                    't': 'h_',
                    'ia': 'web',
                    's': '0'
                }
                time.sleep(1)
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
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = []
                    results = soup.find_all('div', class_='result')
                    for result in results:
                        link = result.find('a', class_='result__a')
                        if not link:
                            continue
                        href = link.get('href', '')
                        if href.startswith('/'):
                            href = 'https://duckduckgo.com' + href
                        if 'duckduckgo.com/l/?uddg=' in href:
                            try:
                                href = unquote(href.split('uddg=')[-1].split('&')[0])
                            except:
                                continue
                        if href and href.startswith('http') and not any(x in href.lower() for x in ['duckduckgo.com', 'duck.co']):
                            if href not in links:
                                links.append(href)
                                if len(links) >= max_results:
                                    break
                    return links
            return []
        except requests.Timeout:
            print(f"Timeout while searching DuckDuckGo for '{keyword}'")
            return []
        except requests.ConnectionError as e:
            print(f"Connection error while searching DuckDuckGo for '{keyword}': {str(e)}")
            return []
        except Exception as e:
            print(f"Error searching DuckDuckGo: {str(e)}")
            return []

    def get_unique_links(self, links, count=15):
        unique_links = []
        seen_base_domains = set()
        for link in links:
            try:
                domain = urlparse(link).netloc.lower()
                domain_parts = domain.split('.')
                if len(domain_parts) >= 2:
                    base_domain = '.'.join(domain_parts[-2:])
                else:
                    base_domain = domain
                if base_domain not in seen_base_domains and self.is_valid_url(link):
                    unique_links.append(link)
                    seen_base_domains.add(base_domain)
                    if len(unique_links) >= count:
                        break
            except:
                continue
        return unique_links

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
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

    def scrape_url(self, url, min_length=100, timeout=None):
        """
        Scrape content from a single URL
        """
        try:
            print(f"Scraping: {url}")
            timeout = timeout or self.default_timeout
            response = self.session.get(url, timeout=timeout)
            response.raise_for_status()
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type:
                return None
            # Dummy main content extraction (replace with real logic if needed)
            soup = BeautifulSoup(response.content, 'html.parser')
            title = soup.title.string if soup.title else url
            content = soup.get_text(separator=' ', strip=True)
            content = re.sub(r'\s+', ' ', content).strip()
            if len(content) < min_length:
                print(f"❌ Content too short ({len(content)} < {min_length})")
                return None
            return {
                'title': title,
                'content': content[:5000],
                'url': url,
                'content_length': len(content)
            }
        except requests.Timeout:
            print(f"Timeout while scraping {url}")
            return None
        except requests.ConnectionError:
            print(f"Connection error while scraping {url}")
            return None
        except Exception as e:
            print(f"Error scraping {url}: {e}")
            return None

    def scrape_multiple_urls(self, urls, target_count=5, delay=2, min_length=100):
        """
        Scrape multiple URLs in parallel (up to target_count at a time).
        Ensures exactly target_count successful scrapes by using backup URLs.
        """
        import threading
        results = []
        processed_urls = set()
        threads = []
        results_lock = threading.Lock()

        def scrape_and_collect(url):
            result = self.scrape_url(url, min_length=min_length)
            if result:
                with results_lock:
                    if len(results) < target_count:
                        results.append(result)
                        print(f"✅ Successfully scraped ({len(results)}/{target_count})")
            else:
                print(f"❌ Failed to scrape or insufficient content")

        for url in urls:
            if len(results) >= target_count:
                break
            if url in processed_urls:
                continue
            processed_urls.add(url)
            print(f"Processing {len(results)+1}/{target_count}: {url}")
            t = threading.Thread(target=scrape_and_collect, args=(url,))
            t.start()
            threads.append(t)
            while len([th for th in threads if th.is_alive()]) >= target_count:
                time.sleep(0.1)
            time.sleep(delay)

        for t in threads:
            t.join()
            if len(results) >= target_count:
                break

        return results[:target_count]

    def video_link_scraper(self, keyword):
        """
        Scrape the first YouTube video link and title for a given keyword
        Returns a dict with 'title' and 'url', or None if not found.
        """
        try:
            search_keyword = f"{keyword} video" if "video" not in keyword.lower() else keyword
            search_url = "https://duckduckgo.com/"
            print(f"Searching for: {search_keyword}")
            response = self.session.get(
                search_url,
                params={'q': search_keyword},
                timeout=self.default_timeout
            )
            if response.status_code == 200:
                search_params = {
                    'q': search_keyword,
                    't': 'h_',
                    'ia': 'web',
                    's': '0'
                }
                time.sleep(1)
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
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    results = soup.find_all('div', class_='result')
                    for result in results:
                        link = result.find('a', class_='result__a')
                        if not link:
                            continue
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        if href.startswith('/'):
                            href = 'https://duckduckgo.com' + href
                        if 'duckduckgo.com/l/?uddg=' in href:
                            try:
                                href = unquote(href.split('uddg=')[-1].split('&')[0])
                            except:
                                continue
                        if 'youtube.com/watch' in href or 'youtu.be/' in href:
                            print(f"\nFound YouTube video:")
                            print(f"Title: {title}")
                            print(f"URL: {href}")
                            return {
                                'title': title,
                                'url': href
                            }
                    print("No YouTube videos found in the search results.")
                    return None
                else:
                    print(f"❌ Failed to get search results. Status code: {response.status_code}")
                    return None
            return None
        except Exception as e:
            print(f"Error searching for video: {str(e)}")
            return None

    def get_yahoo_news_links(self, category_url):
        """
        Scrape all news article links from a Yahoo News category page.
        Improved: Accepts more link patterns and both relative and absolute URLs.
        Always uses a browser User-Agent to avoid bot detection.
        """
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = self.session.get(category_url, headers=headers, timeout=self.default_timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            links = set()
            for a in soup.find_all('a', href=True):
                href = a['href']
                # Accept relative and absolute Yahoo article links
                if (
                    href.startswith('/news/') or
                    href.startswith('/finance/') or
                    href.startswith('/business/') or
                    href.startswith('/lifestyle/') or
                    href.startswith('/world/') or
                    (href.startswith('https://') and 'yahoo.com' in href)
                ):
                    # Only include links that look like articles (not navigation, ads, etc.)
                    if href.count('-') > 0 or 'article' in href:
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = f'https://www.yahoo.com{href}'
                        links.add(full_url)
            return list(links)
        except Exception as e:
            print(f"[YAHOO][ERROR] Failed to scrape Yahoo news links: {e}")
            return []

    # Add other utility methods as needed, e.g., scrape_multiple_urls, extract_main_content, video_link_scraper, etc. 


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <URL>")
        sys.exit(1)
    url = sys.argv[1]
    scraper = WebContentScraper()
    if "yahoo.com/news/" in url:
        links = scraper.get_yahoo_news_links(url)
        print(f"Found {len(links)} article links:")
        for link in links:
            print(link)
    else:
        result = scraper.scrape_url(url)
        if result:
            print("\n--- SCRAPED RESULT ---")
            print(f"Title: {result['title']}")
            print(f"URL: {result['url']}")
            print(f"Content Length: {result['content_length']}")
            print(f"Content (first 500 chars):\n{result['content'][:500]}")
        else:
            print("Failed to scrape or insufficient content.") 