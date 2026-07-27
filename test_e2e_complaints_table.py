"""
Playwright E2E UI Test - Complaints Route, Table Rendering & Auto-Refresh Verification
"""

import sys
import subprocess

def run_playwright_e2e():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        from playwright.sync_api import sync_playwright

    logs = []
    dialogs = []
    requests = []

    print("🚀 Starting Playwright E2E Test for Complaints Route & Table ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.on("console", lambda msg: logs.append(msg.text))
        
        def handle_dialog(dialog):
            dialogs.append(dialog.message)
            print(f"💬 Dialog: '{dialog.message}' -> Accepting...")
            dialog.accept()

        page.on("dialog", handle_dialog)

        def handle_req(req):
            if "complaints" in req.url:
                requests.append({"url": req.url, "method": req.method})
                print(f"🌐 Captured Request: {req.method} {req.url}")

        page.on("request", handle_req)

        # Step 1: Open app
        page.goto("http://localhost:8080", wait_until="networkidle")
        print("✅ Navigated to http://localhost:8080")

        # Step 2: Click "Tüm Veritabanı" nav button
        print("👉 Clicking 'Tüm Veritabanı' sidebar button...")
        btn = page.locator('.nav-item[data-tab="complaints-db"]')
        btn.click()
        page.wait_for_timeout(1000)

        # Step 3: Assert Hash URL is #/complaints
        current_url = page.url
        print(f"📌 Current URL after click: {current_url}")
        assert "#/complaints" in current_url, f"Expected URL to contain #/complaints, got {current_url}"

        # Step 4: Check Table Rows in DOM
        rows = page.locator("#complaints-tbody tr")
        row_count = rows.count()
        print(f"📊 DOM Table Row Count: {row_count}")
        assert row_count > 0, "Complaints table is empty!"

        # Extract first row data for verification
        first_row_text = rows.first.inner_text()
        print(f"📝 First Row Sample Text: {first_row_text.splitlines()}")

        # Step 5: Test Scrape Button & Auto-refresh
        print("👉 Clicking #btn-prototype-scrape...")
        scrape_btn = page.locator("#btn-prototype-scrape")
        scrape_btn.click()

        page.wait_for_timeout(6000)

        # Assert table is still populated after scrape
        new_row_count = page.locator("#complaints-tbody tr").count()
        print(f"📊 DOM Table Row Count After Scrape: {new_row_count}")
        assert new_row_count > 0, "Table became empty after scrape!"

        browser.close()

    print("\n🎉 PLAYWRIGHT E2E ROUTE & TABLE RENDER TEST PASSED 100%!")

if __name__ == "__main__":
    run_playwright_e2e()
