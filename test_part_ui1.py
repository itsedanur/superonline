import asyncio
from playwright.async_api import async_playwright

async def run_test():
    print("--- UI TESTS FOR PART UI-1 (Redesign) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        await page.goto("http://localhost:8080/#/social-providers")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("1. Checking Social Grid Element")
        grid = page.locator(".social-grid")
        await grid.wait_for(state="visible")
        print("SUCCESS: .social-grid is visible.")
        
        print("2. Checking Cards count and structure")
        cards = page.locator(".social-card")
        count = await cards.count()
        print(f"SUCCESS: Found {count} social cards.")
        
        if count > 0:
            card = cards.nth(0)
            
            # Check SVG icon instead of emoji
            svg_count = await card.locator(".social-card-icon svg").count()
            if svg_count > 0:
                print("SUCCESS: SVG icon is used instead of emoji.")
            else:
                print("ERROR: SVG icon not found in card.")
                
            # Check Badges
            badge = card.locator(".status-badge")
            badge_count = await badge.count()
            if badge_count > 0:
                print("SUCCESS: Status badge is present.")
            else:
                print("ERROR: Status badge not found.")
                
            # Check buttons
            buttons = card.locator(".social-card-actions button")
            btn_count = await buttons.count()
            if btn_count == 3:
                print("SUCCESS: Exactly 3 action buttons are present in the card.")
            else:
                print(f"ERROR: Expected 3 buttons, found {btn_count}.")
                
        print("3. Checking responsive behavior")
        
        # Desktop
        await page.set_viewport_size({"width": 1440, "height": 900})
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshot_desktop.png")
        print("SUCCESS: Desktop screenshot captured.")
        
        # Tablet
        await page.set_viewport_size({"width": 768, "height": 1024})
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshot_tablet.png")
        print("SUCCESS: Tablet screenshot captured.")
        
        # Mobile
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.wait_for_timeout(500)
        await page.screenshot(path="screenshot_mobile.png")
        print("SUCCESS: Mobile screenshot captured.")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            if "favicon" not in err.lower(): # ignore favicon errors
                print(err)
        if not [e for e in console_errors if "favicon" not in e.lower()]:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
