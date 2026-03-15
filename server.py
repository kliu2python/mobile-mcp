from pathlib import Path
import os
import base64
from io import BytesIO
import time

from PIL import Image

from mcp.server.fastmcp import FastMCP
from appium_driver import (
    start_session,
    get_driver,
    stop_session
)
from appium_config import load_profiles, get_profile, AppiumConfigError
from utils import (
    resize_image,
    get_current_timestamp,
    scale_bounds,
    parse_ios_xml,
    get_focused_element_id
)
from waiter import wait_for_element
from actions import execute_with_retry


mcp = FastMCP("appium-stdio-mcp")
LAST_UI_TREE = None


def collect_artifacts(driver):
    png = driver.get_screenshot_as_png()
    xml = driver.page_source
    img = Image.open(BytesIO(png))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return {
        "screenshot_base64": base64.b64encode(buf.getvalue()).decode(),
        "page_source_xml": xml
    }

def get_bounds_by_element_id(element_id):
    if not LAST_UI_TREE:
        return None

    for el in LAST_UI_TREE["elements"]:
        if el["id"] == element_id:
            return el["bounds"]

    return None

@mcp.tool()
def list_appium_profiles(config_path: str | None = None):
    """List available Appium profiles from config file."""
    try:
        profiles = load_profiles(config_path=config_path)
        return {
            "status": "ok",
            "profiles": sorted(profiles.keys()),
        }
    except AppiumConfigError as e:
        return {"status": "failed", "reason": str(e)}

@mcp.tool()
def start_appium_session_with_profile(
    profile_name: str,
    config_path: str | None = None,
    capabilities_override: dict | None = None,
):
    """Start session from named profile, with optional capability overrides."""
    try:
        profile = get_profile(profile_name, config_path=config_path)
    except AppiumConfigError as e:
        return {"status": "failed", "reason": str(e)}

    capabilities = dict(profile["capabilities"])
    if capabilities_override:
        capabilities.update(capabilities_override)

    start_session(profile["platform"], profile["server_url"], capabilities)
    return {
        "status": "ok",
        "profile": profile_name,
        "platform": profile["platform"],
        "server_url": profile["server_url"],
    }


@mcp.tool()
def start_default_ios_appium_session(config_path: str | None = None):
    profile_name = os.getenv("APPIUM_MCP_DEFAULT_IOS_PROFILE", "ios-local")
    return start_appium_session_with_profile(profile_name, config_path=config_path)


@mcp.tool()
def start_default_android_appium_session(config_path: str | None = None):
    profile_name = os.getenv("APPIUM_MCP_DEFAULT_ANDROID_PROFILE", "android-local")
    return start_appium_session_with_profile(profile_name, config_path=config_path)

@mcp.tool()
def start_appium_session(platform: str, server_url: str, capabilities: dict):
    start_session(platform, server_url, capabilities)
    return {"status": "ok", "platform": platform, "server_url": server_url}

@mcp.tool()
def stop_appium_session():
    stop_session()
    return {"status": "ok"}

@mcp.tool()
def get_screenshot(region: str = "full"):
    driver = get_driver()
    ts = get_current_timestamp()
    focused_id = LAST_UI_TREE.get("focused") if LAST_UI_TREE else None

    base_dir = Path(__file__).resolve().parent
    out_dir = base_dir / "screenshots"
    out_dir.mkdir(exist_ok=True)

    png_bytes = driver.get_screenshot_as_png()
    img = Image.open(BytesIO(png_bytes))

    if region == "focused":
        bounds = get_bounds_by_element_id(focused_id)

        if bounds:
            bounds = scale_bounds(
                bounds,
                img.size,
                (LAST_UI_TREE["ui_width"], LAST_UI_TREE["ui_height"])
            )
            img = img.crop(bounds)
        else:
            region = "full"  # fallback: do not fail when no focused node is available

    img = resize_image(img, max_long=768, max_short=384)

    path = out_dir / f"{region}_{ts}.jpg"
    img.save(path, "JPEG", quality=60, optimize=True)

    return {
        "type": "image_ref",
        "region": region,
        "path": str(path),
        "width": img.width,
        "height": img.height,
        "focused_element_id": focused_id
    }

@mcp.tool()
def get_ui_tree():
    global LAST_UI_TREE

    driver = get_driver()
    source = driver.page_source  # XML

    elements, ui_w, ui_h = parse_ios_xml(source)  # currently iOS-oriented parser
    focused = get_focused_element_id(elements)

    LAST_UI_TREE = {
        "focused": focused,
        "elements": elements,
        "ui_width": ui_w,
        "ui_height": ui_h,
    }

    return {
        "platform": "ios",
        "focused_element_id": focused,
        "elements": elements
    }

@mcp.tool()
def tap(by: str, value: str):
    d = get_driver()
    def action():
        el = wait_for_element(d, by, value)
        el.click()
    meta = execute_with_retry(d, action)
    return {
        "action": "tap",
        "locator": f"{by}={value}",
        "meta": meta,
        **collect_artifacts(d)
    }

@mcp.tool()
def tap_element(element_id: str):
    bounds = get_bounds_by_element_id(element_id)
    if not bounds:
        return {"status": "failed", "reason": "element not found"}

    x1, y1, x2, y2 = bounds
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2

    driver = get_driver()
    driver.tap([(cx, cy)])

    return {
        "status": "ok",
        "element_id": element_id,
        "tap_point": [cx, cy]
    }

@mcp.tool()
def launch_app(
    platform: str,
    bundle_id: str | None = None,
    app_package: str | None = None,
    activity: str | None = None,
):
    """
    Launch an app by bundleId (iOS) or package/activity (Android)
    """
    driver = get_driver()

    if platform == "ios":
        if not bundle_id:
            return {"status": "failed", "reason": "bundle_id required for iOS"}
        driver.activate_app(bundle_id)

    elif platform == "android":
        if not app_package:
            return {"status": "failed", "reason": "app_package required for Android"}
        if activity:
            driver.start_activity(app_package, activity)
        else:
            driver.activate_app(app_package)

    else:
        return {"status": "failed", "reason": "unknown platform"}

    return {
        "status": "ok",
        "platform": platform,
        "bundle_id": bundle_id,
        "app_package": app_package,
    }

@mcp.tool()
def terminate_app(platform: str, bundle_id: str = None, app_package: str = None):
    driver = get_driver()

    if platform == "ios" and bundle_id:
        driver.terminate_app(bundle_id)
    elif platform == "android" and app_package:
        driver.terminate_app(app_package)
    else:
        return {"status": "failed", "reason": "missing app id"}

    return {"status": "ok"}

@mcp.tool()
def type_text(text: str, clear: bool = True):
    driver = get_driver()

    try:
        el = driver.switch_to.active_element
        if clear:
            el.clear()
        el.send_keys(text)
    except Exception:
        return {"status": "failed", "reason": "no active input"}

    return {
        "status": "ok",
        "text": text,
    }

@mcp.tool()
def swipe(direction: str, distance: float = 0.6):
    """
    direction: up | down | left | right
    distance: percentage of screen
    """
    driver = get_driver()
    size = driver.get_window_size()

    w, h = size["width"], size["height"]
    cx, cy = w // 2, h // 2

    dx = dy = 0
    if direction == "up":
        dy = -int(h * distance)
    elif direction == "down":
        dy = int(h * distance)
    elif direction == "left":
        dx = -int(w * distance)
    elif direction == "right":
        dx = int(w * distance)
    else:
        return {"status": "failed", "reason": "invalid direction"}

    driver.swipe(cx, cy, cx + dx, cy + dy, 300)

    return {
        "status": "ok",
        "direction": direction,
        "distance": distance,
    }

@mcp.tool()
def scroll_until_text(text: str, max_swipes: int = 5):
    for _ in range(max_swipes):
        tree = get_ui_tree()
        for el in tree["elements"]:
            if text.lower() in el["label"].lower():
                return {
                    "status": "found",
                    "element_id": el["id"],
                }
        swipe("up", 0.5)

    return {"status": "not_found", "text": text}


@mcp.tool()
def assert_element_visible(label: str):
    tree = get_ui_tree()
    for el in tree["elements"]:
        if label.lower() in el["label"].lower() and el["visible"]:
            return {"status": "ok", "element_id": el["id"]}

    return {"status": "failed", "reason": "not visible"}

@mcp.tool()
def wait_for_text(text: str, timeout: int = 10):
    start = time.time()
    while time.time() - start < timeout:
        tree = get_ui_tree()
        for el in tree["elements"]:
            if text.lower() in el["label"].lower():
                return {"status": "ok", "element_id": el["id"]}
        time.sleep(1)

    return {"status": "timeout", "text": text}



if __name__ == "__main__":
    mcp.run()
