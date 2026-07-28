import os
from .provider import InstagramProvider, FacebookProvider, TikTokProvider
from .x_provider import XPublicWebCollector

class ProviderRegistry:
    def __init__(self):
        self.providers = {
            "X": XPublicWebCollector(),
            "INSTAGRAM": InstagramProvider(),
            "FACEBOOK": FacebookProvider(),
            "TIKTOK": TikTokProvider()
        }
        self._load_config()

    def _load_config(self):
        """Loads enabled status from env vars."""
        for name, provider in self.providers.items():
            if name == "X":
                is_enabled = str(os.environ.get("ENABLE_X_PUBLIC_WEB_PROTOTYPE", "false")).lower() == "true"
                provider.is_enabled = is_enabled
            else:
                env_key = f"SOCIAL_{name}_ENABLED"
                is_enabled = str(os.environ.get(env_key, "false")).lower() == "true"
                provider.is_enabled = is_enabled

    def get_status(self):
        status_list = []
        for name, provider in self.providers.items():
            # Special case for X prototype
            is_configured = False
            if name == "X":
                is_configured = True # No token needed for prototype
            else:
                is_configured = provider.validate_configuration()
                
            status_list.append({
                "platform": name,
                "enabled": provider.is_enabled,
                "configured": is_configured,
                "ready": provider.is_enabled and is_configured,
                "prototype": True if name == "X" else False
            })
        return status_list

    def get_provider(self, name: str):
        return self.providers.get(name)
