import time
import hashlib
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    ElementNotInteractableException
)

RETRYABLE = (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    ElementNotInteractableException,
)

def hash_xml(xml: str) -> str:
    return hashlib.md5(xml.encode("utf-8")).hexdigest()

def wait_for_element(driver, by, value, timeout=10, poll=0.5):
    end = time.time() + timeout
    last_exc = None
    while time.time() < end:
        try:
            el = driver.find_element(by, value)
            if el.is_displayed() and el.is_enabled():
                return el
        except RETRYABLE as e:
            last_exc = e
        time.sleep(poll)
    raise TimeoutException(f"Element not ready: {by}={value}") from last_exc

def wait_for_ui_change(driver, old_xml_hash, timeout=5, poll=0.5):
    end = time.time() + timeout
    while time.time() < end:
        if hash_xml(driver.page_source) != old_xml_hash:
            return True
        time.sleep(poll)
    return False
