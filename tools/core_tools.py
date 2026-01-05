"""
Core device interaction tools for Bluestacks Android emulator.

These are tools directly exposed by the bluestacks agent sdk, including:
- Tapping on the screen
- Swiping on the screen
- Pressing hardware keys
- Typing text input
- Navigating back
- Navigating home
- Waiting/delaying
- Starting apps
- Taking screenshots
- Retrieving the UI hierarchy/tree
"""

import base64
from typing import TYPE_CHECKING, Optional

from models import ToolResult, ScreenshotResult, UITreeResult

if TYPE_CHECKING:
    from bluestacks import BluestacksAgent


async def tap_screen(
    x: int,
    y: int,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Tap at specific screen coordinates.

    Args:
        x: X coordinate (pixels from left edge)
        y: Y coordinate (pixels from top edge)

    Returns:
        ToolResult with success status
    """
    result = await agent.tap(x, y)

    return ToolResult(
        success=result.success,
        message=f"Tapped at ({x}, {y})" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def swipe_screen(
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
    duration_ms: int,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Perform a swipe gesture on the screen.

    Args:
        start_x: Starting X coordinate
        start_y: Starting Y coordinate  
        end_x: Ending X coordinate
        end_y: Ending Y coordinate
        duration_ms: Duration of swipe in milliseconds. Longer duration means slower swipe.

    Returns:
        ToolResult with success status
    """
    result = await agent.swipe(start_x, start_y, end_x, end_y, duration_ms)
    
    return ToolResult(
        success=result.success,
        message=f"Swiped from ({start_x}, {start_y}) to ({end_x}, {end_y})" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def press_key(
    keycode: int,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Press an Android key by its keycode.

    Args:
        keycode: Android keycode integer

    Returns:
        ToolResult with success status
    """
    result = await agent.press_key(keycode)
    
    return ToolResult(
        success=result.success,
        message=f"Pressed key: {keycode}" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def type_input(
    text: str,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Type text into the currently focused input field.

    Args:
        text: Text to type into the focused field

    Returns:
        ToolResult with success status
    """
    result = await agent.input_text(text)
    
    return ToolResult(
        success=result.success,
        message=f"Typed text: '{text[:50]}{'...' if len(text) > 50 else ''}'" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def go_back(
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Press the Android BACK button.

    Returns:
        ToolResult with success status
    """
    result = await agent.back()
    
    return ToolResult(
        success=result.success,
        message="Pressed back button" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def go_home(
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Press the Android HOME button.

    Returns:
        ToolResult with success status
    """
    result = await agent.home()
    
    return ToolResult(
        success=result.success,
        message="Navigated to home screen" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def wait_delay(
    milliseconds: int,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Wait for a specified duration.

    Args:
        milliseconds: Time to wait in milliseconds

    Returns:
        ToolResult with success status
    """
    result = await agent.delay(milliseconds)
    
    return ToolResult(
        success=result.success,
        message=f"Waited {milliseconds}ms" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def start_app(
    package: str,
    activity: str,
    agent: "BluestacksAgent",
) -> ToolResult:
    """
    Start an Android application.

    Args:
        package: Package name (e.g., "com.android.settings", "com.twitter.android", "com.whatsapp")
        activity: Specific activity to launch within the app.

    Returns:
        ToolResult with success status
    """
    result = await agent.start_app(package, activity)
    
    return ToolResult(
        success=result.success,
        message=f"Started {package}" if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def take_screenshot(
    agent: "BluestacksAgent",
    path: Optional[str] = None,
) -> ScreenshotResult:
    """
    Capture a screenshot of the current emulator screen.

    Args:
        agent: The bluestacks agent instance
        path: Optional local file path to save the screenshot (e.g., "screenshot.png")

    Returns:
        ScreenshotResult with base64 encoded PNG image and optional file path

    Note:
        - Screenshots are PNG format
    """
    try:
        png_bytes = await agent.take_screenshot()
        base64_image = base64.b64encode(png_bytes).decode("utf-8")

        if path:
            with open(path, "wb") as f:
                f.write(png_bytes)

        return ScreenshotResult(
            success=True,
            image_base64=base64_image,
            file_path=path,
        )

    except Exception as e:
        return ScreenshotResult(
            success=False,
            error=str(e),
        )

async def get_ui_tree(
    agent: "BluestacksAgent",
) -> UITreeResult:
    """
    Get the UI hierarchy/accessibility tree of the current screen.

    Returns:
        UITreeResult with JSON string of UI hierarchy
    """
    try:
        ui_json = await agent.get_ui_tree()
        
        return UITreeResult(
            success=True,
            ui_tree=ui_json,
        )

    except Exception as e:
        return UITreeResult(
            success=False,
            error=str(e),
        )
