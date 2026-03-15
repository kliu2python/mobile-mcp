# Appium FastMCP stdio MCP (Auto-Wait + Retry)

This MCP allows Claude Code to control Android/iOS Appium sessions via stdio.

## Features
- Auto-wait
- Retry heuristics
- Screenshot + XML after each action
- External Appium profile config (no hardcoded server/capabilities)

## Install
- `pip install --upgrade uv`
- `uv sync`
- `source .venv/bin/activate` (macOS/Linux)
- `.venv\Scripts\activate` (Windows)

## Run
`python server.py`

## Register (without starting manually)
`claude mcp add --transport stdio appium-mcp -- python3 /abs/path/server.py`

---

## Decoupled Appium configuration

### 1) Create your local config

```bash
cp appium_profiles.example.yaml appium_profiles.yaml
```

Then edit `appium_profiles.yaml` for your device farm or local Appium server.

### 2) Start sessions from profiles

- List profiles: `list_appium_profiles(config_path=None)`
- Start by profile: `start_appium_session_with_profile(profile_name, config_path=None, capabilities_override=None)`
- Backward-compatible direct start: `start_appium_session(platform, server_url, capabilities)`

Default tools read profiles by name:
- `start_default_ios_appium_session()` → defaults to `ios-local`
- `start_default_android_appium_session()` → defaults to `android-local`

You can override default profile names with env vars:
- `APPIUM_MCP_DEFAULT_IOS_PROFILE`
- `APPIUM_MCP_DEFAULT_ANDROID_PROFILE`

### 3) Switch config file by environment

```bash
export APPIUM_MCP_CONFIG=/abs/path/to/profiles.yaml
```

`appium_profiles.yaml` is ignored by git, so local UDID/secrets stay uncommitted.

### 4) Advanced profile capabilities

The config loader supports:
- **Profile inheritance** with `extends`
- **Environment placeholder expansion** (e.g. `${IOS_UDID}`)

See `appium_profiles.example.yaml` for both patterns.

---

## Improvements to handle more scenarios

### A. Multi-device and concurrency
- Replace singleton driver with session pool (`session_id -> driver`)
- Require `session_id` in action tools
- Add `list_sessions`, `close_session(session_id)`, and session metadata

### B. Cross-platform UI abstraction
- Add Android XML parser and normalize fields with iOS
- Unified semantic query layer: role/text/state/bounds

### C. Semantic action APIs
- Add high-level tools like `tap_text`, `input_into`, and `assert_text_visible`
- Reduce dependence on brittle raw locators

### D. Observability and reliability
- Structured JSON logs per action (duration, retries, error type)
- Action traces with before/after screenshot + XML change summary
- Stable error codes (`ELEMENT_NOT_FOUND`, `ACTION_TIMEOUT`, etc.)

### E. Quality gates
- Unit tests for config parsing, profile resolution, and retries
- Contract tests for MCP tool return schemas
- CI checks (`pytest`, lint, static checks)
