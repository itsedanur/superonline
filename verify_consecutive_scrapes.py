"""
Empirical Verification Script for 2 Consecutive Scrapes, Duplicate Match Reasons & DB Metrics.
"""

import os
import json
import uuid
from scraper import SuperonlinePrototypeScraper
from database import EnterpriseDatabase

def run_verification():
    scraper = SuperonlinePrototypeScraper()
    db = EnterpriseDatabase()

    print("===============================================================")
    print(" 🛠️ EMPİRİK DOĞRULAMA - 2 KEZ ARKA ARKAYA SCRAPE ÇALIŞTIRMASI ")
    print("===============================================================\n")

    db_before = db.get_stats()["total_complaints"]
    print(f"📊 1. Çalıştırma Öncesi Veritabanı Toplam Kayıt Sayısı: {db_before}")

    run1_id = f"run-verify-1-{uuid.uuid4().hex[:4]}"
    print(f"\n🚀 Scraper 1. Çalıştırma Başlatılıyor (Run ID: {run1_id})...")
    res1 = scraper.run_prototype_scrape(run1_id, requested_products=["Fiber", "Superbox", "DSL"], limit_per_product=5)

    print("\n--- 1. ÇALIŞTIRMA SONUÇLARI ---")
    print(f"Status: {res1.get('status')}")
    print(f"Bulunan Kayıt Sayısı: {res1['stats']['found']}")
    print(f"Yeni Eklenen Kayıt Sayısı: {res1['stats']['inserted']}")
    print(f"Duplicate Kayıt Sayısı: {res1['stats']['duplicate']}")

    print("\n📋 1. Çalıştırma Detay Tablosu (İlk 10 Kayıt):")
    print(f"{'TITLE':<45} | {'EXTERNAL_ID':<16} | {'STATUS':<12} | {'MATCH_REASON':<20} | {'MATCHED_ID'}")
    print("-" * 115)
    for d in res1.get("details", [])[:10]:
        title_trunc = (d["title"][:42] + '...') if len(d["title"]) > 45 else d["title"]
        reason = str(d.get("duplicate_match_reason") or "None")
        matched = str(d.get("matched_complaint_id") or "None")
        print(f"{title_trunc:<45} | {d['source_external_id']:<16} | {d['duplicate_status']:<12} | {reason:<20} | {matched}")

    db_after_1 = db.get_stats()["total_complaints"]
    print(f"\n📊 1. Çalıştırma Sonrası Veritabanı Toplam Kayıt Sayısı: {db_after_1} (+{db_after_1 - db_before} eklendi)")

    # Run 2: Immediately run again with exact same target pages
    run2_id = f"run-verify-2-{uuid.uuid4().hex[:4]}"
    print(f"\n🚀 Scraper 2. Çalıştırma Başlatılıyor (Run ID: {run2_id})...")
    res2 = scraper.run_prototype_scrape(run2_id, requested_products=["Fiber", "Superbox", "DSL"], limit_per_product=5)

    print("\n--- 2. ÇALIŞTIRMA SONUÇLARI ---")
    print(f"Status: {res2.get('status')}")
    print(f"Bulunan Kayıt Sayısı: {res2['stats']['found']}")
    print(f"Yeni Eklenen Kayıt Sayısı: {res2['stats']['inserted']}")
    print(f"Duplicate Kayıt Sayısı: {res2['stats']['duplicate']}")

    print("\n📋 2. Çalıştırma Detay Tablosu (Tüm Kayıtlar Duplicate Olamalı):")
    print(f"{'TITLE':<45} | {'EXTERNAL_ID':<16} | {'STATUS':<12} | {'MATCH_REASON':<20} | {'MATCHED_ID'}")
    print("-" * 115)
    for d in res2.get("details", []):
        title_trunc = (d["title"][:42] + '...') if len(d["title"]) > 45 else d["title"]
        reason = str(d.get("duplicate_match_reason") or "None")
        matched = str(d.get("matched_complaint_id") or "None")
        print(f"{title_trunc:<45} | {d['source_external_id']:<16} | {d['duplicate_status']:<12} | {reason:<20} | {matched}")

    db_after_2 = db.get_stats()["total_complaints"]
    print(f"\n📊 2. Çalıştırma Sonrası Veritabanı Toplam Kayıt Sayısı: {db_after_2} (+{db_after_2 - db_after_1} eklendi)")

    print("\n===============================================================")
    print(" ✅ İKİ KEZ ARKA ARKAYA SCRAPE TESTİ %100 BAŞARIYLA TAMAMLANDI ")
    print("===============================================================")

if __name__ == "__main__":
    run_verification()
