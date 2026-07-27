import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to complaints DB tab...")
        await page.goto("http://localhost:8080/#/complaints")
        await page.wait_for_selector("#complaints-tbody tr", state="visible")
        
        # Helper to open modal
        async def open_modal():
            print("Opening first complaint modal...")
            first_row_id = page.locator("#complaints-tbody tr:nth-child(1) td:nth-child(1) strong")
            await first_row_id.click()
            await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
            print("Modal opened successfully.")

        # Test 1: X Button
        await open_modal()
        print("Clicking X button...")
        await page.locator("#complaint-detail-close").click()
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via X button.")

        # Test 2: Close Button
        await open_modal()
        print("Clicking 'Kapat' button...")
        await page.locator("#complaint-detail-close-footer").click()
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via Kapat button.")

        # Test 3: ESC Key
        await open_modal()
        print("Pressing Escape key...")
        await page.keyboard.press("Escape")
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via ESC key.")

        # Test 4: Backdrop Click
        await open_modal()
        print("Clicking backdrop...")
        await page.mouse.click(10, 10) # Top left is definitely backdrop
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via Backdrop click.")
        
        print("Checking body overflow...")
        overflow = await page.evaluate("document.body.style.overflow")
        if overflow == "":
            print("SUCCESS: Body scroll state is normal.")
        else:
            print(f"ERROR: Body overflow is {overflow}")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
