import asyncio
from playwright.async_api import async_playwright
import sqlite3

async def run_test():
    conn = sqlite3.connect("superonline_enterprise.db")
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM complaints")
    total_count_before = cursor.fetchone()[0]
    
    print("--- UI TESTS FOR PART 2B.2 (Free Web Discovery) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        await page.goto("http://localhost:8080/#/social-providers")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("1. Checking X Provider UI with Free Discovery")
        await page.wait_for_selector(".kpi-card h4:text-is('X')", state="visible")
        x_card = page.locator(".kpi-card").filter(has=page.locator("h4:text-is('X')"))
        
        card_text = await x_card.inner_text()
        if "Ücretsiz Web Discovery" in card_text:
            print("SUCCESS: X provider is correctly showing 'Ücretsiz Web Discovery'.")
        else:
            print(f"ERROR: X provider text missing. Found: {card_text}")
            
        print("2. Clicking 'Gerçek X Bağlantılarını Bul ve Ön İzle'")
        alert_msgs = []
        page.on("dialog", lambda dialog: asyncio.create_task(handle_dialog(dialog, alert_msgs)))
        
        async def handle_dialog(dialog, msgs):
            msgs.append(dialog.message)
            await dialog.accept()
            
        await x_card.locator("button:has-text('Gerçek X Bağlantılarını Bul ve Ön İzle')").click()
        await page.wait_for_timeout(25000) # DDG search + visiting each link takes longer
        
        print("Alerts triggered:")
        for a in alert_msgs:
            print(a)
            
        if len(alert_msgs) >= 2:
            print("SUCCESS: Free Discovery was triggered and completed.")
        else:
            print("ERROR: Free Discovery didn't complete or show results.")
            
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
