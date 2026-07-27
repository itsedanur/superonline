import sys
import time
from playwright.sync_api import sync_playwright

def run():
    print("🚀 Starting Playwright E2E Test on http://localhost:8080 ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()

        page.on("console", lambda msg: print(f"🖥️ BROWSER CONSOLE: [{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: print(f"💥 BROWSER ERROR: {err}"))

        def handle_dialog(dialog):
            print(f"💬 DIALOG INTERCEPTED | Type: {dialog.type} | Message: {dialog.message[:40]}...")
            if dialog.type == "prompt":
                dialog.accept("1")
            else:
                dialog.accept()

        page.on("dialog", handle_dialog)

        post_responses = []

        def handle_response(response):
            if "/api/v1/prototype-scrape" in response.url and response.request.method == "POST":
                post_responses.append({
                    "url": response.url,
                    "status": response.status,
                    "json": response.json()
                })

        page.on("response", handle_response)

        start_time = time.time()
        page.goto("http://localhost:8080", wait_until="networkidle")
        print("✅ Homepage loaded in", round(time.time() - start_time, 2), "s")

        btn = page.locator("#btn-prototype-scrape")
        if not btn.is_visible():
            print("❌ ERROR: Button #btn-prototype-scrape not found")
            sys.exit(1)

        print("👉 Clicking #btn-prototype-scrape ...")
        t_click_start = time.time()
        btn.click()
        
        # Wait for URL hash redirection
        print("⏳ Waiting for auto-redirection to #/scrape-runs/ ...")
        try:
            page.wait_for_url(lambda url: "#/scrape-runs/" in url, timeout=10000)
            print(f"✅ SUCCESS: Auto-redirection verified! URL is now: {page.url}")
        except Exception as e:
            print(f"❌ FAIL: Redirection timeout. Current URL: {page.url}")

        current_url = page.url

        if post_responses:
            res_info = post_responses[0]
            print("📡 POST Response Status:", res_info["status"])
            print("📡 POST Response JSON:", res_info["json"])
            if res_info["json"].get("status") in ["RUNNING", "COMPLETED"]:
                print("✅ SUCCESS: POST returned valid status 'RUNNING' or 'COMPLETED'!")
        
        screenshot_path = "/tmp/playwright_scrape_run_verification.png"
        page.screenshot(path=screenshot_path)
        print(f"📸 Screenshot saved to {screenshot_path}")

        browser.close()

if __name__ == "__main__":
    run()
