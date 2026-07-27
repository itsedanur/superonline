import unittest
from nlp_engine import SuperonlineEnterpriseAIEngine

class TestProductClassifier(unittest.TestCase):
    def setUp(self):
        self.ai = SuperonlineEnterpriseAIEngine()

    def test_logic_a_high_confidence(self):
        # Clear strong signal for Superbox -> confidence should be >= 0.80
        res = self.ai.analyze("superbox 4.5g internetim sürekli kesiliyor", source_page_product="Superbox")
        self.assertEqual(res["finalProduct"], "Superbox")
        self.assertEqual(res["productDecisionSource"], "TEXT_HIGH_CONFIDENCE")
        self.assertFalse(res["productConflict"])

    def test_logic_a_conflict(self):
        # Clear signal for Fiber, but source is DSL -> conflict
        res = self.ai.analyze("ont cihazımdaki los ışığı kırmızı yanıyor", source_page_product="DSL")
        self.assertEqual(res["finalProduct"], "Fiber")
        self.assertEqual(res["productDecisionSource"], "TEXT_HIGH_CONFIDENCE")
        self.assertTrue(res["productConflict"])
        self.assertTrue(res["needsHumanReview"])

    def test_logic_b_and_c_medium_confidence(self):
        # Medium confidence (0.60-0.79)
        pass

    def test_logic_d_low_confidence_fallback(self):
        # No signal words, confidence < 0.60
        res = self.ai.analyze("internetim sürekli kesiliyor hiçbir şey yapamıyorum", source_page_product="Fiber")
        # confidence should be 0.55
        self.assertEqual(res["finalProduct"], "Fiber")
        self.assertEqual(res["productDecisionSource"], "SOURCE_FALLBACK")
        self.assertTrue(res["needsHumanReview"])

    def test_logic_e_multi_product(self):
        # Needs to have strong signals for both to be included in multi-product
        res = self.ai.analyze("evde fiber internet kullanıyorum los ışığı yanıyor ama superbox 4.5g modem de çekmiyor", source_page_product="Fiber")
        self.assertEqual(res["primaryProduct"], "Çoklu Ürün")
        self.assertEqual(res["finalProduct"], "Çoklu Ürün")
        self.assertEqual(res["productDecisionSource"], "MANUAL_REVIEW")
        self.assertTrue(res["needsHumanReview"])

if __name__ == '__main__':
    unittest.main()
