import time
from time import sleep
from io import BytesIO
import base64

from appium import webdriver
from PIL import Image
import xml.etree.ElementTree as ET
import yaml


def resize_image(img, max_long=768, max_short=384):
    w, h = img.size
    scale = min(max_long / max(w, h), max_short / min(w, h), 1.0)
    return img.resize((int(w * scale), int(h * scale)))


def prepare_llm_screenshot(img):
    img = resize_image(img, max_long=768, max_short=384)
    img = crop_center(img, ratio=0.7)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=60, optimize=True)

    return base64.b64encode(buf.getvalue()).decode()

def crop_center(img, ratio=0.6):
    w, h = img.size
    cw, ch = int(w * ratio), int(h * ratio)
    left = (w - cw) // 2
    top = (h - ch) // 2
    return img.crop((left, top, left + cw, top + ch))

def format_image(image_path, output_path):
    # Open an image file
    with Image.open(image_path) as img:
        width, height = img.size

        new_img = Image.new("RGB", (width, height), "white")
        new_img.paste(img)

        resize_image(new_img).save(output_path)


def write_to_file(file_path, string_to_write):
    with open(file_path, "w") as file:
        file.write(string_to_write)
    return file_path


def write_to_file_with_line_filter(file_path, string_to_write, filter):
    filtered_lines = [
        line.strip() for line in string_to_write.split("\n") if filter in line
    ]
    with open(file_path, "w") as file:
        file.write("\n".join(filtered_lines))
    return file_path


def remove_unexpected_attr(node):
    unexpected_keys = [
        key
        for key, value in node.attrib.items()
        if key
        not in [
            "index",
            "package",
            "class",
            "text",
            "resource-id",
            "content-desc",
            "clickable",
            "scrollable",
            "bounds",
        ]
    ]
    for key in unexpected_keys:
        del node.attrib[key]
    for child in node:
        remove_unexpected_attr(child)


def refine_xml(xml_str):
    root = ET.fromstring(xml_str)
    remove_unexpected_attr(root)
    return ET.tostring(root, encoding="unicode")


def xml_to_dict(xml_element: ET.Element):
    result = {}
    for child in xml_element:
        child_dict = xml_to_dict(child)
        if child_dict:
            if child.tag in result and result[child.tag]:
                result[child.tag].append(child_dict)
            else:
                result[child.tag] = [child_dict]

    if xml_element.text and xml_element.text.strip():
        text = xml_element.text.strip()
        if "content" in result and result["content"]:
            result["content"].append(text)
        else:
            result["content"] = [text]

    expected_attrib = {
        (key, value)
        for key, value in xml_element.attrib.items()
        if key
        in [
            "index",
            "package",
            "class",
            "text",
            "resource-id",
            "content-desc",
            "clickable",
            "scrollable",
            "bounds",
        ]
        and value.strip()
    }
    if expected_attrib:
        result.update(expected_attrib)
    return result


def xml_to_yaml(xml_file, yaml_file):
    root = ET.fromstring(read_file_content(xml_file))
    xml_dict = xml_to_dict(root)
    yaml_data = yaml.dump(xml_dict, default_flow_style=False)
    return write_to_file(yaml_file, yaml_data)


def xml_str_to_yaml(yaml_file, xml_str):
    root = ET.fromstring(xml_str)
    xml_dict = xml_to_dict(root)
    yaml_data = yaml.dump(xml_dict, default_flow_style=False)
    return write_to_file(yaml_file, yaml_data)


def take_page_source(driver, folder, name):
    write_to_file(f"{folder}/{name}.xml", driver.page_source)
    return xml_str_to_yaml(f"{folder}/{name}.yaml", driver.page_source)


def take_screenshot(driver: webdriver.Remote, folder, name):
    driver.save_screenshot(f"{folder}/{name}.png")
    format_image(f"{folder}/{name}.png", f"{folder}/{name}.jpg")
    return f"{folder}/{name}.jpg"


def get_current_timestamp():
    return int(time.time() * 1000)


def keep_driver_live(driver: webdriver.Remote):
    try:
        while driver:
            driver.page_source
            sleep(10)
    except:
        print("closing thread.")

def get_focused_element_bbox(driver):
    el = driver.switch_to.active_element
    if not el:
        return None

    rect = el.rect
    return (
        int(rect["x"]),
        int(rect["y"]),
        int(rect["x"] + rect["width"]),
        int(rect["y"] + rect["height"]),
    )


ALLOWED_TYPES = {
    "XCUIElementTypeButton",
    "XCUIElementTypeStaticText",
    "XCUIElementTypeTextField",
    "XCUIElementTypeSecureTextField",
    "XCUIElementTypeSwitch",
}

def parse_ios_xml(xml_source: str):
    """
    Parse iOS page_source XML and extract meaningful UI elements
    """
    root = ET.fromstring(xml_source)
    screen_width = float(root.attrib.get("width", 0))
    screen_height = float(root.attrib.get("height", 0))
    elements = []
    element_id = 0

    for node in root.iter():
        element_type = node.attrib.get("type")
        if element_type not in ALLOWED_TYPES:
            continue

        label = (
            node.attrib.get("label")
            or node.attrib.get("name")
            or node.attrib.get("value")
            or ""
        ).strip()

        # bounds: x,y,width,height
        try:
            x = int(float(node.attrib.get("x", 0)))
            y = int(float(node.attrib.get("y", 0)))
            w = int(float(node.attrib.get("width", 0)))
            h = int(float(node.attrib.get("height", 0)))
        except ValueError:
            continue

        elements.append({
            "id": f"E{element_id}",
            "type": element_type,
            "label": label,
            "enabled": node.attrib.get("enabled") == "true",
            "visible": node.attrib.get("visible") != "false",
            "bounds": [x, y, x + w, y + h],
            "has_focus": node.attrib.get("hasFocus") == "true"
        })

        element_id += 1

    return elements, screen_width, screen_height

def get_focused_element_id(elements):
    """
    Determine the currently focused element using heuristics
    """
    # Strategy 1: explicit focus
    for el in elements:
        if el.get("has_focus"):
            return el["id"]

    # Strategy 2: enabled TextField / SecureTextField
    for el in elements:
        if (
            el["type"] in (
                "XCUIElementTypeTextField",
                "XCUIElementTypeSecureTextField",
            )
            and el["enabled"]
            and el["visible"]
        ):
            return el["id"]

    largest = None
    max_area = 0

    for el in elements:
        x1, y1, x2, y2 = el["bounds"]
        area = (x2 - x1) * (y2 - y1)
        if area > max_area and el["enabled"] and el["visible"]:
            largest = el
            max_area = area

    if largest:
        return largest["id"]

    return None

def scale_bounds(bounds, img_size, ui_size):
    img_w, img_h = img_size
    ui_w, ui_h = ui_size

    if ui_w == 0 or ui_h == 0:
        return bounds  # fallback

    sx = img_w / ui_w
    sy = img_h / ui_h

    x1, y1, x2, y2 = bounds
    return (
        int(x1 * sx),
        int(y1 * sy),
        int(x2 * sx),
        int(y2 * sy),
    )