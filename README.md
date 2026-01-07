# BlueStacks MCP Server

An MCP (Model Context Protocol) server that enables AI assistants to control and test Android applications on BlueStacks emulator.

## Overview

**📊 [View Project Overview Diagram](https://drive.google.com/file/d/1dtahwJrOKcIt6p658u7t70kZKGz3k4R_/view?usp=sharing)**

## Features

- 🤖 AI-powered Android automation via natural language
- 📱 Complete device control (tap, swipe, type, navigate)
- 📸 Screenshot capture and UI hierarchy inspection
- 📦 App management (install, uninstall, list apps)
- 🧪 Automated testing and QA report generation
- 📋 Comprehensive logging with file output

---

## Installation & Running

### Option 1: Using `uv` (Recommended - Simplest)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager that **automatically handles virtual environments**. You don't need to activate anything—just run the command.

<details>
<summary><b>macOS / Linux</b></summary>

```bash
# Install uv (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the MCP server (uv auto-creates venv and installs deps)
cd /path/to/bluestacksmcp
uv run python main.py
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
# Install uv (one-time)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Run the MCP server
cd C:\path\to\bluestacksmcp
uv run python main.py
```
</details>

---

### Option 2: Using `pip` with Virtual Environment

<details>
<summary><b>macOS / Linux</b></summary>

```bash
cd /path/to/bluestacksmcp

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```
</details>

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
cd C:\path\to\bluestacksmcp

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```

> **Note:** If you get an execution policy error, run:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```
</details>

<details>
<summary><b>Windows (Command Prompt)</b></summary>

```cmd
cd C:\path\to\bluestacksmcp

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Run the server
python main.py
```
</details>

---

## MCP Client Configuration

### VS Code (GitHub Copilot)

Create `.vscode/mcp.json` in your workspace or add to user settings:

<details>
<summary><b>Using uv (Recommended)</b></summary>

**macOS / Linux:**
```json
{
    "mcpServers": {
        "bluestacks": {
            "command": "uv",
            "args": ["run", "python", "main.py"],
            "cwd": "/path/to/bluestacksmcp"
        }
    }
}
```

**Windows:**
```json
{
    "mcpServers": {
        "bluestacks": {
            "command": "uv",
            "args": ["run", "python", "main.py"],
            "cwd": "C:\\path\\to\\bluestacksmcp"
        }
    }
}
```
</details>

<details>
<summary><b>Using venv directly (no activation needed)</b></summary>

**macOS / Linux:**
```json
{
    "mcpServers": {
        "bluestacks": {
            "command": "/path/to/bluestacksmcp/.venv/bin/python",
            "args": ["main.py"],
            "cwd": "/path/to/bluestacksmcp"
        }
    }
}
```

**Windows:**
```json
{
    "mcpServers": {
        "bluestacks": {
            "command": "C:\\path\\to\\bluestacksmcp\\.venv\\Scripts\\python.exe",
            "args": ["main.py"],
            "cwd": "C:\\path\\to\\bluestacksmcp"
        }
    }
}
```
</details>

---

## Environment Variables

## Available Tools

### App Management
- `mcp_install_app` - Install APK files
- `mcp_uninstall_app` - Uninstall apps by package name
- `mcp_list_installed_apps` - List all installed packages
- `mcp_start_app` - Launch an app by package/activity

### Device Control
- `mcp_tap_screen` - Tap at coordinates
- `mcp_swipe_screen` - Swipe gesture
- `mcp_type_input` - Type text
- `mcp_press_key` - Press Android keys
- `mcp_go_back` - Press BACK button
- `mcp_go_home` - Press HOME button

### Inspection
- `mcp_take_screenshot` - Capture screen
- `mcp_get_ui_tree` - Get UI hierarchy as JSON
- `mcp_get_error_logs` - Get Android logcat

### AI-Powered Tasks
- `mcp_run_android_task` - Execute complex tasks via natural language
- `mcp_generate_test_report` - Generate comprehensive QA report
- `mcp_test_feature` - Test a specific app feature

---

## Sample Use Case

To see the BlueStacks MCP in action, we've created a **sample Flutter app** that serves as a test application:

**🔗 [mcpFlutterSample](https://github.com/Sankalp-bst/mcpFlutterSample)**

This simple Flutter app is used to demonstrate the MCP server's capabilities. Check out these demo videos showing the complete workflow:

**📹 Demo Videos:**
- [Demo 1](https://drive.google.com/file/d/1sivK2yg_MvB39nlqYUXzM2tXBUMX4QBb/view?usp=drive_link) - Vibe coding an app feature and automated testing
- [Demo 2](https://drive.google.com/file/d/1JedzlSKOwRwyDB6aevSwiSMXStnB2Nq2/view?usp=drive_link) - Generate comprehensive test report for the app

These demos showcase how the MCP server can:
- Automate testing of Flutter applications on BlueStacks emulator
- Perform AI-powered interactions and validations
- Generate comprehensive QA reports
- Test specific features and workflows