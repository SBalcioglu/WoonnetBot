# --- URLS ---
BASE_URL = "https://www.woonnetrijnmond.nl"
LOGIN_URL = f"{BASE_URL}/inloggeninschrijven/"
DISCOVERY_URL = f"{BASE_URL}/nieuw-aanbod/"

# --- SELECTORS ---
from selenium.webdriver.common.by import By

USERNAME_FIELD_SELECTOR = (By.ID, "username")
PASSWORD_FIELD_SELECTOR = (By.ID, "password")
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//a[contains(@class, 'js-submit-button') and contains(text(), 'Inloggen')]")
LOGOUT_LINK_SELECTOR = (By.PARTIAL_LINK_TEXT, "Uitloggen")
PRIORITY_LISTING_SELECTOR = (By.CSS_SELECTOR, 'div.box[data-passendheid="voorrang"]')
LINK_SELECTOR = (By.TAG_NAME, "a")
PRICE_SELECTOR = (By.CSS_SELECTOR, "div.box--obj__price")
FINAL_APPLY_BUTTON_SELECTOR = (By.XPATH, "//button[@name='Command' and @value='plaats-einkomen']")
NEW_OFFER_TITLE_SELECTOR = (By.CSS_SELECTOR, "h2.nieuw-aanbod-geduld__title")
