"""
Turkcell Superonline Enterprise - Phase 2.1 Unit & Integration Test Suite
Verifies Required Test Cases (A, B, C, D, E), KVKK Masking, Confidence Rules, and Schema Integrity.
"""

import unittest
import os
import json
from nlp_engine import SuperonlineEnterpriseAIEngine
from database import EnterpriseDatabase

class TestPhase21ClassificationEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = SuperonlineEnterpriseAIEngine()
        cls.db = EnterpriseDatabase()

    def test_case_a_fiber_los(self):
        """Case A: Fiber + LOS Light + High Urgency + Negative Sentiment (Never Neutral)"""
        text = "İnternetim sürekli kopuyor, modemde LOS ışığı yanıyor."
        res = self.engine.analyze(text)
        
        self.assertEqual(res["primaryProduct"], "Fiber", f"Expected Fiber, got {res['primaryProduct']}")
        self.assertIn("Fiber", res["products"])
        self.assertEqual(res["mainCategory"], "Bağlantı ve Erişim")
        self.assertEqual(res["subCategory"], "LOS Işığı / Optik Sinyal Kesintisi")
        self.assertEqual(res["sentiment"], "Negative", "Sentiment must NEVER be Neutral for LOS issues!")
        self.assertEqual(res["emotion"], "Hayal Kırıklığı")
        self.assertEqual(res["urgency"], "High")
        self.assertGreaterEqual(res["confidence"], 0.95)
        self.assertFalse(res["needsHumanReview"])

    def test_case_b_superbox_signal(self):
        """Case B: Superbox + 4.5G Signal Problem"""
        text = "Taşınabilir modem evin içinde çekmiyor, 4.5G sinyali çok düşük."
        res = self.engine.analyze(text)
        
        self.assertEqual(res["primaryProduct"], "Superbox")
        self.assertIn("Superbox", res["products"])
        self.assertEqual(res["sentiment"], "Negative")
        self.assertIn("4.5G", res["subCategory"])

    def test_case_c_dsl_ankastre(self):
        """Case C: DSL + Ankastre / Senkronizasyon"""
        text = "DSL ışığım yanmıyor, ankastreden modeme sinyal gelmiyor."
        res = self.engine.analyze(text)
        
        self.assertEqual(res["primaryProduct"], "DSL")
        self.assertEqual(res["mainCategory"], "Bağlantı ve Erişim")
        self.assertEqual(res["subCategory"], "DSL Senkronizasyon Sorunu")

    def test_case_d_multi_product(self):
        """Case D: Multi-Product Detection (Fiber + Superbox)"""
        text = "Fiber aboneliğimi kapatıp Superbox aldım fakat ikisinde de bağlantı problemi yaşıyorum."
        res = self.engine.analyze(text)
        
        self.assertTrue(res["isMultiProduct"])
        self.assertIn("Fiber", res["products"])
        self.assertIn("Superbox", res["products"])

    def test_case_e_billing_product_independent(self):
        """Case E: Product Independent Billing Complaint (Must NOT be Belirlenemedi)"""
        text = "Faturam çok yüksek geldi."
        res = self.engine.analyze(text)
        
        self.assertEqual(res["primaryProduct"], "Ürün Bağımsız Genel Şikâyet")
        self.assertNotEqual(res["primaryProduct"], "Belirlenemedi")
        self.assertEqual(res["mainCategory"], "Fatura ve Ücretlendirme")

    def test_kvkk_masking(self):
        """KVKK Masking of Phone, Customer ID, Email"""
        raw = "05321234567 nolu hattımla 12345678 müşteri nom ile test@superonline.com adresinden ulaşıyorum"
        masked = self.engine.mask_kvkk(raw)
        
        self.assertNotIn("05321234567", masked)
        self.assertNotIn("12345678", masked)
        self.assertNotIn("test@superonline.com", masked)
        self.assertIn("[TELEFON GİZLENDİ]", masked)

    def test_database_persistence_schema(self):
        """Database insertion and retrieving Phase 2.1 schema fields"""
        sample = self.engine.analyze("Fiber hızım 1000 Mbps olmasına rağmen yavaş")
        sample["id"] = "TEST-UNIT-001"
        self.db.insert_complaint(sample)
        
        records = self.db.get_all_complaints(product_filter="Fiber")
        found = next((r for r in records if r["id"] == "TEST-UNIT-001"), None)
        self.assertIsNotNone(found)
        self.assertEqual(found["primary_product"], "Fiber")
        self.assertEqual(found["main_category"], "Hız ve Performans")

if __name__ == "__main__":
    unittest.main()
