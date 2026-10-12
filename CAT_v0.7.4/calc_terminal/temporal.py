"""
CAT Temporal — Dynamic Date, Time, and Temporal Query Resolution Engine.

Computes live system dates and resolves relative temporal queries
(e.g., "last month", "past 30 days", "this month", "recent", "yesterday")
dynamically at runtime without hardcoded years or stale snapshot dates.
"""

from __future__ import annotations

import calendar
import datetime
import re
from typing import Any, Dict, Optional, Tuple


def get_temporal_context(now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """Calculate rich dynamic temporal metadata based on live system clock."""
    if now is None:
        now = datetime.datetime.now()

    year = now.year
    month = now.month
    day = now.day

    # Determine "last month" (calendar month: 1st through last day)
    if month == 1:
        last_m_year = year - 1
        last_m = 12
    else:
        last_m_year = year
        last_m = month - 1

    last_m_name = calendar.month_name[last_m]
    _, last_m_days = calendar.monthrange(last_m_year, last_m)
    last_month_start = f"{last_m_year:04d}-{last_m:02d}-01"
    last_month_end = f"{last_m_year:04d}-{last_m:02d}-{last_m_days:02d}"

    # Determine rolling 30-day window
    rolling_30_start = (now - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    rolling_30_end = now.strftime("%Y-%m-%d")

    # Determine current month bounds
    _, this_m_days = calendar.monthrange(year, month)
    this_month_start = f"{year:04d}-{month:02d}-01"
    this_month_end = f"{year:04d}-{month:02d}-{this_m_days:02d}"

    # Determine past 7 days
    past_7_start = (now - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    yesterday = (now - datetime.timedelta(days=1)).strftime("%Y-%m-%d")

    return {
        "current_datetime": now.isoformat(),
        "current_date": now.strftime("%Y-%m-%d"),
        "current_year": year,
        "current_month": month,
        "current_month_name": calendar.month_name[month],
        "current_day": day,
        "weekday": now.strftime("%A"),
        "today_display": now.strftime("%A, %B %d, %Y"),
        "last_month_name": last_m_name,
        "last_month_year": last_m_year,
        "last_month_start": last_month_start,
        "last_month_end": last_month_end,
        "last_month_range": (last_month_start, last_month_end),
        "rolling_30_days_start": rolling_30_start,
        "rolling_30_days_end": rolling_30_end,
        "rolling_30_days_range": (rolling_30_start, rolling_30_end),
        "this_month_start": this_month_start,
        "this_month_end": this_month_end,
        "past_week_start": past_7_start,
        "yesterday": yesterday,
    }


def resolve_temporal_query(query: str, now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    """Analyze a user query or topic to identify relative time expressions
    and formulate dynamically dated search queries using live system dates.
    
    Supports:
    - Calendar month interpretation for 'last month' (e.g. Sept 1 - Sept 30, 2026).
    - Rolling 30-day interpretation when requested explicitly ('past 30 days', 'rolling 30 days').
    - Cleaning stale/hallucinated years (e.g. 2024 or 2025) from queries about recent events.
    """
    ctx = get_temporal_context(now)
    q_lower = query.lower()

    temporal_type = None
    start_date = None
    end_date = None
    time_label = None
    refined_query = query

    # Check for explicit rolling 30-day window
    if re.search(r"\b(rolling\s+30\s*days?|past\s+30\s*days?|last\s+30\s*days?|trailing\s+30\s*days?)\b", q_lower):
        temporal_type = "rolling_30_days"
        start_date = ctx["rolling_30_days_start"]
        end_date = ctx["rolling_30_days_end"]
        time_label = f"past 30 days ({start_date} to {end_date})"
        clean_q = re.sub(r"\b(rolling|past|last|trailing)\s+30\s*days?\b", "", query, flags=re.IGNORECASE).strip()
        refined_query = f"{clean_q} {ctx['current_year']}".strip()

    # Check for "last month" / "previous month" / "past month"
    elif re.search(r"\b(last\s+month|past\s+month|previous\s+month)\b", q_lower):
        temporal_type = "last_month"
        start_date = ctx["last_month_start"]
        end_date = ctx["last_month_end"]
        last_m_str = f"{ctx['last_month_name']} {ctx['last_month_year']}"
        time_label = f"{last_m_str} ({start_date} to {end_date})"

        # Replace 'last month' phrase with the actual month name & year
        clean_q = re.sub(r"\b(what\s+happened?\s+(in\s+)?|what\s+happen\s+(in\s+)?)", "", query, flags=re.IGNORECASE).strip()
        clean_q = re.sub(r"\b(last|past|previous)\s+month\b", "", clean_q, flags=re.IGNORECASE).strip()
        # Strip trailing questions or symbols
        clean_q = clean_q.rstrip("? ").strip()
        refined_query = f"{clean_q} {last_m_str}".strip()

    # Check for "this month" / "current month"
    elif re.search(r"\b(this\s+month|current\s+month)\b", q_lower):
        temporal_type = "this_month"
        start_date = ctx["this_month_start"]
        end_date = ctx["current_date"]
        time_label = f"{ctx['current_month_name']} {ctx['current_year']}"
        clean_q = re.sub(r"\b(this|current)\s+month\b", "", query, flags=re.IGNORECASE).strip()
        refined_query = f"{clean_q} {ctx['current_month_name']} {ctx['current_year']}".strip()

    # Check for "past week" / "last week" / "this week"
    elif re.search(r"\b(past\s+week|last\s+week|this\s+week)\b", q_lower):
        temporal_type = "past_week"
        start_date = ctx["past_week_start"]
        end_date = ctx["current_date"]
        time_label = f"past week ({start_date} to {end_date})"
        clean_q = re.sub(r"\b(past|last|this)\s+week\b", "", query, flags=re.IGNORECASE).strip()
        refined_query = f"{clean_q} {ctx['current_year']}".strip()

    # Check for general "latest" / "recent" / "today"
    elif re.search(r"\b(latest|recent|newest|today)\b", q_lower):
        temporal_type = "recent"
        start_date = ctx["rolling_30_days_start"]
        end_date = ctx["current_date"]
        time_label = f"recent {ctx['current_year']}"
        # Make sure current year is included
        if str(ctx["current_year"]) not in query:
            refined_query = f"{query} {ctx['current_year']}".strip()

    # Sanitize any stale years (e.g., 2024 or 2025 in recent-news queries)
    # If the user is asking about recent news, replace older years with current year/month
    if temporal_type in ("last_month", "rolling_30_days", "this_month", "recent", "past_week"):
        for stale_yr in range(2020, ctx["current_year"]):
            stale_str = str(stale_yr)
            if stale_str in refined_query:
                # Replace with appropriate year
                target_yr = ctx["last_month_year"] if temporal_type == "last_month" else ctx["current_year"]
                refined_query = re.sub(rf"\b{stale_str}\b", str(target_yr), refined_query)

    # Normalize multiple whitespace
    refined_query = " ".join(refined_query.split())

    return {
        "original_query": query,
        "refined_query": refined_query,
        "temporal_type": temporal_type,
        "start_date": start_date,
        "end_date": end_date,
        "time_label": time_label,
        "context": ctx,
    }


def get_system_prompt_temporal_block(now: Optional[datetime.datetime] = None) -> str:
    """Produces the formatted system prompt context block to anchor the AI agent
    to current reality and prevent training-cutoff hallucinations."""
    ctx = get_temporal_context(now)
    return (
        f"\n\n## CURRENT SYSTEM TEMPORAL CONTEXT\n"
        f"- Current Date & Time: {ctx['today_display']} ({ctx['current_date']})\n"
        f"- Current Year: {ctx['current_year']} | Current Month: {ctx['current_month_name']} {ctx['current_year']}\n"
        f"- Last Calendar Month: {ctx['last_month_name']} {ctx['last_month_year']} ({ctx['last_month_start']} to {ctx['last_month_end']})\n"
        f"- Rolling 30-Day Period: {ctx['rolling_30_days_start']} to {ctx['rolling_30_days_end']}\n"
        f"- Guidelines for Time-Sensitive Queries:\n"
        f"  1. When asked about 'last month', always refer to {ctx['last_month_name']} {ctx['last_month_year']}.\n"
        f"  2. If the user asks for a rolling 30-day period, use {ctx['rolling_30_days_start']} to {ctx['rolling_30_days_end']}.\n"
        f"  3. NEVER hallucinate older training-cutoff years (e.g. 2024 or 2025) for recent news.\n"
        f"  4. Formulate live web search queries using the calculated dates: e.g. '{ctx['last_month_name']} {ctx['last_month_year']}'.\n"
    )
