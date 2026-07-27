import asyncio
from playwright.async_api import async_playwright

async def run_test():
    print("--- UI TESTS FOR PART UI-2 (Enterprise UX Polish) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        # Test alert intercept - if window.alert is called, we will flag it
        alert_called = False
        def handle_dialog(dialog):
            nonlocal alert_called
            alert_called = True
            asyncio.create_task(dialog.accept())
        page.on("dialog", handle_dialog)
        
        await page.goto("http://localhost:8080/#/social-providers")
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("1. Checking global header actions visibility")
        header_actions = page.locator("#global-header-actions")
        is_visible = await header_actions.is_visible()
        if not is_visible:
            print("SUCCESS: Global header actions are hidden on this tab.")
        else:
            print("ERROR: Global header actions are still visible.")
        
        print("2. Checking Card styling (radius, border)")
        cards = page.locator(".social-card")
        count = await cards.count()
        if count > 0:
            card = cards.nth(0)
            radius = await card.evaluate("el => window.getComputedStyle(el).borderRadius")
            if radius == "12px":
                print("SUCCESS: Card border-radius is 12px.")
            else:
                print(f"ERROR: Card border-radius is {radius}")
                
            # Trigger preview to check modal and loading state
            print("3. Clicking preview to test Loading Spinner and Enterprise Modal")
            preview_btn = card.locator("button:has-text('Ön İzleme')")
            await preview_btn.click()
            
            # Check for spinner
            spinner_visible = await preview_btn.locator(".spinner").is_visible()
            if spinner_visible:
                print("SUCCESS: Loading spinner is visible.")
            else:
                print("ERROR: Loading spinner is not visible.")
                
            # Wait for modal to appear
            await page.wait_for_selector("#enterprise-alert-modal:not(.hidden)", state="visible", timeout=30000)
            print("SUCCESS: Enterprise Alert Modal opened successfully.")
            
            if alert_called:
                print("ERROR: window.alert() was called! Alert is not allowed.")
            else:
                print("SUCCESS: No window.alert() was called.")
                
        # Take screenshot of the modal
        await page.screenshot(path="screenshot_ui2_modal.png")
        print("SUCCESS: Screenshot of modal captured.")
        
        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            if "favicon" not in err.lower():
                print(err)
        if not [e for e in console_errors if "favicon" not in e.lower()]:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
