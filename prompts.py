"""
QA Prompt Templates

Builds structured prompts for test report generation and feature testing.
"""

from typing import Optional


def build_test_report_prompt(
    app_name: str,
    app_description: Optional[str] = None,
) -> str:
    """
    Build a comprehensive QA test report prompt.

    Args:
        app_name: Name or package of the app to test
        app_description: Optional context about the app's purpose

    Returns:
        Formatted prompt string for run_task()
    """

    context_section = ""
    if app_description:
        context_section = f"""
**App Context:** {app_description}
Use this context to prioritize testing relevant features and workflows.
"""

    prompt = f"""**Role:** Senior Mobile QA Automation Engineer

**App Under Test:** {app_name}
{context_section}
**Objective:** Execute a comprehensive QA workflow on this application and generate a structured test report. Follow the login-first → navigation → interactions testing sequence.

---

## ⚠️ CRITICAL RULES

### Text Field Handling
**Before entering ANY text in ANY input field throughout testing:**
1. **ALWAYS clear the field first** — select all text and delete, or clear the field completely
2. **Verify the field is empty** before typing new content
3. **Do NOT assume fields are empty** — previous test data may persist

This applies to: login fields, search fields, form inputs, dialogs with text fields, etc.

### Destructive Actions — SAVE FOR LAST
**The following actions should ONLY be performed at the very end, after all other testing is complete:**
- Logout / Sign out
- Delete account
- Clear all data / Reset app
- Uninstall or disable features
- Any action that would end the session or require re-authentication

**Rationale:** Performing these early will disrupt the testing flow and require re-login/re-setup.

### Hidden Content Discovery
**On EVERY screen, scroll to check for content below the fold:**
- Scroll down to reveal hidden elements, buttons, or sections
- Scroll up to ensure nothing is hidden above
- Check for horizontal scroll areas (carousels, tabs)
- Look for expandable sections or "show more" buttons
- Test any discovered hidden elements before moving to the next screen

---

## PHASE 1: AUTHENTICATION FLOW (Priority: Critical)

**If the app has a login/signup screen, test it FIRST with negative cases before successful login.**

### 1.1 Negative Test Cases — Execute Before Valid Login

**⚠️ IMPORTANT: Clear ALL input fields before EACH test case below.**

| Test Type | Pre-Action | Action | Expected Behavior |
|-----------|------------|--------|-------------------|
| Empty submission | Clear all fields | Submit with all fields empty | Validation errors for required fields |
| Invalid format | Clear all fields | Enter malformed email/username | Format validation error shown |
| Short password | Clear all fields | Enter password below minimum length | Password length error shown |
| Wrong credentials | Clear all fields | Enter incorrect but valid-format credentials | Error message displayed (no crash) |

### 1.2 Positive Test Cases

| Test Type | Pre-Action | Action | Expected Behavior |
|-----------|------------|--------|-------------------|
| Valid login | **Clear all fields first** | Enter correct credentials and submit | Navigate to main/home screen |
| Loading state | - | Observe during authentication | Loading indicator visible |
| Password visibility | - | Toggle password visibility if available | Text shows/hides correctly |

### 1.3 Post-Login Verification
- Verify user info displayed correctly on main screen
- Confirm session is established

**⚠️ If no authentication screen exists, skip to Phase 2.**

---

## PHASE 2: CORE NAVIGATION

### 2.1 Primary Navigation
- Identify main navigation (bottom nav, tabs, drawer, etc.)
- Test each navigation item — verify correct screen loads
- Test back button from each screen
- Verify smooth transitions between screens

### 2.2 Secondary Navigation
- Test app bar buttons (profile, settings, notifications, etc.)
- Test any floating action buttons
- Test menu items and overflow menus
- **⚠️ Do NOT tap logout/sign-out buttons yet**

### 2.3 Screen Exploration
- **Scroll each screen fully** to discover all content
- Note any elements that only appear after scrolling
- Check for sticky headers/footers
- Look for pull-to-refresh indicators

### 2.4 Navigation Edge Cases
- Rapid switching between screens
- Navigate during loading states
- Deep navigation and back out

---

## PHASE 3: INTERACTIVE ELEMENTS

**For each main screen discovered, test all interactive elements:**

### 3.1 Discovery — Scroll First
Before testing interactions on any screen:
1. **Scroll to the bottom** of the screen
2. **Scroll back to the top**
3. Note ALL interactive elements visible throughout the scroll
4. Check for lazy-loaded content that appears while scrolling

### 3.2 Buttons & Tappables
- Tap all visible buttons and verify response
- Tap cards, list items, icons that appear interactive
- Test floating action buttons and their menus
- **Skip any logout/delete/destructive buttons**

### 3.3 Input Fields

**⚠️ For EVERY input field test:**
1. **Clear the field before entering new text**
2. Enter test data
3. Verify the input is accepted/displayed correctly
4. **Clear again before the next test**

| Test Type | Pre-Action | Action | Verify |
|-----------|------------|--------|--------|
| Text entry | Clear field | Enter valid text | Text displays correctly |
| Search | Clear field | Enter search query | Results or behavior triggered |
| Special chars | Clear field | Enter special characters | Handled gracefully |

### 3.4 Dialogs & Menus
- Open all dialogs and menus
- **Clear any text fields in dialogs before entering data**
- Test all options within dialogs
- Verify dialogs dismiss correctly (back button, tap outside)
- **Skip any destructive options (delete, clear all, etc.) for now**

### 3.5 Gestures
- Scroll lists and content areas
- Pull-to-refresh where applicable
- Swipe actions on list items
- Long-press for context menus

### 3.6 Hidden Features Check
- Expand any collapsed sections
- Tap "Show more" or "View all" links
- Check settings screens for additional options (scroll!)
- Look for easter eggs or hidden debug menus

---

## PHASE 4: VALUE & STATE MONITORING

### 4.1 Track Dynamic Values
- Identify any counters, statistics, or numbers displayed
- Note their initial values

### 4.2 Test State Changes
- Perform actions that should change values (add, delete, increment)
- Verify values update correctly after each action
- Navigate away and back — verify persistence
- Test reset/clear functionality if available

### 4.3 Log Changes
Document: Action → Value Before → Value After → Expected → Match?

---

## PHASE 5: EDGE CASES & STABILITY

### 5.1 Error Handling
- Submit empty forms
- Enter maximum length text (**clear field first**)
- Test rapid consecutive taps

### 5.2 Stability
- Monitor for crashes throughout testing
- Note any freezes or unresponsive moments
- Check for UI glitches (overlapping text, clipped elements)

---

## PHASE 6: DESTRUCTIVE ACTIONS (Execute LAST)

**⚠️ Only perform these after ALL other testing is complete.**

### 6.1 Data Clearing
- Test "Clear all" or "Reset" options
- Verify data is actually cleared
- Note if confirmation dialogs appear

### 6.2 Logout Flow
- Tap logout/sign-out button
- Verify session ends correctly
- Confirm return to login screen
- Verify no user data persists after logout

### 6.3 Re-authentication (Optional)
- Attempt to log back in after logout
- Verify fresh login works correctly

---

**REQUIRED OUTPUT FORMAT:**

# 📱 {app_name} - QA Test Report

## 1. Executive Summary
| Metric | Value |
|--------|-------|
| **App Name** | {app_name} |
| **Test Date** | [Current Date] |
| **Overall Stability** | [Stable / Unstable / Crashed] |
| **Tests Executed** | [Number] |
| **Pass Rate** | [X/Y] ([Percentage]%) |

### Category Breakdown
| Category | Passed | Failed |
|----------|--------|--------|
| Authentication | [X] | [Y] |
| Navigation | [X] | [Y] |
| Interactions | [X] | [Y] |
| State/Values | [X] | [Y] |
| Destructive Actions | [X] | [Y] |

## 2. Authentication Results
| TC-ID | Test Case | Expected | Actual | Status |
|-------|-----------|----------|--------|--------|
| AUTH-01 | Empty form submission | Validation errors | [Observed] | PASS/FAIL |
| AUTH-02 | Invalid email format | Format error | [Observed] | PASS/FAIL |
| AUTH-03 | Wrong credentials | Error message | [Observed] | PASS/FAIL |
| AUTH-04 | Valid login | Navigate to home | [Observed] | PASS/FAIL |
| ... |

## 3. Navigation Results
| TC-ID | Test Case | Expected | Actual | Status |
|-------|-----------|----------|--------|--------|
| NAV-01 | [Screen navigation] | Loads correctly | [Observed] | PASS/FAIL |
| ... |

## 4. Interaction Results
| TC-ID | Screen | Element | Action | Result | Status |
|-------|--------|---------|--------|--------|--------|
| INT-01 | [Screen] | [Element] | [Action] | [Result] | PASS/FAIL |
| ... |

## 5. Hidden Features Discovered
| Screen | Element/Feature | Location | Tested | Status |
|--------|-----------------|----------|--------|--------|
| [Screen] | [Feature found by scrolling] | [Below fold / Collapsed] | Yes/No | PASS/FAIL |
| ... |

## 6. Value Monitoring Log
| Action | Before | After | Expected | Match |
|--------|--------|-------|----------|-------|
| [Action] | [Val] | [Val] | [Val] | ✅/❌ |
| ... |

## 7. Destructive Actions Results
| TC-ID | Test Case | Expected | Actual | Status |
|-------|-----------|----------|--------|--------|
| DEST-01 | Logout | Return to login | [Observed] | PASS/FAIL |
| ... |

## 8. Defects Found

✅ No critical defects found during testing.

*OR for each defect:*

### 🐛 BUG-001: [Title]
- **Severity:** [Critical / High / Medium / Low]
- **Steps to Reproduce:**
  1. [Step]
  2. [Step]
- **Expected:** [What should happen]
- **Actual:** [What happened]

## 9. Recommendations
1. [Recommendation]
2. [Recommendation]

---
*Report generated by BlueStacks MCP QA Agent*
"""

    return prompt


def build_feature_test_prompt(
    app_name: str,
    feature_name: str,
    feature_description: str,
) -> str:
    """
    Build a focused prompt for testing a specific feature.

    Args:
        app_name: Name or package of the app
        feature_name: Name of the feature to test (e.g., "Login Flow")
        feature_description: Detailed description of the feature and how to test it

    Returns:
        Formatted prompt string for run_task()
    """

    prompt = f"""**Role:** Senior Mobile QA Automation Engineer

**App Under Test:** {app_name}
**Feature Under Test:** {feature_name}

**Feature Description:**
{feature_description}

**Objective:** Thoroughly test this specific feature and generate a focused test report.

**Testing Approach:**

1. **Navigate to Feature:**
   - Launch the app if not already running
   - Navigate to the screen/area where this feature exists

2. **Happy Path Testing:**
   - Test the feature with valid/expected inputs
   - Verify the feature works as described
   - Confirm success states and feedback

3. **Edge Case Testing:**
   - Test with empty/blank inputs where applicable
   - Test with boundary values
   - Test rapid/repeated interactions
   - Test interruptions (back button, home, etc.)

4. **Error Handling:**
   - Test with invalid inputs if applicable
   - Verify error messages are clear and helpful
   - Ensure the app doesn't crash on bad input

5. **State Verification:**
   - Verify data persistence if applicable
   - Check state after background/foreground cycling
   - Verify integration with other features

---

**REQUIRED OUTPUT FORMAT:**

# 🔍 Feature Test Report: {feature_name}

## Summary
| Metric | Value |
|--------|-------|
| **App** | {app_name} |
| **Feature** | {feature_name} |
| **Test Date** | [Current Date] |
| **Overall Status** | [PASS / FAIL / PARTIAL] |
| **Tests Executed** | [Number] |
| **Pass Rate** | [X/Y] ([Percentage]%) |

## Test Cases

| TC-ID | Test Scenario | Input/Action | Expected | Actual | Status |
|-------|---------------|--------------|----------|--------|--------|
| FT-001 | [Scenario] | [Action] | [Expected] | [Actual] | PASS/FAIL |
| FT-002 | [Scenario] | [Action] | [Expected] | [Actual] | PASS/FAIL |
| [Continue...] |

## Defects Found

If no defects: "✅ No defects found in {feature_name}."

For each defect:
### 🐛 [ID]: [Title]
- **Severity:** [Critical/High/Medium/Low]  
- **Steps:** [1, 2, 3...]
- **Expected vs Actual:** [Comparison]

## Observations
- [Observation about feature behavior]
- [Performance notes]
- [UX feedback]

## Recommendation
[Pass to production / Needs fixes / Block release]

---
*Feature test by BlueStacks MCP QA Agent*
"""

    return prompt
