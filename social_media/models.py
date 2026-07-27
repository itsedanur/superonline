from dataclasses import dataclass
from typing import Optional

@dataclass
class NormalizedSocialContent:
    platform: str
    external_id: str
    source_url: str
    text: str
    source_created_at: str
    
    source_author_id: Optional[str] = None
    source_author_username: Optional[str] = None
    source_author_masked: Optional[str] = None
    
    language: str = "tr"
    content_type: str = "UNKNOWN"
    business_unit: str = "UNKNOWN"
    brand: str = "UNKNOWN"
    product: Optional[str] = None
    
    brand_replied: bool = False
    brand_reply_at: Optional[str] = None
    
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    engagement_count: int = 0
    
    parent_external_id: Optional[str] = None
    conversation_external_id: Optional[str] = None
    source_metadata_json: str = "{}"
    collected_at: Optional[str] = None

    def __post_init__(self):
        # Validate content_type
        valid_content_types = [
            "COMPLAINT", "QUESTION", "REQUEST", "PRAISE", "COMMENT",
            "CAMPAIGN_INTERACTION", "TECHNICAL_SUPPORT", "SUGGESTION",
            "SPAM", "IRRELEVANT", "UNKNOWN"
        ]
        if self.content_type not in valid_content_types:
            self.content_type = "UNKNOWN"
            
        # Normalize negative metrics to 0
        self.like_count = max(0, self.like_count)
        self.comment_count = max(0, self.comment_count)
        self.share_count = max(0, self.share_count)
        self.view_count = max(0, self.view_count)
        
        # Calculate engagement if not provided
        if self.engagement_count <= 0:
            self.engagement_count = self.like_count + self.comment_count + self.share_count
        else:
            self.engagement_count = max(0, self.engagement_count)
