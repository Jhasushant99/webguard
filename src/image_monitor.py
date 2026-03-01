

import json
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.utils import timestamp, now_iso, safe_name

SCREENSHOT_DIR = Path("snapshots/screenshots")
JSON_DIR       = Path("snapshots/json")


def process(driver, url: str, page_num: int) -> dict:
    
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
    except Exception:
        pass

    
    _scroll_to_bottom(driver)

    
    try:
        total_width  = driver.execute_script("return document.body.scrollWidth")
        total_height = driver.execute_script(
            "return Math.max("
            "  document.body.scrollHeight,"
            "  document.documentElement.scrollHeight,"
            "  document.body.offsetHeight,"
            "  document.documentElement.offsetHeight"
            ")"
        )
        # Clamp: minimum 1080px, maximum 20000px to avoid memory issues
        total_width  = max(1920, min(total_width,  5000))
        total_height = max(1080, min(total_height, 20000))

        driver.set_window_size(total_width, total_height)
        time.sleep(0.5)   # let layout reflow after resize
    except Exception:
        driver.set_window_size(1920, 1080)

    # ── Step 4: Scroll back to top before screenshot ───────
    try:
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(0.3)
    except Exception:
        pass

    # ── Step 5: Save screenshot ────────────────────────────
    ts    = timestamp()
    fname = safe_name(url)
    img   = SCREENSHOT_DIR / f"{page_num:03d}_{fname}_{ts}.png"
    jpath = JSON_DIR        / f"img_{page_num:03d}_{fname}_{ts}.json"

    driver.save_screenshot(str(img))

    # ── Step 6: Reset window to standard size ──────────────
    try:
        driver.set_window_size(1920, 1080)
    except Exception:
        pass

    # ── Step 7: Save JSON with source + absolute path ──────
    meta = {
        "page"         : page_num,
        "source_url"   : url,                        # ← source URL of the page
        "screenshot_path": str(img.resolve()),        # ← absolute path on disk
        "screenshot_file": img.name,                  # ← just the filename
        "time"         : now_iso(),
        "title"        : _get_title(driver),
        "page_width"   : total_width  if "total_width"  in dir() else 1920,
        "page_height"  : total_height if "total_height" in dir() else 1080,
    }
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

    print(f"        📸 Screenshot → {img.name}  ({meta['page_width']}×{meta['page_height']}px)")
    return meta


# ── Helpers ───────────────────────────────────────────────

def _scroll_to_bottom(driver):
    """Scroll page to bottom in steps to trigger lazy loading."""
    try:
        total = driver.execute_script("return document.body.scrollHeight")
        step  = 800
        pos   = 0
        while pos < total:
            driver.execute_script(f"window.scrollTo(0, {pos});")
            time.sleep(0.1)
            pos += step
        time.sleep(0.5)   # final pause for any remaining lazy assets
    except Exception:
        pass


def _get_title(driver) -> str:
    try:
        return driver.title
    except Exception:
        return ""
