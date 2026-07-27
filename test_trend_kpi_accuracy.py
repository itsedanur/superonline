import unittest
from database import EnterpriseDatabase
from nlp_engine import SuperonlineNLPEngine

class TestTrendKPIAccuracy(unittest.TestCase):
    def setUp(self):
        self.db = EnterpriseDatabase()
        self.nlp = SuperonlineNLPEngine()

    def test_calculate_period_change_both_zero(self):
        res = self.db.calculate_period_change(0, 0)
        self.assertEqual(res["change_status"], "NO_CHANGE")
        self.assertEqual(res["change_pct"], 0.0)
        self.assertEqual(res["current_count"], 0)
        self.assertEqual(res["previous_count"], 0)

    def test_calculate_period_change_new_activity(self):
        res = self.db.calculate_period_change(150, 0)
        self.assertEqual(res["change_status"], "NEW_ACTIVITY")
        self.assertIsNone(res["change_pct"])
        self.assertEqual(res["current_count"], 150)
        self.assertEqual(res["previous_count"], 0)

    def test_calculate_period_change_increase(self):
        res = self.db.calculate_period_change(10, 5)
        self.assertEqual(res["change_status"], "INCREASE")
        self.assertEqual(res["change_pct"], 100.0)

    def test_calculate_period_change_decrease(self):
        res = self.db.calculate_period_change(5, 10)
        self.assertEqual(res["change_status"], "DECREASE")
        self.assertEqual(res["change_pct"], -50.0)

    def test_executive_summary_structure(self):
        summary = self.db.get_executive_summary()
        self.assertIn("daily_metrics", summary)
        self.assertIn("weekly_metrics", summary)
        self.assertIn("monthly_metrics", summary)
        self.assertIn("most_problematic_summary", summary)

        wm = summary["weekly_metrics"]
        if wm["previous_count"] == 0 and wm["current_count"] > 0:
            self.assertEqual(wm["change_status"], "NEW_ACTIVITY")
            self.assertIsNone(wm["change_pct"])

    def test_executive_trends_coverage_metadata(self):
        trends = self.db.get_executive_trends(days=30)
        self.assertIn("series", trends)
        self.assertIn("coverage_metadata", trends)
        meta = trends["coverage_metadata"]
        self.assertEqual(meta["total_timepoints_count"], 30)
        self.assertIsInstance(meta["is_sparse"], bool)

    def test_fastest_rising_category_sample_threshold(self):
        summary = self.db.get_executive_summary()
        categories = summary.get("fastest_rising_categories", [])
        for cat in categories:
            total_sample = cat["recent_7d"] + cat["prev_7d"]
            self.assertGreaterEqual(total_sample, 5, f"Category {cat['sub_category']} sample size is less than 5!")

    def test_grounded_ai_insights_new_activity(self):
        mock_summary = {
            "total_complaints": 303,
            "most_problematic_product": "Fiber",
            "critical_ratio_pct": 4.0,
            "this_week_complaints": 303,
            "weekly_metrics": {
                "current_count": 303,
                "previous_count": 0,
                "change_pct": None,
                "change_status": "NEW_ACTIVITY"
            },
            "product_metrics": {
                "Fiber": {"total": 76, "critical_count": 10}
            },
            "fastest_rising_categories": [
                {
                    "sub_category": "LOS Işığı / Optik Sinyal Kesintisi",
                    "recent_7d": 61,
                    "prev_7d": 0,
                    "growth_pct": None,
                    "change_status": "NEW_ACTIVITY"
                }
            ]
        }

        insights = self.nlp.generate_executive_insights(mock_summary)
        self.assertTrue(len(insights) >= 3)
        
        # Verify AI copy does NOT claim "%100 artış"
        alert_body = insights[0]["body"]
        self.assertNotIn("%100 artış", alert_body)
        self.assertIn("büyüme oranı hesaplanamadı", alert_body)

        surge_body = insights[2]["body"]
        self.assertNotIn("%100 oranında sıçrama", surge_body)
        self.assertIn("önceki dönem karşılaştırma verisi yok", surge_body)

if __name__ == "__main__":
    unittest.main()
