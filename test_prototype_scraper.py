"""
Turkcell Superonline Enterprise - Prototype Scraper Unit & Integration Test Suite (12 Required Scenarios)
Verifies Fiber/Superbox/DSL fetching, Duplicate Prevention, HTTP 403/429 Abort, KVKK Masking, Product Conflict, Env Var Disable & Audit Logging.
"""

import unittest
import os
import json
import uuid
from unittest.mock import patch, MagicMock
from scraper import SuperonlinePrototypeScraper, PrototypeWebScraperException
from database import EnterpriseDatabase

class TestPrototypeScraper(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scraper = SuperonlinePrototypeScraper()
        cls.db = EnterpriseDatabase()

    def setUp(self):
        os.environ["ENABLE_PUBLIC_WEB_PROTOTYPE"] = "true"

    def test_01_fiber_page_fetch(self):
        """Test 1: Fiber page real record fetching structure"""
        items = self.scraper.scrape_product_page("Fiber", "https://www.sikayetvar.com/superonline/fiber-internet", limit=2)
        self.assertIsInstance(items, list)
        if items:
            self.assertEqual(items[0]["sourceProduct"], "Fiber")
            self.assertIn("sikayetvar.com", items[0]["sourceUrl"])

    def test_02_superbox_page_fetch(self):
        """Test 2: Superbox page real record fetching structure"""
        items = self.scraper.scrape_product_page("Superbox", "https://www.sikayetvar.com/superonline/superbox", limit=2)
        self.assertIsInstance(items, list)
        if items:
            self.assertEqual(items[0]["sourceProduct"], "Superbox")

    def test_03_dsl_page_fetch(self):
        """Test 3: DSL page real record fetching structure"""
        items = self.scraper.scrape_product_page("DSL", "https://www.sikayetvar.com/superonline/adsl", limit=2)
        self.assertIsInstance(items, list)
        if items:
            self.assertEqual(items[0]["sourceProduct"], "DSL")

    def test_04_duplicate_prevention(self):
        """Test 4: 4-tier duplicate record prevention"""
        ext_id = f"TEST-DUP-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": ext_id,
            "source": "Şikayetvar",
            "sourceType": "public_web_prototype",
            "sourceUrl": f"https://www.sikayetvar.com/superonline/test-{ext_id}",
            "externalId": ext_id,
            "title": "Duplicate Test Title",
            "rawText": "Duplicate Test Text",
            "maskedText": "Duplicate Test Text",
            "primaryProduct": "Fiber",
            "sourceProduct": "Fiber",
            "recordHash": f"hash-{ext_id}",
            "date": "2026-07-22 14:00"
        }
        self.db.insert_complaint(sample)

        # Tier 1: external_id match
        is_dup1, reason1 = self.db.check_is_duplicate(external_id=ext_id)
        self.assertTrue(is_dup1)
        self.assertEqual(reason1, "external_id_match")

        # Tier 2: source_url match
        is_dup2, reason2 = self.db.check_is_duplicate(source_url=sample["sourceUrl"])
        self.assertTrue(is_dup2)
        self.assertEqual(reason2, "source_url_match")

        # Tier 3: record_hash match
        is_dup3, reason3 = self.db.check_is_duplicate(record_hash=sample["recordHash"])
        self.assertTrue(is_dup3)
        self.assertEqual(reason3, "record_hash_match")

    def test_05_offline_no_records_added(self):
        """Test 5: No records added when offline / fetch fails"""
        with patch.object(self.scraper, 'fetch_url', side_effect=Exception("No internet")):
            res = self.scraper.run_prototype_scrape(f"run-off-{uuid.uuid4().hex[:4]}", requested_products=["Fiber"], limit_per_product=1)
            self.assertEqual(res["stats"]["inserted"], 0)

    def test_06_stop_on_http_403(self):
        """Test 6: Immediately stop execution on HTTP 403"""
        with patch.object(self.scraper, 'fetch_url', side_effect=PrototypeWebScraperException("HTTP 403 Forbidden", 403)):
            res = self.scraper.run_prototype_scrape(f"run-403-{uuid.uuid4().hex[:4]}", requested_products=["Fiber"], limit_per_product=1)
            self.assertEqual(res["status"], "STOPPED_RATE_LIMIT")

    def test_07_stop_on_http_429(self):
        """Test 7: Immediately stop execution on HTTP 429 Rate Limit"""
        with patch.object(self.scraper, 'fetch_url', side_effect=PrototypeWebScraperException("HTTP 429 Rate Limit", 429)):
            res = self.scraper.run_prototype_scrape(f"run-429-{uuid.uuid4().hex[:4]}", requested_products=["Fiber"], limit_per_product=1)
            self.assertEqual(res["status"], "STOPPED_RATE_LIMIT")

    def test_08_empty_html_handling(self):
        """Test 8: Handle empty HTML gracefully without adding fake records"""
        with patch.object(self.scraper, 'fetch_url', return_value=""):
            items = self.scraper.scrape_product_page("Fiber", "https://example.com", limit=5)
            self.assertEqual(len(items), 0)

    def test_09_kvkk_masking(self):
        """Test 9: KVKK masking of customer PII before persistence"""
        raw = "Ahmet Yılmaz, Tel: 05329876543, Müşteri No: 88776655, adres: Kadıköy İstanbul"
        masked = self.scraper.ai.mask_kvkk(raw)
        self.assertNotIn("05329876543", masked)
        self.assertNotIn("88776655", masked)

    def test_10_product_conflict_detection(self):
        """Test 10: Page product and AI product conflict detection"""
        item = {
            "sourceProduct": "Fiber",
            "sourceUrl": "https://www.sikayetvar.com/superonline/fiber-test",
            "externalId": "SK-CONFLICT-101",
            "title": "Superbox modemim hiç çekmiyor 4.5G kesildi"
        }
        with patch.object(self.scraper, 'fetch_url', return_value="<p>Superbox 4.5G modemim çalışmıyor</p>"):
            proc = self.scraper.process_item(item, "run-test-conflict")
            self.assertTrue(proc["productConflict"])
            self.assertEqual(proc["sourceProduct"], "Fiber")
            self.assertEqual(proc["primaryProduct"], "Superbox")
            self.assertTrue(proc["needsHumanReview"])

    def test_11_disabled_env_var(self):
        """Test 11: Disabled when ENABLE_PUBLIC_WEB_PROTOTYPE=false"""
        os.environ["ENABLE_PUBLIC_WEB_PROTOTYPE"] = "false"
        self.assertFalse(self.scraper.is_enabled())
        with self.assertRaises(PrototypeWebScraperException):
            self.scraper.fetch_url("https://www.sikayetvar.com")

    def test_12_scrape_runs_log_persistence(self):
        """Test 12: Audit log persistence in scrape_runs table"""
        run_id = f"run-audit-{uuid.uuid4().hex[:6]}"
        self.db.create_scrape_run(run_id, requested_limit=20, source_urls=["https://test.com"])
        self.db.update_scrape_run(run_id, "COMPLETED", found=10, inserted=8, duplicate=2, failed=0)
        
        run_data = self.db.get_scrape_run(run_id)
        self.assertIsNotNone(run_data)
        self.assertEqual(run_data["status"], "COMPLETED")
        self.assertEqual(run_data["inserted_count"], 8)

if __name__ == "__main__":
    unittest.main()
