"""
Inspection script for Şikayetvar static HTML structure and complaint selectors.
"""
import urllib.request
import urllib.error
import ssl
import re
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
}

ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

url = "https://www.sikayetvar.com/superonline/fiber-internet"
print(f"Fetching {url}...")

req = urllib.request.Request(url, headers=HEADERS)
try:
    with urllib.request.urlopen(req, context=ssl_context, timeout=10) as res:
        status = res.status
        final_url = res.url
        html = res.read().decode('utf-8', errors='ignore')
        
    print(f"Status Code: {status}")
    print(f"Final URL: {final_url}")
    print(f"Content Length: {len(html)} bytes")
    print(f"Cloudflare/Bot Blocked?: {'Just a moment...' in html or '403 Forbidden' in html}")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Try finding complaint cards
    cards = soup.find_all('article', class_=re.compile(r'complaint|card', re.I)) or soup.find_all('div', class_=re.compile(r'complaint-card|card-v2', re.I))
    print(f"Found card elements (article/div): {len(cards)}")
    
    links = soup.find_all('a', href=True)
    complaint_links = []
    for a in links:
        href = a['href']
        if href.startswith('/superonline/') and href.count('-') >= 2:
            if not any(x in href for x in ['/fiber', '/adsl', '/superbox', '/hiz', '/modem']):
                title = a.get_text(strip=True)
                if len(title) > 10 and not title.isdigit():
                    complaint_links.append((href, title))
                    
    print(f"Total valid complaint links found: {len(complaint_links)}")
    print("\nTop 5 Complaint Links Extracted:")
    for href, title in complaint_links[:5]:
        print(f" - https://www.sikayetvar.com{href} | Title: {title}")

except Exception as e:
    print(f"Error fetching URL: {e}")
