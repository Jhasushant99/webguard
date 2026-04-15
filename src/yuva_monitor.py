"""
WebGuard — YUVA Monitor (Full Debug Version)
=============================================
Built for: https://vedas.sac.gov.in/uva/index.html#app_id=visualization
✔ Waits for Angular to render dialog list items
✔ Safely expands categories (won't collapse if already open)
✔ 3-tier layer clicking (Exact JS -> Loose JS -> Selenium)
✔ Handles mat-select Date dropdowns
✔ Clicks Data Tool + Map -> Pauses -> Takes Full Screenshot
✔ Saves Paired .png Image + .json Data File
"""

import time
import random
import json
import re
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

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
        
        for sub in ["yuva_output"]:
            (self.output_base / sub).mkdir(parents=True, exist_ok=True)

        self.discovered_layers = []
        self._hash_cache = {}

    # ─────────────────────────────────────────────
    # 1. NAVIGATION
    # ─────────────────────────────────────────────
    def navigate(self, wait_time=None):
        wait = wait_time or 25
        print(f"\n🌐 Opening VEDAS UVA...")
        self.driver.get(self.cfg.get("TARGET_URL", "https://vedas.sac.gov.in/uva/index.html#app_id=visualization"))
        
        try:
            WebDriverWait(self.driver, wait).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#map canvas, .ol-viewport canvas"))
            )
            print("   ✅ Map canvas rendered. Waiting 3s for toolbar...")
            time.sleep(3)
        except Exception as e:
            print(f"   ⚠️ Map wait failed: {e}. Waiting {wait}s anyway...")
            time.sleep(wait)

    # ─────────────────────────────────────────────
    # 2. OPEN DIALOG (Waits for items to render)
    # ─────────────────────────────────────────────
    def _open_layer_dialog(self) -> bool:
        print("      [1/4] Opening Dialog...", end=" ")
        try:
            buttons = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Add Layer')]")
            for btn in buttons:
                try:
                    if btn.is_displayed() and len(btn.text.strip()) < 30:
                        btn.click()
                        time.sleep(1.5)
                        # DEBUG: Wait explicitly for the list items to exist inside dialog
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, "mat-dialog-container mat-list-item, mat-dialog-container li, mat-dialog-container [class*='item']"))
                            )
                            print("✅ (Items loaded)")
                            return True
                        except:
                            print("⚠️ (Opened, but no list items found)")
                            return True
                except Exception as e:
                    pass
        except Exception as e:
            print(f"[DEBUG] XPath error: {e}")

        try:
            clicked = self.driver.execute_script("""
                var els = document.querySelectorAll('button, div, span, mat-icon');
                for(var i=0; i<els.length; i++){
                    var t = els[i].innerText.trim();
                    if(t.includes('Add Layer') && t.length < 30 && els[i].offsetParent !== null){
                        els[i].click(); return true;
                    }
                }
                return false;
            """)
            if clicked:
                time.sleep(1.5)
                try:
                    WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "mat-dialog-container mat-list-item"))
                    )
                except: pass
                print("✅ (JS Fallback)")
                return True
        except Exception as e:
            print(f"[DEBUG] JS error: {e}")
        
        print("❌ Failed")
        return False

    def _close_layer_dialog(self):
        try:
            close_btns = self.driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Close'], [mat-dialog-close], .mat-dialog-close")
            for btn in close_btns:
                if btn.is_displayed():
                    btn.click()
                    time.sleep(1)
                    return
        except: pass
        try:
            backdrops = self.driver.find_elements(By.CSS_SELECTOR, ".cdk-overlay-backdrop")
            for bd in backdrops:
                if bd.is_displayed(): bd.click()
        except: pass
        time.sleep(1)

    # ─────────────────────────────────────────────
    # 3. EXPAND CATEGORY (ONLY inside dialog)
    # ─────────────────────────────────────────────
    def _expand_dialog_category(self, cat_name: str) -> bool:
        js = """
            var cat = arguments[0].toLowerCase();
            var dialog = document.querySelector('mat-dialog-container');
            if(!dialog) return false;
            
            var headers = dialog.querySelectorAll('mat-expansion-panel-header, h3, h4, [class*="category"]');
            for(var i=0; i<headers.length; i++){
                var text = headers[i].innerText.toLowerCase();
                if(text.includes(cat)){
                    // DEBUG FIX: Only click if it's NOT already expanded
                    var isExpanded = headers[i].getAttribute('aria-expanded');
                    if(isExpanded !== 'true'){
                        headers[i].click();
                        return true; // Clicked to expand
                    }
                    return 'already_open'; // Already open, don't click
                }
            }
            return false;
        """
        try:
            result = self.driver.execute_script(js, cat_name)
            if result == 'already_open':
                return True
            return bool(result)
        except Exception as e:
            print(f"\n      [DEBUG] Expand error for {cat_name}: {e}")
            return False

    # ─────────────────────────────────────────────
    # 4. CLICK LAYER (3-Tier Robust Match)
    # ─────────────────────────────────────────────
    def _click_dialog_layer(self, name: str) -> bool:
        # Tier 1: Exact JS click inside dialog
        js_exact = """
            var n = arguments[0];
            var dialog = document.querySelector('mat-dialog-container');
            if(!dialog) return false;
            var items = dialog.querySelectorAll('mat-list-item, [class*="layer-item"], li, div');
            for(var i=0; i<items.length; i++){
                var t = items[i].innerText.trim();
                if(t === n || t.startsWith(n + ' ') || t.startsWith(n + '[')){
                    items[i].scrollIntoView({block: 'center'});
                    items[i].dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    return true;
                }
            }
            return false;
        """
        try:
            if self.driver.execute_script(js_exact, name):
                time.sleep(1)
                return True
        except: pass

        # Tier 2: Loose JS match (handles extra text like "(Latest)")
        js_loose = """
            var n = arguments[0];
            var dialog = document.querySelector('mat-dialog-container');
            if(!dialog) return false;
            var items = dialog.querySelectorAll('mat-list-item, [class*="layer-item"], li, div');
            for(var i=0; i<items.length; i++){
                var t = items[i].innerText.trim();
                if(t.includes(n) && t.length < 100){
                    items[i].scrollIntoView({block: 'center'});
                    items[i].dispatchEvent(new MouseEvent('click', {bubbles: true}));
                    return true;
                }
            }
            return false;
        """
        try:
            if self.driver.execute_script(js_loose, name):
                time.sleep(1)
                return True
        except: pass

        # Tier 3: Selenium Click (Fallback for stubborn Angular)
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, "mat-dialog-container mat-list-item, mat-dialog-container li")
            for item in items:
                txt = item.text.strip()
                if name in txt and item.is_displayed():
                    ActionChains(self.driver).move_to_element(item).click().perform()
                    time.sleep(1)
                    return True
        except: pass

        return False

    # ─────────────────────────────────────────────
    # 5. SUB-DIALOG (Angular Mat-Select Dates)
    # ─────────────────────────────────────────────
    def _handle_sub_dialog(self) -> bool:
        print("      [3/4] Handling Date Popup...", end=" ")
        time.sleep(2)
        handled = False
        
        try:
            selects = self.driver.find_elements(By.CSS_SELECTOR, "mat-form-field mat-select")
            for select in selects:
                try:
                    if not select.is_displayed(): continue
                    trigger = select.find_element(By.CSS_SELECTOR, ".mat-select-trigger")
                    trigger.click()
                    time.sleep(1)
                    
                    options = self.driver.find_elements(By.CSS_SELECTOR, "mat-option")
                    for opt in options:
                        if "mat-option-disabled" not in opt.get_attribute("class") and opt.is_displayed():
                            opt.click()
                            time.sleep(0.5)
                            break
                except Exception as e:
                    print(f"[Select err] ", end="")
            
            time.sleep(0.5)
            buttons = self.driver.find_elements(By.CSS_SELECTOR, "button")
            for btn in buttons:
                if btn.is_displayed() and btn.text.strip().lower() in ['ok', 'add', 'apply', 'save']:
                    btn.click()
                    time.sleep(1)
                    handled = True
                    break
        except Exception as e:
            print(f"[DEBUG] {e}", end=" ")
            
        print("✅" if handled else "⚠️ (No popup/OK)")
        return handled

    # ─────────────────────────────────────────────
    # 6. TRIGGER DATA POPUP (Cut/Scissor Tool)
    # ─────────────────────────────────────────────
    def _trigger_data_popup(self):
        print("      [5/6] Clicking Data Tool...", end=" ")
        try:
            tools = self.driver.find_elements(By.CSS_SELECTOR, "button, mat-icon, div[role='button']")
            tool_clicked = False
            
            for tool in tools:
                try:
                    tooltip = (tool.get_attribute("mattooltip") or tool.get_attribute("title") or "").lower()
                    text = (tool.text or "").lower()
                    cls = (tool.get_attribute("class") or "").lower()
                    
                    if any(word in tooltip or word in text or word in cls 
                           for word in ["cut", "scissor", "identify", "feature info", "info", "query"]):
                        if "clear" not in text and "remove" not in text:
                            tool.click()
                            tool_clicked = True
                            time.sleep(1)
                            break
                except: pass

            if tool_clicked:
                try:
                    map_el = self.driver.find_element(By.CSS_SELECTOR, "#map, .ol-viewport, canvas")
                    ActionChains(self.driver).move_to_element(map_el).click().perform()
                    time.sleep(1)
                    print("✅ Clicked Map")
                except Exception as e:
                    print(f"⚠️ Map click failed: {e}")
            else:
                print("⚠️ Tool not found")
                
        except Exception as e:
            print(f"❌ {e}")

    # ─────────────────────────────────────────────
    # 7. WAIT FOR TILES
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
    # 8. SAVE OUTPUT (Image + JSON)
    # ─────────────────────────────────────────────
    def _parse_date(self, text: str) -> Tuple[Optional[str], Optional[int]]:
        text = text.strip()
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%B %Y", "%b %Y"]:
            try:
                dt = datetime.strptime(text, fmt)
                return text, (datetime.now() - dt).days
            except ValueError: pass
        return None, None

    def _save_output(self, layer_name: str, status: str) -> Optional[str]:
        out_dir = self.output_base / "yuva_output"
        out_dir.mkdir(parents=True, exist_ok=True)

        ts = int(time.time())
        safe_name = re.sub(r'[^a-zA-Z0-9]', '_', layer_name)[:50]
        base_filename = f"{safe_name}_{ts}"
        img_path = out_dir / f"{base_filename}.png"
        json_path = out_dir / f"{base_filename}.json"

        if status == "success":
            self._trigger_data_popup()
            print("      [6/6] Pausing for data panel (4s)...", end=" ")
            time.sleep(4)
            print("done")

        # Full Window Screenshot
        self.driver.save_screenshot(str(img_path))

        # Extract Text & Date
        visible_data_text = ""
        date_found, days_old = None, None
        try:
            visible_data_text = self.driver.find_element(By.TAG_NAME, "body").text
            match = re.search(r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}|\d{4}-\d{2}-\d{2})", visible_data_text, re.IGNORECASE)
            if match:
                date_found, days_old = self._parse_date(match.group(1))
        except: pass

        metadata = {
            "layer_name": layer_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "source_url": self.cfg.get("TARGET_URL", ""),
            "output_files": {"image": str(img_path.resolve()), "json": str(json_path.resolve())},
            "data_check": {
                "date_found": date_found,
                "days_old": days_old,
                "needs_update": True if (days_old is not None and days_old > 10) else False
            },
            "extracted_ui_text": visible_data_text[:1000]
        }

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4, ensure_ascii=False)

        # Dedup
        try:
            with open(img_path, "rb") as f: h = hashlib.md5(f.read()).hexdigest()
            if self._hash_cache.get(layer_name) == h:
                img_path.unlink(); json_path.unlink()
                print("      ⏭️  Exact duplicate skipped"); return None
            self._hash_cache[layer_name] = h
        except: pass

        flag = " [⚠️ STALE >10d]" if metadata["data_check"]["needs_update"] else ""
        print(f"      🖼️  {img_path.name} + .json{flag}")
        return str(img_path)

    # ─────────────────────────────────────────────
    # 9. DISCOVER LAYERS
    # ─────────────────────────────────────────────
    def discover_layers(self) -> List[str]:
        print("\n🔍 Discovering layers...")
        if not self._open_layer_dialog(): return []
        
        found = set()
        try:
            items = self.driver.find_elements(By.CSS_SELECTOR, "mat-dialog-container mat-list-item, mat-dialog-container li, mat-dialog-container [class*='item']")
            for i in items:
                txt = i.text.strip()
                if 3 < len(txt) < 80: found.add(txt)
        except: pass

        for l in VEDAS_KNOWN_LAYERS: found.add(l)
        self.discovered_layers = sorted(list(found))
        print(f"   📊 Found {len(self.discovered_layers)} layers")
        self._close_layer_dialog()
        return self.discovered_layers

    # ─────────────────────────────────────────────
    # 10. ACTIVATE LAYER (Full Flow + Debug)
    # ─────────────────────────────────────────────
    def activate_layer(self, name: str) -> bool:
        if not self._open_layer_dialog():
            print("         [DEBUG] Failed at step 1: Dialog didn't open.")
            return False
        
        print(f"      [2/4] Searching for '{name}'...", end=" ")
        
        # Try direct click
        if self._click_dialog_layer(name):
            self._handle_sub_dialog()
            self._close_layer_dialog()
            time.sleep(1)
            print("      ✅ Layer added successfully.")
            return True
        
        print("Not found directly. Expanding categories...")
        
        # Fallback: Expand categories
        for cat, subcats in VEDAS_CATEGORIES.items():
            self._expand_dialog_category(cat)
            time.sleep(0.5)
            for subcat in subcats:
                self._expand_dialog_category(subcat)
                time.sleep(0.5)
                if self._click_dialog_layer(name):
                    self._handle_sub_dialog()
                    self._close_layer_dialog()
                    print(f"      ✅ Found in {cat} -> {subcat}")
                    return True
        
        print(f"         [DEBUG] Failed at step 2: Layer '{name}' does not exist in dialog.")
        self._close_layer_dialog()
        return False

    def deactivate_all(self):
        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, "[class*='layer-item'] button, button[mattooltip*='remove']")
            for btn in btns:
                if btn.is_displayed(): btn.click()
        except: pass
        time.sleep(0.5)

    # ─────────────────────────────────────────────
    # 11. MODES
    # ─────────────────────────────────────────────
    def screenshot_single_layers(self):
        print("\n📸 SINGLE MODE")
        targets = [l for l in self.discovered_layers if any(k in l.lower() for k in 
            ["awifs", "sentinel", "liss", "ndvi", "fcc", "lulc", "water", "forest", "flood", "dem", "boundary", "sar", "cloud", "evi"])]
        if not targets: targets = self.discovered_layers[:10]
            
        for l in targets:
            print(f"\n   ➕ {l}")
            self.deactivate_all()
            if self.activate_layer(l):
                self._wait_for_tiles(timeout=12)
                self._save_output(l, "success")
            else:
                self._save_output(l, "failed_to_add")

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
            print(f"\n   ➕ {label} ({layers})")
            self.deactivate_all()
            added = [l for l in layers if self.activate_layer(l)]
            if added:
                self._wait_for_tiles(timeout=15)
                self._save_output(f"Combined_{label}", "success")
            else:
                print("      ⚠️ Skipped (None could be added)")

    def screenshot_random_layers(self, count=3, iterations=5):
        print(f"\n📸 RANDOM MODE ({iterations}x{count})")
        targets = [l for l in self.discovered_layers if any(k in l.lower() for k in 
            ["awifs", "sentinel", "liss", "ndvi", "fcc", "lulc", "water", "forest", "flood", "dem", "boundary", "sar", "evi"])]
        if len(targets) < 2: 
            print("   ⚠️ Not enough valid layers"); return

        for i in range(iterations):
            pick = random.sample(targets, min(count, len(targets)))
            print(f"\n   🎲 #{i+1} {pick}")
            self.deactivate_all()
            for p in pick: self.activate_layer(p)
            self._wait_for_tiles(timeout=15)
            label = f"Random_{i}_{'_'.join(p[0].split()[:2])}"
            self._save_output(label, "success")

    def check_freshness(self, threshold=10):
        print(f"\n📅 FRESHNESS: Automatically checked per layer (> {threshold} days = STALE)")
        print("   (See 'needs_update' flag inside each generated .json file)")

    # ─────────────────────────────────────────────
    # 12. RUN ALL
    # ─────────────────────────────────────────────
    def run_all(self):
        self.discover_layers()
        self.check_freshness()
        self.screenshot_single_layers()
        self.screenshot_combined_by_category()
        self.screenshot_random_layers()