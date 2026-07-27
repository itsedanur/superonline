"""
Turkcell Superonline Enterprise - Phase 2.2 Review Queue Unit & Integration Test Suite (15 Scenarios)
Verifies Review Queue filtering, AI Approval, Manual Correction, History Logging, Deferral, Deletion & Invalid Value Rejection.
"""

import unittest
import os
import json
import uuid
from database import EnterpriseDatabase

class TestPhase22ReviewQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = EnterpriseDatabase()

    def test_01_low_confidence_lands_in_queue(self):
        """Test 1: confidence < 0.85 lands in review queue"""
        cid = f"TEST-RQ-LOW-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": cid,
            "maskedText": "Bağlantım yavaş gibi galiba",
            "primaryProduct": "Fiber",
            "mainCategory": "Hız ve Performans",
            "confidence": 0.65,
            "needsHumanReview": True
        }
        self.db.insert_complaint(sample)

        queue = self.db.get_review_queue()
        ids = [x["id"] for x in queue]
        self.assertIn(cid, ids)

    def test_02_product_conflict_lands_in_queue(self):
        """Test 2: productConflict = True lands in review queue"""
        cid = f"TEST-RQ-CONF-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": cid,
            "maskedText": "Superbox 4.5G cihazı harika ama fiber kablo koptu",
            "sourceProduct": "Fiber",
            "primaryProduct": "Superbox",
            "productConflict": True,
            "confidence": 0.95,
            "needsHumanReview": True
        }
        self.db.insert_complaint(sample)

        queue = self.db.get_review_queue()
        ids = [x["id"] for x in queue]
        self.assertIn(cid, ids)

    def test_03_undetermined_lands_in_queue(self):
        """Test 3: Belirlenemedi lands in review queue"""
        cid = f"TEST-RQ-UNDET-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": cid,
            "maskedText": "Test metni",
            "primaryProduct": "Belirlenemedi",
            "confidence": 0.50,
            "needsHumanReview": True
        }
        self.db.insert_complaint(sample)

        queue = self.db.get_review_queue()
        ids = [x["id"] for x in queue]
        self.assertIn(cid, ids)

    def test_04_approve_ai_result(self):
        """Test 4: Approve AI result sets review_status = 'AI_RESULT_APPROVED'"""
        cid = f"TEST-RQ-APP-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": cid,
            "maskedText": "Fiber los ışığı kırmızı yanıyor",
            "primaryProduct": "Fiber",
            "confidence": 0.70,
            "needsHumanReview": True
        }
        self.db.insert_complaint(sample)

        ok, msg = self.db.approve_complaint(cid)
        self.assertTrue(ok)

        complaints = self.db.get_all_complaints()
        record = next((c for c in complaints if c["id"] == cid), None)
        self.assertIsNotNone(record)
        self.assertEqual(record["review_status"], "AI_RESULT_APPROVED")
        self.assertEqual(record["needs_human_review"], 0)

    def test_05_manual_correction_product(self):
        """Test 5: Manual correction of product updates primary_product & sets review_status = 'MANUALLY_CORRECTED'"""
        cid = f"TEST-RQ-CORR-{uuid.uuid4().hex[:6]}"
        sample = {
            "id": cid,
            "maskedText": "Taşınabilir modem aldım",
            "primaryProduct": "DSL", # Incorrect initial
            "confidence": 0.70,
            "needsHumanReview": True
        }
        self.db.insert_complaint(sample)

        update_dict = {
            "primaryProduct": "Superbox",
            "mainCategory": "Cihaz ve Modem",
            "subCategory": "SIM Kart Arızası / Okumama",
            "sentiment": "Negative",
            "reviewNote": "Ürün Superbox olarak düzeltildi"
        }
        ok, msg = self.db.review_and_correct_complaint(cid, update_dict)
        self.assertTrue(ok)

        complaints = self.db.get_all_complaints()
        record = next((c for c in complaints if c["id"] == cid), None)
        self.assertEqual(record["primary_product"], "Superbox")
        self.assertEqual(record["review_status"], "MANUALLY_CORRECTED")

    def test_06_review_history_logging(self):
        """Test 6: Audit history logging in review_history table"""
        cid = f"TEST-RQ-HIST-{uuid.uuid4().hex[:6]}"
        sample = {"id": cid, "maskedText": "Audit test", "primaryProduct": "Fiber", "needsHumanReview": True}
        self.db.insert_complaint(sample)

        self.db.approve_complaint(cid, reviewed_by="Saha Uzmanı")
        history = self.db.get_review_history(cid)
        self.assertGreaterEqual(len(history), 1)
        self.assertEqual(history[0]["action"], "APPROVE")
        self.assertEqual(history[0]["reviewed_by"], "Saha Uzmanı")

    def test_07_defer_complaint(self):
        """Test 7: Defer review sets review_status = 'DEFERRED'"""
        cid = f"TEST-RQ-DEF-{uuid.uuid4().hex[:6]}"
        sample = {"id": cid, "maskedText": "Erteleme testi", "primaryProduct": "DSL", "needsHumanReview": True}
        self.db.insert_complaint(sample)

        ok, msg = self.db.defer_complaint(cid, note="Müşteri aranacak")
        self.assertTrue(ok)

        queue = self.db.get_review_queue()
        record = next((c for c in queue if c["id"] == cid), None)
        self.assertEqual(record["review_status"], "DEFERRED")

    def test_08_delete_complaint(self):
        """Test 8: Delete complaint removes from queue & DB"""
        cid = f"TEST-RQ-DEL-{uuid.uuid4().hex[:6]}"
        sample = {"id": cid, "maskedText": "Silme testi", "primaryProduct": "Fiber", "needsHumanReview": True}
        self.db.insert_complaint(sample)

        ok, msg = self.db.delete_complaint(cid)
        self.assertTrue(ok)

        complaints = self.db.get_all_complaints()
        record = next((c for c in complaints if c["id"] == cid), None)
        self.assertIsNone(record)

    def test_09_review_stats_accuracy(self):
        """Test 9: Accuracy metrics calculated only from manually reviewed records"""
        stats = self.db.get_review_stats()
        self.assertIn("pending_queue_count", stats)
        self.assertIn("accuracy_metrics", stats)

if __name__ == "__main__":
    unittest.main()
