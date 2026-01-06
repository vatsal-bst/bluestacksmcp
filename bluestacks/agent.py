from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import platform
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable, Awaitable, List

import httpx

from .config import BluestacksAgentConfig
from .types import RunResult
from .errors import (
    BluestacksSDKError,
    SessionCreationError,
    TaskStartError,
    TaskStatusError,
    TaskResumeError,
    ScreenshotError,
    StartAppError,
    DelayError,
    HomeCommandError,
    BackCommandError,
    InputTextError,
    PressKeyError,
    SwipeError,
    TapError,
    UITreeError,
)

# Type aliases for callbacks
AsyncTaskCallback = Callable[[Dict[str, Any]], Awaitable[None]]
SyncTaskCallback = Callable[[Dict[str, Any]], None]
TaskCallback = Optional[Callable[[Dict[str, Any]], Any]]

SDK_LOG_TAG = "[BlueStacks Agent]"

# ----------------------------------------------------------------------
# Default LLM config used if developer does not provide llm_config
# or provides only a partial config.
# ----------------------------------------------------------------------
DEFAULT_LLM_CONFIG: Dict[str, Any] = {
    "provider": "GoogleGenAI",
    "model": "gemini-3-flash-preview",
    "temperature": 1.0,
    "max_tokens": 10000,
    "max_steps": 25,
    "timeout": 300,
    "vision": True,
    "accessibility": True
}


def load_helper_service_url() -> str:
    """
    Detect the helper service base_url by reading bluestacksai.json.

    macOS:
        /Users/Shared/Library/Application Support/BlueStacks/bluestacksai.json

    Windows:
        <BlueStacksUserDefinedDir>/bluestacksai.json
        where <BlueStacksUserDefinedDir> is read from:
            HKEY_LOCAL_MACHINE\\SOFTWARE\\BlueStacks_nxt\\UserDefinedDir

    Returns:
        e.g. "http://127.0.0.1:8080", or falls back to "http://localhost:8080".
    """
    system = platform.system()
    json_path: Optional[Path] = None

    if system == "Darwin":  # macOS
        json_path = Path(
            "/Users/Shared/Library/Application Support/BlueStacks/bluestacksai.json"
        )
    elif system == "Windows":
        try:
            import winreg

            reg_path = r"SOFTWARE\\BlueStacks_nxt"
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path)
            user_defined_dir, _ = winreg.QueryValueEx(key, "UserDefinedDir")
            winreg.CloseKey(key)

            json_path = Path(user_defined_dir) / "bluestacksai.json"
        except Exception:
            json_path = None

    if json_path and json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            host = cfg.get("host_url", "http://127.0.0.1")
            port = cfg.get("port", 8080)
            host = str(host).rstrip("/")
            return f"{host}:{port}"
        except Exception:
            pass

    return "http://localhost:8080"


class BluestacksAgent:
    """
    High-level async SDK for the Bluestacks Agent helper service.

    Key behavior:

    - One BluestacksAgent instance manages a single backend session.
    - A long-lived SSE stream is opened per task_id and remains open
      until stop_task() is called.
    - run_task(query):
        * POST /v1/task/create
        * ensures a SSE stream /v1/task/stream is running in the background
        * waits until a 'task_completed' or 'task_failed' event arrives
          for this turn, then returns RunResult.
    - resume_task(new_query):
        * POST /v1/task/resume
        * uses the same SSE stream
        * waits for the next 'task_completed' or 'task_failed' event,
          then returns RunResult.
    - The SSE stream stays alive across multiple resume_task() calls
      until stop_task() is invoked.

    Error handling philosophy:

    - For LLM methods (run_task, resume_task, stop_task + SSE):
        * normal runtime failures (network issues, helper crash, bad responses)
          are converted into RunResult(success=False, reason=..., error_code=...),
          and, if a turn was pending, will also trigger on_completed with
          type 'task_error'.
        * we avoid raising TaskStatusError / TaskResumeError in those flows
          so application code can keep running.
    - Programming errors (wrong argument types, using a closed agent in
      unsupported ways, etc.) may still raise exceptions.
    - Tool methods (home, tap, etc.) already return RunResult and wrap
      internal exceptions in the same way.
    """

    def __init__(
        self,
        config: Optional[BluestacksAgentConfig] = None,
        *,
        use_default_callbacks: bool = True,
    ) -> None:
        # Use default config if none provided
        if config is None:
            config = BluestacksAgentConfig()

        self.config = config
        self._use_default_callbacks = use_default_callbacks
        self._print_progress_to_console = use_default_callbacks

        # ------------------------------------------------------------------
        # Determine base_url
        # ------------------------------------------------------------------
        # Allow override via metadata if provided, otherwise load from file.
        override_url = self.config.metadata.get("helper_base_url")
        if override_url:
            self.base_url = str(override_url).rstrip("/")
        else:
            self.base_url = load_helper_service_url().rstrip("/")

        # ------------------------------------------------------------------
        # LLM config: merge developer config over defaults
        # ------------------------------------------------------------------
        if not self.config.llm_config:
            # Covers llm_config=None and llm_config={}
            self.llm_config: Dict[str, Any] = deepcopy(DEFAULT_LLM_CONFIG)
        else:
            # Merge developer-provided config into defaults
            self.llm_config = deepcopy(DEFAULT_LLM_CONFIG)
            for k, v in self.config.llm_config.items():
                self.llm_config[k] = v

        # ------------------------------------------------------------------
        # Logger setup (per-instance)
        # ------------------------------------------------------------------
        logger_name = f"BluestacksAgentSDK.{id(self)}"
        self._logger = logging.getLogger(logger_name)
        self._logger.propagate = False
        self._logger.setLevel(logging.DEBUG)

        # Determine log directory
        if platform.system() == "Windows":
            log_dir = Path(os.getenv("TEMP", "")) / "BluestacksAI" / "logs"
        else:
            log_dir = Path("/Users") / "Shared" / ".bluestacks_ai" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        #print("using log dir: " + str(log_dir))

        # File name: agent_<YYYYMMDD_HHMMSS>.log
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"agent_{timestamp}.log"
        file_path = log_dir / file_name

        file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        fh = logging.FileHandler(file_path, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(file_formatter)
        self._logger.addHandler(fh)
        self._logger.debug("File logging enabled at: %s", file_path)

        # Optional console logging
        log_to_console = bool(self.config.metadata.get("sdk_log_to_console", False))
        console_level_str = self.config.metadata.get("sdk_console_log_level", "INFO")
        console_level = getattr(logging, console_level_str.upper(), logging.INFO)

        if log_to_console:
            ch = logging.StreamHandler()
            ch.setLevel(console_level)
            ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
            self._logger.addHandler(ch)
            self._logger.debug(
                "Console logging enabled at level: %s", console_level_str.upper()
            )

        self._logger.debug("Initialized BluestacksAgent: base_url=%s", self.base_url)

        # HTTP client (Accept SSE + JSON)
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.config.request_timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream, application/json",
            },
        )

        # Session + task
        self._session_id: Optional[str] = None
        self._current_task_id: Optional[str] = None

        # Long-lived SSE stream for current task
        self._event_stream_task: Optional[asyncio.Task] = None
        self._stop_stream: bool = False

        # Pending "turn" completion future (for run_task/resume_task)
        self._pending_turn_future: Optional[asyncio.Future] = None

        # Metadata-driven extras
        self.helper_log_level: str = self.config.metadata.get(
            "helper_logging_level", "warning"
        )
        self.screenshot_path: Optional[str] = self.config.metadata.get(
            "screenshot_path"
        )

        # Callbacks (set via set_callbacks)
        self._on_event: TaskCallback = None
        self._on_progress: TaskCallback = None
        self._on_waiting_input: TaskCallback = None
        self._on_completed: TaskCallback = None

    # ------------------------------------------------------------------
    # Callback registration
    # ------------------------------------------------------------------

    def set_callbacks(
        self,
        *,
        on_event: TaskCallback = None,
        on_progress: TaskCallback = None,
        on_waiting_input: TaskCallback = None,
        on_completed: TaskCallback = None,
    ) -> None:
        """
        Register callbacks for task events.

        All callbacks receive a single argument: the event dict:

            {
              "type": "<event_name>",
              "data": { ...parsed JSON from data line... },
              # plus convenience fields:
              #   "step_index", "task_state", "responses", "delta", "output"
            }
        """
        self._on_event = on_event
        self._on_progress = on_progress
        self._on_waiting_input = on_waiting_input
        self._on_completed = on_completed

        self._logger.debug(
            "Callbacks set: on_event=%s, on_progress=%s, on_waiting_input=%s, on_completed=%s",
            bool(on_event),
            bool(on_progress),
            bool(on_waiting_input),
            bool(on_completed),
        )

    async def _maybe_await(self, cb: TaskCallback, event: Dict[str, Any]) -> None:
        """
        Utility to handle callbacks that may be sync or async.
        """
        if cb is None:
            return
        try:
            result = cb(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            self._logger.warning("Callback raised exception: %s", e)

    async def _read_console_input(self, prompt: str) -> str:
        try:
            return await asyncio.to_thread(input, prompt)
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------

    async def _post(self, path: str, json_body: Dict[str, Any]) -> Dict[str, Any]:
        self._logger.info("POST %s", path)
        self._logger.debug("POST %s payload=%s", path, json_body)

        try:
            resp = await self._client.post(path, json=json_body)
        except httpx.TimeoutException as e:
            self._logger.error("POST %s timed out: %s", path, e)
            raise BluestacksSDKError(
                "Connection with BlueStacks AppPlayer timed out",
                code="connection_timeout",
            ) from e
        except httpx.HTTPError as e:
            self._logger.error("HTTP error in POST %s: %s", path, e)
            raise BluestacksSDKError(
                "Could not connect to BlueStacks AppPlayer. Please ensure that BlueStacks AppPlayer is running and you have configured API_KEY properly",
                code="connection_failed",
            ) from e

        # Try parsing JSON no matter what status code is
        try:
            data = resp.json()
        except ValueError:
            self._logger.error(
                "Non-JSON response from %s (status=%s): %s",
                path,
                resp.status_code,
                resp.text,
            )
            raise BluestacksSDKError(
                f"Non-JSON response from {path}",
                code="invalid_response",
            )

        # Treat any non-200 as error
        if resp.status_code != 200:
            error = data.get("error") or "http_error"
            message = data.get("message") or f"HTTP {resp.status_code}"
            self._logger.error(
                "POST %s failed: status=%s error=%s message=%s",
                path,
                resp.status_code,
                error,
                message,
            )
            raise BluestacksSDKError(message, code=error)

        self._logger.debug("POST %s response=%s", path, data)
        return data

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        self._logger.info("GET %s", path)
        self._logger.debug("GET %s params=%s", path, params)

        try:
            resp = await self._client.get(path, params=params)
        except httpx.TimeoutException as e:
            self._logger.error("GET %s timed out: %s", path, e)
            raise BluestacksSDKError(
                "Connection with App Player timed out",
                code="connection_timeout",
            ) from e
        except httpx.HTTPError as e:
            self._logger.error("HTTP error in GET %s: %s", path, e)
            raise BluestacksSDKError(
                "Could not connect to BlueStacks AppPlayer. Please ensure that BlueStacks AppPlayer is running and you have configured API_KEY properly",
                code="connection_failed",
            ) from e

        try:
            data = resp.json()
        except ValueError:
            self._logger.error(
                "Non-JSON response from %s (status=%s): %s",
                path,
                resp.status_code,
                resp.text,
            )
            raise BluestacksSDKError(
                f"Non-JSON response from {path}",
                code="invalid_response",
            )

        if resp.status_code != 200:
            error = data.get("error") or "http_error"
            message = data.get("message") or f"HTTP {resp.status_code}"
            self._logger.error(
                "GET %s failed: status=%s error=%s message=%s",
                path,
                resp.status_code,
                error,
                message,
            )
            raise BluestacksSDKError(message, code=error)

        self._logger.debug("GET %s response=%s", path, data)
        return data

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> str:
        """
        Lazily creates a session if not already created.

        Calls:
            POST /v1/session/create

        Note: /v1/session/create does NOT include LLM config.
        LLM settings are sent later with /v1/task/create.
        """
        if self._session_id is not None:
            return self._session_id

        payload: Dict[str, Any] = {}

        # Defaults if not provided
        payload.setdefault("mode", "agent")

        self._logger.info("Creating new session via /v1/session/create")
        if self._print_progress_to_console:
            print(f"{SDK_LOG_TAG}: Creating new session...")
        data = await self._post("/v1/session/create", payload)

        if data.get("status") != "success":
            error = data.get("error", "session_creation_failed")
            message = data.get("message", "Unknown session creation error")
            self._logger.error(
                "Session creation failed: error=%s message=%s response=%s",
                error,
                message,
                data,
            )
            raise SessionCreationError(f"{error}: {message} (response: {data!r})")

        self._session_id = data["session_id"]
        self._logger.info("Session created: session_id=%s", self._session_id)
        return self._session_id

    async def close(self, go_home: bool = False) -> None:
        """
        Closes the session (if any) and the underlying HTTP client.

        If go_home is True, the Android HOME command is sent before
        closing the session, so that the device UI ends on the home screen.
        """
        try:
            if self._print_progress_to_console:
                print(f"{SDK_LOG_TAG}: Stopping current session...")

            # First, stop current task / SSE stream
            await self.stop_task()

            # Optionally send HOME before closing session
            if go_home and self._session_id is not None:
                try:
                    await self.home()
                    self._logger.info("HOME command executed before closing session")
                except Exception as e:
                    self._logger.warning("Failed to send HOME command in close(): %s", e)

            # Close the session if it exists
            if self._session_id is not None:
                self._logger.info("Closing session: session_id=%s", self._session_id)
                payload = {"session_id": self._session_id}
                try:
                    _ = await self._post("/v1/session/close", payload)
                except Exception as e:
                    self._logger.warning("Error while closing session: %s", e)
        finally:
            # Always close HTTP client and reset state
            try:
                await self._client.aclose()
            except Exception:
                pass

            self._session_id = None
            self._current_task_id = None
            self._event_stream_task = None
            self._pending_turn_future = None

            self._logger.debug("Agent fully closed")

    # ------------------------------------------------------------------
    # Task APIs with long-lived SSE stream
    # ------------------------------------------------------------------

    async def _start_task(self, query: str) -> str:
        """
        Calls:
            POST /v1/task/create
        """
        session_id = await self._ensure_session()

        payload = {
            "session_id": session_id,
            "query": query,
            "llm": self.llm_config,
            "metadata": {
                "timeout": self.config.task_timeout,
                "grid_config": self.config.metadata.get("grid_config"),
            },
        }

        self._logger.info("Starting task with query: %s", query)
        data = await self._post("/v1/task/create", payload)

        if data.get("status") != "success":
            error = data.get("error", "task_start_failed")
            message = data.get("message", "Unknown task start error")
            self._logger.error(
                "Task creation failed: error=%s message=%s response=%s",
                error,
                message,
                data,
            )
            raise TaskStartError(f"{error}: {message} (response: {data!r})")

        task_id = data["task_id"]
        self._current_task_id = task_id
        self._logger.info("Task created: task_id=%s", task_id)
        return task_id

    async def _ensure_event_stream(self) -> None:
        """
        Ensure there is a long-lived SSE stream consuming events for the
        current task_id.
        """
        if self._session_id is None or self._current_task_id is None:
            self._logger.error("Cannot start SSE stream without active session/task")
            raise BluestacksSDKError(
                "Cannot start SSE stream without active session/task",
                code="invalid_state",
            )

        if self._event_stream_task is not None and not self._event_stream_task.done():
            return

        self._logger.info(
            "Starting SSE stream loop for session_id=%s task_id=%s",
            self._session_id,
            self._current_task_id,
        )
        self._stop_stream = False
        self._event_stream_task = asyncio.create_task(self._event_stream_loop())

    async def _fail_pending_turn_gracefully(
        self,
        reason: str,
        exc: Optional[BaseException] = None,
    ) -> None:
        """
        If there is a pending turn (run_task/resume_task waiting), complete it
        with a failure RunResult instead of throwing an exception.

        Also dispatches an 'error-like' event to on_completed so developer
        callbacks can handle it uniformly.
        """
        if self._pending_turn_future is None or self._pending_turn_future.done():
            return

        event = {
            "type": "task_error",
            "data": {
                "reason": reason,
                "exception": repr(exc) if exc else None,
            },
            "step_index": None,
            "task_state": "error",
            "timestamp": None,
            "responses": [],
            "delta": None,
            "output": "",
        }

        self._logger.error("Failing pending turn gracefully: %s", reason)

        # Let the app know via on_completed
        await self._maybe_await(self._on_completed, event)

        result = RunResult(
            success=False,
            output="",
            reason=reason,
            error_code="event_stream_error",
            needs_input=False,
            input_prompt=None,
            responses=[],
            delta=None,
            raw=event,
        )
        self._pending_turn_future.set_result(result)

    async def _event_stream_loop(self) -> None:
        """
        Long-lived SSE consumer for the current task_id.
        """
        if self._session_id is None or self._current_task_id is None:
            self._logger.error("No active task to consume events for")
            return

        params = {
            "session_id": self._session_id,
            "task_id": self._current_task_id,
        }

        self._logger.info(
            "Opening SSE stream for task: session_id=%s task_id=%s",
            self._session_id,
            self._current_task_id,
        )

        error: Optional[BaseException] = None

        try:
            async with self._client.stream(
                "GET", "/v1/task/stream", params=params
            ) as resp:
                resp.raise_for_status()

                current_event_name: Optional[str] = None
                current_event_data: Optional[str] = None

                async for raw_line in resp.aiter_lines():
                    if self._stop_stream:
                        self._logger.info("SSE stream stop requested; exiting loop")
                        break

                    if raw_line is None:
                        continue

                    line = raw_line.strip()

                    # Blank line → dispatch accumulated event (if any)
                    if line == "":
                        if current_event_data is not None:
                            await self._handle_sse_event(
                                current_event_name, current_event_data
                            )
                        current_event_name = None
                        current_event_data = None
                        continue

                    if line == ": keepalive":
                        continue

                    # Parse "event: <name>"
                    if line.startswith("event:"):
                        current_event_name = line[len("event:") :].strip()
                        continue

                    # Parse "data: <json>"
                    if line.startswith("data:"):
                        data_part = line[len("data:") :].strip()
                        if current_event_data is None:
                            current_event_data = data_part
                        else:
                            current_event_data += "\n" + data_part
                        continue

                    self._logger.debug("Ignoring unexpected SSE line: %s", line)

        except Exception as e:
            error = e
            self._logger.error("Error in SSE event stream: %s", e)

        finally:
            self._logger.info("SSE stream loop finished")
            reason = (
                f"Event stream error: {error}"
                if error is not None
                else f"{SDK_LOG_TAG}: ERROR: Lost connection to BlueStacks AppPlayer. Please check if BlueStacks AppPlayer is running."
            )
            await self._fail_pending_turn_gracefully(reason, error)

    async def _handle_sse_event(
        self,
        event_name: Optional[str],
        data_str: str,
    ) -> None:
        """
        Parse one SSE event and dispatch to callbacks.
        """
        try:
            payload = json.loads(data_str)
        except json.JSONDecodeError:
            self._logger.warning("Invalid JSON in SSE data: %s", data_str)
            payload = {"raw": data_str}

        step_index = payload.get("step_index")
        task_state = payload.get("task_state")
        timestamp = payload.get("timestamp")
        responses: List[Any] = payload.get("responses", []) or []
        delta = payload.get("delta")
        result_block = payload.get("result", {}) or {}

        event: Dict[str, Any] = {
            "type": event_name,
            "data": payload,
            "step_index": step_index,
            "task_state": task_state,
            "timestamp": timestamp,
            "responses": responses,
            "delta": delta,
        }

        #print("---------------- event name: " + event_name)

        self._logger.debug("SSE event received: %s", event)
        if self._print_progress_to_console:
            if event_name == "task_completed" and self._on_completed is None and self._use_default_callbacks:
                task_result = event["data"]["result"]
                if task_result.get("status") == "success":
                    print(f"{SDK_LOG_TAG}: Task completed successfully.")
                    print(f"{SDK_LOG_TAG}: " + task_result.get("output", ""))
                else:
                    print(f"{SDK_LOG_TAG}: Task failed.")
                    print(f"{SDK_LOG_TAG}: Error: " + task_result.get("message", ""))

            if event_name == "task_progress" and self._on_progress is None and self._use_default_callbacks:
                #print("\n\n--------- SSE data: ", event["delta"])
                delta_message = event.get("delta") if isinstance(event, dict) else None
                message_type = None
                if delta_message:
                    message_type = (
                        delta_message.get("type")
                        if isinstance(delta_message, dict)
                        else None
                    )

                # Print llm delta response to console if enabled
                if self._print_progress_to_console and message_type == "llm_response":
                    try:
                        delta_obj = event.get("delta") or event["data"].get("delta")
                        if isinstance(delta_obj, dict):
                            message = delta_obj.get("message")
                            if message:
                                print(f"{SDK_LOG_TAG}: {message}")
                    except Exception:
                        # Never let console printing break SDK flow
                        pass

        await self._maybe_await(self._on_event, event)

        if event_name == "task_progress":
            await self._maybe_await(self._on_progress, event)

        elif event_name == "task_await_input":
            if self._on_waiting_input is not None:
                await self._maybe_await(self._on_waiting_input, event)
            elif self._use_default_callbacks:
                # Default behavior: print prompt, read input, and resume the task
                prompt_text = f"{SDK_LOG_TAG}: Agent needs input:"
                try:
                    msg = event["data"]["result"]["output"]
                    if msg:
                        prompt_text = f"{SDK_LOG_TAG}: {msg}"
                except Exception:
                    pass

                if self._print_progress_to_console:
                    print(prompt_text)

                user_text = await self._read_console_input("> ")

                if self._session_id is not None and self._current_task_id is not None:
                    payload_resume: Dict[str, Any] = {
                        "session_id": self._session_id,
                        "task_id": self._current_task_id,
                        "resume_query": user_text,
                    }
                    try:
                        _ = await self._post("/v1/task/resume", payload_resume)
                    except Exception as e:
                        self._logger.error("resume_task failed with exception: %s", e)
                        await self._fail_pending_turn_gracefully(str(e), e)

        elif event_name == "task_completed":
            output = result_block.get("output", "")
            status_str = result_block.get("status")
            success = status_str == "success"
            error_code = None
            if not success:
                error_code = result_block.get("error") or "task_failed"

            event["output"] = output

            self._logger.info(
                "Task turn completed: task_id=%s success=%s output_length=%s",
                self._current_task_id,
                success,
                len(output),
            )

            await self._maybe_await(self._on_completed, event)

            if (
                self._pending_turn_future is not None
                and not self._pending_turn_future.done()
            ):
                result = RunResult(
                    success=success,
                    output=output,
                    reason="" if success else "task_failed",
                    error_code=error_code,
                    needs_input=False,
                    input_prompt=None,
                    responses=responses,
                    delta=delta,
                    raw=event,
                )
                self._pending_turn_future.set_result(result)

    async def _wait_for_turn_completion(self) -> RunResult:
        """
        Wait for the next "task_completed" or "task_failed" event, or for
        _fail_pending_turn_gracefully to complete it on error.
        """
        if (
            self._pending_turn_future is not None
            and not self._pending_turn_future.done()
        ):
            raise BluestacksSDKError(
                "Another task turn is already waiting for completion. "
                "Wait for it to finish before starting/resuming again.",
                code="task_turn_in_progress",
            )

        loop = asyncio.get_running_loop()
        self._pending_turn_future = loop.create_future()

        try:
            result: RunResult = await self._pending_turn_future
            return result
        finally:
            self._pending_turn_future = None

    async def run_task(self, query: str) -> RunResult:
        """
        Start a new LLM task and wait for one turn to complete.

        Any runtime error is converted into RunResult(success=False, reason=..., error_code=...).
        """
        if query is None or not isinstance(query, str) or query.strip() == "":
            return RunResult(
                success=False,
                output="",
                reason="ERROR: run_task(query) requires a non-empty string",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        self._logger.debug("run_task called with query=%s", query)

        try:
            await self._start_task(query)
            await self._ensure_event_stream()
            return await self._wait_for_turn_completion()
        except Exception as e:
            self._logger.error("run_task failed with exception: %s", e)
            await self._fail_pending_turn_gracefully(str(e), e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def resume_task(self, new_query: str) -> RunResult:
        """
        Continue the current task after a previous turn.

        Sends:
            POST /v1/task/resume

            {
                "session_id": "...",
                "task_id": "...",
                "resume_query": "..."
            }

        Any runtime error is converted into RunResult(success=False, reason=..., error_code=...).
        """
        if new_query is None or not isinstance(new_query, str) or new_query.strip() == "":
            return RunResult(
                success=False,
                output="",
                reason="ERROR: resume_task(new_query) requires a non-empty string",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        if self._session_id is None or self._current_task_id is None:
            reason = "No active task to resume"
            self._logger.error(reason)
            return RunResult(
                success=False,
                output="",
                reason=reason,
                error_code="no_active_task",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        payload: Dict[str, Any] = {
            "session_id": self._session_id,
            "task_id": self._current_task_id,
        }
        if new_query is not None:
            payload["resume_query"] = new_query

        loop = asyncio.get_running_loop()
        if (
            self._pending_turn_future is not None
            and not self._pending_turn_future.done()
        ):
            reason = (
                "Another task turn is already waiting for completion. "
                "Wait for it to finish before resuming again."
            )
            self._logger.error(reason)
            return RunResult(
                success=False,
                output="",
                reason=reason,
                error_code="task_turn_in_progress",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        self._pending_turn_future = loop.create_future()

        try:
            await self._ensure_event_stream()
            data = await self._post("/v1/task/resume", payload)

            status = data.get("status")
            if status not in (None, "accepted", "in_progress", "success"):
                error = data.get("error", "task_resume_failed")
                message = data.get("message", "Unknown task resume error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "Task resume failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                await self._fail_pending_turn_gracefully(reason)
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            # Normal path: wait for SSE turn completion
            result: RunResult = await self._pending_turn_future
            return result

        except Exception as e:
            self._logger.error("resume_task failed with exception: %s", e)
            await self._fail_pending_turn_gracefully(str(e), e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        finally:
            self._pending_turn_future = None

    def submit_input_async(self, text: str) -> None:
        """
        Fire-and-forget submit input (safe to call from SSE callbacks).
        """
        asyncio.create_task(self.submit_input(text))

    async def submit_input(self, text: str) -> None:
        if self._session_id is None or self._current_task_id is None:
            raise BluestacksSDKError("No active task to submit input to", code="no_active_task")

        payload = {
            "session_id": self._session_id,
            "task_id": self._current_task_id,
            "resume_query": text,
        }
        await self._post("/v1/task/resume", payload)

    async def stop_task(self) -> None:
        """
        Stop tracking the current task and close the SSE stream.

        If a turn was pending, it is completed with a failure RunResult
        instead of raising an exception.
        """
        self._logger.info("Stopping current task: task_id=%s", self._current_task_id)
        self._stop_stream = True

        if self._session_id is not None and self._current_task_id is not None:
            payload = {
                "session_id": self._session_id,
                "task_id": self._current_task_id,
            }
            try:
                _ = await self._post("/v1/task/close", payload)
            except Exception as e:
                self._logger.warning("Error while sending task close request: %s", e)

        if self._event_stream_task is not None and not self._event_stream_task.done():
            try:
                await self._event_stream_task
            except Exception as e:
                self._logger.warning("Error while stopping SSE stream: %s", e)

        self._event_stream_task = None
        self._current_task_id = None

        await self._fail_pending_turn_gracefully("Task stopped before turn completion")
        self._pending_turn_future = None

    # ------------------------------------------------------------------
    # Tool APIs (all return RunResult except take_screenshot)
    # ------------------------------------------------------------------

    async def get_ui_tree(self, file_path: Optional[str] = None) -> str:
        """
        Get the UI hierarchy dump of the Android screen.

        Retrieves the current UI hierarchy of the Android emulator screen as a
        JSON string, useful for understanding the UI structure and element properties.

        HTTP:
            GET /v1/tools/ui_dump
            Params: { "session_id": "<session-id>" }

        Expected success response:
            {
              "status": "success",
              "output": "...",
              "data": {
                "ui_dump": "<json_string>"
              }
            }

        Args:
            file_path: Optional path to save the UI dump JSON to a file.

        Returns:
            UI hierarchy dump as a JSON string.

        Raises:
            UITreeError: If the UI dump retrieval fails.
        """
        session_id = await self._ensure_session()
        self._logger.info("Requesting UI tree for session_id=%s", session_id)

        payload = {"session_id": session_id}

        data = await self._get("/v1/tools/ui_dump", payload)

        if data.get("status") != "success":
            error = data.get("error", "ui_tree_failed")
            message = data.get("message", "Unknown UI tree error")
            self._logger.error(
                "UI tree failed: error=%s message=%s response=%s",
                error,
                message,
                data,
            )
            raise UITreeError(f"{error}: {message} (response: {data!r})")

        data_field = data.get("data") or {}
        ui_dump: Optional[str] = data_field.get("ui_dump")

        if ui_dump is None:
            self._logger.error("Missing UI dump data in response: %s", data)
            raise UITreeError("Error: Missing UI dump data in response")

        # Save JSON if explicit file_path is provided
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(ui_dump)
                self._logger.info("UI tree (JSON) saved to %s", file_path)
            except Exception as e:
                self._logger.error(
                    "Failed to save UI tree to %s: %s", file_path, e
                )
                raise UITreeError(
                    f"Failed to save UI tree to {file_path}: {e}"
                ) from e

        return ui_dump

    async def take_screenshot(self, file_path: Optional[str] = None) -> bytes:
        """
        Take a screenshot for the current session.

        HTTP:
            GET /v1/tools/screenshot
            Params: { "session_id": "<session-id>" }

        Expected success response:
            {
              "status": "success",
              "data": {
                "screenshot_base64": "<base64_encoded_png_string>"
              }
            }

        Returns:
            Raw PNG bytes.

        Behavior:
        - If self.screenshot_path (from metadata) is set, saves PNG there.
        - If file_path is provided, also saves PNG to that path.
        """
        session_id = await self._ensure_session()
        self._logger.info("Requesting screenshot for session_id=%s", session_id)

        payload = {"session_id": session_id}

        data = await self._get("/v1/tools/screenshot", payload)

        if data.get("status") != "success":
            error = data.get("error", "screenshot_failed")
            message = data.get("message", "Unknown screenshot error")
            self._logger.error(
                "Screenshot failed: error=%s message=%s response=%s",
                error,
                message,
                data,
            )
            raise ScreenshotError(f"{error}: {message} (response: {data!r})")

        data_field = data.get("data") or {}
        screenshot_b64: Optional[str] = data_field.get("screenshot_base64")

        if not screenshot_b64:
            self._logger.error("Missing screenshot data in response: %s", data)
            raise ScreenshotError("Error: Missing screenshot data in response")

        try:
            png_bytes = base64.b64decode(screenshot_b64)
        except Exception as e:
            self._logger.error("Invalid base64 screenshot data: %s", e)
            raise ScreenshotError(
                f"Invalid base64 screenshot data: {e} (data: {data!r})"
            ) from e

        # Save PNG if metadata screenshot_path is set (existing behavior)
        if self.screenshot_path:
            try:
                with open(self.screenshot_path, "wb") as f:
                    f.write(png_bytes)
                self._logger.info("Screenshot (PNG) saved to %s", self.screenshot_path)
            except Exception as e:
                self._logger.warning(
                    "Failed to save PNG screenshot to %s: %s",
                    self.screenshot_path,
                    e,
                )

        # Save PNG if explicit file_path is provided
        if file_path:
            try:
                with open(file_path, "wb") as f:
                    f.write(png_bytes)
                self._logger.info("Screenshot (PNG) saved to %s", file_path)
            except Exception as e:
                self._logger.error(
                    "Failed to save PNG screenshot to %s: %s", file_path, e
                )
                raise ScreenshotError(
                    f"Failed to save screenshot as PNG to {file_path}: {e}"
                ) from e

        return png_bytes

    async def start_app(self, package: str, activity: Optional[str] = None) -> RunResult:
        """
        Start an application in the current session.
        """
        if not package:
            return RunResult(
                success=False,
                output="",
                reason="package is required for start_app()",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info(
                "Starting app: package=%s activity=%s session_id=%s",
                package,
                activity,
                session_id,
            )

            payload: Dict[str, Any] = {
                "session_id": session_id,
                "package": package,
            }
            if activity is not None:
                payload["activity"] = activity

            data = await self._post("/v1/tools/start_app", payload)

            if data.get("status") != "success":
                error = data.get("error", "start_app_failed")
                message = data.get("message", "Unknown start_app error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "start_app failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="start_app executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("start_app encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def delay(self, ms: int) -> RunResult:
        """
        Pause execution on the device for the given duration (milliseconds).
        """
        if ms <= 0:
            return RunResult(
                success=False,
                output="",
                reason="delay(ms) requires a positive duration in milliseconds",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info("Issuing delay: ms=%s session_id=%s", ms, session_id)

            payload = {
                "session_id": session_id,
                "ms": ms,
            }

            data = await self._post("/v1/tools/delay", payload)

            if data.get("status") != "success":
                error = data.get("error", "delay_failed")
                message = data.get("message", "Unknown delay error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "delay failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="delay executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("delay encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def home(self) -> RunResult:
        """
        Executes the Android 'home' command.
        """
        try:
            session_id = await self._ensure_session()
            self._logger.info("Sending HOME command: session_id=%s", session_id)

            payload = {"session_id": session_id}
            data = await self._post("/v1/tools/home", payload)

            if data.get("status") != "success":
                error = data.get("error", "home_failed")
                message = data.get("message", "Unknown home command error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "home failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="home executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("home encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def back(self) -> RunResult:
        """
        Executes the Android 'back' command.
        """
        try:
            session_id = await self._ensure_session()
            self._logger.info("Sending BACK command: session_id=%s", session_id)

            payload = {"session_id": session_id}
            data = await self._post("/v1/tools/back", payload)

            if data.get("status") != "success":
                error = data.get("error", "back_failed")
                message = data.get("message", "Unknown back command error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "back failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="back executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("back encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def input_text(self, text: str) -> RunResult:
        """
        Inputs text into the active UI element / focused field.
        """
        if not isinstance(text, str) or len(text) == 0:
            return RunResult(
                success=False,
                output="",
                reason="input_text() requires a non-empty string",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info(
                "Inputting text (len=%s) into session_id=%s",
                len(text),
                session_id,
            )

            payload = {
                "session_id": session_id,
                "text": text,
            }

            data = await self._post("/v1/tools/input_text", payload)

            if data.get("status") != "success":
                error = data.get("error", "input_text_failed")
                message = data.get("message", "Unknown input_text error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "input_text failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="input_text executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("input_text encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def press_key(self, keycode: int) -> RunResult:
        """
        Presses a key on the Android device using its keycode.
        """
        if not isinstance(keycode, int):
            return RunResult(
                success=False,
                output="",
                reason="press_key() requires an integer keycode",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info(
                "Pressing key: keycode=%s session_id=%s", keycode, session_id
            )

            payload = {
                "session_id": session_id,
                "keycode": keycode,
            }

            data = await self._post("/v1/tools/press_key", payload)

            if data.get("status") != "success":
                error = data.get("error", "press_key_failed")
                message = data.get("message", "Unknown press_key error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "press_key failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="press_key executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("press_key encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300,
    ) -> RunResult:
        """
        Perform a swipe gesture on the device.
        """
        for name, value in [
            ("start_x", start_x),
            ("start_y", start_y),
            ("end_x", end_x),
            ("end_y", end_y),
            ("duration_ms", duration_ms),
        ]:
            if not isinstance(value, int):
                return RunResult(
                    success=False,
                    output="",
                    reason=f"{name} must be an integer",
                    error_code="invalid_argument",
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=None,
                )

        if duration_ms <= 0:
            return RunResult(
                success=False,
                output="",
                reason="duration_ms must be greater than zero",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info(
                "Swipe: (%s,%s)->(%s,%s) duration_ms=%s session_id=%s",
                start_x,
                start_y,
                end_x,
                end_y,
                duration_ms,
                session_id,
            )

            payload = {
                "session_id": session_id,
                "start_x": start_x,
                "start_y": start_y,
                "end_x": end_x,
                "end_y": end_y,
                "duration_ms": duration_ms,
            }

            data = await self._post("/v1/tools/swipe", payload)

            if data.get("status") != "success":
                error = data.get("error", "swipe_failed")
                message = data.get("message", "Unknown swipe error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "swipe failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="swipe executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("swipe encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def tap(self, x: int, y: int) -> RunResult:
        """
        Performs a tap at the given screen coordinates.
        """
        if not isinstance(x, int) or not isinstance(y, int):
            return RunResult(
                success=False,
                output="",
                reason="tap(x, y) requires integer coordinates",
                error_code="invalid_argument",
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

        try:
            session_id = await self._ensure_session()
            self._logger.info("Tap at (%s,%s) session_id=%s", x, y, session_id)

            payload = {
                "session_id": session_id,
                "x": x,
                "y": y,
            }

            data = await self._post("/v1/tools/tap", payload)

            if data.get("status") != "success":
                error = data.get("error", "tap_failed")
                message = data.get("message", "Unknown tap error")
                reason = f"{error}: {message}"
                self._logger.error(
                    "tap failed: error=%s message=%s response=%s",
                    error,
                    message,
                    data,
                )
                return RunResult(
                    success=False,
                    output="",
                    reason=reason,
                    error_code=error,
                    needs_input=False,
                    input_prompt=None,
                    responses=[],
                    delta=None,
                    raw=data,
                )

            return RunResult(
                success=True,
                output="tap executed",
                reason="",
                error_code=None,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=data,
            )
        except Exception as e:
            self._logger.error("tap encountered error: %s", e)
            err_code = "sdk_runtime_error"
            if isinstance(e, BluestacksSDKError):
                err_code = e.code
            return RunResult(
                success=False,
                output="",
                reason=str(e),
                error_code=err_code,
                needs_input=False,
                input_prompt=None,
                responses=[],
                delta=None,
                raw=None,
            )

    async def send_feedback(self, feedback_message: str, rating: int) -> Dict[str, Any]:
        """
        Send feedback to the Bluestacks service.

        Args:
            feedback_message: Feedback message string
            rating: Numeric rating for the feedback

        Returns:
            Dict with response from the server indicating feedback submission status
        """
        self._logger.info(
            "Sending feedback: message_len=%s rating=%s",
            len(feedback_message),
            rating,
        )

        payload = {
            "comments": feedback_message,
            "rating": rating,
        }

        data = await self._post("/v1/feedback", payload)
        return data
