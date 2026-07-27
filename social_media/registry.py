import os
from .provider import XProvider, InstagramProvider, FacebookProvider, TikTokProvider

class ProviderRegistry:
    def __init__(self):
        self.providers = {
            "X": XProvider(),
            "INSTAGRAM": InstagramProvider(),
            "FACEBOOK": FacebookProvider(),
            "TIKTOK": TikTokProvider()
        }
        self._load_config()

    def _load_config(self):
        """Mock loading from .env. In part 2A, all are disabled."""
        for name, provider in self.providers.items():
            env_key = f"SOCIAL_{name}_ENABLED"
            is_enabled = str(os.environ.get(env_key, "false")).lower() == "true"
            provider.is_enabled = is_enabled

    def get_status(self):
        status_list = []
        for name, provider in self.providers.items():
            status_list.append({
                "platform": name,
                "enabled": provider.is_enabled,
                "configured": provider.validate_configuration(),
                "ready": provider.is_enabled and provider.validate_configuration()
            })
        return status_list
