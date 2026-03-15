import os
import tempfile
import textwrap
import unittest
from pathlib import Path

from appium_config import get_profile, load_profiles


class AppiumConfigTests(unittest.TestCase):
    def write_config(self, content: str) -> str:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        tmp.write(textwrap.dedent(content))
        tmp.flush()
        tmp.close()
        self.addCleanup(lambda: Path(tmp.name).unlink(missing_ok=True))
        return tmp.name

    def test_load_basic_profiles(self):
        path = self.write_config(
            """
            profiles:
              ios-local:
                platform: iOS
                server_url: http://127.0.0.1:4723
                capabilities:
                  platformName: iOS
            """
        )
        profiles = load_profiles(path)
        self.assertIn("ios-local", profiles)
        self.assertEqual(profiles["ios-local"]["platform"], "iOS")

    def test_profile_inheritance_and_env_placeholder(self):
        old = os.environ.get("IOS_UDID")
        os.environ["IOS_UDID"] = "udid-from-env"
        self.addCleanup(lambda: os.environ.__setitem__("IOS_UDID", old) if old is not None else os.environ.pop("IOS_UDID", None))

        path = self.write_config(
            """
            profiles:
              base:
                platform: iOS
                server_url: http://farm/grid
                capabilities:
                  appium:automationName: XCUITest
              ios-local:
                extends: base
                capabilities:
                  udid: ${IOS_UDID}
            """
        )
        profile = get_profile("ios-local", path)
        self.assertEqual(profile["server_url"], "http://farm/grid")
        self.assertEqual(profile["capabilities"]["udid"], "udid-from-env")
        self.assertEqual(profile["capabilities"]["appium:automationName"], "XCUITest")


if __name__ == "__main__":
    unittest.main()
