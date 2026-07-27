import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("1. Playwright - Navigating to complaints DB tab...")
        await page.goto("http://localhost:8080/#/complaints")
        await page.wait_for_selector("#complaints-tbody tr", state="visible")

        print("2. Filtering SIKAYETVAR...")
        await page.locator("#filter-platform").select_option("SIKAYETVAR")
        await page.wait_for_timeout(1000)
        rows_count = await page.locator("#complaints-tbody tr").count()
        if rows_count == 314 or rows_count > 100:
            print(f"SUCCESS: Found {rows_count} records for SIKAYETVAR.")
        else:
            print(f"ERROR: SIKAYETVAR filter returned {rows_count} records.")

        print("3. Filtering X (Twitter)...")
        await page.locator("#filter-platform").select_option("X")
        await page.wait_for_timeout(1000)
        empty_text_x = await page.locator("#complaints-tbody tr td").inner_text()
        if "bulunamadı" in empty_text_x.lower():
            print("SUCCESS: X filter returned 0 results as expected.")
        else:
            print(f"ERROR: X filter returned records or unexpected text: {empty_text_x}")

        print("4. Filtering INSTAGRAM...")
        await page.locator("#filter-platform").select_option("INSTAGRAM")
        await page.wait_for_timeout(1000)
        empty_text_ig = await page.locator("#complaints-tbody tr td").inner_text()
        if "bulunamadı" in empty_text_ig.lower():
            print("SUCCESS: INSTAGRAM filter returned 0 results as expected.")
        else:
            print(f"ERROR: INSTAGRAM filter returned records or unexpected text: {empty_text_ig}")

        print("5. Reset filter to SIKAYETVAR & Open Modal...")
        await page.locator("#filter-platform").select_option("SIKAYETVAR")
        await page.wait_for_timeout(1000)
        
        first_row_id = page.locator("#complaints-tbody tr:nth-child(1) td:nth-child(1) strong")
        await first_row_id.click()
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        
        platform_val = await page.locator("#cd-platform").inner_text()
        ctype_val = await page.locator("#cd-content-type").inner_text()
        b_unit = await page.locator("#cd-business-unit").inner_text()
        b_brand = await page.locator("#cd-brand").inner_text()
        b_replied = await page.locator("#cd-brand-replied").inner_text()
        c_status = await page.locator("#cd-case-status").inner_text()

        print(f"Modal values - Platform: {platform_val}, Content Type: {ctype_val}, Business Unit: {b_unit}, Brand: {b_brand}, Replied: {b_replied}, Case Status: {c_status}")
        if platform_val == "SIKAYETVAR" and ctype_val == "COMPLAINT" and b_unit == "INTERNET_SERVICES" and c_status == "NEW":
            print("SUCCESS: Detay modalındaki yeni alanlar dolu ve doğru.")
        else:
            print("ERROR: Modal fields are incorrect.")

        print("6. Test Modal Closing Mechanisms...")
        await page.locator("#complaint-detail-close").click()
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via X button.")

        await first_row_id.click()
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        await page.locator("#complaint-detail-close-footer").click()
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via Kapat button.")

        await first_row_id.click()
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        await page.keyboard.press("Escape")
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via ESC key.")

        await first_row_id.click()
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        await page.mouse.click(10, 10)
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed via Backdrop click.")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
