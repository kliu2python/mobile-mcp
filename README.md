# Appium FastMCP stdio MCP (Auto-Wait + Retry)

This MCP allows Claude Code to control Android/iOS Appium sessions via stdio.
It supports:
- Auto-wait
- Retry heuristics
- Screenshot + XML return after each action

## Install
- pip install --upgrade uv
- uv sync
- source .venv/bin/activate      # macOS / Linux
- .venv\Scripts\activate         # Windows

## Run
python server.py

## Register (Don't require Run)
claude mcp add --transport stdio appium-mcp -- python3 /abs/path/server.py
