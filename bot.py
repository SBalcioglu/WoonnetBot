import time
import re
import sys
import os
import threading
import requests
import logging
from datetime import datetime, time as dt_time
from queue import Queue
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException

from config import (
    BASE_URL, LOGIN_URL, DISCOVERY_URL, API_DISCOVERY_URL, API_DETAILS_SINGLE_URL,
    USERNAME_FIELD_SELECTOR, PASSWORD_FIELD_SELECTOR, LOGIN_BUTTON_SELECTOR,
    LOGOUT_LINK_SELECTOR, CANT_APPLY_YET_SELECTOR, FINAL_APPLY_BUTTON_SELECTOR,
    API_TIMER_URL
)

class WoonnetBot:
    def __init__(self, status_queue: Queue, logger: logging.Logger):
        self.driver: webdriver.Chrome | None = None
        self.status_queue = status_queue; self.logger = logger
        self.service = ChromeService(ChromeDriverManager().install())
        self.stop_event = threading.Event(); self.session = requests.Session()
        self.is_logged_in = False

    def _log(self, message: str, level: str = 'info'):
        getattr(self.status_queue, 'put_nowait', lambda msg: None)(message)
        getattr(self.logger, level, self.logger.info)(message)

    def start_headless_browser(self):
        if self.driver: self._log("Browser already running.", "warning"); return
        self._log("Starting persistent headless browser...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new"); options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu"); options.add_argument("--log-level=3")
        if getattr(sys, 'frozen', False):
            app_dir = os.path.join(os.environ['APPDATA'], 'WoonnetBot')
            os.makedirs(app_dir, exist_ok=True)
            options.add_argument(f"user-data-dir={os.path.join(app_dir, 'chrome_profile')}")
        try:
            self.driver = webdriver.Chrome(service=self.service, options=options)
            self._log("Headless browser started successfully.")
        except Exception as e:
            self._log(f"Failed to start headless browser: {e}", level='error'); self.driver = None

    def login(self, username, password) -> Tuple[bool, requests.Session | None]:
        if not self.driver: self._log("Browser not started.", 'error'); return False, None
        self._log(f"Attempting to log in as {username}...");
        try:
            self.driver.get(LOGIN_URL)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(USERNAME_FIELD_SELECTOR)).send_keys(username)
            self.driver.find_element(*PASSWORD_FIELD_SELECTOR).send_keys(password)
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)).click()
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(LOGOUT_LINK_SELECTOR))
            self._log("Login successful.")
            for cookie in self.driver.get_cookies():
                self.session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/javascript, */*; q=0.01', 'Content-Type': 'application/json; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest', 'Referer': DISCOVERY_URL, 'Pragma': 'no-cache', 'Cache-Control': 'no-cache',
            })
            self.is_logged_in = True
            return True, self.session
        except Exception as e:
            self._log(f"Login error: {e}", level='error'); self.is_logged_in = False; return False, None

    def _get_server_countdown_seconds(self) -> float | None:
        self._log("Fetching precise countdown from server API...")
        try:
            response = self.session.get(API_TIMER_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            remaining_ms = int(data['resterendetijd'])
            if remaining_ms <= 0:
                self._log("Server countdown is zero or negative. Proceeding immediately.", "warning")
                return 0.0
            seconds = remaining_ms / 1000.0
            self._log(f"Success! Server countdown received: {seconds:.2f} seconds.")
            return seconds
        except requests.RequestException as e:
            self._log(f"API Error (Timer): Could not get official time. {e}", "error")
            return None
        except (KeyError, ValueError, TypeError) as e:
            self._log(f"API Error (Timer): Could not parse server response. {e}", "error")
            return None

    def apply_to_listings(self, listing_ids: List[str]):
        if not self.driver or not self.is_logged_in: self._log("Not logged in.", 'error'); return 0
        if not listing_ids: self._log("No listings selected."); return 0

        self._log(f"Pre-loading {len(listing_ids)} application pages...")
        original_window = self.driver.current_window_handle

        for lid in listing_ids:
            if self.stop_event.is_set(): self._log("Stop command received."); return
            self.driver.switch_to.new_window('tab'); self.driver.get(f"{BASE_URL}/reageren/{lid}")
            self._log(f"Page for {lid} is pre-loading...")

        self._log("All pages pre-loaded. Determining wait time...")
        
        remaining_seconds = self._get_server_countdown_seconds()

        if remaining_seconds is not None and remaining_seconds > 0:
            start_time = time.monotonic()
            while not self.stop_event.is_set():
                elapsed = time.monotonic() - start_time
                if elapsed >= remaining_seconds:
                    self._log("Server countdown finished! Applying now!", 'warning')
                    break

                time_left = remaining_seconds - elapsed
                mins, secs = divmod(time_left, 60)
                hours, mins = divmod(mins, 60)
                timer_display = f"{int(hours):02}:{int(mins):02}:{int(secs):02}"
                self._log(f"Waiting for server... T-minus {timer_display}")
                time.sleep(1)
        else:
            self._log("Could not get server time or time is up. Falling back to 8 PM check.", "warning")
            while not self.stop_event.is_set():
                now = datetime.now()
                if now.hour >= 20:
                    self._log("It's 20:00! Applying now!", 'warning'); break
                remaining = (now.replace(hour=20, minute=0, second=0) - now).seconds
                self._log(f"Waiting (fallback)... T-minus {remaining} seconds.")
                time.sleep(1)

        if self.stop_event.is_set(): self._log("Stop command received during wait."); return

        success_count = 0
        tabs_to_process = [h for h in self.driver.window_handles if h != original_window]
        
        MAX_REFRESH_ATTEMPTS = 15

        for i, handle in enumerate(tabs_to_process):
            self.driver.switch_to.window(handle)
            match = re.search(r'/(\d+)$', self.driver.current_url)
            lid = match.group(1) if match else "unknown"

            self._log(f"({lid}) Checking if page is ready...")
            for attempt in range(MAX_REFRESH_ATTEMPTS):
                try:
                    self.driver.find_element(*CANT_APPLY_YET_SELECTOR)
                    self._log(f"({lid}) Attempt {attempt+1}: Not ready yet. Refreshing...", 'warning')
                    time.sleep(0.2); self.driver.refresh()
                except NoSuchElementException:
                    self._log(f"({lid}) Page is now live! Proceeding to apply.")
                    break
            else:
                 self._log(f"({lid}) Page did not become ready after {MAX_REFRESH_ATTEMPTS} attempts.", 'error')

            self._log(f"({i+1}/{len(tabs_to_process)}) Attempting to click apply on listing {lid}...")
            try:
                final_button = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable(FINAL_APPLY_BUTTON_SELECTOR))
                final_button.click(); time.sleep(0.5)
                self._log(f"Successfully applied to listing {lid}.")
                success_count += 1
            except Exception as e:
                self._log(f"FAILED to apply to listing {lid}: {e}", level='error')

        self._log("Closing application tabs...")
        for handle in tabs_to_process:
            self.driver.switch_to.window(handle); self.driver.close()
        self.driver.switch_to.window(original_window)
        self._log(f"Finished. Applied to {success_count} of {len(listing_ids)}.")
        return success_count

    def quit(self):
        self._log("Shutting down bot instance...")
        self.stop_event.set()
        if self.driver:
            try: self.driver.quit()
            except WebDriverException: pass
        self.driver = None; self.is_logged_in = False

    def _parse_price(self, price_text: str) -> float:
        if not price_text: return 0.0
        return float(re.sub(r'[^\d,]', '', price_text).replace(',', '.'))
    def _parse_publ_date(self, date_str: str):
        try: return datetime.strptime(date_str, "%B %d, %Y %H:%M:%S")
        except (ValueError, TypeError): return None

    def discover_listings_api(self) -> List[Dict[str, Any]]:
        if not self.is_logged_in: self._log("Not logged in.", 'error'); return []
        self._log("Discovering listings...")
        try:
            today_str = datetime.now().strftime("%Y-%m-%d"); payload = { "woonwens": { "Kenmerken": [{"waarde": "1", "geenVoorkeur": False, "kenmerkType": "24", "name": "objecttype"}], "BerekendDatumTijd": today_str }, "paginaNummer": 1, "paginaGrootte": 100, "filterMode": "AlleenNieuwVandaag" }
            response = self.session.post(API_DISCOVERY_URL, json=payload, timeout=15); response.raise_for_status()
            results = response.json().get('d', {}).get('resultaten', [])
            if not results: self._log("API returned no new listings."); return []
            listing_ids = [str(r['FrontendAdvertentieId']) for r in results if r.get('FrontendAdvertentieId')]
            self._log(f"Found {len(listing_ids)} IDs. Fetching details...")
        except requests.RequestException as e: self._log(f"API Error (Discovery): {e}", level='error'); return []
        processed_listings = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {executor.submit(self.get_listing_details, lid): lid for lid in listing_ids}
            for future in as_completed(future_to_id):
                item = future.result()
                if item:
                    # *** MODIFIED: More detailed status logic ***
                    now = datetime.now()
                    publ_start_dt = self._parse_publ_date(item.get('publstart'))
                    is_live = publ_start_dt and now >= publ_start_dt
                    
                    is_in_selectable_window = now.hour >= 18
                    can_be_selected = is_live or (is_in_selectable_window and not is_live)
                    
                    status_text = "LIVE"
                    if not is_live:
                        start_time_str = publ_start_dt.strftime('%H:%M') if publ_start_dt else "20:00"
                        if is_in_selectable_window:
                            status_text = f"SELECTABLE ({start_time_str})"
                        else:
                            status_text = f"PREVIEW ({start_time_str})"

                    main_photo = next((m for m in item.get('media', []) if m.get('type') == 'StraatFoto'), None)
                    image_url = f"https:{main_photo['fotoviewer']}" if main_photo and main_photo.get('fotoviewer') else None
                    
                    processed_listings.append({
                        'id': item.get('id'), 'address': f"{item.get('straat', '')} {item.get('huisnummer', '')}",
                        'type': item.get('objecttype', 'N/A'), 'price_str': f"€ {item.get('kalehuur', '0,00')}",
                        'price_float': self._parse_price(item.get('kalehuur', '')), 
                        'status_text': status_text,
                        'is_selectable': can_be_selected,
                        'image_url': image_url,
                    })
        self._log(f"Processed {len(processed_listings)} listings."); return sorted(processed_listings, key=lambda x: x['price_float'])
        
    def get_listing_details(self, listing_id: str):
        payload = {"Id": listing_id, "VolgendeId": 0, "Filters": "gebruik!=Complex|nieuwab==True", "inschrijfnummerTekst": "", "Volgorde": "", "hash": ""}
        try: response = self.session.post(API_DETAILS_SINGLE_URL, json=payload, timeout=10); response.raise_for_status(); return response.json().get('d', {}).get('Aanbod')
        except requests.RequestException: return None