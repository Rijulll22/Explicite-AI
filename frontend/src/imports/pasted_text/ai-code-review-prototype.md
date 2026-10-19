Design a high-fidelity desktop web application prototype for:

“AI-Powered Explainable Code Review Assistant — Enhanced SonarQube”

This is the first version of a university software engineering project prototype. The application enhances a SonarQube-style code analysis experience by helping users understand detected code issues, assess their risk, prioritize them and receive guidance for resolving them.

IMPORTANT:
This is VERSION 1 BEFORE USER FEEDBACK.
Do not show any “improved version”, feedback labels, iteration labels, before/after comparisons, or references to user testing.

The design should look like a realistic developer software tool rather than an AI marketing website.

VISUAL STYLE:
- Desktop web application
- Light theme
- Clean professional developer-tool interface
- White and light gray backgrounds
- Dark text
- Restrained blue accent
- Simple borders
- Moderate corner radius
- Clear typography
- Consistent spacing
- Simple professional icons
- Practical information-dense layout
- No futuristic AI graphics
- No robots
- No glowing effects
- No excessive gradients
- No glassmorphism
- No unnecessary illustrations
- No marketing landing page
- No excessive rounded cards

The application should feel like an early but realistic university-developed software product.

GLOBAL NAVIGATION:

Create a persistent left sidebar containing:

Dashboard
Issues
AI Code Assistant
Code Analysis
Projects
Learning
Settings

At the top, show:
- Project name
- Repository
- Last analysis
- User profile

Use consistent navigation and components across all screens.

CORE WORKFLOW:

Detect → Understand → Prioritise → Fix → Verify → Learn

SCREEN 1 — LOGIN

Create a simple login page.

Include:
- Application name
- Email field
- Password field
- Login button
- Sign Up option
- Forgot password option

Keep it functional-looking and minimal.

SCREEN 2 — PROJECT DASHBOARD

Create the main project dashboard for a fictional project called:

“Student Management System”

Include:

Project Health
Quality Gate
Bugs
Vulnerabilities
Code Smells
Security Hotspots
Technical Debt

Use realistic sample values:

Bugs: 12
Vulnerabilities: 3
Code Smells: 24
Security Hotspots: 5

Include a “Priority Issues” section containing several high-priority issues.

Include:
- Project health summary
- Quality Gate status
- Priority issues
- Recent analysis
- Quick actions

Use only a small number of charts. Do not make the dashboard visually overwhelming.

SCREEN 3 — ISSUES

Create an issue-management page.

Include:
- Search
- Filters
- Severity filter
- Issue type filter
- Status filter

Create a table with:

Severity
Issue
Rule
File
Line
Risk
Status
Action

Use fictional examples such as:

SQL Injection
Hard-coded Password
Null Pointer Dereference
High Cognitive Complexity
Duplicate Code

Use Critical, High, Medium and Low severity indicators.

Allow the user to select an issue and open its details.

SCREEN 4 — ISSUE DETAILS

Make this one of the most important screens.

Show a selected issue:

“SQL Injection”

Include:

Severity: Critical
Risk: High

Show:
- File name
- Line number
- Code snippet
- Issue description

Create a clear section:

“WHAT IS THE ISSUE?”

Provide a short plain-language explanation.

Create:

“WHY DOES IT MATTER?”

Explain the potential impact.

Create:

“RISK ANALYSIS”

Show:
- Severity
- Impact
- Likelihood
- Overall Risk

Create:

“CODE CONTEXT”

Show the relevant code snippet and location.

Create:

“AI EXPLANATION”

Clearly label this as AI-generated information.

Create:

“SUGGESTED GUIDANCE”

Provide a short recommendation describing what the developer could consider doing.

Do not make the AI section look futuristic.

SCREEN 5 — AI CODE ASSISTANT

Create a dedicated AI Code Assistant page.

The interface should look like a normal developer assistant rather than a chatbot marketing screen.

Include:
- Conversation area
- User question
- AI response
- Code context
- Suggested questions

Example suggested questions:

“What does this issue mean?”
“Why is this risky?”
“How can I fix it?”
“Show me a safer approach.”

Clearly identify AI-generated responses.

SCREEN 6 — SUGGESTED FIX / CODE COMPARISON

Create a page where the developer can examine a suggested improvement.

Show:

ORIGINAL CODE
versus
SUGGESTED CODE

Include:
- Code comparison
- AI explanation
- Why the suggested approach helps
- Next steps

Add actions:

Apply Fix
Reject Suggestion
Ask AI

Do not claim that the system automatically modifies real code. This is only a prototype interaction.

SCREEN 7 — CODE ANALYSIS

Create a code-analysis results page.

Show:

Before Changes
After Changes

Include:
- Issue count
- Resolved issues
- Remaining issues
- Quality Gate status
- Quality changes

The screen should represent the verification stage of the workflow.

SCREEN 8 — LEARNING

Create a Learning & Recommendations page for users who want to improve their coding skills.

Include:

Recommended Learning
Learning Progress
Recently Detected Issues
Learning Paths

Example resources:

Understanding Code Smells
Understanding Security Vulnerabilities
Technical Debt Basics
Secure Coding Practices

Keep this screen simple and educational.

SCREEN 9 — PROJECTS

Create a project overview page for users managing multiple projects.

Include:
- Project name
- Quality status
- Bugs
- Vulnerabilities
- Code Smells
- Coverage
- Last analysis
- Actions

Show multiple fictional projects.

SCREEN 10 — SETTINGS

Create a settings page containing:

Profile
Appearance
Preferences
Project Defaults
Analysis Settings
Developer Settings

Keep the layout practical and simple.

INTERACTIONS:

Create clickable prototype interactions between the screens.

Primary flow:

Login
→ Dashboard
→ Issues
→ Select Issue
→ Issue Details
→ AI Explanation
→ Suggested Fix
→ Code Comparison
→ Code Analysis

Secondary navigation:

Dashboard
→ Projects

Dashboard
→ Learning

Dashboard
→ Settings

ISSUE DETAILS INTERACTIONS:

Issue Details
→ AI Assistant
→ Suggested Fix
→ Code Analysis

DESIGN REQUIREMENTS:

Maintain consistency across every screen.

Use:
- Consistent typography
- Consistent navigation
- Consistent buttons
- Consistent severity indicators
- Consistent spacing
- Consistent component structure

Give priority to information that users need to understand and act on.

The prototype should communicate:

1. What problem was detected?
2. Why does it matter?
3. How risky is it?
4. What should the user do?
5. How can the user verify the result?

Use fictional project and code data only.

Do not implement an actual LLM.
Do not implement actual SonarQube integration.
Do not implement a real risk-scoring algorithm.
Represent these as realistic prototype interfaces and sample data.

FINAL RESULT:

Create a coherent high-fidelity VERSION 1 prototype with all ten screens connected through a realistic developer workflow.

The final interface should look like a genuine software engineering project rather than an AI-generated concept advertisement.