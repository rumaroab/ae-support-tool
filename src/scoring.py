import numpy as np
import pandas as pd

OPERATING_HORIZON_DAYS = 90

PROTECTION_WEIGHTS = {
    "idle_seats": 0.25,
    "low_ai_adoption": 0.25,
    "support_pressure": 0.25,
    "contact_gap": 0.25,
}

REASON_LABELS = {
    "idle_seats": "low licensed-seat utilization",
    "low_ai_adoption": "low AI adoption",
    "support_pressure": "elevated support load per active user",
    "contact_gap": "stale sales contact",
    "peer_growth": "peer seat headroom; validate expansion fit",
}


def _ai_for_scoring(df: pd.DataFrame) -> pd.Series:
    median = df["ai_usage"].median()
    neutral = 0.5 if pd.isna(median) else float(median)
    return df["ai_usage"].fillna(neutral).clip(0, 1)


def _contact_for_scoring(df: pd.DataFrame) -> pd.Series:
    contact = df["days_since_last_sales_activity"]
    median = contact.median()
    neutral = 0.0 if pd.isna(median) else float(median)
    return contact.fillna(neutral)


def _renewal_urgency(df: pd.DataFrame) -> pd.Series:
    days = df["days_to_next_renewal"].clip(lower=0)
    return 1 / (1 + days / OPERATING_HORIZON_DAYS)


def _protection_parts(
    df: pd.DataFrame,
    ai_for_scoring: pd.Series,
    contact_for_scoring: pd.Series,
) -> dict[str, pd.Series]:
    return {
        "idle_seats": 1 - df["seat_utilization"].clip(0, 1),
        "low_ai_adoption": 1 - ai_for_scoring,
        "support_pressure": df["support_tickets_per_active_user"]
        .rank(pct=True)
        .fillna(0.5),
        "contact_gap": (
            contact_for_scoring / OPERATING_HORIZON_DAYS
        ).clip(0, 1),
    }


def _priority_reasons(
    df: pd.DataFrame, parts: dict[str, pd.Series]
) -> tuple[pd.Series, pd.Series]:
    reason_candidates = pd.DataFrame(parts)
    reason_candidates.loc[df["ai_usage"].isna(), "low_ai_adoption"] = -1
    reason_candidates.loc[
        df["days_since_last_sales_activity"].isna(), "contact_gap"
    ] = -1
    strongest_protection = reason_candidates.idxmax(axis=1)
    reason_key = strongest_protection.where(
        df["priority_action"].eq("Protect"), "peer_growth"
    )
    reason_text = reason_key.map(REASON_LABELS)
    reason_text = (
        df["priority_action"]
        + " — "
        + reason_text
        + "; renews in "
        + df["days_to_next_renewal"].round().astype(int).astype(str)
        + "d"
    )
    return reason_key, reason_text


def score_accounts(df: pd.DataFrame) -> pd.DataFrame:
    """Add action-value proxies, a dominant action, and an AE-readable reason."""
    df = df.copy()
    ai_for_scoring = _ai_for_scoring(df)
    contact_for_scoring = _contact_for_scoring(df)
    parts = _protection_parts(df, ai_for_scoring, contact_for_scoring)
    renewal_urgency = _renewal_urgency(df)

    protection_strength = sum(
        parts[name] * weight for name, weight in PROTECTION_WEIGHTS.items()
    )
    adoption_readiness = (
        df["seat_utilization"].clip(0, 1) * ai_for_scoring
    ) ** 0.5

    for name, values in parts.items():
        df[f"score_{name}"] = values
    df["score_protection_strength"] = protection_strength
    df["score_renewal_urgency"] = renewal_urgency
    df["score_adoption_readiness"] = adoption_readiness

    df["protect_value"] = (
        df["current_revenue"] * protection_strength * renewal_urgency
    )
    df["growth_value"] = (
        df["peer_expansion_seats"]
        * df["revenue_per_licensed_seat"]
        * adoption_readiness
        * renewal_urgency
    )
    df["priority_value"] = df[["protect_value", "growth_value"]].max(axis=1)
    df["priority_action"] = np.where(
        df["protect_value"] >= df["growth_value"], "Protect", "Grow"
    )
    df["contact_unknown"] = df["days_since_last_sales_activity"].isna()
    df["needs_contact"] = df["days_since_last_sales_activity"].gt(
        OPERATING_HORIZON_DAYS
    )

    keys, texts = _priority_reasons(df, parts)
    df["priority_reason_key"] = keys
    df["priority_reasons"] = texts
    return df