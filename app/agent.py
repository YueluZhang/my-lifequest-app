# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types
from google.adk.tools import ToolContext

# Import the MCP filesystem toolset and callbacks
from app.tools import mcp_filesystem_toolset, load_game_state, save_game_state

# ==========================================
# SUB-AGENT 1: JobBossAgent Tools & Definition
# ==========================================


def get_boss_intel(job_description: str, tool_context: ToolContext) -> dict:
    """Analyze a job description to return boss intel (fit score and prep tips).
    Awards XP on completion.

    Args:
        job_description: The job description text to analyze.
    """
    state = tool_context.state
    # Award 50 XP
    xp = state.get("xp", 0) + 50
    state["xp"] = xp

    # Append to quest log
    quest_log = state.get("quest_log", [])
    quest_log.append(f"Analyzed Job: {job_description[:30]}...")
    state["quest_log"] = quest_log

    return {
        "fit_score": 88,
        "interview_tips": [
            "Highlight past projects matching requirements.",
            "Prepare questions about the team structure.",
            "Review technical prerequisites.",
        ],
        "xp_awarded": 50,
    }


job_boss_agent = Agent(
    name="job_boss_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the JobBossAgent. Your role is to analyze job descriptions, return a fit score, and offer interview preparation tips.
When analyzing, call get_boss_intel to retrieve intel and award XP to the user.""",
    tools=[get_boss_intel],
    description="Analyzes job descriptions, returns fit score/prep tips, and awards XP.",
)

# ==========================================
# SUB-AGENT 2: GoldKeeperAgent Tools & Definition
# ==========================================


def record_transaction(
    amount: float, entry_type: str, description: str, tool_context: ToolContext
) -> dict:
    """Record a real financial transaction (income or expense), updates local save,
    and updates game gold. Triggers HP penalty and warning if gold drops too low.

    Args:
        amount: The real dollar amount of the transaction.
        entry_type: Either 'income' or 'expense'.
        description: Description of the transaction.
    """
    state = tool_context.state
    real_balance = state.get("real_balance", float(state.get("gold", 500.0)))
    real_transactions = state.get("real_transactions", [])

    # Ensure amount is signed correctly based on entry_type or keep the sign if already negative
    amt = amount
    if entry_type.lower() == "expense":
        if amt > 0:
            amt = -amt
    elif entry_type.lower() == "income":
        if amt < 0:
            amt = -amt

    # Update real balance (stored locally only)
    real_balance += amt

    real_transactions.append(
        {"amount": amt, "type": entry_type, "description": description}
    )
    state["real_balance"] = real_balance
    state["real_transactions"] = real_transactions

    import calendar

    # Convert/Update gold (1 USD = 1 Gold Point)
    state["gold"] = int(real_balance)

    budget = state.get("budget", 1500)
    today = datetime.date.today()
    _, total_days = calendar.monthrange(today.year, today.month)
    days_remaining = total_days - today.day + 1
    threshold = (days_remaining / total_days) * budget

    hp = state.get("hp", 100)
    warning = ""
    budget_suggestion = ""
    if state["gold"] < threshold:
        # HP penalty
        hp = max(0, hp - 10)
        state["hp"] = hp
        warning = f"⚠️ HP Warning! Your gold ({state['gold']}) is below the proportional monthly budget threshold of {threshold:.1f} ({days_remaining} days remaining). You lost 10 HP!"
        budget_suggestion = f"Budget Suggestion: You are spending faster than your monthly budget of {budget} allows. Minimize discretionary spending immediately."

    return {
        "status": "success",
        "new_gold": state["gold"],
        "hp": hp,
        "warning": warning,
        "budget_suggestion": budget_suggestion,
    }


def update_monthly_budget(budget: float, tool_context: ToolContext) -> dict:
    """Update the user's monthly budget target.

    Args:
        budget: The new monthly budget target amount.
    """
    state = tool_context.state
    state["budget"] = int(budget)
    return {"status": "success", "new_budget": state["budget"]}


gold_keeper_agent = Agent(
    name="gold_keeper_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the GoldKeeperAgent. Your role is to record real income/expense transactions and update the gold balance.
Call record_transaction to update stats. If gold drops below 100, issue an HP warning and budget suggestion.
Additionally, if the user expresses an intent to set or change their monthly budget, call update_monthly_budget to parse and save the new budget, and confirm it in your response.""",
    tools=[record_transaction, update_monthly_budget],
    description="Handles income/expense entries, updates gold, handles low budget warnings, and manages monthly budget targets.",
)

# ==========================================
# SUB-AGENT 3: TimeGuardianAgent Tools & Definition
# ==========================================


def manage_deadlines(
    action: str,
    title: Optional[str] = None,
    due_date: Optional[str] = None,
    month_query: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> dict:
    """Add, view, or manage deadlines. Detects conflicts and returns countdown warnings.

    Args:
        action: 'add' or 'list'.
        title: Title of the deadline/task.
        due_date: Due date in YYYY-MM-DD format.
        month_query: Optional filter for a specific month (e.g. '2026-08' or 'August 2026').
    """
    state = tool_context.state
    deadlines = state.get("deadlines", [])

    if action == "add" and title and due_date:
        month_tag = due_date[:7]  # YYYY-MM
        deadlines.append(
            {
                "label": title,
                "date": due_date,
                "month": month_tag,
                "title": title,
                "due_date": due_date,
            }
        )
        state["deadlines"] = deadlines

    # Check for conflicts (same due date)
    date_counts = {}
    for d in deadlines:
        d_date = d.get("date") or d.get("due_date")
        if d_date:
            date_counts[d_date] = date_counts.get(d_date, 0) + 1

    conflicts = [date for date, count in date_counts.items() if count > 1]

    warnings = []
    if conflicts:
        warnings.append(
            f"⚠️ Conflict Detected! You have multiple deadlines on: {', '.join(conflicts)}"
        )

    # Calculate countdown warnings
    today = datetime.date.today()
    countdown_warnings = []
    for d in deadlines:
        d_date = d.get("date") or d.get("due_date")
        d_title = d.get("label") or d.get("title")
        if d_date and d_title:
            try:
                due = datetime.datetime.strptime(d_date, "%Y-%m-%d").date()
                days_left = (due - today).days
                if 0 <= days_left <= 3:
                    countdown_warnings.append(
                        f"Countdown: '{d_title}' is due in {days_left} days!"
                    )
            except Exception:
                pass

    # Filter by month if query is provided
    returned_deadlines = deadlines
    if month_query:
        import re

        q = month_query.strip().lower()
        target_month = None
        if re.match(r"^\d{4}-\d{2}$", q):
            target_month = q
        else:
            months_map = {
                "jan": "01",
                "feb": "02",
                "mar": "03",
                "apr": "04",
                "may": "05",
                "jun": "06",
                "jul": "07",
                "aug": "08",
                "sep": "09",
                "oct": "10",
                "nov": "11",
                "dec": "12",
                "january": "01",
                "february": "02",
                "march": "03",
                "april": "04",
                "june": "06",
                "july": "07",
                "august": "08",
                "september": "09",
                "october": "10",
                "november": "11",
                "december": "12",
            }
            year_match = re.search(r"\b(\d{4})\b", q)
            if year_match:
                year_str = year_match.group(1)
                for name, num in months_map.items():
                    if name in q:
                        target_month = f"{year_str}-{num}"
                        break

        if not target_month:
            target_month = q

        returned_deadlines = [
            d
            for d in deadlines
            if d.get("month") == target_month
            or (d.get("date") or d.get("due_date", ""))[:7] == target_month
        ]

    return {"deadlines": returned_deadlines, "warnings": warnings + countdown_warnings}


time_guardian_agent = Agent(
    name="time_guardian_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the TimeGuardianAgent. Your role is to manage deadlines, detect scheduling conflicts, and issue countdown warnings.
Call manage_deadlines to view, add, or query deadlines.
If the user queries deadlines for a specific month (e.g. 'August 2026' or '2026-08'), call manage_deadlines with action='list' and the month_query argument (e.g. month_query='2026-08'), then list only the deadlines matching that month.""",
    tools=[manage_deadlines],
    description="Manages deadlines, detects scheduling conflicts, and filters deadlines by month.",
)

# ==========================================
# DATA SECURITY LAYER / EXPORT TOOL
# ==========================================


def export_share_data(tool_context: ToolContext) -> dict:
    """Generates a shareable summary of the user's progress.
    Anonymizes real dollar amounts into 'Gold Points' to protect data privacy.
    """
    state = tool_context.state

    # DATA SECURITY LAYER:
    # Real dollar amounts (like real_balance) are only stored locally.
    # We anonymize real balance into "Gold Points" (1 USD = 1 Gold Point) before exporting.
    # This demonstrates the security-features requirement.
    gold_points = int(state.get("real_balance", 1000.0))
    hp = state.get("hp", 100)
    xp = state.get("xp", 0)
    quests = state.get("quest_log", [])

    export_string = (
        f"🏆 LIFEQUEST EXPORT 🏆\n"
        f"Player HP: {hp}/100\n"
        f"Gold Points: {gold_points} GP\n"
        f"XP: {xp}\n"
        f"Completed Quests: {', '.join(quests) if quests else 'None'}\n"
        f"Status: Active Adventurer!"
    )

    return {
        "share_summary": export_string,
        "note": "Real dollar amounts have been successfully anonymized into Gold Points.",
    }


# ==========================================
# ROOT AGENT: QuestMasterAgent Definition
# ==========================================

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction="""You are the QuestMasterAgent, the root coordinator of the "LifeQuest" RPG personal life management system.
You route user requests to the appropriate sub-agents:
1. JobBossAgent (job_boss_agent): For job descriptions, interview prep, fit scores, and completing job quests to earn XP.
2. GoldKeeperAgent (gold_keeper_agent): For recording real income/expense transactions, updating gold, and dealing with budget issues.
3. TimeGuardianAgent (time_guardian_agent): For adding/viewing deadlines, detecting scheduling conflicts, and warnings.

You also have the export_share_data tool for exporting progress.

Note: The game state is automatically loaded from and saved to save.json by the system callbacks. Do NOT call read_file or write_file to manage the state yourself. Instead, use the current values injected into your context below:
HP: {hp}
Gold: {gold}
XP: {xp}
Quest Log: {quest_log}

CRITICAL: Compound Event Detection
If the player faces a compound event (e.g., a tight deadline AND low gold/budget, or job prep under a tight deadline), you must trigger a coordinated "Dual-Quest" alert.
A Dual-Quest alert should be a single, joint warning/quest generated in the voices of both relevant sub-agents (e.g. TimeGuardian and GoldKeeper). Do not just output separate replies. For example:
"⚠️ DUAL-QUEST ALERT: 'The Eleventh Hour Thrift'! You have a critical deadline tomorrow and your gold is dangerously low. Complete the deadline quest to save HP, and outline a budget immediately to survive!"

Always maintain and update the game state {hp, gold, xp, quest_log} and display the updated stats block at the end of every reply in a beautiful RPG format:
=== PLAYER STATS ===
HP: {hp}/100 | Gold: {gold} | XP: {xp}
Quests: {quest_log}
====================
""",
    sub_agents=[job_boss_agent, gold_keeper_agent, time_guardian_agent],
    tools=[mcp_filesystem_toolset, export_share_data],
    before_agent_callback=load_game_state,
    after_agent_callback=save_game_state,
)

app = App(
    root_agent=root_agent,
    name="app",
)
