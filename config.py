# config.py
from selenium.webdriver.common.by import By

# --- URLS ---
BASE_URL = "https://www.woonnetrijnmond.nl"
LOGIN_URL = f"{BASE_URL}/inloggeninschrijven/"
DISCOVERY_URL = f"{BASE_URL}/nieuw-aanbod/"

# --- API ENDPOINTS ---
API_DISCOVERY_URL = "https://www.woonnetrijnmond.nl/wsWoonnetRijnmond/Woonwensen/wsWoonwensen.asmx/GetWoonwensResultatenVoorPagina"
API_DISCOVERY_ALL_URL = "https://www.woonnetrijnmond.nl/wsWoonnetRijnmond/Woonwensen/wsWoonwensen.asmx/GetWoonwensResultatenVoorPaginaByInschrijfnummer"  # NEW: All actuele + upcoming listings for account
API_DETAILS_SINGLE_URL = "https://www.woonnetrijnmond.nl/wsWoonnetRijnmond/WoningenModule/Service.asmx/getAanbodEnVolgendeViaId"
API_TIMER_URL = "https://www.woonnetrijnmond.nl/Umbraco/api/SqlServerTime/GetTijdTotNieuwAanbod"

# --- TIMING CONFIG --- # NEW
PRE_SELECTION_HOUR = 18
PRE_SELECTION_MINUTE = 0
FINAL_REFRESH_HOUR = 19
FINAL_REFRESH_MINUTE = 55
APPLICATION_HOUR = 20

# --- SELECTORS ---
USERNAME_FIELD_SELECTOR = (By.ID, "username")
PASSWORD_FIELD_SELECTOR = (By.ID, "password")
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//a[contains(@class, 'js-submit-button') and contains(text(), 'Inloggen')]")
LOGOUT_LINK_SELECTOR = (By.PARTIAL_LINK_TEXT, "Uitloggen")

# --- USER AGENT --- # NEW
# A more modern and generic user agent
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36'