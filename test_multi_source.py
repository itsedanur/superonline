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

        # 1-3. Verify new columns
        print("Checking column headers...")
        headers = await page.locator("table.data-table thead tr th").all_inner_texts()
        if "Mecra" in headers and "İçerik Tipi" in headers:
            print("SUCCESS: Mecra and İçerik Tipi columns found.")
        else:
            print(f"ERROR: Columns missing. Headers: {headers}")

        # 4-5. Filter SIKAYETVAR
        print("Filtering SIKAYETVAR...")
        await page.locator("#filter-platform").select_option("SIKAYETVAR")
        await page.wait_for_timeout(1000)
        rows_count = await page.locator("#complaints-tbody tr").count()
        if rows_count > 1:
            print(f"SUCCESS: Found {rows_count} records for SIKAYETVAR.")
        else:
            print("ERROR: SIKAYETVAR filter did not return records.")

        # 6-7. Filter X
        print("Filtering X (Twitter)...")
        await page.locator("#filter-platform").select_option("X")
        await page.wait_for_timeout(1000)
        empty_text = await page.locator("#complaints-tbody tr td").inner_text()
        if "bulunamadı" in empty_text.lower():
            print("SUCCESS: X filter returned 0 results as expected.")
        else:
            print(f"ERROR: X filter returned records or unexpected text: {empty_text}")

        # Reset filter
        await page.locator("#filter-platform").select_option("ALL")
        await page.wait_for_timeout(1000)

        # 8-9. Open modal and check fields
        print("Opening first complaint modal...")
        first_row_id = page.locator("#complaints-tbody tr:nth-child(1) td:nth-child(1) strong")
        await first_row_id.click()
        await page.wait_for_selector("#modal-complaint-detail:not(.hidden)", state="visible")
        
        platform_val = await page.locator("#cd-platform").inner_text()
        ctype_val = await page.locator("#cd-content-type").inner_text()
        print(f"Modal values - Platform: {platform_val}, Content Type: {ctype_val}")
        if platform_val == "SIKAYETVAR" and ctype_val == "COMPLAINT":
            print("SUCCESS: Modal fields are populated correctly.")
        else:
            print("ERROR: Modal fields are incorrect.")

        # 10-12. Test modal close
        print("Closing modal via X...")
        await page.locator("#complaint-detail-close").click()
        await page.wait_for_selector("#modal-complaint-detail.hidden", state="hidden")
        print("SUCCESS: Modal closed successfully.")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
