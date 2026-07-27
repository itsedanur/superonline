import unittest
from social_media.models import NormalizedSocialContent
from social_media.utils import mask_author_username, is_social_media_platform, determine_source_group, generate_social_hash
from social_media.dictionary import map_product
from social_media.registry import ProviderRegistry
import os

class TestSocialMediaPart2A(unittest.TestCase):

    def test_normalized_content_validation(self):
        # Test negative metrics normalization
        content = NormalizedSocialContent(
            platform="X",
            external_id="123",
            source_url="http://x.com/123",
            text="Test message",
            source_created_at="2026-07-27T12:00:00Z",
            like_count=-5,
            comment_count=-10,
            share_count=2,
            content_type="INVALID_TYPE"
        )
        
        self.assertEqual(content.like_count, 0)
        self.assertEqual(content.comment_count, 0)
        self.assertEqual(content.share_count, 2)
        self.assertEqual(content.engagement_count, 2)
        self.assertEqual(content.content_type, "UNKNOWN")

    def test_mask_author_username(self):
        self.assertEqual(mask_author_username("@edanurunal"), "@eda*******")
        self.assertEqual(mask_author_username("eda"), "e***")
        self.assertEqual(mask_author_username("@a"), "@a***")
        self.assertEqual(mask_author_username(""), "")

    def test_is_social_media_platform(self):
        self.assertTrue(is_social_media_platform("X"))
        self.assertTrue(is_social_media_platform("INSTAGRAM"))
        self.assertTrue(is_social_media_platform("FACEBOOK"))
        self.assertTrue(is_social_media_platform("TIKTOK"))
        self.assertFalse(is_social_media_platform("SIKAYETVAR"))
        self.assertFalse(is_social_media_platform("INTERNAL"))

    def test_determine_source_group(self):
        self.assertEqual(determine_source_group("X"), "SOCIAL_MEDIA")
        self.assertEqual(determine_source_group("SIKAYETVAR"), "COMPLAINT_PLATFORM")
        self.assertEqual(determine_source_group("INTERNAL"), "INTERNAL")
        self.assertEqual(determine_source_group("RANDOM"), "UNKNOWN")

    def test_map_product(self):
        self.assertEqual(map_product("Harika bir TV Plus yayını!"), "TV_PLUS")
        self.assertEqual(map_product("game+ çöktü"), "GAME_PLUS")
        self.assertEqual(map_product("bip uygulamasını seviyorum"), "BIP")
        self.assertEqual(map_product("Rastgele metin"), "UNKNOWN")

    def test_generate_social_hash(self):
        h1 = generate_social_hash("X", "hello", "123", "2026")
        h2 = generate_social_hash("X", "hello", "123", "2026")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, generate_social_hash("X", "hello2", "123", "2026"))

    def test_provider_registry(self):
        # Ensure all are disabled by default since env vars are not set
        os.environ["SOCIAL_X_ENABLED"] = "false"
        registry = ProviderRegistry()
        status = registry.get_status()
        
        self.assertEqual(len(status), 4)
        for p in status:
            self.assertFalse(p["enabled"])
            self.assertFalse(p["configured"])
            self.assertFalse(p["ready"])
            self.assertIn(p["platform"], ["X", "INSTAGRAM", "FACEBOOK", "TIKTOK"])

if __name__ == '__main__':
    unittest.main()
