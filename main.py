

import argparse

from src.utils import load_config, ensure_dirs
from src.browser import get_driver
from src.crawler import crawl
from src import image_monitor, dom_monitor, report_generator

# ── Load config.json ──────────────────────────────────────
cfg       = load_config("config.json")
START_URL = cfg["TARGET_URL"]
SELECTOR  = cfg["TARGET_SELECTOR"]
MAX_PAGES = cfg["MAX_PAGES"]

# ── Ensure all snapshot folders exist ─────────────────────
ensure_dirs(
    "snapshots/screenshots",
    "snapshots/json",
    "snapshots/dom",
    "snapshots/diffs",
    "snapshots/reports",
)


parser = argparse.ArgumentParser(description="VEDAS WebGuard — Stack Crawler")
parser.add_argument("--mode",      choices=["screenshot", "dom", "both"], default="both")
parser.add_argument("--max",       type=int, default=MAX_PAGES)
parser.add_argument("--no-report", action="store_true")
args = parser.parse_args()


def on_page(driver, url: str, page_num: int):
    if args.mode in ("screenshot", "both"):
        image_monitor.process(driver, url, page_num)
    if args.mode in ("dom", "both"):
        dom_monitor.process(driver, url, page_num, selector=SELECTOR)


print("=" * 55)
print("  VEDAS WebGuard")
print(f"  URL      : {START_URL}")
print(f"  Selector : {SELECTOR}")
print(f"  Mode     : {args.mode}")
print(f"  Max Pages: {args.max}")
print(f"  Headless : {cfg.get('HEADLESS', True)}")
print(f"  Config   : config.json")
print(f"  Strategy : STACK (depth-first, LIFO)")
print("=" * 55)

driver = get_driver()

try:
    visited = crawl(
        start_url        = START_URL,
        driver           = driver,
        max_pages        = args.max,
        on_page_callback = on_page,
    )
finally:
    driver.quit()


if not args.no_report:
    report_generator.generate(
        visited_urls = visited,
        mode         = args.mode,
        start_url    = START_URL,
    )

print("\n All done!\n")
