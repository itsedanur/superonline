DSS_PRODUCTS_AND_BRANDS = {
    "TV_PLUS": [
        "TV+", "TV Plus", "Turkcell TV+", "tvplus"
    ],
    "GAME_PLUS": [
        "Game+", "Game Plus", "GeForce NOW", "GAMEPLUS"
    ],
    "LIFEBOX": [
        "lifebox", "life box"
    ],
    "BIP": [
        "BiP", "bip"
    ],
    "FIZY": [
        "fizy", "Fizy"
    ],
    "SUPERONLINE": [
        "Superonline", "superonline", "SOL", "Turkcell Superonline"
    ],
    "TURKCELL": [
        "Turkcell", "turkcell"
    ]
}

def map_product(text: str) -> str:
    """Basic dictionary matching for product identification."""
    if not text:
        return "UNKNOWN"
        
    text_lower = text.lower()
    for brand, keywords in DSS_PRODUCTS_AND_BRANDS.items():
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return brand
    return "UNKNOWN"
