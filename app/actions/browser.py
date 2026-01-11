from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


@dataclass
class BrowserOptions:
    headless: bool = False
    user_data_dir: Optional[str] = None
    profile_dir: Optional[str] = None


class BrowserController:
    def __init__(self) -> None:
        self._driver: Optional[webdriver.Chrome] = None
        self._options: Optional[BrowserOptions] = None

    def ensure_driver(self, options: BrowserOptions) -> webdriver.Chrome:
        if self._driver:
            return self._driver
        chrome_options = webdriver.ChromeOptions()
        if options.headless:
            chrome_options.add_argument("--headless=new")
        if options.user_data_dir:
            chrome_options.add_argument(f"--user-data-dir={options.user_data_dir}")
        if options.profile_dir:
            chrome_options.add_argument(f"--profile-directory={options.profile_dir}")
        service = Service(ChromeDriverManager().install())
        self._driver = webdriver.Chrome(service=service, options=chrome_options)
        self._options = options
        return self._driver

    def open_url(self, url: str, options: BrowserOptions) -> None:
        driver = self.ensure_driver(options)
        driver.get(url)

    def click_selector(self, selector: str, by: str = "css") -> None:
        driver = self._require_driver()
        element = driver.find_element(self._resolve_by(by), selector)
        element.click()

    def type_selector(self, selector: str, text: str, clear_first: bool = True, by: str = "css") -> None:
        driver = self._require_driver()
        element = driver.find_element(self._resolve_by(by), selector)
        if clear_first:
            element.clear()
        element.send_keys(text)

    def wait_selector(self, selector: str, timeout_s: int = 10, by: str = "css") -> None:
        driver = self._require_driver()
        wait = WebDriverWait(driver, timeout_s)
        wait.until(EC.presence_of_element_located((self._resolve_by(by), selector)))

    def press_keys(self, keys: list[str]) -> None:
        driver = self._require_driver()
        resolved_keys = [self._resolve_key(item) for item in keys]
        ActionChains(driver).send_keys(*resolved_keys).perform()

    def close(self) -> None:
        if self._driver:
            self._driver.quit()
            self._driver = None
            self._options = None

    def _require_driver(self) -> webdriver.Chrome:
        if not self._driver:
            raise RuntimeError("浏览器尚未启动，请先使用浏览器打开动作。")
        return self._driver

    def _resolve_by(self, by: str) -> str:
        mapping = {
            "css": By.CSS_SELECTOR,
            "xpath": By.XPATH,
            "id": By.ID,
            "name": By.NAME,
        }
        return mapping.get(by, By.CSS_SELECTOR)

    def _resolve_key(self, key: str) -> str:
        key_upper = key.strip().upper()
        if hasattr(Keys, key_upper):
            return getattr(Keys, key_upper)
        return key

    def shutdown(self) -> None:
        self.close()
