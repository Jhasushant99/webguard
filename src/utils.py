

import re
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse



def load_config(path: str = "config.json") -> dict:
    """Load config.json from project root."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)



def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_iso() -> str:
    return datetime.now().isoformat()



def get_domain(url: str) -> str:
    return urlparse(url).netloc


def normalize_url(href: str, base: str) -> str:
    
    full = urljoin(base, href)
    p    = urlparse(full)
    return p.scheme + "://" + p.netloc + p.path.rstrip("/")


def is_internal(url: str, base_domain: str) -> bool:
    """Return True if URL belongs to the same domain."""
    parsed = urlparse(url)
    return parsed.netloc == base_domain or parsed.netloc == ""


def is_blacklisted(url: str, cfg: dict) -> bool:
    """
    Return True if URL should be skipped.
    Checks file extensions (PDF, ZIP, images…) and URL patterns.
    """
    url_lower = url.lower()

    # Check blocked extensions
    for ext in cfg.get("BLACKLIST_EXTENSIONS", []):
        if url_lower.endswith(ext):
            return True

    # Check blocked patterns (logout, login, download, etc.)
    for pattern in cfg.get("BLACKLIST_PATTERNS", []):
        if pattern.lower() in url_lower:
            return True

    return False


def safe_name(url: str, max_len: int = 60) -> str:
    """Convert URL path into a filesystem-safe string."""
    path = urlparse(url).path.strip("/")
    name = re.sub(r"[^a-zA-Z0-9]", "_", path)
    return name[:max_len] or "home"


# ── Directory Setup ────────────────────────────────────────
def ensure_dirs(*paths):
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
