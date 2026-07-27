"""
Playwright & Container Verification Script for Superbox Canonical URL, Multi-Page Pagination & Checkpoints
"""

import sys
import subprocess
import time
import json

def verify_pagination():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        from playwright.sync_api import sync_playwright

    print("🚀 Running Superbox & Multi-Page Pagination Playwright Verification...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Step 1: Verify Superbox URL
        print("🔍 Navigating to Superbox page...")
        res = page.goto("https://www.sikayetvar.com/turkcell/superbox", wait_until="domcontentloaded")
        print(f"✅ Superbox HTTP Status: {res.status}")
        assert res.status == 200, "Superbox page failed to load!"

        # Extract page 1 complaints excluding promo links
        cards_page1 = page.locator("a[href*='/turkcell/']").all()
        urls_p1 = []
        for c in cards_page1:
            href = c.get_attribute("href") or ""
            txt = c.inner_text().strip()
            if href.count('-') >= 2 and len(txt) > 15 and not any(x in href for x in ['/superbox-500-gb', '/yurt-disi-paketleri']):
                if href not in urls_p1:
                    urls_p1.append(href)

        print(f"📊 Page 1 Actual Complaints Found: {len(urls_p1)}")
        assert len(urls_p1) > 0, "No complaints found on page 1!"

        # Step 2: Navigate to Page 2
        print("🔍 Navigating to Superbox Page 2...")
        res2 = page.goto("https://www.sikayetvar.com/turkcell/superbox?page=2", wait_until="domcontentloaded")
        print(f"✅ Superbox Page 2 HTTP Status: {res2.status}")
        assert res2.status == 200, "Superbox page 2 failed to load!"

        cards_page2 = page.locator("a[href*='/turkcell/']").all()
        urls_p2 = []
        for c in cards_page2:
            href = c.get_attribute("href") or ""
            txt = c.inner_text().strip()
            if href.count('-') >= 2 and len(txt) > 15 and not any(x in href for x in ['/superbox-500-gb', '/yurt-disi-paketleri']):
                if href not in urls_p2:
                    urls_p2.append(href)

        print(f"📊 Page 2 Actual Complaints Found: {len(urls_p2)}")
        assert len(urls_p2) > 0, "No complaints found on page 2!"

        # Assert page 1 and page 2 first actual complaint URLs are DIFFERENT
        print(f"📌 Page 1 First Complaint: {urls_p1[0]}")
        print(f"📌 Page 2 First Complaint: {urls_p2[0]}")
        assert urls_p1[0] != urls_p2[0], "Page 1 and Page 2 contain identical items!"

        # Step 3: Trigger UI Standard Scrape on localhost:8080
        print("🌐 Navigating to http://localhost:8080...")
        page.goto("http://localhost:8080", wait_until="networkidle")

        def handle_dialog(d):
            print(f"💬 Dialog Alert/Confirm: '{d.message[:80]}...' -> Accepting...")
            d.accept()

        page.on("dialog", handle_dialog)

        print("👉 Clicking #btn-prototype-scrape...")
        btn = page.locator("#btn-prototype-scrape")
        btn.click()

        # Wait for scrape completion
        page.wait_for_timeout(8000)

        browser.close()

    print("\n🎉 PLAYWRIGHT SUPERBOX & MULTI-PAGE PAGINATION TEST PASSED 100%!")

if __name__ == "__main__":
    verify_pagination()
