from pathlib import Path

import pandas as pd

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "account_data.csv"
OUTCOME_COLUMN = "revenue_end_of_quarter"
MAX_SEAT_GROWTH_MULTIPLIER = 2


def load_data(path: str | Path = DEFAULT_CSV) -> pd.DataFrame:
    return pd.read_csv(path)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # Pandas parses the CSV's North America code ("NA") as a missing value.
    df["region"] = df["region"].fillna("NA")
    df["call_transcript_summary"] = df["call_transcript_summary"].fillna("")
    return df


def add_derived_metrics(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    licensed = df["nr_licensed_seats"].replace(0, pd.NA)
    active = df["nr_active_users"].replace(0, pd.NA)
    employees = df["nr_employees"].replace(0, pd.NA)

    df["seat_utilization"] = (
        (df["nr_active_users"] / licensed).astype(float).fillna(0.0).clip(0, 1)
    )
    df["unused_seats"] = (
        df["nr_licensed_seats"] - df["nr_active_users"]
    ).clip(lower=0)
    df["revenue_per_licensed_seat"] = (
        (df["current_revenue"] / licensed).astype(float).fillna(0.0)
    )
    df["support_tickets_per_active_user"] = (
        (df["nr_support_tickets"] / active).astype(float).fillna(0.0)
    )

    seat_penetration = (
        (df["nr_licensed_seats"] / employees).astype(float).fillna(0.0).clip(0, 1)
    )
    peer_penetration = seat_penetration.groupby(df["segment"]).transform("median")
    peer_target_seats = (peer_penetration * df["nr_employees"]).clip(
        upper=df["nr_licensed_seats"] * MAX_SEAT_GROWTH_MULTIPLIER
    )
    df["peer_expansion_seats"] = (
        peer_target_seats - df["nr_licensed_seats"]
    ).clip(lower=0)

    return df


def process_data(path: str | Path = DEFAULT_CSV) -> pd.DataFrame:
    """Return the runtime feature frame without the future outcome column."""
    df = clean_data(load_data(path))
    df = df.drop(columns=[OUTCOME_COLUMN], errors="ignore")
    return add_derived_metrics(df)