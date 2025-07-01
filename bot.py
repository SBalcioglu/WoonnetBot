
import time
import re
import sys
import os
from datetime import datetime
from queue import Queue

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Import configuration
from config import (
    BASE_URL, LOGIN_URL, DISCOVERY_URL,
    USERNAME_FIELD_SELECTOR, PASSWORD_FIELD_SELECTOR, LOGIN_BUTTON_SELECTOR,
    LOGOUT_LINK_SELECTOR, PRIORITY_LISTING_SELECTOR, LINK_SELECTOR,
    PRICE_SELECTOR, FINAL_APPLY_BUTTON_SELECTOR, NEW_OFFER_TITLE_SELECTOR
)

class WoonnetBot:
    """Encapsulates the bot's logic for interacting with the WoonnetRijnmond website."""

    def __init__(self, status_queue: Queue):
        self.driver = None
        self.status_queue = status_queue
        self.service = ChromeService(ChromeDriverManager().install())

    def _log(self, message):
        """Puts a message into the status queue for the GUI to display."""
        self.status_queue.put(message)

    def _parse_price(self, price_text):
        """Cleans and converts a price string to a float."""
        cleaned_price = re.sub(r'[^\d,]', '', price_text)
        return float(cleaned_price.replace(',', '.'))

    def login(self, username, password):
        """Initializes the webdriver and logs into the website."""
        self._log("Initializing WebDriver...")
        # Check if running as a bundled exe and set user data dir
        if getattr(sys, 'frozen', False):
            app_dir = os.path.join(os.environ['APPDATA'], 'WoonnetBot')
            os.makedirs(app_dir, exist_ok=True)
            options = webdriver.ChromeOptions()
            options.add_argument(f"user-data-dir={os.path.join(app_dir, 'chrome_profile')}")
        else:
            options = None # Use default profile behavior when running as script

        self.driver = webdriver.Chrome(service=self.service, options=options)
        self._log(f"Attempting to log in as {username}...")
        
        try:
            self.driver.get(LOGIN_URL)
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(USERNAME_FIELD_SELECTOR)).send_keys(username)
            self.driver.find_element(*PASSWORD_FIELD_SELECTOR).send_keys(password)
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(LOGIN_BUTTON_SELECTOR)).click()
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located(LOGOUT_LINK_SELECTOR))
            self._log("Login successful.")
            return True
        except TimeoutException:
            self._log("Login FAILED. Check credentials or website status.")
            return False
        except Exception as e:
            self._log(f"An unexpected login error occurred: {e}")
            return False

    def discover_and_sort_listings(self):
        """Discovers priority listings and sorts them by price."""
        assert self.driver is not None
        self._log("Navigating to discovery page...")
        self.driver.get(DISCOVERY_URL)
        
        try:
            # Check if the "Nog even geduld" message is present
            title_element = self.driver.find_element(*NEW_OFFER_TITLE_SELECTOR)
            if "Nog even geduld" in title_element.text:
                self._log("Listings are not available yet ('Nog even geduld').")
                return []
        except NoSuchElementException:
            # This is expected when listings are present
            pass

        try:
            self._log("Waiting for priority listings to appear...")
            WebDriverWait(self.driver, 15).until(EC.presence_of_all_elements_located(PRIORITY_LISTING_SELECTOR))
            priority_listings = self.driver.find_elements(*PRIORITY_LISTING_SELECTOR)
            self._log(f"Found {len(priority_listings)} priority listings.")
            
            targets = []
            for listing in priority_listings:
                try:
                    url = listing.find_element(*LINK_SELECTOR).get_attribute('href')
                    if url:
                        price_text = listing.find_element(*PRICE_SELECTOR).text
                        match = re.search(r'/(\d+)$', url)
                        if match:
                            targets.append({'id': match.group(1), 'price_float': self._parse_price(price_text)})
                except Exception as e:
                    self._log(f"Could not parse a listing, skipping. Error: {e}")

            return sorted(targets, key=lambda x: x['price_float'])
        except TimeoutException:
            self._log("No priority listings found within the time limit.")
            return []
        except Exception as e:
            self._log(f"An unexpected discovery error occurred: {e}")
            return []

    def apply_to_listings(self, targets, num_to_apply):
        """Applies to a given number of listings from the sorted list."""
        assert self.driver is not None
        if not targets:
            self._log("No targets to apply to.")
            return 0

        num_to_apply = min(num_to_apply, len(targets))
        self._log(f"Preparing to apply to the {num_to_apply} cheapest listings...")
        application_urls = [f"{BASE_URL}/reageren/{t['id']}" for t in targets[:num_to_apply]]

        original_window = self.driver.current_window_handle
        for i, url in enumerate(application_urls):
            self._log(f"Opening application page for listing {targets[i]['id']}...")
            if i > 0:
                self.driver.switch_to.new_window('tab')
            self.driver.get(url)

        success_count = 0
        # Iterate through all tabs to click the apply button
        for i, window_handle in enumerate(self.driver.window_handles):
            self.driver.switch_to.window(window_handle)
            listing_id = targets[i]['id']
            try:
                self._log(f"Attempting to apply on listing {listing_id}...")
                final_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(FINAL_APPLY_BUTTON_SELECTOR))
                final_button.click()
                # Add a small wait to confirm submission
                time.sleep(1) 
                self._log(f"Successfully applied to listing {listing_id}.")
                success_count += 1
            except TimeoutException:
                self._log(f"FAILED to apply to {listing_id}: Could not find apply button in time.")
            except Exception as e:
                self._log(f"FAILED to apply to {listing_id}: An error occurred: {e}")

        # Close all tabs except the original one
        for window_handle in self.driver.window_handles:
            if window_handle != original_window:
                self.driver.switch_to.window(window_handle)
                self.driver.close()
        self.driver.switch_to.window(original_window)

        self._log(f"Finished. Successfully applied to {success_count} of {num_to_apply} listings.")
        return success_count

    def run(self, username, password, use_max, num_to_apply):
        """Main logic for the 'Run Now' mode."""
        if not self.login(username, password):
            return
        
        sorted_targets = self.discover_and_sort_listings()
        if not sorted_targets:
            self._log("No listings found. Shutting down.")
            return

        if use_max:
            num_to_apply = len(sorted_targets)
        
        self.apply_to_listings(sorted_targets, num_to_apply)

    def run_scheduled(self, username, password, use_max, num_to_apply):
        """Main logic for the 'Run in Background' mode."""
        self._log("Scheduled mode started. Waiting for the 6-8 PM window.")
        if not self.login(username, password):
            return
            
        while True:
            now = datetime.now()
            if 18 <= now.hour < 20:
                self._log(f"It's {now.strftime('%H:%M')}. Within the application window. Checking for listings...")
                sorted_targets = self.discover_and_sort_listings()
                if sorted_targets:
                    if use_max:
                        num_to_apply = len(sorted_targets)
                    self.apply_to_listings(sorted_targets, num_to_apply)
                    self._log("Work is done for today. Shutting down.")
                    break
                else:
                    self._log("No listings yet. Will check again in 1 minute.")
                    time.sleep(60)
            elif now.hour >= 20:
                self._log("Application window has closed for today. Shutting down.")
                break
            else:
                self._log(f"It's {now.strftime('%H:%M')}. Outside of application window. Waiting...")
                time.sleep(300) # Wait 5 minutes

    def run_test(self, username, password, listing_id, actually_apply):
        """Applies to a single listing for testing purposes."""
        self._log(f"Test mode started for listing ID: {listing_id}")
        if not self.login(username, password):
            return

        assert self.driver is not None
        url = f"{BASE_URL}/reageren/{listing_id}"
        self._log(f"Navigating to test URL: {url}")
        self.driver.get(url)
        try:
            final_button = WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable(FINAL_APPLY_BUTTON_SELECTOR))
            self._log("Found the 'Apply' button.")
            if actually_apply:
                self._log("Executing click to apply...")
                final_button.click()
                time.sleep(3) # Wait for application to process
                self._log(f"Test application submitted for listing {listing_id}.")
            else:
                self._log("Test successful. 'Apply' button was found but not clicked as requested.")
        except Exception as e:
            self._log(f"Test FAILED for listing {listing_id}: {e}")

    def quit(self):
        """Closes the webdriver."""
        if self.driver:
            self._log("Shutting down WebDriver.")
            self.driver.quit()
