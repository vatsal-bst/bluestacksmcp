"""
ADB-based interaction tools for Android emulators.

These tools use ADB (Android Debug Bridge) to perform operations, including:
- Install applications
- Uninstall applications
- List installed applications
- Retrieve error logs
"""

from models import ToolResult, AppListResult, ErrorLogsResult
from utils.adb import adb_install, adb_uninstall, adb_list_packages, adb_logcat


async def install_app(
    apk_path: str,
) -> ToolResult:
    """
    Install an APK file onto the Android emulator.

    Args:
        apk_path: Full path to the APK file on the host machine.
                 Example: "/Users/dev/myapp/build/app.apk" on macOS/Linux
                 or "C:\\Projects\\MyApp\\app-release.apk" on Windows

    Returns:
        ToolResult with success status
    """
    result = await adb_install(apk_path)
    
    return ToolResult(
        success=result["success"],
        message=result.get("message", ""),
        error=result.get("error", ""),
    )

async def uninstall_app(
    package: str,
) -> ToolResult:
    """
    Uninstall an app from the Android emulator.

    Args:
        package: Package name to uninstall (e.g., "com.example.myapp")

    Returns:
        ToolResult with success status
    """
    result = await adb_uninstall(package)
    
    return ToolResult(
        success=result["success"],
        message=result.get("message", ""),
        error=result.get("error", ""),
    )

async def list_installed_apps() -> AppListResult:
    """
    List all installed apps on the Android emulator.

    Returns:
        AppListResult with list of package names
    """
    result = await adb_list_packages()
    
    return AppListResult(
        success=result["success"],
        packages=result.get("packages", []),
        error=result.get("error", ""),
    )

async def get_error_logs(
    lines: int = 500,
) -> ErrorLogsResult:
    """
    Get recent Android system logs (logcat).

    Args:
        lines: Number of recent log lines to retrieve (default: 500)

    Returns:
        ErrorLogsResult with raw logcat output
    """
    result = await adb_logcat(lines=lines)
    
    return ErrorLogsResult(
        success=result["success"],
        logs=result.get("logs", ""),
        error=result.get("error", ""),
    )
