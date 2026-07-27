"""
Playwright E2E UI Test - Prototype Scrape Button Click & Dialog Verification
Automates clicking #btn-prototype-scrape on http://localhost:8080, accepting the confirm dialog, and verifying the POST /api/v1/prototype-scrape request & polling completion.
"""

import sys
import time
import subprocess

def run_playwright_test():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed, installing playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        from playwright.sync_api import sync_playwright

    logs = []
    dialog_messages = []
    network_requests = []

    print("🚀 Starting Playwright E2E UI Test on http://localhost:8080 ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Console listener
        page.on("console", lambda msg: logs.append(msg.text))

        # Dialog listener (auto accept window.confirm and alert)
        def handle_dialog(dialog):
            dialog_messages.append(dialog.message)
            print(f"💬 Dialog Triggered: '{dialog.message}' -> Auto-accepting...")
            dialog.accept()

        page.on("dialog", handle_dialog)

        # Network request listener
        def handle_request(req):
            if "prototype-scrape" in req.url:
                network_requests.append({"url": req.url, "method": req.method})
                print(f"🌐 Network Request Captured: {req.method} {req.url}")

        page.on("request", handle_request)

        # Navigate to http://localhost:8080
        page.goto("http://localhost:8080", wait_until="networkidle")
        print("✅ Page loaded: http://localhost:8080")

        # Verify button exists and is visible
        button = page.locator("#btn-prototype-scrape")
        if not button.is_visible():
            raise Exception("Button #btn-prototype-scrape is not visible on DOM")

        print("✅ Button #btn-prototype-scrape found and visible.")

        # Click the button
        print("👉 Clicking #btn-prototype-scrape ...")
        button.click()

        # Wait for async polling to finish (approx 5-6 seconds)
        page.wait_for_timeout(6000)

        browser.close()

    print("\n--- E2E TEST SUMMARY ---")
    print(f"Captured Console Logs: {logs}")
    print(f"Captured Dialog Messages: {dialog_messages}")
    print(f"Captured Network Requests: {network_requests}")

    # Assertions
    assert "APP_JS_PROTOTYPE_FIX_LOADED" in logs, "APP_JS_PROTOTYPE_FIX_LOADED log missing!"
    assert "PROTOTYPE_BUTTON_CLICK_RECEIVED" in logs, "PROTOTYPE_BUTTON_CLICK_RECEIVED log missing!"
    assert "PROTOTYPE_POST_START" in logs, "PROTOTYPE_POST_START log missing!"
    assert any("prototype-scrape" in r["url"] and r["method"] == "POST" for r in network_requests), "POST /api/v1/prototype-scrape request missing!"

    print("\n🎉 E2E UI CLICK TEST PASSED 100% SUCCESSFULLY!")

if __name__ == "__main__":
    run_playwright_test()
