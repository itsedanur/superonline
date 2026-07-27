"""
Pagination and Canonical URL Inspection Script for Şikayetvar.
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

urls_to_test = [
    ("Fiber", "https://www.sikayetvar.com/superonline/fiber-internet"),
    ("Superbox (Turkcell)", "https://www.sikayetvar.com/turkcell/superbox"),
    ("Superbox (Superonline)", "https://www.sikayetvar.com/superonline/superbox"),
    ("DSL", "https://www.sikayetvar.com/superonline/adsl")
]

for label, base_url in urls_to_test:
    print(f"\n==================================================")
    print(f" 🔍 TESTING: {label} ({base_url})")
    print(f"==================================================")
    
    for page_num in range(1, 4):
        target_url = f"{base_url}?page={page_num}" if page_num > 1 else base_url
        print(f"\n--- Page {page_num}: {target_url} ---")
        
        req = urllib.request.Request(target_url, headers=HEADERS)
        try:
            with urllib.request.urlopen(req, context=ssl_context, timeout=8) as res:
                final_url = res.url
                html = res.read().decode('utf-8', errors='ignore')
                
            soup = BeautifulSoup(html, 'html.parser')
            
            canonical_el = soup.find('link', rel='canonical')
            canonical_href = canonical_el['href'] if canonical_el else final_url
            
            total_count_el = soup.find('div', class_=re.compile(r'count|total|stat', re.I)) or soup.find(text=re.compile(r'\d+\s+Şikayet', re.I))
            total_count_text = total_count_el.get_text(strip=True) if hasattr(total_count_el, 'get_text') else str(total_count_el)
            
            links = soup.find_all('a', href=True)
            complaint_links = []
            seen = set()
            
            for a in links:
                href = a['href']
                if (href.startswith('/superonline/') or href.startswith('/turkcell/')) and href.count('-') >= 2:
                    if href not in seen and not any(x in href for x in ['/fiber', '/adsl', '/superbox', '/hiz', '/modem']):
                        title = a.get_text(strip=True)
                        if len(title) > 10 and not title.isdigit():
                            seen.add(href)
                            complaint_links.append((href, title))
                            
            print(f"Final URL: {final_url}")
            print(f"Canonical URL: {canonical_href}")
            print(f"Visible Complaint Cards Found: {len(complaint_links)}")
            print(f"Total Complaints text on page: {total_count_text[:60] if total_count_text else 'N/A'}")
            
            if complaint_links:
                print(f"First complaint on page {page_num}: {complaint_links[0][1]} ({complaint_links[0][0]})")
                print(f"Last complaint on page {page_num}: {complaint_links[-1][1]} ({complaint_links[-1][0]})")

        except Exception as e:
            print(f"Error: {e}")
