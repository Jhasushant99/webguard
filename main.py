#!/usr/bin/env python3
"""
WebGuard — VEDAS Stack Crawler + YUVA Monitor
===============================================
Usage:
    python main.py                          # Normal crawl
    python main.py --mode yuva              # YUVA: single layer screenshots
    python main.py --mode yuva --random 3 --iterations 5  # YUVA: random
    python main.py --mode yuva --combined   # YUVA: combined screenshots
    python main.py --mode yuva --freshness  # YUVA: date check only
    python main.py --mode yuva --all        # YUVA: EVERYTHING
"""

import argparse
import json

from src.utils import load_config, ensure_dirs
from src.browser import get_driver
from src.crawler import crawl
from src import image_monitor, dom_monitor, report_generator
from src.yuva_monitor import YuvaMonitor


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


parser = argparse.ArgumentParser(description="WebGuard — Crawler + YUVA Monitor")
parser.add_argument("--mode", choices=["screenshot", "dom", "both", "yuva"], default="both")
parser.add_argument("--max", type=int, default=MAX_PAGES)

# YUVA-specific flags
parser.add_argument("--all",       action="store_true", help="[YUVA] Run everything")
parser.add_argument("--random",    type=int, default=0, help="[YUVA] Random layer count per iteration")
parser.add_argument("--combined",  action="store_true", help="[YUVA] Combined category screenshots")
parser.add_argument("--freshness", action="store_true", help="[YUVA] Data freshness check only")
parser.add_argument("--iterations",type=int, default=5, help="[YUVA] Random iterations (default 5)")
parser.add_argument("--threshold", type=int, default=10, help="[YUVA] Stale threshold in days (default 10)")
parser.add_argument("--wait",      type=int, default=20, help="[YUVA] Page load wait in seconds")
parser.add_argument("--no-report", action="store_true")

args = parser.parse_args()


# ═══════════════════════════════════════════════════════════
#  YUVA MODE
# ═══════════════════════════════════════════════════════════

def run_yuva_mode():
    print("=" * 60)
    print("  🌐 WebGuard — YUVA Visualization Monitor")
    print(f"  URL       : {cfg.get('TARGET_URL', 'N/A')}")
    print(f"  Headless  : {cfg.get('HEADLESS', True)}")
    print(f"  Threshold : {args.threshold} days")
    print("=" * 60)

    driver = get_driver()
    yuva = YuvaMonitor(driver, output_base="snapshots")

    try:
        yuva.navigate(wait_time=args.wait)

        # 1. Freshness-only mode
        if args.freshness:
            yuva.discover_layers()
            yuva.check_freshness(threshold=args.threshold)
            return

        # 2. Full "run everything" mode
        if args.all:
            yuva.run_all()
            return

        # 3. Random mode
        if args.random:
            yuva.discover_layers()
            yuva.screenshot_random_layers(count=args.random, iterations=args.iterations)
            return

        # 4. Combined category mode
        if args.combined:
            yuva.discover_layers()
            yuva.screenshot_combined_by_category()
            return

        # 5. Default YUVA mode: single layer screenshots
        yuva.screenshot_single_layers()

    finally:
        driver.quit()
        print("\n🏁 Browser closed.\n")


# ═══════════════════════════════════════════════════════════
#  ORIGINAL CRAWL MODE (unchanged)
# ═══════════════════════════════════════════════════════════

def on_page(driver, url: str, page_num: int):
    if args.mode in ("screenshot", "both"):
        image_monitor.process(driver, url, page_num)
    if args.mode in ("dom", "both"):
        dom_monitor.process(driver, url, page_num, selector=SELECTOR)


def run_crawl_mode():
    print("=" * 55)
    print("  VEDAS WebGuard")
    print(f"  URL      : {START_URL}")
    print(f"  Selector : {SELECTOR}")
    print(f"  Mode     : {args.mode}")
    print(f"  Max Pages: {args.max}")
    print(f"  Headless : {cfg.get('HEADLESS', True)}")
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


# ═══════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    if args.mode == "yuva":
        run_yuva_mode()
    else:
        run_crawl_mode()