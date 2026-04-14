"""
WebGuard — YUVA Monitor (Final: Adds Layers & Clean Images)
============================================================
✔ Opens dialog, clicks layer, handles Date/Pass sub-popups
✔ Clicks "OK/Add" so data actually renders on OpenLayers
✔ Takes screenshot of ONLY the map canvas (clean images)
✔ Checks > 10 days data freshness
✔ Single / Combined / Random / Freshness
"""

import time
import random
import json
import re
import hashlib
import base64
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys

from src.utils import load_config


VEDAS_CATEGORIES = {
    "Satellite Data Visualization": ["Optical Data", "Microwave (Radar) Data", "Cloud Mask"],
    "Vegetation Monitoring": ["Vegetation Indices", "Evapo Transpiration", "Crop Mask", "Soil Moisture"],
    "Land Use Land Cover": [], "Water Resources": [], "Crop Monitoring": [],
    "Flood Monitoring": [], "Forest Monitoring": [], "Fire Monitoring": [],
}

VEDAS_KNOWN_LAYERS = [
    "AWIFS FCC [56m]", "AWIFS NDVI [56m]", "Sentinel-2 FCC [10m]", "Sentinel-2 NDVI [10m]",
    "LISS-III FCC [23m]", "RISAT FCC [25m]", "NDVI", "EVI", "SAVI", "LULC",
    "Water Bodies", "Flood Extent", "Forest Cover", "Snow Cover", "Soil Moisture",
    "Administrative Boundary", "DEM", "Slope", "Cloud Mask",
]


class YuvaMonitor:

    def __init__(self, driver, output_base="snapshots"):
        self.driver = driver
        self.cfg = load_config("config.json")

        self.output_base = Path(output_base)
        for sub in ["single", "combined", "random", "yuva_json", "freshness"]:
            (self.output_base / sub).mkdir(parents=True, exist_ok=True)

        self.discovered_layers = []
        self._hash_cache = {}

    # ─────────────────────────────────────────────
    # NAVIGATION
    # ─────────────────────────────────────────────
    def navigate(self, wait_time=None):
        wait = wait_time or 20
        print(f"\n🌐 Opening VEDAS YUVA...")
        self.driver.get(self.cfg.get("TARGET_URL", "https://vedas.sac.gov.in/uva/index.html"))
        
        try:
            WebDriverWait(self.driver, wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "canvas, .ol-viewport"))
            )
            time.sleep(min(5, wait - 3))
        except Exception:
            time.sleep(wait)
        print("   ✅ Map ready")

    # ─────────────────────────────────────────────
    # DIALOG CONTROLS
    # ─────────────────────────────────────────────
    def _open_layer_dialog(self) -> bool:
        js = """
            var clicked = false;
            document.querySelectorAll('button, mat-icon, div[role="button"]').forEach(btn => {
                if (clicked) return;
                var t = (btn.innerText || '').toLowerCase();
                var tt = (btn.getAttribute('mattooltip') || btn.getAttribute('title') || '').toLowerCase();
                if (t.includes('layer') || t.includes('search') || t.includes('add data') || tt.includes('layer') || tt.includes('search')) {
                    btn.scrollIntoView({block: 'center'});
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    clicked = true;
                }
            });
            return clicked;
        """
        try:
            if self.driver.execute_script(js):
                time.sleep(2)
                return True
        except: pass
        return False

    def _close_layer_dialog(self):
        js = """
            document.querySelectorAll('button[aria-label="Close"], [class*="close-btn"], mat-dialog-close, [mat-dialog-close], button[class*="close"]').forEach(btn => {
                if (btn.offsetParent !== null) btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            });
            document.querySelectorAll('.cdk-overlay-backdrop').forEach(bd => {
                bd.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            });
        """
        try:
            self.driver.execute_script(js)
            time.sleep(1)
        except: pass

    def _expand_dialog_category(self, cat_name: str):
        js = """
            var cat = arguments[0], done = false;
            document.querySelectorAll('div, span, mat-expansion-panel-header, h3, h4, p, li').forEach(item => {
                if (done) return;
                if (item.innerText.trim().includes(cat) && item.innerText.trim().length < 100) {
                    item.scrollIntoView({block: 'center'});
                    item.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    done = true;
                }
            });
            return done;
        """
        try: return self.driver.execute_script(js, cat_name)
        except: return False

    def _click_dialog_layer(self, name: str) -> bool:
        js = """
            var n = arguments[0], ok = false;
            document.querySelectorAll('div, span, mat-list-item, li, p, label').forEach(item => {
                if (ok) return;
                var t = item.innerText.trim();
                if (t === n || t.startsWith(n + ' ') || t.startsWith(n + '[')) {
                    item.scrollIntoView({block: 'center'});
                    item.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    ok = true;
                }
            });
            return ok;
        """
        try:
            if self.driver.execute_script(js, name):
                time.sleep(1)
                return True
        except: pass
        return False

    # ─────────────────────────────────────────────
    # 🔥 SUB-DIALOG HANDLER (Crucial for VEDAS)
    # ─────────────────────────────────────────────
    def _handle_sub_dialog(self):
        """
        When you click a layer, VEDAS often opens a 2nd popup asking for Date/Pass.
        This function automatically selects the first available date and clicks OK/Add.
        """
        time.sleep(1.5) # Wait for sub-popup to render
        
        js_handle = """
            var handled = false;
            
            // 1. Try to click "OK", "Add", "Apply", "Submit" buttons
            var buttons = document.querySelectorAll('button');
            buttons.forEach(btn => {
                if (handled) return;
                var text = (btn.innerText || '').toLowerCase().trim();
                if (text === 'ok' || text === 'add' || text === 'apply' || text === 'submit' || 
                    text === 'add layer' || text === 'save' || text.includes('add data')) {
                    if (btn.offsetParent !== null) {
                        btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        handled = true;
                    }
                }
            });
            
            // 2. If no OK button, try clicking the first available Date/Mat-Option item
            if (!handled) {
                var options = document.querySelectorAll(
                    'mat-option, [role="option"], [class*="date-item"], [class*="pass-item"], mat-list-item'
                );
                options.forEach(opt => {
                    if (handled) return;
                    if (opt.offsetParent !== null && opt.innerText.trim().length > 3) {
                        opt.scrollIntoView({block: 'center'});
                        opt.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                        handled = true; // Click first valid option
                    }
                });
                
                // If we clicked an option, try clicking OK again
                if (handled) {
                    setTimeout(() => {
                        document.querySelectorAll('button').forEach(btn => {
                            var text = (btn.innerText || '').toLowerCase().trim();
                            if ((text === 'ok' || text === 'add' || text === 'apply') && btn.offsetParent !== null) {
                                btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
                            }
                        });
                    }, 500);
                }
            }
            return handled;
        """
        try:
            return self.driver.execute_script(js_handle)
        except:
            return False

    # ─────────────────────────────────────────────
    # DISCOVER LAYERS
    # ─────────────────────────────────────────────
    def discover_layers(self) -> List[str]:
        print("\n🔍 Discovering layers...")
        if not self._open_layer_dialog(): return []
        
        found = set()
        try:
            items = self.driver.execute_script("""
                var t = [];
                document.querySelectorAll('mat-dialog-container mat-list-item, mat-dialog-container li, mat-dialog-container [class*="item"]').forEach(i => {
                    var txt = i.innerText.trim();
                    if (txt.length > 3 && txt.length < 80) t.push(txt);
                });
                return [...new Set(t)];
            """) or []
            for i in items:
                clean = self._clean_text(i)
                if clean: found.add(clean)
        except: pass

        for l in VEDAS_KNOWN_LAYERS: found.add(l)
        self.discovered_layers = sorted(list(found))
        print(f"   📊 Found {len(self.discovered_layers)} layers")
        self._close_layer_dialog()
        return self.discovered_layers

    def _clean_text(self, text):
        if not text: return None
        parts = text.replace("\n", " ").split()
        clean = [p for p in parts if len(p) > 1]
        res = " ".join(clean).strip()
        return res if len(res) >= 3 else None

    # ─────────────────────────────────────────────
    # ACTIVATE LAYER (Full Flow: Dialog -> Sub-Dialog -> OK)
    # ─────────────────────────────────────────────
    def activate_layer(self, name: str) -> bool:
        if not self._open_layer_dialog(): return False
        time.sleep(1)
        
        if self._click_dialog_layer(name):
            # 🔥 CRITICAL: Handle the Date/Pass sub-popup
            self._handle_sub_dialog()
            time.sleep(1)
            
            # Close main dialog
            self._close_layer_dialog()
            time.sleep(1)
            return True
        
        # Fallback: Search categories
        for cat, subcats in VEDAS_CATEGORIES.items():
            self._expand_dialog_category(cat)
            time.sleep(0.5)
            for subcat in subcats:
                self._expand_dialog_category(subcat)
                time.sleep(0.3)
                if self._click_dialog_layer(name):
                    self._handle_sub_dialog()
                    time.sleep(1)
                    self._close_layer_dialog()
                    return True
        
        self._close_layer_dialog()
        return False

    def deactivate_all(self):
        js = """
            document.querySelectorAll('[class*="layer-item"] button, [class*="active-layer"] button, button[mattooltip*="remove"], button[mattooltip*="Remove"]').forEach(btn => {
                if (btn.offsetParent !== null) btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            });
            document.querySelectorAll('button, div[role="button"]').forEach(btn => {
                var t = (btn.innerText || '').toLowerCase();
                if (t.includes('clear all') || t.includes('remove all')) btn.dispatchEvent(new MouseEvent('click', {bubbles: true}));
            });
        """
        try:
            self.driver.execute_script(js)
            time.sleep(0.5)
        except: pass

    # ─────────────────────────────────────────────
    # WAIT FOR TILES TO RENDER
    # ─────────────────────────────────────────────
    def _wait_for_tiles(self, timeout=15):
        js = """
            return new Promise(resolve => {
                var start = Date.now(), check = () => {
                    var loading = false;
                    try {
                        var el = document.querySelector('.ol-viewport');
                        if(el) Object.keys(el).forEach(k => {
                            if(k.startsWith('__ol')) {
                                var map = el[k].getMap();
                                if(map) map.getLayers().forEach(l => {
                                    var s = l.getSource();
                                    if(s && s.getState && s.getState() === 'loading') loading = true;
                                });
                            }
                        });
                    } catch(e){}
                    if(!loading || Date.now()-start > %d*1000) resolve(!loading);
                    else setTimeout(check, 500);
                };
                setTimeout(check, 1000);
            });
        """ % timeout
        try:
            self.driver.set_script_timeout((timeout + 2) * 1000)
            self.driver.execute_async_script(js)
        except:
            time.sleep(4)

    # ─────────────────────────────────────────────
    # 🔥 CLEAN MAP IMAGE (Screenshots ONLY the map)
    # ─────────────────────────────────────────────
    def _screenshot(self, name, folder) -> Optional[str]:
        path = self.output_base / folder
        path.mkdir(parents=True, exist_ok=True)

        filename = re.sub(r'[^a-zA-Z0-9]', '_', name)[:50]
        filepath = path / f"{filename}_{int(time.time())}.png"

        # Strategy 1: Screenshot ONLY the map element (Clean Image)
        map_saved = False
        try:
            map_el = self.driver.find_element(By.CSS_SELECTOR, "#map, .ol-viewport, .map-container")
            map_el.screenshot(str(filepath))
            map_saved = True
        except Exception:
            pass

        # Strategy 2: Fallback to full window if map element not found
        if not map_saved:
            self.driver.save_screenshot(str(filepath))

        # Dedup check
        try:
            with open(filepath, "rb") as f:
                h = hashlib.md5(f.read()).hexdigest()
            if self._hash_cache.get(name) == h:
                filepath.unlink()
                print(f"      ⏭️  dup")
                return None
            self._hash_cache[name] = h
        except: pass

        print(f"      🖼️  {filepath.name}")
        return str(filepath)

    # ─────────────────────────────────────────────
    # FRESHNESS CHECK (Scans dialog for > 10 days)
    # ─────────────────────────────────────────────
    def _parse_vedas_date(self, text: str) -> Tuple[Optional[datetime], Optional[int]]:
        text = text.strip()
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %Y", "%b %Y"]:
            try:
                dt = datetime.strptime(text, fmt)
                return dt, (datetime.now() - dt).days
            except ValueError: pass
        return None, None

    def check_freshness(self, threshold=10):
        print(f"\n📅 CHECKING DATA UPDATES (>{threshold} days = STALE)")
        print("-" * 60)
        
        stale, fresh = [], []
        seen = set()

        def process(src, raw):
            if raw in seen: return
            seen.add(raw)
            dt, days = self._parse_vedas_date(raw)
            if dt:
                item = {"source": src, "date": raw, "days_old": days, "needs_update": days > threshold}
                (stale if days > threshold else fresh).append(item)

        if self._open_layer_dialog():
            time.sleep(2)
            for cat in list(VEDAS_CATEGORIES.keys())[:4]:
                self._expand_dialog_category(cat)
                time.sleep(0.5)
            
            try:
                regex = r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2}|\d{2}-\d{2}-\d{4})"
                items = self.driver.execute_script("""
                    var t=[];
                    document.querySelectorAll('mat-dialog-container mat-list-item, mat-dialog-container li, mat-dialog-container [class*="item"]').forEach(e=>t.push(e.innerText.trim()));
                    return t;
                """) or []
                for txt in items:
                    for d in re.findall(regex, txt, re.IGNORECASE):
                        process(f"Dialog: {txt.split(chr(10))[0][:40]}", d)
            except: pass
            self._close_layer_dialog()

        print(f"   Total: {len(stale)+len(fresh)} | ✅ Fresh: {len(fresh)} | ⚠️ Stale: {len(stale)}")
        if stale:
            print(f"\n   🚨 NEEDS UPDATE - DATA OLDER THAN {threshold} DAYS:")
            for s in stale: print(f"      ❌ {s['source']} -> {s['date']} ({s['days_old']}d old)")
        else:
            print("\n   ✅ All data is up to date!")

        report = {"threshold": threshold, "stale_items": stale, "fresh_items": fresh, "time": datetime.now().isoformat()}
        rpath = self.output_base / "freshness" / f"update_report_{int(time.time())}.json"
        with open(rpath, "w") as f: json.dump(report, f, indent=2)
        print(f"   💾 Saved: {rpath.name}")
        return report

    # ─────────────────────────────────────────────
    # MODES
    # ─────────────────────────────────────────────
    def screenshot_single_layers(self):
        print("\n📸 SINGLE MODE (Adding layers & capturing map)")
        targets = [l for l in self.discovered_layers if any(k in l.lower() for k in ["awifs", "sentinel", "liss", "ndvi", "fcc", "lulc", "water", "forest", "flood", "dem", "boundary", "sar", "cloud"])]
        if not targets: targets = self.discovered_layers[:10]
            
        for l in targets:
            print(f"   ➕ {l}", end="")
            self.deactivate_all()
            if self.activate_layer(l):
                self._wait_for_tiles(timeout=12)
                self._screenshot(l, "single")
            else:
                print(" ⚠️ skipped")

    def screenshot_combined_by_category(self):
        print("\n📸 COMBINED MODE")
        combos = [
            (["AWIFS FCC [56m]", "Administrative Boundary"], "AWIFS_Boundary"),
            (["Sentinel-2 FCC [10m]", "NDVI"], "S2_NDVI"),
            (["NDVI", "EVI", "SAVI"], "Vegetation_Combo"),
            (["Water Bodies", "River"], "Water_Combo"),
            (["Forest Cover", "Forest Density"], "Forest_Combo"),
        ]
        for layers, label in combos:
            print(f"   ➕ {label}", end="")
            self.deactivate_all()
            if any(self.activate_layer(l) for l in layers):
                self._wait_for_tiles(timeout=15)
                self._screenshot(label, "combined")
            else:
                print(" ⚠️ skipped")

    def screenshot_random_layers(self, count=3, iterations=5):
        print(f"\n📸 RANDOM MODE ({iterations}x{count})")
        targets = [l for l in self.discovered_layers if any(k in l.lower() for k in ["awifs", "sentinel", "liss", "ndvi", "fcc", "lulc", "water", "forest", "flood", "dem", "boundary", "sar", "evi"])]
        if len(targets) < 2: print("   ⚠️ Not enough layers"); return

        for i in range(iterations):
            pick = random.sample(targets, min(count, len(targets)))
            print(f"   🎲 #{i+1} {pick}", end="")
            self.deactivate_all()
            for p in pick: self.activate_layer(p)
            self._wait_for_tiles(timeout=15)
            self._screenshot(f"rand_{i}_{'_'.join(p[0].split()[:2])}", "random")

    # ─────────────────────────────────────────────
    # RUN ALL
    # ─────────────────────────────────────────────
    def run_all(self):
        self.discover_layers()
        self.check_freshness(threshold=10)
        self.screenshot_single_layers()
        self.screenshot_combined_by_category()
        self.screenshot_random_layers()