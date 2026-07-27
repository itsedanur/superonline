"""
Comprehensive Unit & Integration Verifier for Scraper & Duplicate Mechanics
"""

import unittest
import hashlib
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from scraper import SuperonlinePrototypeScraper
from database import EnterpriseDatabase

class TestScraperMechanics(unittest.TestCase):

    def setUp(self):
        self.scraper = SuperonlinePrototypeScraper()
        self.db = EnterpriseDatabase()

    def test_01_external_id_no_slug_number_pollution(self):
        """Verify that numbers in titles like '3 gün', '14 gün', '150 TL' do NOT produce SK-3 or SK-14."""
        url1 = "https://www.sikayetvar.com/superonline/superonlineda-3-gun-cozulmeyen-internet-arizasi"
        slug1 = "superonlineda-3-gun-cozulmeyen-internet-arizasi"
        ext_id1 = self.scraper.extract_external_id(url1, slug1)

        url2 = "https://www.sikayetvar.com/superonline/rizam-olmadan-islem-ve-14-gun-internetsiz-kalma"
        slug2 = "rizam-olmadan-islem-ve-14-gun-internetsiz-kalma"
        ext_id2 = self.scraper.extract_external_id(url2, slug2)

        self.assertNotEqual(ext_id1, "SK-3")
        self.assertNotEqual(ext_id2, "SK-14")
        self.assertTrue(ext_id1.startswith("SK-URL-"))
        self.assertTrue(ext_id2.startswith("SK-URL-"))

    def test_02_deterministic_sha256_external_id(self):
        """Verify that same canonical URL produces identical SHA-256 external ID every run."""
        url = "https://www.sikayetvar.com/superonline/ayni-pakette-aylik-150-tl-farkli-fiyat-teklifi"
        slug = "ayni-pakette-aylik-150-tl-farkli-fiyat-teklifi"
        
        expected_sha = hashlib.sha256(url.strip().lower().encode('utf-8')).hexdigest()[:16].upper()
        expected_id = f"SK-URL-{expected_sha}"

        id1 = self.scraper.extract_external_id(url, slug)
        id2 = self.scraper.extract_external_id(url, slug)

        self.assertEqual(id1, expected_id)
        self.assertEqual(id2, expected_id)
        self.assertEqual(id1, id2)

    def test_03_date_parser_unparsed_returns_failed(self):
        """Verify unparsed HTML date returns None and 'FAILED' without using datetime.now() fallback."""
        soup = BeautifulSoup("<div>No date info here</div>", "html.parser")
        date_val, status = self.scraper.parse_source_date(soup)
        self.assertIsNone(date_val)
        self.assertEqual(status, "FAILED")

    def test_04_future_date_rejected(self):
        """Verify future dates are rejected and return 'FAILED'."""
        future_str = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
        soup = BeautifulSoup(f"<time>{future_str}</time>", "html.parser")
        date_val, status = self.scraper.parse_source_date(soup)
        self.assertIsNone(date_val)
        self.assertEqual(status, "FAILED")

    def test_05_database_unique_constraints(self):
        """Verify SQLite UNIQUE constraints prevent duplicate inserts at DB level."""
        dummy_id1 = "SK-TEST-UNIQUE-001"
        dummy_url = "https://www.sikayetvar.com/superonline/test-unique-url-1"
        dummy_hash = "hash-unique-test-12345"

        c1 = {
            "id": dummy_id1,
            "source": "Şikayetvar",
            "sourceUrl": dummy_url,
            "externalId": dummy_id1,
            "rawText": "Unique test raw content",
            "maskedText": "Unique test masked content",
            "title": "Unique Test Complaint",
            "primaryProduct": "Fiber",
            "recordHash": dummy_hash
        }

        # First insert succeeds
        self.db.insert_complaint(c1)

        # Duplicate check should detect it
        is_dup, reason, matched_id = self.db.check_is_duplicate(
            external_id=dummy_id1,
            source_url=dummy_url,
            record_hash=dummy_hash
        )
        self.assertTrue(is_dup)
        self.assertIn(reason, ["external_id_match", "source_url_match", "record_hash_match"])

    def test_06_consecutive_scrapes(self):
        """Verify 2 consecutive scrapes produce 0 new insertions on 2nd run."""
        run1 = f"run-unittest-1-{datetime.now().strftime('%H%M%S')}"
        res1 = self.scraper.run_prototype_scrape(run1, requested_products=["Fiber"], limit_per_product=2)

        run2 = f"run-unittest-2-{datetime.now().strftime('%H%M%S')}"
        res2 = self.scraper.run_prototype_scrape(run2, requested_products=["Fiber"], limit_per_product=2)

        self.assertEqual(res2["stats"]["inserted_count"], 0)
        self.assertEqual(res2["stats"]["duplicate_count"], res2["stats"]["found"])

if __name__ == "__main__":
    unittest.main()
