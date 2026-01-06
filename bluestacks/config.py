from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class BluestacksAgentConfig:
    """
    Main configuration object for the BluestacksAgent SDK.

    All of these config dicts are optional.

    llm_config example:
        {
            "name": "Gemini",
            "api_key": "123123",
            "temperature": 0.2,
            "max_steps": 10,
            "timeout": 1000,
            "vision": true,
            "accessibility": true
        }

    metadata example:
        {
            "helper_base_url": "http://localhost:8080",
            "sdk_log_to_console": false,
            "sdk_console_log_level": "INFO",
            "helper_logging_level": "debug",
            "screenshot_path": "/tmp/agent_screenshot.png",
            "grid_config": {
                "enabled": true,
                "color": "#FF0000",
                "columns": 36,
                "rows": 27,
                "font_color": "#FFFFFF"
            },
        }

    The SDK also exposes some behavioral values:
        - request_timeout: HTTP timeout (seconds) for each request
        - task_timeout: timeout passed to /v1/task/start (seconds)
    """

    llm_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    request_timeout: float = 60.0
    task_timeout: int = 1200
