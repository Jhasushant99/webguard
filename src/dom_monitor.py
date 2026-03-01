

import json
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.utils import timestamp, now_iso, safe_name

DOM_DIR  = Path("snapshots/dom")
JSON_DIR = Path("snapshots/json")
DIFF_DIR = Path("snapshots/diffs")


def process(driver, url: str, page_num: int, selector: str = "body") -> dict:
    
    content   = _extract(driver, selector)
    fname     = safe_name(url)
    last_file = DOM_DIR / f"{fname}_last.json"

    # Load previous snapshot for this specific URL
    last = None
    if last_file.exists():
        try:
            last = json.loads(last_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # ── Compare ──────────────────────────────────────────
    if last is not None and content == last.get("content", ""):
        print(f"        ✅ No change")
        return {"source_url": url, "status": "no_change"}

    status = "first_scan" if last is None else "changed"
    label  = "🆕 First scan" if last is None else "⚠️  Changed!"
    print(f"        {label} → saving snapshot")

    # ── Save diff if content changed ──────────────────────
    if status == "changed":
        _save_diff(url, page_num, fname, last.get("content", ""), content)

    # ── Save new snapshot ─────────────────────────────────
    ts    = timestamp()
    jpath = JSON_DIR / f"dom_{page_num:03d}_{fname}_{ts}.json"

    snapshot = {
        "page"         : page_num,
        "source_url"   : url,                    # ← source page URL
        "snapshot_path": str(jpath.resolve()),   # ← absolute path on disk
        "snapshot_file": jpath.name,             # ← just the filename
        "time"         : now_iso(),
        "selector"     : selector,
        "status"       : status,
        "title"        : _get_title(driver),
        "content"      : content,
    }

    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)

    # Update last-seen for this URL (used for next comparison)
    last_file.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    return snapshot


# ── Helpers ───────────────────────────────────────────────

def _extract(driver, selector: str) -> str:
    """Extract text from selector, fallback to full body."""
    try:
        el = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, selector))
        )
        return el.text.strip()
    except Exception:
        try:
            return driver.find_element(By.TAG_NAME, "body").text.strip()
        except Exception:
            return ""


def _get_title(driver) -> str:
    try:
        return driver.title
    except Exception:
        return ""


def _save_diff(url: str, page_num: int, fname: str, old: str, new: str):
    """Save a plain-text diff when content changes."""
    ts    = timestamp()
    dpath = DIFF_DIR / f"diff_{page_num:03d}_{fname}_{ts}.txt"

    old_lines = set(old.splitlines())
    new_lines = set(new.splitlines())

    removed = sorted(old_lines - new_lines)
    added   = sorted(new_lines - old_lines)

    with open(dpath, "w", encoding="utf-8") as f:
        f.write(f"Source URL : {url}\n")
        f.write(f"Diff File  : {dpath.resolve()}\n")
        f.write(f"Time       : {now_iso()}\n\n")
        f.write("── REMOVED ──────────────────────────────\n")
        f.write("\n".join(f"- {l}" for l in removed) if removed else "(none)")
        f.write("\n\n── ADDED ────────────────────────────────\n")
        f.write("\n".join(f"+ {l}" for l in added) if added else "(none)")

    print(f"         Diff → {dpath.name}")
