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

    instance_config example:
        {
            "instance_id": "Pie64"
        }

    metadata example:
        {
            "sdk_logging_level": "info",
            "helper_logging_level": "debug",
            "screenshot_path": "/tmp/agent_screenshot.png"
        }

    The SDK also exposes some behavioral values:
        - request_timeout: HTTP timeout (seconds) for each request
        - task_timeout: timeout passed to /v1/task/start (seconds)
        - status_poll_interval: how often to poll /v1/task/status (seconds)
        - status_max_wait: max total time to wait for a task (seconds)
    """

    llm_config: Dict[str, Any] = field(default_factory=dict)
    instance_config: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    request_timeout: float = 60.0
    task_timeout: int = 300
    status_poll_interval: float = 1.0
    status_max_wait: float = 300.0
