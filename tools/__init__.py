"""
Tools Package

Exports all tool functions for registration with the MCP server.
"""

from .adb_tools import (
    install_app,
    uninstall_app,
    list_installed_apps,
    get_error_logs,
)

from .core_tools import (
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
)

from .smart_tools import (
    run_android_task,
    generate_test_report,
    test_feature,
)

__all__ = [
    # ADB tools
    "install_app",
    "uninstall_app",
    "list_installed_apps",
    "get_error_logs",
    # Core tools
    "tap_screen",
    "swipe_screen",
    "press_key",
    "type_input",
    "go_back",
    "go_home",
    "wait_delay",
    "start_app",
    "take_screenshot",
    "get_ui_tree",
    # Smart tools
    "run_android_task",
    "generate_test_report",
    "test_feature",
]
