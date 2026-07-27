from typing import List, Dict, Any
from .models import NormalizedSocialContent

class SocialMediaProvider:
    def __init__(self):
        self.platform = "UNKNOWN"
        self.is_enabled = False

    def validate_configuration(self) -> bool:
        """Validates if the required API keys/tokens are present and valid."""
        return False

    def fetch_contents(self, **kwargs) -> List[Dict[str, Any]]:
        """Fetches raw content from the platform API."""
        return []

    def normalize_content(self, raw_data: Dict[str, Any]) -> NormalizedSocialContent:
        """Converts raw platform data to NormalizedSocialContent."""
        raise NotImplementedError

    def health_check(self) -> Dict[str, Any]:
        """Checks API connectivity and quota status."""
        return {
            "status": "DISABLED",
            "message": "Provider is not enabled or not implemented."
        }

class XProvider(SocialMediaProvider):
    def __init__(self):
        super().__init__()
        self.platform = "X"

class InstagramProvider(SocialMediaProvider):
    def __init__(self):
        super().__init__()
        self.platform = "INSTAGRAM"

class FacebookProvider(SocialMediaProvider):
    def __init__(self):
        super().__init__()
        self.platform = "FACEBOOK"

class TikTokProvider(SocialMediaProvider):
    def __init__(self):
        super().__init__()
        self.platform = "TIKTOK"
