import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        
        network_errors = []
        page.on("response", lambda response: network_errors.append(f"{response.status} {response.url}") if response.status >= 400 and "/api/" in response.url else None)

        print("Navigating to complaints page...")
        await page.goto("http://localhost:8080/?v=test1234#/complaints")
        await page.wait_for_selector("#complaints-tbody tr", state="visible")
        
        # Test 1: Click ID and verify modal opens
        print("Testing click on Complaint ID...")
        first_row_id = await page.locator("#complaints-tbody tr:nth-child(1) td:nth-child(1) strong").inner_text()
        print(f"First row ID: {first_row_id}")
        await page.locator("#complaints-tbody tr:nth-child(1) td:nth-child(1) strong").click()
        
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        modal_id_text = await page.locator("#cd-id").inner_text()
        print(f"Modal ID loaded: {modal_id_text}")
        
        # Take screenshot of open modal
        await page.screenshot(path="modal_opened.png", full_page=True)
        print("Saved screenshot: modal_opened.png")

        # Verify some fields are filled
        cat = await page.locator("#cd-main-cat").inner_text()
        print(f"Main category in modal: {cat}")

        # Test 2: Close modal via Escape key
        print("Testing modal close via ESC...")
        await page.keyboard.press("Escape")
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("Modal closed successfully via ESC.")

        # Test 3: Check "Kaynakta Aç" buttons
        print("Testing 'Kaynakta Aç' buttons...")
        # Check if disabled button exists
        disabled_buttons = page.locator("button.disabled:has-text('Kaynakta Aç')")
        disabled_count = await disabled_buttons.count()
        print(f"Found {disabled_count} disabled 'Kaynakta Aç' buttons.")
        
        # Check if enabled button exists
        enabled_buttons = page.locator("button:not(.disabled):has-text('Kaynakta Aç')")
        enabled_count = await enabled_buttons.count()
        print(f"Found {enabled_count} enabled 'Kaynakta Aç' buttons.")
        
        if enabled_count > 0:
            print("Testing click on enabled 'Kaynakta Aç' button...")
            async with context.expect_page() as new_page_info:
                await enabled_buttons.first.click()
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("domcontentloaded")
            print(f"New tab opened successfully with URL: {new_page.url}")
            await new_page.close()

        # Test 4: Filters
        print("Testing filters...")
        await page.select_option("#filter-product", "Fiber")
        await page.wait_for_timeout(1000) # wait for network
        rows_fiber = await page.locator("#complaints-tbody tr").count()
        print(f"Rows after Fiber filter: {rows_fiber}")
        await page.screenshot(path="table_filtered.png")
        print("Saved screenshot: table_filtered.png")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")
            
        print("--- NETWORK ERRORS ---")
        for err in network_errors:
            print(err)
        if not network_errors:
            print("No network errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
