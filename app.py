"""Account Intelligence Streamlit app for Account Executives."""

import streamlit as st

from src.data import process_data
from src.llm import DEFAULT_HOST, DEFAULT_MODEL, generate_brief
from src.priorities import daily_focus, daily_pulse, recommended_action
from src.prompts import account_mode, build_account_context
from src.scoring import OPERATING_HORIZON_DAYS, score_accounts

st.set_page_config(page_title="AE Support Tool", layout="wide")


@st.cache_data
def load_scored_accounts():
    return score_accounts(process_data())


def _display_days(value):
    return "Unknown" if value != value else str(int(value))


def render_brief_button(row):
    account_id = row["account_id"]
    mode = account_mode(row)
    cache_key = f"brief_{account_id}_{mode}"
    st.caption(f"Model: `{DEFAULT_MODEL}` @ `{DEFAULT_HOST}`")

    if st.button("Generate meeting brief", type="primary", key=f"brief_{account_id}"):
        with st.spinner("Calling Ollama..."):
            try:
                context = build_account_context(row, mode=mode)
                st.session_state[cache_key] = generate_brief(context, mode=mode)
            except Exception as exc:
                st.error(f"Ollama request failed: {exc}")

    if cache_key in st.session_state:
        st.markdown(st.session_state[cache_key])
        if st.button("Clear cached brief", key=f"clear_{account_id}"):
            del st.session_state[cache_key]
            st.rerun()


def _filter_accounts(df):
    c1, c2 = st.columns(2)
    segment = c1.selectbox(
        "Segment", ["All"] + sorted(df["segment"].unique().tolist())
    )
    region = c2.selectbox(
        "Region", ["All"] + sorted(df["region"].unique().tolist())
    )

    filtered = df
    if segment != "All":
        filtered = filtered[filtered["segment"] == segment]
    if region != "All":
        filtered = filtered[filtered["region"] == region]
    return filtered


def render_today(df):
    st.subheader("Today's Focus")
    st.caption(
        "Transparent action-value proxies for accounts renewing within "
        f"{OPERATING_HORIZON_DAYS} days — not forecasts or committed pipeline."
    )
    filtered = _filter_accounts(df)

    if filtered.empty:
        st.info("No accounts match the current filters.")
        return

    pulse = daily_pulse(filtered)
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Protection priority proxy", f"${pulse['protect_value']:,.0f}")
    p2.metric("Growth priority proxy", f"${pulse['growth_value']:,.0f}")
    p3.metric("Accounts needing contact", pulse["needs_contact"])
    p4.metric("Contact history unknown", pulse["contact_unknown"])

    focus = daily_focus(filtered)
    st.markdown("### Top priorities")
    if focus.empty:
        st.caption("No accounts renew within the current operating horizon.")

    for _, row in focus.iterrows():
        action = row["priority_action"]
        value_column = "protect_value" if action == "Protect" else "growth_value"
        value_label = "protection proxy" if action == "Protect" else "growth proxy"
        if row["contact_unknown"]:
            contact_badge = " | Contact unknown"
        elif row["needs_contact"]:
            contact_badge = " | Needs contact"
        else:
            contact_badge = ""
        title = (
            f"{action} | {row['account_name']} - ${row[value_column]:,.0f} "
            f"{value_label} - {int(row['days_to_next_renewal'])}d{contact_badge}"
        )
        with st.expander(title):
            st.markdown(f"**Why:** {row['priority_reasons']}")
            st.markdown(f"**Next action:** {recommended_action(row)}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Current revenue", f"${row['current_revenue']:,.0f}")
            m2.metric("Seat utilization", f"{row['seat_utilization']:.0%}")
            m3.metric(
                "Days since contact",
                _display_days(row["days_since_last_sales_activity"]),
            )
            m4.metric("Support tickets", int(row["nr_support_tickets"]))
    with st.expander("All ranked accounts"):
        ranked = filtered.sort_values("priority_value", ascending=False)
        display = ranked[
            [
                "account_id",
                "account_name",
                "segment",
                "region",
                "priority_action",
                "priority_value",
                "protect_value",
                "growth_value",
                "needs_contact",
                "contact_unknown",
                "priority_reasons",
                "days_to_next_renewal",
                "current_revenue",
            ]
        ].rename(
            columns={
                "priority_action": "action",
                "priority_value": "priority_proxy",
                "protect_value": "protection_priority_proxy",
                "growth_value": "growth_priority_proxy",
                "priority_reasons": "why_this_account",
                "days_to_next_renewal": "days_to_renewal",
            }
        )
        st.dataframe(display.reset_index(drop=True), width="stretch", hide_index=True)


def render_meeting_brief(df):
    st.subheader("Meeting Brief")
    ranked = df.sort_values("priority_value", ascending=False)
    account_names = ranked.set_index("account_id")["account_name"].to_dict()
    account_id = st.selectbox(
        "Account",
        ranked["account_id"].tolist(),
        format_func=lambda value: f"{account_names[value]} ({value})",
    )
    row = ranked[ranked["account_id"] == account_id].iloc[0]

    st.markdown(f"### {row['account_name']} (`{row['account_id']}`)")
    st.write(row["account_description"])

    dominant_value = (
        row["protect_value"]
        if row["priority_action"] == "Protect"
        else row["growth_value"]
    )
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Suggested scoring motion", row["priority_action"])
    m2.metric("Action value", f"${dominant_value:,.0f}")
    m3.metric("Current revenue", f"${row['current_revenue']:,.0f}")
    m4.metric("Days to renewal", int(row["days_to_next_renewal"]))
    st.caption("Action value is a prioritization proxy, not a financial forecast.")
    st.markdown(f"**Why this account:** {row['priority_reasons']}")
    st.markdown("#### Latest call summary")
    st.write(row["call_transcript_summary"] or "_No call summary available._")
    st.caption("Use the latest call context to validate or qualify the scoring motion.")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Account facts")
        st.table(
            {
                "field": [
                    "Industry",
                    "Segment",
                    "Region",
                    "Licensed seats",
                    "Active users",
                    "Idle seats",
                ],
                "value": [
                    str(row["industry"]),
                    str(row["segment"]),
                    str(row["region"]),
                    str(int(row["nr_licensed_seats"])),
                    str(int(row["nr_active_users"])),
                    str(int(row["unused_seats"])),
                ],
            }
        )
    with right:
        ai_usage = (
            "Unknown"
            if row["ai_usage"] != row["ai_usage"]
            else f"{row['ai_usage']:.2f}"
        )
        st.markdown("#### Account signals")
        st.table(
            {
                "field": [
                    "Seat utilization",
                    "AI adoption",
                    "Support tickets",
                    "Days since contact",
                    "Peer expansion seats",
                    "Needs contact",
                ],
                "value": [
                    f"{row['seat_utilization']:.0%}",
                    ai_usage,
                    str(int(row["nr_support_tickets"])),
                    _display_days(row["days_since_last_sales_activity"]),
                    str(int(round(row["peer_expansion_seats"]))),
                    (
                        "Unknown"
                        if row["contact_unknown"]
                        else ("Yes" if row["needs_contact"] else "No")
                    ),
                ],
            }
        )


    st.markdown("#### Generated brief")
    render_brief_button(row)


def main():
    st.title("Account Intelligence")
    st.caption("Decide who to focus on today and prepare for the next meeting.")
    df = load_scored_accounts()
    tab_focus, tab_brief = st.tabs(["Today's Focus", "Meeting Brief"])
    with tab_focus:
        render_today(df)
    with tab_brief:
        render_meeting_brief(df)


if __name__ == "__main__":
    main()