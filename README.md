# Appium FastMCP stdio MCP (Auto-Wait + Retry)

This MCP allows Claude Code to control Android/iOS Appium sessions via stdio.
It supports:
- Auto-wait
- Retry heuristics
- Screenshot + XML return after each action

## Install
pip install mcp appium-python-client pillow

## Run
python server.py

## Register (Don't require Run)
claude mcp add --transport stdio appium-mcp -- python3 /abs/path/server.py
