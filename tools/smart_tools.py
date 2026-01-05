"""
Core LLM Task Tools

Tools for running AI-driven autonomous tasks on the Android emulator, including:
- Running general Android tasks via natural language prompts
- Generating comprehensive QA test reports for Android applications
- Testing specific features within an Android app
"""

from typing import TYPE_CHECKING, Optional

from models import TaskResult, TestReportResult
from prompts import build_test_report_prompt, build_feature_test_prompt

if TYPE_CHECKING:
    from bluestacks import BluestacksAgent


async def run_android_task(
    query: str,
    agent: "BluestacksAgent",
) -> TaskResult:
    """
    Execute an AI-powered task on the Android emulator.
    
    The LLM agent will autonomously interact with the device to complete 
    the task described in the query. This is the primary way to perform
    complex, multi-step operations.
    
    Args:
        query: Natural language description of what to do.
               Examples:
               - "Open Settings and enable Dark Mode"
               - "Search for 'weather' in the Play Store"
               - "Take a photo and share it to Twitter"
               
    Returns:
        TaskResult with success status and output
    """
    result = await agent.run_task(query)

    await agent.stop_task()
    
    return TaskResult(
        success=result.success,
        output=result.output if result.success else "",
        error=result.reason if not result.success else "",
        error_code=result.error_code,
    )

async def generate_test_report(
    app_name: str,
    agent: "BluestacksAgent",
    app_description: Optional[str] = None,
) -> TestReportResult:
    """
    Generate a comprehensive QA test report for an Android application.
    
    This tool performs an autonomous, AI-driven testing workflow:
    1. Launches the app
    2. Explores main screens and navigation
    3. Tests core interactions (taps, inputs, scrolling)
    4. Checks for crashes, errors, and UI issues
    5. Generates a structured Markdown test report
    
    Args:
        app_name: Name or package of the app to test.
                 Examples: "Twitter", "com.twitter.android", 
                          "My Flutter App", "com.example.myapp"
        app_description: Optional context about what the app does.
                        Helps the AI focus on relevant features.
                        Example: "A social media app with feed, 
                                 messaging, and profile features"
        
    Returns:
        TestReportResult with Markdown-formatted test report
        
    Note:
        This can take 2-5 minutes depending on app complexity.
        The AI agent will autonomously navigate and test the app.
    """
    # Build the QA prompt
    prompt = build_test_report_prompt(
        app_name=app_name,
        app_description=app_description,
    )
    
    # Run the autonomous testing task
    result = await agent.run_task(prompt)

    await agent.stop_task()
    
    if result.success:
        return TestReportResult(
            success=True,
            report_markdown=result.output,
        )
    else:
        return TestReportResult(
            success=False,
            report_markdown="",
            error=result.reason,
            error_code=result.error_code,
        )

async def test_feature(
    app_name: str,
    feature_name: str,
    feature_description: str,
    agent: "BluestacksAgent",
) -> TestReportResult:
    """
    Test a specific feature within an Android application.
    
    Use this for focused testing of a single feature rather than
    comprehensive app testing. Ideal for:
    - Testing a new feature during development
    - Regression testing a specific workflow
    - Validating a bug fix
    
    Args:
        app_name: Name or package of the app.
        feature_name: Name of the feature to test.
                     Examples: "Login Flow", "Search", "Checkout",
                              "Photo Upload", "Push Notifications"
        feature_description: Detailed description of the feature and
                            how it should work. The more detail, the
                            better the testing.
                            
                            Example: "The login flow has email/password
                            fields, a 'Forgot Password' link, and a
                            'Sign Up' button. Valid login should redirect
                            to the home feed. Invalid credentials should
                            show an error message."
        
    Returns:
        TestReportResult with focused test report for the feature
        
    Tip:
        When using with GitHub Copilot, let it generate the 
        feature_description from your code. It understands your
        implementation and can describe expected behavior.
    """
    # Build the focused feature test prompt
    prompt = build_feature_test_prompt(
        app_name=app_name,
        feature_name=feature_name,
        feature_description=feature_description,
    )
    
    # Run the feature testing task
    result = await agent.run_task(prompt)

    await agent.stop_task()
    
    if result.success:
        return TestReportResult(
            success=True,
            report_markdown=result.output,
        )
    else:
        return TestReportResult(
            success=False,
            report_markdown="",
            error=result.reason,
            error_code=result.error_code,
        )
