"""
BlueStacks MCP Server

An MCP server that enables AI assistants to control and test Android 
applications on BlueStacks emulator.

Usage:
    python main.py

MCP Client Configuration (VS Code / Claude Desktop):
    {
        "mcpServers": {
            "bluestacks": {
                "command": "python",
                "args": ["main.py"],
                "cwd": "/path/to/bluestacksmcp"
            }
        }
    }
"""

import sys
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP

# Import BlueStacks SDK
from bluestacks import BluestacksAgent

# Import configuration
from mcp_config import config

# Import utilities
from utils import ensure_adb_ready

# Import models
from models import (
    TaskResult,
    ToolResult,
    ScreenshotResult,
    UITreeResult,
    ErrorLogsResult,
    AppListResult,
    TestReportResult,
)

# Import tool implementations
from tools import (
    install_app,
    list_installed_apps,
    uninstall_app,
    get_error_logs,
    tap_screen,
    swipe_screen,
    press_key,
    type_input,
    go_back,
    go_home,
    wait_delay,
    start_app,
    take_screenshot,
    get_ui_tree,
    run_android_task,
    generate_test_report,
    test_feature,
)


# ============ Application Context ============

@dataclass
class AppContext:
    """Holds the BlueStacks agent instance for tool access."""
    agent: BluestacksAgent


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manage BlueStacks agent lifecycle.

    Creates the agent on server startup and cleanly closes it on shutdown.
    """
    # Ensure ADB is ready (will restart server if needed)
    await ensure_adb_ready()

    # Create agent with configuration from environment
    agent_config = config.to_agent_config()
    agent = BluestacksAgent(agent_config, use_default_callbacks=False)

    print(f"[BlueStacks MCP] Agent initialized", file=sys.stderr)
    print(f"[BlueStacks MCP] LLM: {config.llm_provider}/{config.llm_model}", file=sys.stderr)

    try:
        yield AppContext(agent=agent)
    finally:
        # Clean shutdown - go home and close session
        await agent.close(go_home=True)
        print("[BlueStacks MCP] Agent closed", file=sys.stderr)


# ============ MCP Server ============

mcp = FastMCP(
    "BlueStacks Android Agent",
    lifespan=app_lifespan,
)


# ============ Tool Registrations ============

# --- ADB Tools ---

@mcp.tool()
async def mcp_install_app(apk_path: str) -> ToolResult:
    """
    Install an APK file onto the Android emulator.

    Args:
        apk_path: Full path to the APK file on host machine
    """
    return await install_app(apk_path)

@mcp.tool()
async def mcp_uninstall_app(package: str) -> ToolResult:
    """
    Uninstall an app from the Android emulator.

    Args:
        package: Package name to uninstall
    """
    return await uninstall_app(package)

@mcp.tool()
async def mcp_list_installed_apps() -> AppListResult:
    """
    List all installed apps on the Android emulator.

    Returns a list of all package names.
    """
    return await list_installed_apps()

@mcp.tool()
async def mcp_get_error_logs(lines: int = 1000) -> ErrorLogsResult:
    """
    Get recent Android system logs (logcat).

    Args:
        lines: Number of recent log lines (default: 1000)
    """
    return await get_error_logs(lines)

# --- Core Tools ---

@mcp.tool()
async def mcp_tap_screen(x: int, y: int) -> ToolResult:
    """
    Tap at specific screen coordinates.

    Args:
        x: X coordinate (pixels from left)
        y: Y coordinate (pixels from top)
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await tap_screen(x, y, agent)

@mcp.tool()
async def mcp_swipe_screen(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int,
) -> ToolResult:
    """
    Perform a swipe gesture on the screen.

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate
        end_x: Ending X coordinate
        end_y: Ending Y coordinate
        duration_ms: Duration of swipe in milliseconds
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await swipe_screen(start_x, start_y, end_x, end_y, duration_ms, agent)

@mcp.tool()
async def mcp_press_key(keycode: int) -> ToolResult:
    """
    Press an Android key by its keycode.

    Args:
        keycode: Android keycode integer
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await press_key(keycode, agent)

@mcp.tool()
async def mcp_type_input(text: str) -> ToolResult:
    """
    Type text into the currently focused input field.

    Args:
        text: Text to type
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await type_input(text, agent)

@mcp.tool()
async def mcp_wait_delay(milliseconds: int) -> ToolResult:
    """
    Wait for a specified duration.

    Args:
        milliseconds: Time to wait (1000 = 1 second)
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await wait_delay(milliseconds, agent)

@mcp.tool()
async def mcp_go_back() -> ToolResult:
    """
    Press the Android BACK button.

    Goes back to the previous screen or closes dialogs.
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await go_back(agent)

@mcp.tool()
async def mcp_go_home() -> ToolResult:
    """
    Press the Android HOME button.

    Returns to the Android home screen from any app.
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await go_home(agent)

@mcp.tool()
async def mcp_start_app(package: str, activity: str) -> ToolResult:
    """
    Start an Android application.

    Args:
        package: Package name (e.g., "com.android.settings")
        activity: Activity name (e.g., "com.android.settings.SettingsActivity")
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await start_app(package, activity, agent)

@mcp.tool()
async def mcp_take_screenshot(path: Optional[str] = None) -> ScreenshotResult:
    """
    Capture a screenshot of the current emulator screen.

    Args:
        path: Optional local file path to save the screenshot (e.g., "screenshot.png")

    Useful for visual verification and debugging.
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await take_screenshot(agent, path)

@mcp.tool()
async def mcp_get_ui_tree() -> UITreeResult:
    """
    Get the UI hierarchy of the current screen as JSON.

    Useful for finding element coordinates and understanding screen structure.
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await get_ui_tree(agent)

# --- Smart Tools ---

@mcp.tool()
async def mcp_run_android_task(query: str) -> TaskResult:
    """
    Execute an AI-powered task on the Android emulator.

    The LLM agent will autonomously interact with the device to complete 
    the task described in the query. This is the primary way to perform
    complex, multi-step operations.

    Args:
        query: Natural language description of what to do.
               Examples:
               - "Open Settings and enable Dark Mode"
               - "Search for 'weather' in the Play Store"
               - "Take a photo and share it to Twitter"
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await run_android_task(query, agent)

@mcp.tool()
async def mcp_generate_test_report(
    app_name: str,
    app_description: Optional[str] = None,
) -> TestReportResult:
    """
    Generate a comprehensive QA test report for an Android app.

    Performs autonomous testing and generates a structured Markdown report.
    This can take 2-5 minutes.

    Args:
        app_name: Name or package of the app to test
        app_description: Optional context about what the app does
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await generate_test_report(app_name, agent, app_description)

@mcp.tool()
async def mcp_test_feature(
    app_name: str,
    feature_name: str,
    feature_description: str,
) -> TestReportResult:
    """
    Test a specific feature within an Android application.

    Useful for focused testing of a single feature during development.

    Args:
        app_name: Name or package of the app
        feature_name: Name of the feature (e.g., "Login Flow")
        feature_description: Detailed description of expected behavior
    """
    ctx = mcp.get_context()
    agent = ctx.request_context.lifespan_context.agent
    return await test_feature(app_name, feature_name, feature_description, agent)


# ============ Entry Point ============

def main():
    """Run the MCP server with STDIO transport."""
    print("[BlueStacks MCP] Starting server...", file=sys.stderr)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
