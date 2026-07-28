import asyncio
from playwright.async_api import async_playwright

async def run_test():
    print("--- UI TESTS FOR PART UI-4 (Visual Polish) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        network_errors = []
        
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("response", lambda res: network_errors.append(res.url) if res.status >= 400 else None)
        
        await page.goto("http://localhost:8080/#/social-providers", wait_until="networkidle")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("\nTEST 1: Texts translation")
        content = await page.content()
        if "Prototip Hazır" in content:
            print("SUCCESS: Found 'Prototip Hazır'")
        else:
            print("ERROR: Missing 'Prototip Hazır'")
            
        if "Devre Dışı" in content:
            print("SUCCESS: Found 'Devre Dışı'")
        else:
            print("ERROR: Missing 'Devre Dışı'")
            
        if "Ücretsiz Web Keşfi" in content:
            print("SUCCESS: Found 'Ücretsiz Web Keşfi'")
        else:
            print("ERROR: Missing 'Ücretsiz Web Keşfi'")
            
        print("\nTEST 2: X Card Connection Text")
        if "API Hazır" not in content:
            print("SUCCESS: 'API Hazır' is removed.")
        else:
            print("ERROR: 'API Hazır' still present.")
            
        print("\nTEST 3: Disabled Import button style")
        x_card = page.locator(".social-card:has(h4:has-text('X'))")
        import_btn = x_card.locator("#btn-import-x")
        bg_color = await import_btn.evaluate("el => window.getComputedStyle(el).backgroundColor")
        if bg_color == "rgb(243, 244, 246)": # F3F4F6
            print("SUCCESS: Disabled Import button background is #F3F4F6.")
        else:
            print(f"ERROR: Disabled Import button background is {bg_color}.")
            
        # Check cursor
        cursor = await import_btn.evaluate("el => window.getComputedStyle(el).cursor")
        if cursor == "not-allowed":
            print("SUCCESS: Cursor is not-allowed.")
        else:
            print(f"ERROR: Cursor is {cursor}.")
            
        print("\nTEST 4: Console and Network")
        print(f"Console errors: {len(console_errors)}")
        print(f"Network errors (>= 400): {len(network_errors)}")
        
        # Take a screenshot to verify UI
        await page.screenshot(path="screenshot_ui4_final.png", full_page=True)
        print("SUCCESS: Captured screenshot_ui4_final.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
