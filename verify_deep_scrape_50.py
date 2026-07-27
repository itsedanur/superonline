"""
Deep Scrape 50 & DOM Order Verification Script
"""

import urllib.request
import ssl
import re
import uuid
from bs4 import BeautifulSoup
from scraper import SuperonlinePrototypeScraper, HEADERS, ssl_context
from database import EnterpriseDatabase

def verify_deep_scrape():
    scraper = SuperonlinePrototypeScraper()
    db = EnterpriseDatabase()

    print("==========================================================================")
    print(" 🛠️ SON DOĞRULAMA - DOM SIRASI & 50 LİMİTLİ DERİN SCRAPE TESTİ ")
    print("==========================================================================\n")

    products = ["Fiber", "Superbox", "DSL"]
    
    for prod in products:
        url = scraper.source_pages[prod]
        print(f"📌 {prod.upper()} ÜRÜN SAYFASI ANALİZİ ({url}):")
        
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ssl_context, timeout=8) as res:
            html = res.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        links = soup.find_all('a', href=True)
        
        complaint_cards = []
        seen = set()
        dom_index = 0

        for a in links:
            href = a['href']
            if href.startswith('/superonline/') and href.count('-') >= 2:
                if href not in seen and not any(x in href for x in ['/fiber', '/adsl', '/superbox', '/hiz', '/modem']):
                    title = a.get_text(strip=True)
                    if len(title) > 12 and not title.isdigit():
                        seen.add(href)
                        dom_index += 1
                        complaint_cards.append({
                            "order": dom_index,
                            "title": title,
                            "url": f"https://www.sikayetvar.com{href}"
                        })

        total_cards_on_page = len(complaint_cards)
        parsed_limit_15 = complaint_cards[:15]

        print(f"  • Sayfada Toplam Bulunan Şikâyet Kartı Sayısı: {total_cards_on_page}")
        print(f"  • Scraper Limiti: 15 (İstenen üst sınır)")
        print(f"  • Parse Edilen Kart Sayısı: {len(parsed_limit_15)}")
        if total_cards_on_page > 15:
            print(f"  • Açıklama: Sayfada {total_cards_on_page} şikayet var; ancak scraper 'limit=15' parametresi ile en üstteki (en yeni) 15 kaydı alacak şekilde sınırlandırılmıştır.")
        
        print(f"\n  📋 {prod} Sayfasındaki İlk 15 Kaydın DOM Sıra Numarası ve URL'leri:")
        print(f"  {'SIRA':<5} | {'BAŞLIK':<45} | {'URL'}")
        print("  " + "-" * 105)
        for item in parsed_limit_15:
            t_trunc = (item['title'][:42] + '...') if len(item['title']) > 45 else item['title']
            print(f"  #{item['order']:<4} | {t_trunc:<45} | {item['url']}")
        print("\n" + "="*80 + "\n")

    # Run Deep Scrape test with limit_per_product = 50
    db_before = db.get_stats()["total_complaints"]
    run_50_id = f"run-limit50-{uuid.uuid4().hex[:6]}"
    
    print(f"🚀 Limiti 50 Yaparak Derin Canlı Scrape Testi Başlatılıyor (Run ID: {run_50_id})...")
    res50 = scraper.run_prototype_scrape(run_50_id, requested_products=["Fiber", "Superbox", "DSL"], limit_per_product=50)

    print("\n--- 50 LİMİTLİ SCRAPE ÇALIŞTIRMA SONUÇLARI ---")
    print(f"• Status: {res50.get('status')}")
    print(f"• Bulunan Toplam Kayıt Sayısı: {res50['stats']['found']}")
    print(f"• Yeni Eklenen Kayıt Sayısı: {res50['stats']['inserted']}")
    print(f"• Duplicate (Mevcut) Kayıt Sayısı: {res50['stats']['duplicate']}")
    print(f"• Veritabanı Öncesi / Sonrası: {db_before} ➔ {db.get_stats()['total_complaints']}")
    print("==========================================================================")

if __name__ == "__main__":
    verify_deep_scrape()
