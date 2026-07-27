import asyncio
from playwright.async_api import async_playwright
import sqlite3

async def run_test():
    # Database verification first
    conn = sqlite3.connect("superonline_enterprise.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_count = cursor.fetchone()[0]
    
    print("--- DATABASE CHECK ---")
    if total_count == 314:
        print("SUCCESS: Database record count is exactly 314.")
    else:
        print(f"ERROR: Expected 314 records, found {total_count}.")
        
    cursor.execute("SELECT SUM(like_count), SUM(engagement_count) FROM complaints")
    likes, engagements = cursor.fetchone()
    if likes == 0 and engagements == 0:
        print("SUCCESS: All new interaction columns for existing data are 0.")
    else:
        print(f"ERROR: Interaction columns have non-zero values. Likes: {likes}, Engagements: {engagements}")
    conn.close()

    print("\n--- UI TESTS ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("1. Navigating to social providers tab...")
        await page.goto("http://localhost:8080/#/social-providers")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        # Check if 4 providers are loaded
        await page.wait_for_selector(".kpi-card h4", state="visible")
        provider_cards = await page.locator(".kpi-card h4").all_inner_texts()
        expected = ["X", "INSTAGRAM", "FACEBOOK", "TIKTOK"]
        
        if all(p in provider_cards for p in expected):
            print("SUCCESS: All 4 social media providers are listed in UI.")
        else:
            print(f"ERROR: Missing providers in UI. Found: {provider_cards}")
            
        # Check if all are disabled
        badges = await page.locator(".kpi-card .badge-sent").all_inner_texts()
        if all("Devre Dışı" in b for b in badges):
            print("SUCCESS: All providers are correctly marked as disabled.")
        else:
            print(f"ERROR: Some providers are not disabled. Badges: {badges}")

        print("2. Checking DB Tab...")
        await page.goto("http://localhost:8080/#/complaints")
        await page.wait_for_selector("#complaints-tbody tr", state="visible")
        rows_count = await page.locator("#complaints-tbody tr").count()
        if rows_count > 100:
            print(f"SUCCESS: Complaints DB tab is working, found {rows_count} records.")
        else:
            print(f"ERROR: Complaints DB tab failed to load records. Found: {rows_count}")
            
        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
