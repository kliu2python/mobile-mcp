import time
from waiter import wait_for_ui_change, hash_xml, RETRYABLE
from selenium.common.exceptions import WebDriverException

def execute_with_retry(driver, action_fn, max_retry=3):
    last_error = None
    for attempt in range(1, max_retry + 1):
        try:
            before_hash = hash_xml(driver.page_source)
            action_fn()
            ui_changed = wait_for_ui_change(driver, before_hash)
            return {
                "success": True,
                "attempt": attempt,
                "ui_changed": ui_changed
            }
        except RETRYABLE as e:
            last_error = e
            time.sleep(0.5 * attempt)
        except WebDriverException as e:
            last_error = e
            break
    return {
        "success": False,
        "error": str(last_error),
        "attempts": max_retry
    }
