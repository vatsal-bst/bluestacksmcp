"""
Pydantic Models for MCP Tool Responses

All tools return structured responses for consistent LLM consumption.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class TaskResult(BaseModel):
    """Result from running an LLM-driven task."""
    success: bool = Field(description="Whether the task completed successfully")
    output: str = Field(default="", description="Task output/result text")
    error: str = Field(default="", description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")


class ToolResult(BaseModel):
    """Result from a simple tool operation."""
    success: bool = Field(description="Whether the operation succeeded")
    message: str = Field(default="", description="Success message or details")
    error: str = Field(default="", description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")


class ScreenshotResult(BaseModel):
    """Result from taking a screenshot."""
    success: bool = Field(description="Whether screenshot was captured")
    image_base64: str = Field(default="", description="Base64-encoded PNG image")
    error: str = Field(default="", description="Error message if failed")


class UITreeResult(BaseModel):
    """Result from getting UI hierarchy."""
    success: bool = Field(description="Whether UI tree was retrieved")
    ui_tree: str = Field(default="", description="JSON string of UI hierarchy")
    error: str = Field(default="", description="Error message if failed")


class ErrorLogsResult(BaseModel):
    """Result from fetching error logs."""
    success: bool = Field(description="Whether logs were retrieved")
    logs: str = Field(default="", description="Raw logcat output")
    error: str = Field(default="", description="Error message if failed")


class AppListResult(BaseModel):
    """Result from listing installed apps."""
    success: bool = Field(description="Whether package list was retrieved")
    packages: List[str] = Field(default_factory=list, description="List of package names")
    error: str = Field(default="", description="Error message if failed")


class TestReportResult(BaseModel):
    """Result from generating a test report."""
    success: bool = Field(description="Whether test report was generated")
    report_markdown: str = Field(default="", description="Markdown-formatted test report")
    error: str = Field(default="", description="Error message if failed")
    error_code: Optional[str] = Field(default=None, description="Machine-readable error code")
