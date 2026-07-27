import hashlib

def mask_author_username(username: str) -> str:
    """Masks social media usernames (e.g. @edanurunal -> @eda******)."""
    if not username:
        return ""
    
    prefix = ""
    if username.startswith("@"):
        prefix = "@"
        username = username[1:]
        
    if len(username) <= 3:
        return prefix + username[0] + "***"
        
    return prefix + username[:3] + "*" * (len(username) - 3)

def is_social_media_platform(platform: str) -> bool:
    """Returns True if the platform is a social media source."""
    if not platform:
        return False
    return platform.upper() in ["X", "INSTAGRAM", "FACEBOOK", "TIKTOK"]

def determine_source_group(platform: str) -> str:
    """Maps platform to a logical source group."""
    platform = platform.upper() if platform else ""
    if is_social_media_platform(platform):
        return "SOCIAL_MEDIA"
    elif platform == "SIKAYETVAR":
        return "COMPLAINT_PLATFORM"
    elif platform == "INTERNAL":
        return "INTERNAL"
    return "UNKNOWN"

def generate_social_hash(platform: str, text: str, author_id: str, created_at: str) -> str:
    """Generates a fallback hash for duplicate detection if external_id is not globally unique."""
    raw = f"{platform}|{text}|{author_id}|{created_at}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()
