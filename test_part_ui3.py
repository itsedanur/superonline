import asyncio
from playwright.async_api import async_playwright

async def run_test():
    print("--- UI TESTS FOR PART UI-3 (Enterprise UX & Regression Fixes) ---")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        print("\nTEST 4: Cache (New context + hard reload)")
        context = await browser.new_context()
        page = await context.new_page()

        console_errors = []
        network_errors = []
        
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("response", lambda res: network_errors.append(res.url) if res.status >= 400 else None)
        
        # Test alert intercept - if window.alert is called, flag it
        alert_called = False
        def handle_dialog(dialog):
            nonlocal alert_called
            alert_called = True
            print(f"ERROR: Browser dialog triggered! Type: {dialog.type}")
            asyncio.create_task(dialog.accept())
        page.on("dialog", handle_dialog)
        
        await page.goto("http://localhost:8080/#/social-providers", wait_until="networkidle")
        await page.reload(wait_until="networkidle") # Hard reload simulation
        await page.wait_for_selector("#tab-social-providers.active", state="visible")
        
        print("\nTEST 1: Header Visibility")
        header_actions = page.locator("#global-header-actions")
        is_visible = await header_actions.is_visible()
        if not is_visible:
            print("SUCCESS: Global header actions are hidden on this tab.")
        else:
            print("ERROR: Global header actions are still visible.")
        
        print("\nTEST 2: Disabled Providers (Instagram, Facebook, TikTok)")
        for platform in ["Instagram", "Facebook", "TikTok"]:
            card = page.locator(f".social-card:has(h4:has-text('{platform}'))")
            count = await card.count()
            if count > 0:
                disabled_btn = card.locator("button:has-text('Bağlantı henüz yapılandırılmadı')")
                if await disabled_btn.count() > 0:
                    print(f"SUCCESS: {platform} has the correct disabled fallback button.")
                    # Ensure it is disabled
                    is_disabled = await disabled_btn.evaluate("el => el.disabled")
                    if is_disabled:
                        print(f"SUCCESS: {platform} fallback button is disabled.")
                    else:
                        print(f"ERROR: {platform} fallback button is NOT disabled.")
                else:
                    print(f"ERROR: {platform} does not have the fallback disabled button.")
        
        print("\nTEST 3: X preview")
        x_card = page.locator(".social-card:has(h4:has-text('X'))")
        if await x_card.count() > 0:
            preview_btn = x_card.locator("button:has-text('Ön İzleme')")
            if await preview_btn.count() > 0:
                print("Clicking X Ön İzleme...")
                await preview_btn.click()
                
                # Wait for modal to appear
                await page.wait_for_selector("#enterprise-alert-modal:not(.hidden)", state="visible", timeout=30000)
                print("SUCCESS: Enterprise Alert Modal opened successfully.")
                
                title = await page.locator("#ea-title").text_content()
                if "X İçerik Keşfi Sonucu" in title:
                    print("SUCCESS: Modal title is 'X İçerik Keşfi Sonucu'.")
                else:
                    print(f"ERROR: Modal title is '{title}'.")
                
                body_text = await page.locator("#ea-body").text_content()
                if "NO_RESULTS" in body_text or "Sonuç bulunamadı" in body_text:
                    print("SUCCESS: NO_RESULTS is rendered nicely.")
                
                import_btn = x_card.locator("#btn-import-x")
                if await import_btn.evaluate("el => el.disabled"):
                    print("SUCCESS: İçe Aktar is still disabled.")
                else:
                    print("ERROR: İçe Aktar is enabled.")
        
        if alert_called:
            print("ERROR: window.alert() or another dialog was called!")
        else:
            print("SUCCESS: No window.alert() was called.")
            
        print("\nTEST 5: Console ve Network")
        print(f"Console errors: {len(console_errors)}")
        for err in console_errors:
            if "favicon" not in err.lower():
                print("CONSOLE:", err)
        
        print(f"Network errors (>= 400): {len(network_errors)}")
        for err in network_errors:
            if "favicon" not in err.lower():
                print("NETWORK:", err)
                
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
