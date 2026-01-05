from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RunResult:
    """
    Result of a single LLM 'turn' (run_task or resume_task) or a tool command.

    Fields:
        success: True if the operation succeeded
        output: Primary textual output (usually final LLM answer) on success
        reason: Human-readable error message on failure (empty on success)
        error_code: Machine-readable error code (string) on failure, or None on success
        needs_input: For future use / compatibility (currently always False here)
        input_prompt: Optional text describing what input is required (if any)
        responses: Full list of intermediate responses from the backend (SSE)
        delta: Last incremental chunk from SSE (if any)
        raw: The raw event or response dict for debugging
    """

    success: bool
    output: str
    reason: str
    error_code: Optional[str] = None
    needs_input: bool = False
    input_prompt: Optional[str] = None
    responses: List[Any] = field(default_factory=list)
    delta: Optional[Any] = None
    raw: Optional[Dict[str, Any]] = None
