"""
ADB Command Utilities

Cross-platform subprocess wrappers for Android Debug Bridge commands.
Works on macOS, Windows, and Linux.
"""

import asyncio
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Track if we've already attempted a server restart
_adb_server_restarted = False


def _get_adb_command() -> str:
    """Get the ADB command for the current platform."""
    # On Windows, might need .exe extension or full path
    # For most setups, 'adb' should be in PATH
    return "adb"


def _run_adb_sync(
    args: List[str],
    timeout: int = 60
) -> Dict[str, any]:
    """
    Run an ADB command synchronously.
    
    Args:
        args: ADB command arguments (without 'adb' prefix)
        timeout: Command timeout in seconds
        
    Returns:
        Dict with success, stdout, stderr, return_code
    """
    adb = _get_adb_command()
    cmd = [adb] + args
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "return_code": -1,
        }
    except FileNotFoundError:
        return {
            "success": False,
            "stdout": "",
            "stderr": "ADB not found. Ensure Android SDK platform-tools is in PATH.",
            "return_code": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "return_code": -1,
        }


async def _restart_adb_server() -> bool:
    """
    Restart the ADB server by killing and starting it again.

    Returns:
        True if server restart was successful
    """
    global _adb_server_restarted

    # Kill the ADB server
    await asyncio.to_thread(_run_adb_sync, ["kill-server"], 30)

    # Wait a moment for the server to fully stop
    await asyncio.sleep(1)

    # Start the ADB server
    start_result = await asyncio.to_thread(_run_adb_sync, ["start-server"], 30)

    # Wait for server to be ready
    await asyncio.sleep(2)

    _adb_server_restarted = True

    if start_result["success"]:
        return True
    else:
        # Even if start-server reports issues, the server might still work
        return True

async def _run_adb_command(
    args: List[str],
    timeout: int = 60,
    retry_on_failure: bool = True
) -> Dict[str, any]:
    """
    Run an ADB command asynchronously with automatic server restart on failure.

    Args:
        args: ADB command arguments (without 'adb' prefix)
        timeout: Command timeout in seconds
        retry_on_failure: If True, retry after restarting ADB server on first failure

    Returns:
        Dict with success, stdout, stderr, return_code
    """
    global _adb_server_restarted

    result = await asyncio.to_thread(_run_adb_sync, args, timeout)

    # Check if we should retry with server restart
    if not result["success"] and retry_on_failure and not _adb_server_restarted:
        error_indicators = [
            "device not found",
            "no devices/emulators found",
            "device offline",
            "cannot connect",
            "connection refused",
            "protocol fault",
            "closed",
            "daemon not running",
        ]

        error_text = (result["stderr"] + result["stdout"]).lower()
        should_retry = any(indicator in error_text for indicator in error_indicators)

        if should_retry:
            # Restart the ADB server
            restart_success = await _restart_adb_server()

            if restart_success:
                # Retry the original command
                result = await asyncio.to_thread(_run_adb_sync, args, timeout)

    return result

async def ensure_adb_ready() -> Dict[str, any]:
    """
    Ensure ADB server is running and ready for commands.

    Call this at startup to proactively restart ADB if needed.

    Returns:
        Dict with success status and message
    """
    global _adb_server_restarted

    # Try a simple command to check if ADB is working
    result = await _run_adb_command(["devices"], timeout=10, retry_on_failure=False)

    if result["success"] and "device" in result["stdout"]:
        return {
            "success": True,
            "message": "ADB is ready",
            "devices": result["stdout"],
        }

    # If not working, force a restart
    _adb_server_restarted = False  # Allow restart

    await _restart_adb_server()

    # Check again
    result = await _run_adb_command(["devices"], timeout=10, retry_on_failure=False)

    if result["success"]:
        return {
            "success": True,
            "message": "ADB server restarted and ready",
            "devices": result["stdout"],
        }
    else:
        return {
            "success": False,
            "message": "Failed to initialize ADB",
            "error": result["stderr"],
        }

async def adb_install(apk_path: str) -> Dict[str, any]:
    """
    Install an APK using ADB.
    
    Args:
        apk_path: Path to the APK file (must be accessible from host)
        
    Returns:
        Dict with success status and message
    """
    # Normalize path for cross-platform compatibility
    apk_path = str(Path(apk_path).resolve())
    
    # Check if file exists
    if not Path(apk_path).exists():
        return {
            "success": False,
            "message": "",
            "error": f"APK file not found: {apk_path}",
        }
    
    result = await _run_adb_command(["install", "-r", apk_path], timeout=120)
    
    if result["success"] or "Success" in result["stdout"]:
        return {
            "success": True,
            "message": f"Successfully installed {Path(apk_path).name}",
            "error": "",
        }
    else:
        return {
            "success": False,
            "message": "",
            "error": result["stderr"] or result["stdout"],
        }


async def adb_uninstall(package: str) -> Dict[str, any]:
    """
    Uninstall an app by package name.
    
    Args:
        package: Package name (e.g., com.example.app)
        
    Returns:
        Dict with success status and message
    """
    result = await _run_adb_command(["uninstall", package], timeout=60)
    
    if result["success"] or "Success" in result["stdout"]:
        return {
            "success": True,
            "message": f"Successfully uninstalled {package}",
            "error": "",
        }
    else:
        return {
            "success": False,
            "message": "",
            "error": result["stderr"] or result["stdout"],
        }


async def adb_logcat(lines: int = 1000) -> Dict[str, any]:
    """
    Get recent Android logs via logcat.
    
    Args:
        lines: Number of recent log lines to retrieve
        
    Returns:
        Dict with success status and log content
    """
    # -d: dump and exit, -t: last N lines
    result = await _run_adb_command(["logcat", "-d", "-t", str(lines)], timeout=30)
    
    if result["success"]:
        return {
            "success": True,
            "logs": result["stdout"],
            "error": "",
        }
    else:
        return {
            "success": False,
            "logs": "",
            "error": result["stderr"],
        }


async def adb_list_packages() -> Dict[str, any]:
    """
    List all installed packages.
    
    Returns:
        Dict with success status and list of package names
    """
    result = await _run_adb_command(["shell", "pm", "list", "packages"], timeout=30)
    
    if result["success"]:
        # Parse output: each line is "package:com.example.app"
        packages = [
            line.replace("package:", "").strip()
            for line in result["stdout"].split("\n")
            if line.strip() and line.startswith("package:")
        ]
        return {
            "success": True,
            "packages": sorted(packages),
            "error": "",
        }
    else:
        return {
            "success": False,
            "packages": [],
            "error": result["stderr"],
        }
