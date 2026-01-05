from typing import Optional


class BluestacksSDKError(Exception):
    """
    Base class for all Bluestacks SDK errors.

    Attributes:
        code: Machine-readable error code (string)
        message: Human-readable error message
    """

    def __init__(self, message: str, code: Optional[str] = None):
        self.code = code or "sdk_error"
        self.message = message
        super().__init__(f"{self.message}\nError code: {self.code}")


class SessionCreationError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "session_creation_failed"):
        super().__init__(message, code)


class TaskStartError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "task_start_failed"):
        super().__init__(message, code)


class TaskStatusError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "task_status_failed"):
        super().__init__(message, code)


class TaskResumeError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "task_resume_failed"):
        super().__init__(message, code)


class UITreeError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "ui_tree_failed"):
        super().__init__(message, code)


class ScreenshotError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "screenshot_failed"):
        super().__init__(message, code)


class StartAppError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "start_app_failed"):
        super().__init__(message, code)


class DelayError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "delay_failed"):
        super().__init__(message, code)


class HomeCommandError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "home_failed"):
        super().__init__(message, code)


class BackCommandError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "back_failed"):
        super().__init__(message, code)


class InputTextError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "input_text_failed"):
        super().__init__(message, code)


class PressKeyError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "press_key_failed"):
        super().__init__(message, code)


class SwipeError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "swipe_failed"):
        super().__init__(message, code)


class TapError(BluestacksSDKError):
    def __init__(self, message: str, code: str = "tap_failed"):
        super().__init__(message, code)
