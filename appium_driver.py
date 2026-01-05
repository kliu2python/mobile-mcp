from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.options.ios import XCUITestOptions

_driver = None

def start_session(platform: str, server_url: str, caps: dict):
    global _driver
    if _driver:
        return _driver
    if platform.lower() == "android":
        options = UiAutomator2Options().load_capabilities(caps)
    else:
        options = XCUITestOptions().load_capabilities(caps)
    _driver = webdriver.Remote(server_url, options=options)
    return _driver

def get_driver():
    if not _driver:
        raise RuntimeError("Appium session not started")
    return _driver

def stop_session():
    global _driver
    if _driver:
        _driver.quit()
        _driver = None
