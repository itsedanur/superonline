import unittest
from social_media.x_provider import XPublicWebCollector
import os

class TestPart2B(unittest.TestCase):
    def setUp(self):
        self.collector = XPublicWebCollector()

    def test_content_type_classification(self):
        self.assertEqual(self.collector._determine_content_type("Uygulama çalışmıyor rezalet"), "COMPLAINT")
        self.assertEqual(self.collector._determine_content_type("Bunu nasıl yaparım? Destek lütfen"), "QUESTION")
        self.assertEqual(self.collector._determine_content_type("Harika bir özellik teşekkürler"), "PRAISE")
        self.assertEqual(self.collector._determine_content_type("Yeni bir şey ekleyin istiyorum"), "SUGGESTION")
        self.assertEqual(self.collector._determine_content_type("Rastgele bir yorum attım"), "COMMENT")

    def test_x_provider_dry_run_flag(self):
        # We ensure it handles normalization cleanly
        raw = {
            "external_id": "12345",
            "source_url": "https://x.com/abc",
            "text": "nasıl iptal edilir",
            "source_author_username": "@testuser",
            "matched_brand": "GAME_PLUS",
            "source_created_at": "2026-07-27T12:00:00Z"
        }
        
        norm = self.collector.normalize_content(raw)
        self.assertEqual(norm.platform, "X")
        self.assertEqual(norm.content_type, "QUESTION") # 'nasıl' and 'iptal' -> Wait 'iptal' gives COMPLAINT, but 'nasıl' is checked first. So QUESTION. Let's verify.
        # Check source: 'nasıl' is first in the list, so it returns QUESTION.
        self.assertEqual(norm.brand, "GAME_PLUS")
        self.assertTrue(norm.source_metadata_json)

if __name__ == '__main__':
    unittest.main()
