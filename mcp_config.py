"""
MCP Server Configuration for BlueStacks MCP Server
"""

from dataclasses import dataclass

# Import BlueStacks SDK config
from bluestacks.config import BluestacksAgentConfig


@dataclass
class MCPConfig:
    """Configuration for the BlueStacks MCP Server."""

    # LLM Configuration
    llm_provider: str = "GoogleGenAI"
    llm_model: str = "gemini-3-flash-preview"
    llm_temperature: float = 1.0
    llm_max_tokens: int = 10000
    llm_max_steps: int = 50
    llm_timeout: int = 300
    llm_vision_enabled: bool = True
    llm_accessibility_enabled: bool = True

    # Task Configuration
    task_timeout: int = 1200

    def to_agent_config(self) -> BluestacksAgentConfig:
        """Convert to BluestacksAgentConfig for the SDK."""
        return BluestacksAgentConfig(
            llm_config={
                "provider": self.llm_provider,
                "model": self.llm_model,
                "temperature": self.llm_temperature,
                "max_tokens": self.llm_max_tokens,
                "max_steps": self.llm_max_steps,
                "timeout": self.llm_timeout,
                "vision": self.llm_vision_enabled,
                "accessibility": self.llm_accessibility_enabled,
            },
            task_timeout=self.task_timeout,
        )


# Global config instance
config = MCPConfig()
