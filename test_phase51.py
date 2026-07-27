import asyncio
from playwright.async_api import async_playwright
import time

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        print("Navigating to Review Queue...")
        await page.goto("http://localhost:8080/?v=phase51#/review-queue")
        await page.wait_for_selector("#rq-tbody tr", state="visible")
        
        # 1. Bekleyen kayıt sayısını al
        initial_queue_count = await page.locator("#nav-review-badge").inner_text()
        print(f"Initial Queue Count: {initial_queue_count}")

        # 2. İlk kaydı aç
        first_row_btn = page.locator("#rq-tbody tr:nth-child(1) button:has-text('İncele')")
        complaint_id = await first_row_btn.get_attribute("data-complaint-id")
        print(f"Opening review for complaint ID: {complaint_id}")
        await first_row_btn.click()
        await page.wait_for_selector("#modal-review-detail:not(.hidden)", state="visible")
        
        # 3. AI sonucunu onayla
        print("Clicking 'AI Sonucunu Onayla'...")
        # Handle the JS alert
        page.once("dialog", lambda dialog: dialog.accept())
        await page.locator("button:has-text('AI Sonucunu Onayla')").click()
        
        # Wait for modal to hide
        await page.wait_for_selector("#modal-review-detail.hidden", state="hidden")
        
        # 4. Kaydın kuyruktan kalktığını doğrula
        await page.wait_for_timeout(1000) # Give DOM time to update
        new_queue_count = await page.locator("#nav-review-badge").inner_text()
        print(f"New Queue Count: {new_queue_count}")
        if int(new_queue_count) == int(initial_queue_count) - 1:
            print("SUCCESS: Queue count decremented!")
        else:
            print("ERROR: Queue count did NOT decrement as expected.")

        # 5. İncelenen Şikâyetler sayfasını aç
        print("Navigating to Reviewed Complaints...")
        await page.goto("http://localhost:8080/?v=phase51#/reviewed-complaints")
        await page.wait_for_selector("#rc-tbody tr", state="visible")
        
        # 6. Aynı kaydın APPROVED olarak göründüğünü doğrula
        approved_row = page.locator(f"#rc-tbody tr:has(strong:has-text('{complaint_id}'))")
        await approved_row.wait_for(state="visible")
        status_text = await approved_row.locator("td:nth-child(8) span").inner_text()
        print(f"Complaint {complaint_id} status in Reviewed Table: {status_text}")
        if status_text == "APPROVED":
            print("SUCCESS: Status is APPROVED.")
        else:
            print(f"ERROR: Expected APPROVED, got {status_text}")

        # 7. Başka bir kaydı manuel düzelt
        print("Navigating back to Review Queue to test MANUAL CORRECTION...")
        await page.goto("http://localhost:8080/?v=phase51#/review-queue")
        await page.wait_for_selector("#rq-tbody tr", state="visible")
        
        first_row_btn2 = page.locator("#rq-tbody tr:nth-child(1) button:has-text('İncele')")
        complaint_id2 = await first_row_btn2.get_attribute("data-complaint-id")
        print(f"Opening review for complaint ID: {complaint_id2}")
        await first_row_btn2.click()
        await page.wait_for_selector("#modal-review-detail:not(.hidden)", state="visible")
        
        print("Changing sentiment to Positive and clicking 'Düzenleyip Onayla'...")
        await page.locator("#edit-sentiment").select_option("Positive")
        
        page.once("dialog", lambda dialog: dialog.accept())
        await page.locator("button:has-text('Düzenleyip Onayla')").click()
        await page.wait_for_selector("#modal-review-detail.hidden", state="hidden")
        
        # 8. Kaydın CORRECTED olarak göründüğünü doğrula
        print("Navigating to Reviewed Complaints...")
        await page.goto("http://localhost:8080/?v=phase51#/reviewed-complaints")
        await page.wait_for_selector("#rc-tbody tr", state="visible")
        
        corrected_row = page.locator(f"#rc-tbody tr:has(strong:has-text('{complaint_id2}'))")
        await corrected_row.wait_for(state="visible")
        status_text2 = await corrected_row.locator("td:nth-child(8) span").inner_text()
        print(f"Complaint {complaint_id2} status in Reviewed Table: {status_text2}")
        
        # 9. Review history ekranında eski ve yeni değerleri doğrula
        print(f"Opening history for {complaint_id2}...")
        await corrected_row.locator("button:has-text('Geçmiş')").click()
        await page.wait_for_selector("#modal-review-history:not(.hidden)", state="visible")
        history_text = await page.locator("#rh-content").inner_text()
        print(f"History Content:\n{history_text}")

        # Screenshot the reviewed table
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)
        await page.screenshot(path="reviewed_complaints_table.png", full_page=True)
        print("Saved screenshot: reviewed_complaints_table.png")

        print("--- CONSOLE ERRORS ---")
        for err in console_errors:
            print(err)
        if not console_errors:
            print("No console errors.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
