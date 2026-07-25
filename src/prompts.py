import math

MODE_DIRECTIVES = {
    "PROTECT": (
        "Prepare for a retention conversation. Focus on adoption, support, contact, "
        "and contract risks; do not propose an upsell."
    ),
    "GROW": (
        "Prepare for a growth conversation. Validate the peer seat opportunity before "
        "proposing a scoped expansion."
    ),
}


def account_mode(row) -> str:
    return str(row["priority_action"]).upper()


def _value(value):
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and math.isnan(value):
        return "unknown"
    if isinstance(value, float):
        return round(value, 4)
    return value


def build_account_context(row, mode: str | None = None) -> dict:
    """Return a small whitelist of meeting-relevant account facts."""
    mode = mode or account_mode(row)
    context = {
        "account_name": _value(row["account_name"]),
        "industry": _value(row["industry"]),
        "segment": _value(row["segment"]),
        "current_revenue_usd": int(round(row["current_revenue"])),
        "days_to_renewal": int(round(row["days_to_next_renewal"])),
        "days_since_last_sales_contact": _value(
            row["days_since_last_sales_activity"]
        ),
        "licensed_seats": int(round(row["nr_licensed_seats"])),
        "active_users": int(round(row["nr_active_users"])),
        "idle_seats": int(round(row["unused_seats"])),
        "seat_utilization_pct": round(float(row["seat_utilization"]) * 100, 1),
        "ai_adoption_0_to_1": _value(row["ai_usage"]),
        "open_support_tickets": int(round(row["nr_support_tickets"])),
        "primary_reason": _value(row["priority_reasons"]),
    }

    if mode == "PROTECT":
        context["weighted_revenue_exposure_usd"] = int(round(row["protect_value"]))
    else:
        context["weighted_growth_potential_usd"] = int(round(row["growth_value"]))
        context["peer_expansion_seats"] = int(round(row["peer_expansion_seats"]))

    summary = str(row.get("call_transcript_summary", "") or "").strip()
    if summary:
        context["call_summary"] = summary[:500]
    return context


def build_meeting_brief_prompt(context: dict, mode: str) -> str:
    facts = "\n".join(f"- {key}: {value}" for key, value in context.items())
    return f"""### Role
You are a sales assistant preparing an Account Executive for a meeting.

### Task
Write a concise meeting-preparation brief using only the supplied facts.
Meeting mode: {mode}. {MODE_DIRECTIVES[mode]}

### Result format
Use these short markdown sections:
1. Headline
2. Key signals
3. Recommended play
4. Talking points
5. Questions and unknowns

### Guardrails
- Use only supplied facts and cite a supplied number for quantitative claims.
- Treat weighted exposure and growth potential as prioritization proxies, not forecasts.
- If the call summary conflicts with the meeting mode, state the conflict and do not force the proposed motion.
- Do not mention internal field names, scoring formulas, percentiles, or synthetic outcomes.
- Do not ask a question already answered by the facts.
- Keep the result concise.

### Account facts
{facts}
"""