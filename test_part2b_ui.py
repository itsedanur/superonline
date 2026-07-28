import asyncio
from playwright.async_api import async_playwright
import sqlite3

async def run_test():
    conn = sqlite3.connect("superonline_enterprise.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_count_before = cursor.fetchone()[0]
    
    print("--- UI TESTS FOR PART 2B ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        # Test 1: Feature Flag is ON
        # Actually since we start the server using os.environ, we will set ENABLE_X_PUBLIC_WEB_PROTOTYPE=true when running this script
        await page.goto("http://localhost:8080/#/social-providers")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("1. Checking X Provider UI with Feature Flag ON")
        await page.wait_for_selector(".kpi-card h4:has-text('X')", state="visible")
        x_card = page.locator(".kpi-card", has_text="X")
        
        badge_text = await x_card.locator(".badge-sent").inner_text()
        if "Prototip Hazır" in badge_text:
            print("SUCCESS: X provider is ready for prototype.")
        else:
            print(f"ERROR: X provider is not ready. Badge: {badge_text}")
            
        print("2. Clicking 'Ön İzleme Yap'")
        # We trigger the preview, but we mock window.alert to not block and capture the message
        alert_msgs = []
        page.on("dialog", lambda dialog: asyncio.create_task(handle_dialog(dialog, alert_msgs)))
        
        async def handle_dialog(dialog, msgs):
            msgs.append(dialog.message)
            await dialog.accept()
            
        await x_card.locator("button:has-text('Ön İzleme Yap')").click()
        # Wait for the network request to finish and second alert
        await page.wait_for_timeout(15000) # Wait 15 seconds for search to finish
        
        print("Alerts triggered:", alert_msgs)
        if len(alert_msgs) >= 2:
            print("SUCCESS: Preview was triggered and completed.")
        else:
            print("ERROR: Preview didn't complete or show results.", alert_msgs)
            
        print("3. Checking Database after DRY RUN")
        cursor.execute("SELECT COUNT(*) FROM complaints")
        total_count_after = cursor.fetchone()[0]
        if total_count_before == total_count_after:
            print("SUCCESS: Database record count did not change during preview (DRY RUN worked).")
        else:
            print(f"ERROR: Database changed during preview! Before: {total_count_before}, After: {total_count_after}")
            
        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()
    conn.close()

if __name__ == "__main__":
    asyncio.run(run_test())
