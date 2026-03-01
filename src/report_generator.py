

import json
from datetime import datetime
from pathlib import Path

from src.utils import timestamp, now_iso

JSON_DIR    = Path("snapshots/json")
REPORT_DIR  = Path("snapshots/reports")


def generate(visited_urls: list, mode: str, start_url: str) -> str:
    
    ts      = timestamp()
    outpath = REPORT_DIR / f"report_{ts}.html"

    # Collect all JSON metadata files from this run
    records = _load_json_records()

    html = _build_html(visited_urls, records, mode, start_url, ts)
    outpath.write_text(html, encoding="utf-8")

    print(f"\n  📊 Report saved → {outpath}")
    return str(outpath)




def _load_json_records() -> list:
    records = []
    for f in sorted(JSON_DIR.glob("*.json")):
        try:
            records.append(json.loads(f.read_text()))
        except Exception:
            pass
    return records


def _build_html(urls, records, mode, start_url, ts) -> str:
    rows = ""
    for i, url in enumerate(urls, 1):
        # Find matching record
        rec = next((r for r in records if r.get("url") == url), {})
        status  = rec.get("status", "screenshot")
        title   = rec.get("title", "—")
        time    = rec.get("time", "—")
        img     = rec.get("file", "")
        content = rec.get("content", "")[:200] + "..." if rec.get("content") else "—"

        badge_color = {
            "first_scan": "#4caf50",
            "changed":    "#ff9800",
            "no_change":  "#5c6773",
            "screenshot": "#6c63ff",
        }.get(status, "#5c6773")

        img_tag = f'<img src="../../{img}" style="max-width:180px;border-radius:6px;border:1px solid #2e3355">' if img else "—"

        rows += f"""
        <tr>
          <td style="color:#8892b0">{i:03d}</td>
          <td><a href="{url}" target="_blank" style="color:#82aaff;word-break:break-all">{url}</a></td>
          <td>{title}</td>
          <td><span style="background:{badge_color}22;color:{badge_color};padding:2px 8px;border-radius:10px;font-size:0.78rem;font-weight:600">{status}</span></td>
          <td style="color:#8892b0;font-size:0.82rem">{time[:19] if time != '—' else '—'}</td>
          <td>{img_tag if mode == 'screenshot' else f'<span style="color:#8892b0;font-size:0.8rem">{content}</span>'}</td>
        </tr>"""

    changed = sum(1 for r in records if r.get("status") == "changed")
    first   = sum(1 for r in records if r.get("status") == "first_scan")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>VEDAS Monitor — Crawl Report</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:#0f1117; color:#e8eaf6; font-family:'Segoe UI',system-ui,sans-serif; padding:32px; }}
  h1 {{ font-size:1.8rem; background:linear-gradient(90deg,#6c63ff,#00d4aa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; margin-bottom:6px; }}
  .meta {{ color:#5c6773; font-size:0.85rem; margin-bottom:30px; }}
  .stats {{ display:flex; gap:16px; margin-bottom:28px; flex-wrap:wrap; }}
  .stat {{ background:#1a1d2e; border:1px solid #2e3355; border-radius:10px; padding:14px 20px; }}
  .stat .n {{ font-size:1.6rem; font-weight:700; color:#00d4aa; }}
  .stat .l {{ font-size:0.75rem; color:#5c6773; text-transform:uppercase; letter-spacing:.05em; }}
  table {{ width:100%; border-collapse:collapse; font-size:0.85rem; }}
  th {{ text-align:left; color:#5c6773; font-size:0.75rem; text-transform:uppercase; letter-spacing:.07em; padding:10px 14px; border-bottom:1px solid #2e3355; }}
  td {{ padding:12px 14px; border-bottom:1px solid #1a1d2e; vertical-align:top; }}
  tr:hover td {{ background:#1a1d2e; }}
</style>
</head>
<body>
<h1>🔍 VEDAS Monitor — Crawl Report</h1>
<div class="meta">Generated: {now_iso()[:19]} &nbsp;|&nbsp; Mode: {mode} &nbsp;|&nbsp; Root: <a href="{start_url}" style="color:#6c63ff">{start_url}</a></div>
<div class="stats">
  <div class="stat"><div class="n">{len(urls)}</div><div class="l">Pages Crawled</div></div>
  <div class="stat"><div class="n" style="color:#ff9800">{changed}</div><div class="l">Changed</div></div>
  <div class="stat"><div class="n" style="color:#4caf50">{first}</div><div class="l">First Scan</div></div>
  <div class="stat"><div class="n" style="color:#5c6773">{len(urls)-changed-first}</div><div class="l">No Change</div></div>
</div>
<table>
  <thead>
    <tr>
      <th>#</th><th>URL</th><th>Title</th><th>Status</th><th>Time</th><th>{'Screenshot' if mode == 'screenshot' else 'Content Preview'}</th>
    </tr>
  </thead>
  <tbody>{rows}</tbody>
</table>
</body>
</html>"""
