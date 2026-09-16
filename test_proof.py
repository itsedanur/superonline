import asyncio
from playwright.async_api import async_playwright
import sqlite3
import requests
import json
import time

API_BASE = "http://localhost:8080"
DB_PATH = "superonline_enterprise.db"

DATES = ["2026-08-04", "2026-08-03", "2026-07-28", "2026-07-27", "2026-07-26"]
PRODUCTS = ["Fiber", "Superbox", "ADSL", "Ürün Bağımsız Genel Şikâyet"]
FILTERS = ["LAST_7_DAYS", "LAST_30_DAYS", "THIS_WEEK", "THIS_MONTH"]

def run_db_query(query, params=()):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchone()["cnt"]
    except Exception as e:
        print(f"DB Error: {e}")
        return -1

def check_db_date(date_str, product=None):
    if product and product != "ALL":
        return run_db_query(
            "SELECT COUNT(*) as cnt FROM complaints WHERE date(COALESCE(NULLIF(source_published_at, ''), created_at)) = ? AND (final_product = ? OR primary_product = ?)",
            (date_str, product, product)
        )
    else:
        return run_db_query(
            "SELECT COUNT(*) as cnt FROM complaints WHERE date(COALESCE(NULLIF(source_published_at, ''), created_at)) = ?",
            (date_str,)
        )

def check_db_custom(d1, d2, product=None):
    if product and product != "ALL":
        return run_db_query(
            "SELECT COUNT(*) as cnt FROM complaints WHERE date(COALESCE(NULLIF(source_published_at, ''), created_at)) >= ? AND date(COALESCE(NULLIF(source_published_at, ''), created_at)) <= ? AND (final_product = ? OR primary_product = ?)",
            (d1, d2, product, product)
        )
    else:
        return run_db_query(
            "SELECT COUNT(*) as cnt FROM complaints WHERE date(COALESCE(NULLIF(source_published_at, ''), created_at)) >= ? AND date(COALESCE(NULLIF(source_published_at, ''), created_at)) <= ?",
            (d1, d2)
        )

async def check_ui_product(page, date_range_val, d1=None, d2=None):
    await page.evaluate(f'{{ const el = document.querySelector("#pd-filter-date"); el.value = "{date_range_val}"; el.dispatchEvent(new Event("change")); }}')
    if date_range_val == "CUSTOM" and d1 and d2:
        await page.evaluate(f'document.querySelector("#pd-date-from").value = "{d1}"')
        await page.evaluate(f'document.querySelector("#pd-date-to").value = "{d2}"')
        await page.evaluate('(selector) => document.querySelector(selector).click()', "#pd-custom-date button")
    await asyncio.sleep(1)
    kpi = await page.inner_text("#pd-kpi-total")
    return int(kpi.replace('.', '')) if kpi != "-" else 0

def check_api_product(product, date_range_val):
    res = requests.get(f"{API_BASE}/api/v1/product-analytics?product={product}&platform=ALL&date_range={date_range_val}&sentiment=ALL&category=ALL&status=ALL")
    if res.status_code == 200:
        return res.json().get("kpis", {}).get("total", 0)
    return -1

async def run_proof():
    print("Starting Comprehensive Proof Test...")
    
    # 1. DB -> API -> UI for DATES
    print("\\n### 1. DB -> API -> UI KARŞILAŞTIRMASI (Fiber Örneği - Özel Tarih)")
    
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to Fiber
        await page.goto(f"{API_BASE}/#/product-fiber")
        await asyncio.sleep(2)
        
        for d in DATES:
            db_cnt = check_db_custom(d, d, "Fiber")
            api_cnt = check_api_product("Fiber", f"{d},{d}")
            ui_cnt = await check_ui_product(page, "CUSTOM", d, d)
            print(f"| {d} | {db_cnt} | {api_cnt} | {ui_cnt} |")
            
        print("\\n### 2. ÜRÜN BAZLI DOĞRULAMA (28 Temmuz)")
        for prod in PRODUCTS:
            # Map ADSL to DSL for frontend navigation if needed, but backend supports ADSL or DSL
            p_api = prod
            
            # Use requests for API
            api_cnt = check_api_product(p_api, "2026-07-28,2026-07-28")
            db_cnt = check_db_custom("2026-07-28", "2026-07-28", p_api)
            
            # Use Playwright for UI
            nav_prod = p_api
            if p_api == "Ürün Bağımsız Genel Şikâyet": nav_prod = "urun-bagimsiz"
            elif p_api == "ADSL": nav_prod = "adsl"
            elif p_api == "DSL": nav_prod = "adsl"
            
            await page.evaluate(f'switchTab("product-{nav_prod.lower()}")')
            await asyncio.sleep(2)
            ui_cnt = await check_ui_product(page, "CUSTOM", "2026-07-28", "2026-07-28")
            print(f"28 Temmuz {prod}: DB={db_cnt}, API={api_cnt}, UI={ui_cnt}")
            
        print("\\n### 3. BUGÜN TESTİ")
        await page.goto(f"{API_BASE}/#/executive")
        await asyncio.sleep(2)
        await page.evaluate('{ const el = document.querySelector("#exec-date-filter"); el.value = "TODAY"; el.dispatchEvent(new Event("change")); }')
        await asyncio.sleep(2)
        today_kpi = await page.inner_text("#exec-daily-cnt")
        print(f"Genel Bakış Bugün KPI: {today_kpi}")
        
        await page.goto(f"{API_BASE}/#/complaints-db")
        await asyncio.sleep(2)
        await page.evaluate('{ const el = document.querySelector("#filter-date"); el.value = "TODAY"; el.dispatchEvent(new Event("change")); }')
        await asyncio.sleep(1)
        today_rows = await page.locator("#db-tbody tr").count()
        print(f"Tüm Kayıtlar Bugün Satır: {today_rows}")
        
        print("\\n### 4-7. ZAMAN DİLİMLERİ (Fiber Üzerinden)")
        await page.goto(f"{API_BASE}/#/product-fiber")
        await asyncio.sleep(2)
        for f in FILTERS:
            api_cnt = check_api_product("Fiber", f)
            ui_cnt = await check_ui_product(page, f)
            print(f"{f}: API={api_cnt}, UI={ui_cnt}")
            
        print("\n### 8. ÖZEL TARİH")
        db_28 = check_db_custom("2026-07-28", "2026-07-28", "Fiber")
        api_28 = check_api_product("Fiber", "2026-07-28,2026-07-28")
        ui_28 = await check_ui_product(page, "CUSTOM", "2026-07-28", "2026-07-28")
        print(f"2026-07-28,2026-07-28: DB={db_28}, API={api_28}, UI={ui_28}")

        db_26_28 = check_db_custom("2026-07-26", "2026-07-28", "Ürün Bağımsız Genel Şikâyet")
        api_26_28 = check_api_product("Ürün Bağımsız Genel Şikâyet", "2026-07-26,2026-07-28")
        ui_26_28 = await check_ui_product(page, "CUSTOM", "2026-07-26", "2026-07-28")
        print(f"2026-07-26,2026-07-28: DB={db_26_28}, API={api_26_28}, UI={ui_26_28}")
        
        print("\n### GELECEK TARİH (REGRESYON TESTİ)")
        db_fut = check_db_custom("2026-08-05", "2026-08-05", "Fiber")
        api_fut = check_api_product("Fiber", "2026-08-05,2026-08-05")
        ui_fut = await check_ui_product(page, "CUSTOM", "2026-08-05", "2026-08-05")
        print(f"2026-08-05: DB={db_fut}, API={api_fut}, UI={ui_fut}")

        await browser.close()
        
    print("\n### 11. API ÖRNEKLERİ")
    print("TODAY:")
    print(requests.get(f"{API_BASE}/api/v1/product-analytics?product=Fiber&platform=ALL&date_range=TODAY&sentiment=ALL&category=ALL&status=ALL").json())
    print("LAST_7_DAYS:")
    print(requests.get(f"{API_BASE}/api/v1/product-analytics?product=Fiber&platform=ALL&date_range=LAST_7_DAYS&sentiment=ALL&category=ALL&status=ALL").json())

if __name__ == "__main__":
    asyncio.run(run_proof())
