from flask import Flask, request, jsonify
from flask_cors import CORS
from newspaper import Article, ArticleException
import requests
from bs4 import BeautifulSoup
import json
import logging
from datetime import datetime
import random
import time
from urllib.parse import urlparse, urljoin
import re
from readability import Document
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from contextlib import contextmanager
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Multiple User Agents for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
]

def get_random_headers():
    """Generate random headers to avoid bot detection"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }

@contextmanager
def get_selenium_driver():
    """Context manager for Selenium WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument(f'user-agent={random.choice(USER_AGENTS)}')
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = None
    try:
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        yield driver
    finally:
        if driver:
            driver.quit()

def extract_metadata(soup, url):
    """Extract comprehensive metadata from HTML"""
    metadata = {
        'title': None,
        'authors': [],
        'publish_date': None,
        'description': None,
        'keywords': [],
        'images': [],
        'canonical_url': url,
        'site_name': None,
        'language': None,
    }
    
    # Extract title
    title_candidates = [
        soup.find('meta', property='og:title'),
        soup.find('meta', attrs={'name': 'twitter:title'}),
        soup.find('h1'),
        soup.find('title')
    ]
    for candidate in title_candidates:
        if candidate:
            metadata['title'] = candidate.get('content') or candidate.text.strip()
            break
    
    # Extract authors
    author_selectors = [
        ('meta', {'name': 'author'}),
        ('meta', {'property': 'article:author'}),
        ('meta', {'name': 'article:author'}),
        ('span', {'class': re.compile(r'author|byline', re.I)}),
        ('div', {'class': re.compile(r'author|byline', re.I)}),
        ('a', {'rel': 'author'}),
        ('p', {'class': re.compile(r'author|byline', re.I)}),
    ]
    for tag, attrs in author_selectors:
        elements = soup.find_all(tag, attrs)
        for elem in elements:
            author = elem.get('content') or elem.text.strip()
            if author and author not in metadata['authors']:
                metadata['authors'].append(author)
    
    # Extract publish date
    date_selectors = [
        ('meta', {'property': 'article:published_time'}),
        ('meta', {'name': 'publish_date'}),
        ('meta', {'name': 'date'}),
        ('time', {'datetime': True}),
        ('span', {'class': re.compile(r'date|published', re.I)}),
    ]
    for tag, attrs in date_selectors:
        elem = soup.find(tag, attrs)
        if elem:
            metadata['publish_date'] = elem.get('content') or elem.get('datetime') or elem.text.strip()
            break
    
    # Extract description
    desc = soup.find('meta', attrs={'name': 'description'}) or soup.find('meta', property='og:description')
    if desc:
        metadata['description'] = desc.get('content')
    
    # Extract keywords
    keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_meta:
        metadata['keywords'] = [k.strip() for k in keywords_meta.get('content', '').split(',')]
    
    # Extract images
    images = []
    og_image = soup.find('meta', property='og:image')
    if og_image:
        images.append(og_image.get('content'))
    
    for img in soup.find_all('img', src=True)[:10]:  # Limit to first 10 images
        img_url = urljoin(url, img['src'])
        if img_url not in images:
            images.append(img_url)
    
    metadata['images'] = images
    
    # Extract canonical URL
    canonical = soup.find('link', rel='canonical')
    if canonical:
        metadata['canonical_url'] = canonical.get('href')
    
    # Extract site name
    site_name = soup.find('meta', property='og:site_name')
    if site_name:
        metadata['site_name'] = site_name.get('content')
    
    # Extract language
    html_tag = soup.find('html')
    if html_tag:
        metadata['language'] = html_tag.get('lang')
    
    return metadata

def extract_tables(soup):
    """Extract all tables from the page"""
    tables = []
    for table in soup.find_all('table'):
        table_data = []
        for row in table.find_all('tr'):
            row_data = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
            if row_data:
                table_data.append(row_data)
        if table_data:
            tables.append(table_data)
    return tables

def clean_text(text):
    """Clean and normalize text"""
    if not text:
        return ''
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove common boilerplate
    text = re.sub(r'(Accept all cookies|Subscribe to newsletter|Sign up|Login|Register)', '', text, flags=re.I)
    return text.strip()

# Fallback Strategy 1: Newspaper3k
def scrape_with_newspaper(url):
    """Use newspaper3k library for article extraction"""
    try:
        logger.info(f"Attempting scrape with Newspaper3k: {url}")
        article = Article(url)
        article.download()
        article.parse()
        
        try:
            article.nlp()  # Extract keywords and summary
        except:
            pass
        
        if article.text and len(article.text) > 100:
            return {
                'method': 'newspaper3k',
                'title': article.title,
                'authors': article.authors,
                'publish_date': str(article.publish_date) if article.publish_date else None,
                'text': clean_text(article.text),
                'top_image': article.top_image,
                'images': article.images,
                'keywords': article.keywords,
                'summary': article.summary,
                'source': url,
                'success': True
            }
    except Exception as e:
        logger.warning(f"Newspaper3k failed: {str(e)}")
    return None

# Fallback Strategy 2: Trafilatura
def scrape_with_trafilatura(url):
    """Use trafilatura for robust content extraction"""
    try:
        logger.info(f"Attempting scrape with Trafilatura: {url}")
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
            metadata = trafilatura.extract_metadata(downloaded)
            
            if text and len(text) > 100:
                return {
                    'method': 'trafilatura',
                    'title': metadata.title if metadata else None,
                    'authors': [metadata.author] if metadata and metadata.author else [],
                    'publish_date': metadata.date if metadata else None,
                    'text': clean_text(text),
                    'top_image': metadata.image if metadata else None,
                    'images': [],
                    'keywords': metadata.tags if metadata else [],
                    'summary': text[:500] + '...' if len(text) > 500 else text,
                    'source': url,
                    'success': True
                }
    except Exception as e:
        logger.warning(f"Trafilatura failed: {str(e)}")
    return None

# Fallback Strategy 3: Readability
def scrape_with_readability(url):
    """Use readability-lxml for content extraction"""
    try:
        logger.info(f"Attempting scrape with Readability: {url}")
        response = requests.get(url, headers=get_random_headers(), timeout=15)
        doc = Document(response.content)
        
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        # Get metadata from original page
        original_soup = BeautifulSoup(response.content, 'html.parser')
        metadata = extract_metadata(original_soup, url)
        
        if text and len(text) > 100:
            return {
                'method': 'readability',
                'title': metadata['title'] or doc.short_title(),
                'authors': metadata['authors'],
                'publish_date': metadata['publish_date'],
                'text': clean_text(text),
                'top_image': metadata['images'][0] if metadata['images'] else None,
                'images': metadata['images'],
                'keywords': metadata['keywords'],
                'summary': text[:500] + '...' if len(text) > 500 else text,
                'source': url,
                'success': True
            }
    except Exception as e:
        logger.warning(f"Readability failed: {str(e)}")
    return None

# Fallback Strategy 4: Advanced BeautifulSoup
def scrape_with_beautifulsoup(url):
    """Advanced BeautifulSoup scraping with comprehensive selectors"""
    try:
        logger.info(f"Attempting scrape with BeautifulSoup: {url}")
        
        # Try multiple request attempts with different headers
        for attempt in range(3):
            try:
                response = requests.get(url, headers=get_random_headers(), timeout=15, allow_redirects=True)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(random.uniform(1, 3))
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove unwanted elements
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()
        
        # Extract metadata
        metadata = extract_metadata(soup, url)
        
        # Extract main content with comprehensive selectors
        content_selectors = [
            ('article', {}),
            ('div', {'class': re.compile(r'article|content|post|entry|main|story', re.I)}),
            ('div', {'id': re.compile(r'article|content|post|entry|main|story', re.I)}),
            ('main', {}),
            ('section', {'class': re.compile(r'article|content', re.I)}),
            ('[role="main"]', {}),
            ('div', {'itemprop': 'articleBody'}),
        ]
        
        text_content = []
        for tag, attrs in content_selectors:
            elements = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
            for elem in elements:
                # Extract paragraphs
                paragraphs = elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li'])
                for p in paragraphs:
                    p_text = p.get_text(strip=True)
                    if len(p_text) > 20:  # Filter out short fragments
                        text_content.append(p_text)
        
        # Extract tables
        tables = extract_tables(soup)
        
        # Combine all text
        text = ' '.join(text_content)
        
        # Add table content to text
        if tables:
            table_text = '\n\nTables:\n'
            for i, table in enumerate(tables):
                table_text += f'\nTable {i+1}:\n'
                for row in table:
                    table_text += ' | '.join(row) + '\n'
            text += table_text
        
        # Fallback: get all text if content is too short
        if len(text) < 200:
            text = soup.get_text(separator=' ', strip=True)
        
        if text and len(text) > 50:
            return {
                'method': 'beautifulsoup',
                'title': metadata['title'],
                'authors': metadata['authors'],
                'publish_date': metadata['publish_date'],
                'text': clean_text(text),
                'top_image': metadata['images'][0] if metadata['images'] else None,
                'images': metadata['images'],
                'keywords': metadata['keywords'],
                'summary': text[:500] + '...' if len(text) > 500 else text,
                'tables': tables,
                'description': metadata['description'],
                'source': url,
                'success': True
            }
    except Exception as e:
        logger.warning(f"BeautifulSoup failed: {str(e)}")
    return None

# Fallback Strategy 5: Selenium for JavaScript-heavy sites
def scrape_with_selenium(url):
    """Use Selenium for JavaScript-rendered content"""
    try:
        logger.info(f"Attempting scrape with Selenium: {url}")
        
        with get_selenium_driver() as driver:
            driver.get(url)
            
            # Wait for content to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "article"))
                )
            except:
                time.sleep(3)  # Fallback wait
            
            # Scroll to load lazy content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(1)
            
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe']):
                tag.decompose()
            
            metadata = extract_metadata(soup, url)
            
            # Extract content
            content_selectors = [
                'article',
                '[role="main"]',
                'div[class*="article"]',
                'div[class*="content"]',
                'div[class*="post"]',
                'main'
            ]
            
            text_content = []
            for selector in content_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    paragraphs = elem.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'li'])
                    for p in paragraphs:
                        p_text = p.get_text(strip=True)
                        if len(p_text) > 20:
                            text_content.append(p_text)
            
            text = ' '.join(text_content)
            
            # Extract tables
            tables = extract_tables(soup)
            
            if tables:
                table_text = '\n\nTables:\n'
                for i, table in enumerate(tables):
                    table_text += f'\nTable {i+1}:\n'
                    for row in table:
                        table_text += ' | '.join(row) + '\n'
                text += table_text
            
            if len(text) < 200:
                text = soup.get_text(separator=' ', strip=True)
            
            if text and len(text) > 50:
                return {
                    'method': 'selenium',
                    'title': metadata['title'],
                    'authors': metadata['authors'],
                    'publish_date': metadata['publish_date'],
                    'text': clean_text(text),
                    'top_image': metadata['images'][0] if metadata['images'] else None,
                    'images': metadata['images'],
                    'keywords': metadata['keywords'],
                    'summary': text[:500] + '...' if len(text) > 500 else text,
                    'tables': tables,
                    'source': url,
                    'success': True
                }
    except Exception as e:
        logger.warning(f"Selenium failed: {str(e)}")
    return None

# Fallback Strategy 6: Raw extraction as last resort
def scrape_raw(url):
    """Last resort: extract everything from the page"""
    try:
        logger.info(f"Attempting raw scrape: {url}")
        response = requests.get(url, headers=get_random_headers(), timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove scripts and styles
        for tag in soup(['script', 'style']):
            tag.decompose()
        
        metadata = extract_metadata(soup, url)
        text = soup.get_text(separator=' ', strip=True)
        tables = extract_tables(soup)
        
        return {
            'method': 'raw',
            'title': metadata['title'] or 'Unknown Title',
            'authors': metadata['authors'] or ['Unknown'],
            'publish_date': metadata['publish_date'],
            'text': clean_text(text),
            'top_image': metadata['images'][0] if metadata['images'] else None,
            'images': metadata['images'],
            'keywords': metadata['keywords'],
            'summary': text[:500] + '...' if len(text) > 500 else text,
            'tables': tables,
            'source': url,
            'success': True
        }
    except Exception as e:
        logger.error(f"Raw scrape failed: {str(e)}")
        return None

@app.route('/scrape', methods=['GET', 'POST'])
def scrape():
    """Main scraping endpoint with cascading fallback strategies"""
    try:
        # Get URL from query params or JSON body
        if request.method == 'POST':
            data = request.get_json()
            url = data.get('url') if data else None
        else:
            url = request.args.get('url')
        
        if not url:
            return jsonify({'error': 'URL parameter is required', 'success': False}), 400
        
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return jsonify({'error': 'Invalid URL format', 'success': False}), 400
        
        logger.info(f"Scraping request for: {url}")
        start_time = time.time()
        
        # Try all fallback strategies in order
        strategies = [
            scrape_with_newspaper,
            scrape_with_trafilatura,
            scrape_with_readability,
            scrape_with_beautifulsoup,
            scrape_with_selenium,
            scrape_raw
        ]
        
        result = None
        for strategy in strategies:
            result = strategy(url)
            if result and result.get('success'):
                break
            time.sleep(random.uniform(0.5, 1.5))  # Random delay between attempts
        
        if not result:
            return jsonify({
                'error': 'All scraping methods failed',
                'success': False,
                'url': url
            }), 500
        
        # Add scraping metadata
        result['scrape_time'] = round(time.time() - start_time, 2)
        result['timestamp'] = datetime.utcnow().isoformat()
        
        logger.info(f"Successfully scraped {url} using {result.get('method')} in {result['scrape_time']}s")

            # Convert sets to lists for JSON serialization
    for key, value in result.items():
        if isinstance(value, set):
            result[key] = list(value)
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}", exc_info=True)
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat(),
        'service': 'web-scraper-api'
    })

@app.route('/', methods=['GET'])
def index():
    """API documentation endpoint"""
    return jsonify({
        'service': 'Web Scraper API',
        'version': '2.0',
        'endpoints': {
            '/scrape': {
                'methods': ['GET', 'POST'],
                'description': 'Scrape article content from a URL',
                'parameters': {
                    'url': 'The URL to scrape (required)'
                },
                'example': '/scrape?url=https://example.com/article'
            },
            '/health': {
                'methods': ['GET'],
                'description': 'Health check endpoint'
            }
        },
        'strategies': [
            'newspaper3k - News article extraction',
            'trafilatura - Robust content extraction',
            'readability - Main content extraction',
            'beautifulsoup - Advanced HTML parsing',
            'selenium - JavaScript-rendered content',
            'raw - Fallback full text extraction'
        ]
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
