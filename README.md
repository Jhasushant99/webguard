# VEDAS WebGuard 🔍

Stack-based (depth-first) web crawler that monitors every internal page of a site.

## Structure

```
SUSHANTWEBGUARD/
├── main.py                  ← Entry point
├── .env                     ← Your config
├── requirements.txt
├── src/
│   ├── browser.py           ← Chrome WebDriver setup
│   ├── crawler.py           ← STACK-based DFS link crawler
│   ├── image_monitor.py     ← Screenshot every page → PNG
│   ├── dom_monitor.py       ← Extract & compare DOM text
│   ├── report_generator.py  ← HTML summary report
│   └── utils.py             ← Shared helpers
└── snapshots/
    ├── screenshots/         ← PNG per page
    ├── json/                ← Metadata JSON per page
    ├── dom/                 ← Last-seen content per URL
    ├── diffs/               ← Text diff when content changes
    └── reports/             ← HTML crawl report
```

## Setup

```bash
pip install -r requirements.txt
# Edit .env with your target URL
```

## Run

```bash
python main.py                        # screenshot + DOM check (default)
python main.py --mode screenshot      # screenshots only
python main.py --mode dom             # DOM content check only
python main.py --max 20               # limit to 20 pages
python main.py --no-report            # skip HTML report
```

## How the Stack Works

```
stack = [https://example.com]

while stack:
    url = stack.pop()          ← LIFO: deepest link visited first
    visit(url)
    screenshot(url)
    check_dom(url)
    new_links = find_all_internal_links(url)
    stack.extend(new_links)    ← push deeper links on top
```

## Snapshots Output

| File | What it is |
|---|---|
| `screenshots/001_home_TIMESTAMP.png` | Full-page screenshot |
| `json/img_001_home_TIMESTAMP.json` | Screenshot metadata |
| `json/dom_001_home_TIMESTAMP.json` | DOM content snapshot |
| `dom/home_last.json` | Last-seen content (used for comparison) |
| `diffs/diff_001_home_TIMESTAMP.txt` | What changed (added/removed lines) |
| `reports/report_TIMESTAMP.html` | Full crawl summary report |
