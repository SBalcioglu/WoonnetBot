# -*- coding: utf-8 -*-
"""
WoonnetBot Core Logic
---------------------
This module contains the WoonnetBot class, which encapsulates all interactions
with the WoonnetRijnmond website, including browser control via Selenium,
session management with requests, and API interactions for discovering and
applying to listings.
"""

import time
import re
import sys
import os
import threading
import requests
import logging
from datetime import datetime
from queue import Queue
from typing import List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException

# Only import webdriver_manager if not running as a frozen executable
if not getattr(sys, 'frozen', False):
    from webdriver_manager.chrome import ChromeDriverManager

from config import (
    BASE_URL, LOGIN_URL, DISCOVERY_URL, API_DISCOVERY_URL, API_DETAILS_SINGLE_URL,
    API_TIMER_URL, USERNAME_FIELD_SELECTOR, PASSWORD_FIELD_SELECTOR,
    LOGIN_BUTTON_SELECTOR, LOGOUT_LINK_SELECTOR
)


class WoonnetBot:
    """
    Manages all automated interactions with the WoonnetRijnmond website.
    """
    def __init__(self, status_queue: Queue, logger: logging.Logger):
        """
        Initializes the WoonnetBot instance.

        Args:
            status_queue (Queue): A queue to send status messages to the GUI.
            logger (logging.Logger): The logger instance for file/console logging.
        """
        self.driver: webdriver.Chrome | None = None
        self.status_queue = status_queue
        self.logger = logger
        self.stop_event = threading.Event()
        self.session = requests.Session()
        self.is_logged_in = False

        if getattr(sys, 'frozen', False):
            driver_path = os.path.join(sys._MEIPASS, "chromedriver.exe") # type: ignore
            self.service = ChromeService(executable_path=driver_path)
            self._log(f"Bundle mode: Using chromedriver from {driver_path}")
        else:
            self.service = ChromeService(ChromeDriverManager().install()) # type: ignore
            self._log("Script mode: Using webdriver-manager.")

    def _log(self, message: str, level: str = 'info'):
        """
        Sends a log message to both the GUI status queue and the logger.
        """
        self.status_queue.put_nowait(message)
        getattr(self.logger, level, self.logger.info)(message)

    def start_headless_browser(self):
        """
        Initializes and starts the Selenium WebDriver instance.
        """
        if self.driver:
            self._log("Browser is already running.", "warning")
            return
        self._log("Starting browser...")
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")
        options.add_argument("--log-level=3")

        if getattr(sys, 'frozen', False):
            app_dir = os.path.join(os.environ['APPDATA'], 'WoonnetBot')
            os.makedirs(app_dir, exist_ok=True)
            options.add_argument(f"user-data-dir={os.path.join(app_dir, 'chrome_profile')}")
        try:
            self.driver = webdriver.Chrome(service=self.service, options=options)
            self._log("Browser started successfully.")
        except Exception as e:
            self._log(f"Failed to start browser: {e}", level='error')
            self.driver = None

    def login(self, username, password) -> Tuple[bool, requests.Session | None]:
        """
        Performs login using Selenium and transfers the session to requests.
        """
        if not self.driver:
            self._log("Browser not started.", 'error')
            return False, None
        self._log(f"Attempting to log in as {username}...")
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
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Content-Type': 'application/json; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Referer': DISCOVERY_URL,
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
            })
            self.is_logged_in = True
            return True, self.session
        except Exception as e:
            self._log(f"Login failed: {e}", level='error')
            self.is_logged_in = False
            return False, None

    def _get_server_countdown_seconds(self) -> float | None:
        """
        Fetches the official countdown time from the server's API.
        """
        self._log("Fetching precise countdown from server API...")
        try:
            response = self.session.get(API_TIMER_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            remaining_ms = int(data['resterendetijd'])
            if remaining_ms <= 0:
                self._log("Server countdown is zero or negative. Proceeding.", "warning")
                return 0.0
            seconds = remaining_ms / 1000.0
            self._log(f"Success! Server countdown: {seconds:.2f} seconds.")
            return seconds
        except requests.RequestException as e:
            self._log(f"API Error (Timer): Could not get official time. {e}", "error")
            return None
        except (KeyError, ValueError, TypeError) as e:
            self._log(f"API Error (Timer): Could not parse server response. {e}", "error")
            return None

    def apply_to_listings(self, listing_ids: List[str]):
        """
        Applies to a list of properties by sending direct POST requests in parallel.
        This provides a significant speed advantage over sequential applications.

        Args:
            listing_ids (List[str]): A list of advertisement IDs to apply for.
        """
        if not self.is_logged_in or not self.session:
            self._log("Not logged in. Please log in before applying.", 'error')
            return

        # --- The timing and countdown logic remains the same ---
        self._log("Waiting for the application window to open...")
        remaining_seconds = self._get_server_countdown_seconds()
        if remaining_seconds is not None and remaining_seconds > 0:
            start_time = time.monotonic()
            while not self.stop_event.is_set():
                elapsed = time.monotonic() - start_time
                if elapsed >= remaining_seconds: break
                time_left = remaining_seconds - elapsed
                mins, secs = divmod(time_left, 60)
                hours, mins = divmod(mins, 60)
                timer_display = f"{int(hours):02}:{int(mins):02}:{int(secs):02}"
                self._log(f"Waiting for server... T-minus {timer_display}")
                time.sleep(1)
        else:
            self._log("Could not get server time or time is up. Falling back to 8 PM check.", "warning")
            while not self.stop_event.is_set():
                if datetime.now().hour >= 20: break
                self._log(f"Waiting for 8:00 PM... Current time: {datetime.now().strftime('%H:%M:%S')}")
                time.sleep(1)

        if self.stop_event.is_set():
            self._log("Stop command received during wait. Aborting application.", "warning")
            return

        self._log("Application window is open! Applying to all selected listings IN PARALLEL...", 'warning')
        
        # --- PARALLEL APPLICATION LOGIC ---
        
        def _apply_task(listing_id: str) -> bool:
            """This is the worker function that applies to a single listing.
            It will be executed in a separate thread for each selected listing."""
            
            apply_url = f"{BASE_URL}/reageren/{listing_id}"
            try:
                # The shared self.session is thread-safe for this use case.
                page_res = self.session.get(apply_url, timeout=15)
                soup = BeautifulSoup(page_res.text, 'html.parser')
                
                form_button = soup.find('button', {'name': 'Command', 'value': 'plaats-einkomen'})
                if not form_button or not (form_element := form_button.find_parent('form')):
                    self._log(f"({listing_id}) FAILED: Application form not found.", 'error')
                    return False

                payload = {tag.get('name'): tag.get('value', '') for tag in form_element.find_all('input') if tag.get('name')}
                payload['Command'] = 'plaats-einkomen'

                if '__RequestVerificationToken' not in payload:
                    self._log(f"({listing_id}) FAILED: Security token not found.", 'error')
                    return False

                submit_res = self.session.post(apply_url, data=payload, headers={'Referer': apply_url})
                
                if "Wij hebben uw reactie verwerkt" in submit_res.text or "U heeft al gereageerd" in submit_res.text:
                    self._log(f"SUCCESS! Applied to listing {listing_id}.", 'info')
                    return True
                else:
                    self._log(f"({listing_id}) FAILED: Success message not found in response.", 'error')
                    return False
            except Exception as e:
                self._log(f"({listing_id}) FAILED: An unexpected error occurred: {e}", 'error')
                return False

        # Use a ThreadPoolExecutor to run all the _apply_task functions concurrently.
        success_count = 0
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Submit all tasks to the pool at once
            future_to_id = {executor.submit(_apply_task, lid): lid for lid in listing_ids}
            
            # Process results as they complete
            for future in as_completed(future_to_id):
                if future.result():  # future.result() returns True or False from _apply_task
                    success_count += 1
    
        self._log(f"Finished. Applied to {success_count} of {len(listing_ids)} selected listings.")

    def quit(self):
        """
        Safely shuts down the bot, closing the browser and stopping threads.
        """
        self._log("Shutting down bot instance...")
        self.stop_event.set()
        if self.driver:
            try:
                self.driver.quit()
            except WebDriverException:
                pass
        self.driver = None
        self.is_logged_in = False

    def _parse_price(self, price_text: str) -> float:
        """Utility to convert a formatted price string to a float."""
        if not price_text: return 0.0
        return float(re.sub(r'[^\d,]', '', price_text).replace(',', '.'))

    def _parse_publ_date(self, date_str: str | None) -> datetime | None:
        """Utility to parse a publication date string into a datetime object."""
        if not date_str: return None
        try: return datetime.strptime(date_str, "%B %d, %Y %H:%M:%S")
        except (ValueError, TypeError): return None

    def discover_listings_api(self) -> List[Dict[str, Any]]:
        """
        Discovers new listings for the day using the website's internal API.
        """
        if not self.is_logged_in:
            self._log("Not logged in.", 'error')
            return []
        self._log("Discovering listings via API...")
        try:
            payload = {"woonwens": {"Kenmerken": [{"waarde": "1", "geenVoorkeur": False, "kenmerkType": "24", "name": "objecttype"}], "BerekendDatumTijd": datetime.now().strftime("%Y-%m-%d")}, "paginaNummer": 1, "paginaGrootte": 100, "filterMode": "AlleenNieuwVandaag"}
            response = self.session.post(API_DISCOVERY_URL, json=payload, timeout=15)
            response.raise_for_status()
            results = response.json().get('d', {}).get('resultaten', [])
            if not results:
                self._log("API returned no new listings.")
                return []
            listing_ids = [str(r['FrontendAdvertentieId']) for r in results if r.get('FrontendAdvertentieId')]
            self._log(f"Found {len(listing_ids)} IDs. Fetching details concurrently...")
        except requests.RequestException as e:
            self._log(f"API Error (Discovery): {e}", level='error')
            return []

        processed_listings = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_id = {executor.submit(self.get_listing_details, lid): lid for lid in listing_ids}
            for future in as_completed(future_to_id):
                item = future.result()
                if not item: continue
                now = datetime.now()
                publ_start_dt = self._parse_publ_date(item.get('publstart'))
                is_live = publ_start_dt and now >= publ_start_dt
                is_in_selectable_window = now.hour >= 18
                if is_live:
                    status_text = "LIVE"
                else:
                    start_time_str = publ_start_dt.strftime('%H:%M') if publ_start_dt else "20:00"
                    status_text = f"SELECTABLE ({start_time_str})" if is_in_selectable_window else f"PREVIEW ({start_time_str})"
                can_be_selected = is_live or is_in_selectable_window
                main_photo = next((m for m in item.get('media', []) if m.get('type') == 'StraatFoto'), None)
                image_url = f"https:{main_photo['fotoviewer']}" if main_photo and main_photo.get('fotoviewer') else None
                processed_listings.append({'id': item.get('id'),'address': f"{item.get('straat', '')} {item.get('huisnummer', '')}",'type': item.get('objecttype', 'N/A'),'price_str': f"€ {item.get('kalehuur', '0,00')}",'price_float': self._parse_price(item.get('kalehuur', '')),'status_text': status_text,'is_selectable': can_be_selected,'image_url': image_url})
        self._log(f"Processed {len(processed_listings)} listings.")
        return sorted(processed_listings, key=lambda x: x['price_float'])

    def get_listing_details(self, listing_id: str) -> Dict | None:
        """
        Fetches detailed information for a single listing via API.
        """
        payload = {"Id": listing_id, "VolgendeId": 0, "Filters": "gebruik!=Complex|nieuwab==True", "inschrijfnummerTekst": "", "Volgorde": "", "hash": ""}
        try:
            response = self.session.post(API_DETAILS_SINGLE_URL, json=payload, timeout=10)
            response.raise_for_status()
            return response.json().get('d', {}).get('Aanbod')
        except requests.RequestException:
            return None