import asyncio
from playwright.async_api import async_playwright

async def run_test():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()

        print("1. Anasayfaya gidelim ve İnceleme Kuyruğuna tıklayalım...")
        await page.goto("http://localhost:8080/")
        await asyncio.sleep(2)
        
        # Manuel İnceleme sekmesine geç
        await page.click("text=Manuel İnceleme")
        await asyncio.sleep(1)

        print("2. Bekleyen bir kayıt bulup AI Sonucunu Onayla diyelim...")
        # Get the first review button
        review_btn = await page.query_selector("button[data-action='review-complaint']")
        if review_btn:
            cid = await review_btn.get_attribute("data-complaint-id")
            print(f"Secilen ID: {cid}")
            await review_btn.click()
            await asyncio.sleep(1)
            
            # Click AI Approve
            await page.click("text=AI Sonucunu Onayla")
            await asyncio.sleep(1)
            
            # Click Enter on the enterprise modal
            ok_btn = await page.wait_for_selector("#ea-ok-btn")
            await ok_btn.click()
            print("AI Onaylandi ve toast kapatildi.")
            await asyncio.sleep(1)
            
            # Check if it disappeared from queue
            row = await page.query_selector(f"#rq-tbody button[data-complaint-id='{cid}']")
            assert row is None, f"{cid} kuyruktan kaybolmadi!"
            print(f"{cid} kuyruktan kayboldu.")
            
            print("3. İncelenenler ekranina gidelim ve kaydi bulalim...")
            await page.click("text=İncelenen Şikâyetler")
            await asyncio.sleep(1)
            
            # Look for the reviewed item
            reviewed_row = await page.query_selector(f"tr:has-text('{cid}')")
            assert reviewed_row is not None, f"{cid} incelenenlerde yok!"
            print(f"{cid} incelenenlerde var.")
            
            print("4. Detay modalini acip bilgileri kontrol edelim...")
            detail_btn = await reviewed_row.query_selector("button[title='Detay']")
            await detail_btn.click()
            await asyncio.sleep(1)
            
            # Check history
            history_text = await page.inner_text("#rd-history-content")
            assert "AI_APPROVED" in history_text, "History'de AI_APPROVED yok!"
            print("History'de AI_APPROVED bulundu.")
            
            await page.click("text=Kapat")
            
        print("TUM TESTLER BASARILI!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
