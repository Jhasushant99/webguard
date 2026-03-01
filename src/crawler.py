

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from src.utils import normalize_url, is_internal, is_blacklisted, get_domain, load_config


def collect_links(driver, current_url: str, base_domain: str, cfg: dict) -> set:
    
    links = set()
    try:
        anchors = driver.find_elements(By.TAG_NAME, "a")
        for a in anchors:
            href = a.get_attribute("href") or ""

            
            if not href or not href.startswith("http"):
                continue

            norm = normalize_url(href, current_url)

            # Must be internal
            if not is_internal(norm, base_domain):
                continue

            # Skip blacklisted (PDF, images, downloads, login, etc.)
            if is_blacklisted(norm, cfg):
                continue

            links.add(norm)

    except Exception:
        pass
    return links


def crawl(start_url: str, driver, max_pages: int, on_page_callback) -> list:
   
    cfg         = load_config()
    wait_time   = cfg.get("PAGE_LOAD_WAIT", 15)
    base_domain = get_domain(start_url)

    visited  = set()
    stack    = [start_url]    # ← STACK (list used as stack)
    order    = []
    page_num = 0

    print(f"\n🕷  Crawler started")
    print(f"   Domain   : {base_domain}")
    print(f"   Max pages: {max_pages}")
    print(f"   Strategy : STACK — Depth-First (LIFO)")
    print(f"   Blacklist: {len(cfg.get('BLACKLIST_EXTENSIONS',[]))} extensions, "
          f"{len(cfg.get('BLACKLIST_PATTERNS',[]))} patterns\n")

    while stack and page_num < max_pages:
        url = stack.pop()             # ← POP from top (LIFO = STACK)

        if url in visited:
            continue

        # Skip blacklisted URLs that somehow got on the stack
        if is_blacklisted(url, cfg):
            print(f"  [SKIP] Blacklisted → {url}")
            continue

        visited.add(url)
        page_num += 1
        order.append(url)

        print(f"\n  [{page_num:03d}] {url}")

        try:
            driver.get(url)
            WebDriverWait(driver, wait_time).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            on_page_callback(driver, url, page_num)

            new_links = collect_links(driver, url, base_domain, cfg) - visited
            for link in new_links:
                stack.append(link)    # ← PUSH onto stack

            print(f"       +{len(new_links)} new links pushed | Stack depth: {len(stack)}")

        except Exception as e:
            print(f"         Error: {e}")

    print(f"\n   Crawl complete — {page_num} pages visited\n")
    return order
