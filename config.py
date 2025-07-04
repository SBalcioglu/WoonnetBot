# --- URLS ---
BASE_URL = "https://www.woonnetrijnmond.nl"
LOGIN_URL = f"{BASE_URL}/inloggeninschrijven/"
DISCOVERY_URL = f"{BASE_URL}/nieuw-aanbod/"

# --- API ENDPOINTS ---
API_DISCOVERY_URL = "https://www.woonnetrijnmond.nl/wsWoonnetRijnmond/Woonwensen/wsWoonwensen.asmx/GetWoonwensResultatenVoorPagina"
API_DETAILS_SINGLE_URL = "https://www.woonnetrijnmond.nl/wsWoonnetRijnmond/WoningenModule/Service.asmx/getAanbodEnVolgendeViaId"


# --- SELECTORS ---
from selenium.webdriver.common.by import By

USERNAME_FIELD_SELECTOR = (By.ID, "username")
PASSWORD_FIELD_SELECTOR = (By.ID, "password")
LOGIN_BUTTON_SELECTOR = (By.XPATH, "//a[contains(@class, 'js-submit-button') and contains(text(), 'Inloggen')]")
LOGOUT_LINK_SELECTOR = (By.PARTIAL_LINK_TEXT, "Uitloggen")

# *** NEW: Selector for the "can't apply yet" warning message ***
CANT_APPLY_YET_SELECTOR = (By.CSS_SELECTOR, "div.msg.msg--red")
FINAL_APPLY_BUTTON_SELECTOR = (By.XPATH, "//button[@name='Command' and (@value='plaats-einkomen' or @value='plaats')]")