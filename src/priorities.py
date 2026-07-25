import pandas as pd

from src.scoring import OPERATING_HORIZON_DAYS

FOCUS_SIZE = 10

NEXT_ACTIONS = {
    "idle_seats": "Review seat assignments and right-size before renewal.",
    "low_ai_adoption": "Schedule enablement around the workflow blocking adoption.",
    "support_pressure": "Review open tickets with CS and bring a remediation plan.",
    "contact_gap": "Rebook a touchpoint this week; do not wait for renewal.",
    "peer_growth": "Validate the peer seat gap and propose a scoped rollout.",
}


def daily_pulse(df: pd.DataFrame) -> dict:
    near = df["days_to_next_renewal"] <= OPERATING_HORIZON_DAYS
    protect = near & df["priority_action"].eq("Protect")
    grow = near & df["priority_action"].eq("Grow")
    return {
        "protect_value": float(df.loc[protect, "protect_value"].sum()),
        "growth_value": float(df.loc[grow, "growth_value"].sum()),
        "needs_contact": int((near & df["needs_contact"]).sum()),
        "contact_unknown": int((near & df["contact_unknown"]).sum()),
    }


def daily_focus(df: pd.DataFrame) -> pd.DataFrame:
    near = df["days_to_next_renewal"] <= OPERATING_HORIZON_DAYS
    return (
        df.loc[near]
        .sort_values("priority_value", ascending=False)
        .head(FOCUS_SIZE)
    )


def recommended_action(row: pd.Series) -> str:
    if row["needs_contact"]:
        return NEXT_ACTIONS["contact_gap"]
    return NEXT_ACTIONS[row["priority_reason_key"]]