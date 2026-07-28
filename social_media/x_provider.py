import urllib.parse
from datetime import datetime
from typing import List, Dict, Any
from .models import NormalizedSocialContent
from .provider import SocialMediaProvider
from .dictionary import DSS_PRODUCTS_AND_BRANDS
from playwright.sync_api import sync_playwright

class XPublicWebCollector(SocialMediaProvider):
    def __init__(self):
        super().__init__()
        self.platform = "X"

    def _determine_content_type(self, text: str) -> str:
        """Basic rule-based classification."""
        if not text:
            return "UNKNOWN"
        t = text.lower()
        if any(word in t for word in ["nasıl", "neden", "niye", "yardım", "destek"]):
            return "QUESTION"
        if any(word in t for word in ["teşekkür", "harika", "süper", "iyi"]):
            return "PRAISE"
        if any(word in t for word in ["istiyorum", "getirin", "ekleyin", "olsun"]):
            return "SUGGESTION"
        if any(word in t for word in ["bozuk", "çalışmıyor", "donuyor", "hata", "rezalet", "açılmıyor", "iptal"]):
            return "COMPLAINT"
        return "COMMENT"

    def fetch_contents(self, max_results: int = 10, brands_to_search: List[str] = None) -> Dict[str, Any]:
        """Discovers indexed X posts via DuckDuckGo (html.duckduckgo.com)"""
        if not brands_to_search:
            brands_to_search = list(DSS_PRODUCTS_AND_BRANDS.keys())

        result = {
            "status": "UNKNOWN",
            "scanned_queries": 0,
            "raw_items": [],
            "message": "",
            "unreadable_count": 0
        }

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()

                for brand in brands_to_search:
                    if brand not in DSS_PRODUCTS_AND_BRANDS:
                        continue
                    
                    keywords = DSS_PRODUCTS_AND_BRANDS[brand]
                    query = keywords[0]
                    # DuckDuckGo query for x.com statuses
                    ddg_q = f'site:x.com/status "{query}"'
                    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(ddg_q)}"
                    
                    try:
                        page.goto(url, timeout=15000)
                        page.wait_for_timeout(2000)  # Wait for render
                        result["scanned_queries"] += 1
                        
                        # Check DDG page
                        page_content = page.content().lower()
                        if "we've detected" in page_content and "captcha" in page_content:
                            result["status"] = "CAPTCHA_DETECTED"
                            result["message"] = "DDG Captcha engelini tespit etti, işlem durduruldu."
                            break
                        
                        # Extract DDG results
                        links = page.query_selector_all('.result__url')
                        urls_to_visit = []
                        for link in links:
                            href = link.inner_text().strip()
                            if "x.com" in href and "/status/" in href:
                                if not href.startswith("http"):
                                    href = "https://" + href
                                urls_to_visit.append(href)
                        
                        if urls_to_visit:
                            result["status"] = "PUBLIC_RESULTS_AVAILABLE"
                        
                        count = 0
                        for u in urls_to_visit:
                            if count >= max_results:
                                break
                            
                            # Navigate to actual X post
                            try:
                                post_page = context.new_page()
                                post_page.goto(u, timeout=10000)
                                post_page.wait_for_timeout(2000)
                                post_content = post_page.content().lower()
                                
                                is_unreadable = False
                                if "login" in post_content or "sign in" in post_content or "log in" in post_content:
                                    if not post_page.query_selector('article[data-testid="tweet"]'):
                                        is_unreadable = True
                                
                                if is_unreadable:
                                    result["unreadable_count"] += 1
                                    post_page.close()
                                    continue
                                
                                # Try to extract tweet content
                                tweet = post_page.query_selector('article[data-testid="tweet"]')
                                if not tweet:
                                    result["unreadable_count"] += 1
                                    post_page.close()
                                    continue
                                    
                                text_el = tweet.query_selector('[data-testid="tweetText"]')
                                text = text_el.inner_text() if text_el else ""
                                if not text:
                                    result["unreadable_count"] += 1
                                    post_page.close()
                                    continue
                                    
                                author_el = tweet.query_selector('[data-testid="User-Name"]')
                                author = author_el.inner_text() if author_el else "Unknown"
                                username = "Unknown"
                                if "@" in author:
                                    username = "@" + author.split("@")[1].split()[0].strip()
                                
                                # Extract ID from URL
                                external_id = u.split("/status/")[-1].split("?")[0].replace("/", "")
                                
                                item = {
                                    "external_id": external_id,
                                    "source_url": u,
                                    "text": text,
                                    "source_author_username": username,
                                    "matched_brand": brand,
                                    "source_created_at": datetime.utcnow().isoformat() + "Z"
                                }
                                result["raw_items"].append(item)
                                count += 1
                                post_page.close()
                            except Exception as e:
                                result["unreadable_count"] += 1
                                try: post_page.close()
                                except: pass
                                
                    except Exception as e:
                        result["status"] = "UNKNOWN_ERROR"
                        result["message"] = str(e)
                        break
                        
                browser.close()
                
        except Exception as e:
            result["status"] = "UNKNOWN_ERROR"
            result["message"] = str(e)

        if not result["raw_items"] and result["status"] == "UNKNOWN":
            result["status"] = "NO_RESULTS"
            
        return result

    def normalize_content(self, raw_data: Dict[str, Any]) -> NormalizedSocialContent:
        brand = raw_data.get("matched_brand", "UNKNOWN")
        content_type = self._determine_content_type(raw_data.get("text", ""))
        
        meta = {
            "collector": "X_FREE_WEB_DISCOVERY",
            "matched_query": brand,
            "discovery_source": "DuckDuckGo"
        }
        import json
        
        return NormalizedSocialContent(
            platform="X",
            external_id=raw_data.get("external_id", ""),
            source_url=raw_data.get("source_url", ""),
            text=raw_data.get("text", ""),
            source_created_at=raw_data.get("source_created_at", ""),
            source_author_username=raw_data.get("source_author_username", ""),
            content_type=content_type,
            business_unit="DSS",
            brand=brand,
            source_metadata_json=json.dumps(meta)
        )
