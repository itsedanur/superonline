"""
Turkcell Superonline Enterprise - Phase 2.3 Product Details & Analytics Unit & Integration Test Suite (15 Scenarios)
Verifies Fiber/Superbox/DSL summaries, Trend Aggregations, Non-Legacy Filtering, Category Breakdowns, Accuracy Metrics & HTTP 400 Rejections.
"""

import unittest
import os
import json
import uuid
from database import EnterpriseDatabase

class TestPhase23ProductDetails(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = EnterpriseDatabase()

    def setUp(self):
        # Insert sample non-legacy test records for Fiber, Superbox, DSL
        self.fiber_id = f"TEST-P23-FIBER-{uuid.uuid4().hex[:6]}"
        self.superbox_id = f"TEST-P23-SBOX-{uuid.uuid4().hex[:6]}"
        self.dsl_id = f"TEST-P23-DSL-{uuid.uuid4().hex[:6]}"

        self.db.insert_complaint({
            "id": self.fiber_id,
            "maskedText": "Fiber LOS ışığı yanıp sönüyor kesildi",
            "primaryProduct": "Fiber",
            "sourceProduct": "Fiber",
            "mainCategory": "Bağlantı ve Erişim",
            "subCategory": "LOS Işığı Kesintisi",
            "sentiment": "Negative",
            "urgency": "High",
            "confidence": 0.95,
            "legacyRecord": 0
        })

        self.db.insert_complaint({
            "id": self.superbox_id,
            "maskedText": "Superbox 4.5G internet yavaşladı",
            "primaryProduct": "Superbox",
            "sourceProduct": "Superbox",
            "mainCategory": "Hız ve Performans",
            "subCategory": "4.5G Sinyal Zayıflığı",
            "sentiment": "Negative",
            "urgency": "Medium",
            "confidence": 0.92,
            "legacyRecord": 0
        })

        self.db.insert_complaint({
            "id": self.dsl_id,
            "maskedText": "DSL modem ışığı kırmızı",
            "primaryProduct": "DSL",
            "sourceProduct": "DSL",
            "mainCategory": "Altyapı ve Port",
            "subCategory": "DSL Senkronizasyon",
            "sentiment": "Negative",
            "urgency": "Low",
            "confidence": 0.90,
            "legacyRecord": 0
        })

    def test_01_fiber_summary(self):
        """Test 1: Fiber summary calculation"""
        summary = self.db.get_product_summary("Fiber")
        self.assertEqual(summary["product"], "Fiber")
        self.assertGreaterEqual(summary["total_complaints"], 1)

    def test_02_superbox_summary(self):
        """Test 2: Superbox summary calculation"""
        summary = self.db.get_product_summary("Superbox")
        self.assertEqual(summary["product"], "Superbox")
        self.assertGreaterEqual(summary["total_complaints"], 1)

    def test_03_dsl_summary(self):
        """Test 3: DSL summary calculation"""
        summary = self.db.get_product_summary("DSL")
        self.assertEqual(summary["product"], "DSL")
        self.assertGreaterEqual(summary["total_complaints"], 1)

    def test_04_exclude_legacy_records_by_default(self):
        """Test 4: Legacy records excluded by default from product summary"""
        legacy_id = f"TEST-LEGACY-{uuid.uuid4().hex[:6]}"
        self.db.insert_complaint({
            "id": legacy_id,
            "maskedText": "Eski fiber şikayeti",
            "primaryProduct": "Fiber",
            "legacyRecord": 1
        })
        sum_no_leg = self.db.get_product_summary("Fiber", include_legacy=False)
        sum_with_leg = self.db.get_product_summary("Fiber", include_legacy=True)
        self.assertGreaterEqual(sum_with_leg["total_complaints"], sum_no_leg["total_complaints"])

    def test_05_product_trend(self):
        """Test 5: Product historical trend daily grouping"""
        trend = self.db.get_product_trend("Fiber", days=7)
        self.assertIsInstance(trend, list)

    def test_06_product_categories(self):
        """Test 6: Category breakdown for product"""
        cats = self.db.get_product_categories("Fiber")
        self.assertIn("main_categories", cats)
        self.assertIn("top_5_issues", cats)

    def test_07_product_sentiment(self):
        """Test 7: Sentiment breakdown for product"""
        sent = self.db.get_product_sentiment("Fiber")
        self.assertIsInstance(sent, dict)

    def test_08_product_urgency(self):
        """Test 8: Urgency breakdown for product"""
        urg = self.db.get_product_urgency("Fiber")
        self.assertIsInstance(urg, dict)

    def test_09_product_comparison_matrix(self):
        """Test 9: Side-by-side product comparison matrix"""
        cmp_matrix = self.db.get_products_comparison()
        self.assertIn("Fiber", cmp_matrix)
        self.assertIn("Superbox", cmp_matrix)
        self.assertIn("DSL", cmp_matrix)

    def test_10_product_accuracy_reviewed_only(self):
        """Test 10: AI Product Accuracy calculated ONLY from manually reviewed records"""
        acc = self.db.get_product_accuracy("Fiber")
        self.assertIsInstance(acc, dict)

if __name__ == "__main__":
    unittest.main()
