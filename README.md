# Account Intelligence - AE Support Tool

A small Streamlit app that helps an Account Executive answer two questions:

1. Which accounts should I focus on today?
2. What should I know before my next meeting?

The account ranking is deterministic and outcome-free. A local Ollama model is used only to turn a small whitelist of account facts into a meeting brief.

## Quick start

The repository includes the synthetic `account_data.csv` used by the app. After cloning the repository:

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints, usually <http://localhost:8501>.

**Add the csv file with the name `account_data.csv` to the root of the repo**

## Ollama

Install Ollama, start it locally, and pull the configured model:

```bash
ollama serve
ollama pull gemma4:12b
```

`gemma4:12b` is about a 7.6 GB download. A different locally installed model can be selected with environment variables:

```powershell
$env:OLLAMA_MODEL = "gemma4:12b"
$env:OLLAMA_HOST = "http://localhost:11434"
```

`OLLAMA_HOST` must use `http://` and either `localhost` or `127.0.0.1`. Before generation, the app checks that Ollama is reachable and that the configured model is installed. Briefs are generated on demand and cached in Streamlit session state.

## Product flow

- **Today's Focus** shows the 10 highest-priority accounts renewing within 90 days, regardless of whether the suggested motion is Protect or Grow.
- **Meeting Brief** shows account facts, the latest call summary, and an optional grounded brief from the local model.
- Segment and region filters recalculate the portfolio summary and top-10 list.

The UI calls `process_data()` once and then `score_accounts()`. The future outcome column is removed before the runtime DataFrame is returned and is never available to scoring, the UI, or the model prompt.

## Architecture

```text
app.py                 # two-tab Streamlit UI
account_data.csv       # supplied synthetic account data
eda.ipynb              # outcome-separated retrospective review
src/data.py            # load, clean, and derive runtime features
src/scoring.py         # deterministic action-value heuristic
src/priorities.py      # daily summary and top-10 selection
src/prompts.py         # whitelisted context and prompt
src/llm.py             # local Ollama HTTP client
```

DataFrames are passed directly between these functions. Scoring does not depend on the LLM, and the LLM never calculates the priority value.

## Key decisions and why

- **Observable risk signals:** unused seats, AI adoption, support load, and contact recency are available before renewal and give the AE a concrete next action.
- **Equal protection weights:** the dataset has no historical training period. Equal weights avoid pretending that the synthetic cross-section supports precise calibration.
- **Revenue weighting:** current revenue represents business impact. The resulting dollar values are prioritization proxies, not churn probabilities or forecasts.
- **90-day horizon:** one quarter is long enough for an AE to act while keeping the daily list focused.
- **Capped peer expansion:** segment-median seat penetration supplies a simple comparison, while the two-times seat cap prevents extreme extrapolation.
- **Truthful missing data:** missing AI and contact values use the portfolio median only inside scoring. They remain `Unknown` in the UI and prompt and cannot become the displayed primary reason.
- **One ranked focus list:** the app selects the top 10 overall instead of reserving equal space for Protect and Grow. The data currently assigns 903 accounts to Protect and 97 to Grow, and the UI does not hide that imbalance.
- **Call summaries qualify rather than score:** short synthetic call text is not converted into brittle keyword rules. It is shown before the brief, and the prompt must surface any conflict with the suggested scoring motion.
- **Outcome separation:** `revenue_end_of_quarter` is used only in the retrospective notebook. The heuristic was not tuned against it.

## Prioritization

Protection strength is the equal-weight mean of:

- idle-seat ratio;
- low AI adoption;
- percentile rank of support tickets per active user;
- contact gap capped at the 90-day operating horizon.

Missing AI adoption and contact recency are median-filled only for these calculations. Missing signals are excluded when selecting the explanation shown to the AE.

Both motions use the same renewal urgency:

`renewal_urgency = 1 / (1 + days_to_renewal / 90)`

The action values are:

- `protect_value = current_revenue * protection_strength * renewal_urgency`
- `growth_value = peer_expansion_seats * revenue_per_licensed_seat * adoption_readiness * renewal_urgency`
- `priority_value = max(protect_value, growth_value)`

The larger value determines the suggested Protect or Grow motion. `needs_contact` is a separate flag for known contact gaps over 90 days; missing contact history is reported separately.

## LLM context and controls

The model receives only meeting-relevant fields for the selected account. The call summary is limited to 500 characters, and the full CSV and future outcome are never included.

The prompt uses Role, Task, Result format, Guardrails, and Facts sections. It requires supplied-number grounding, treats values as proxies, and tells the model not to force a motion when the latest call summary conflicts with it. Generation uses temperature `0.2` and a 400-token output limit for a more repeatable demo.

## Synthetic retrospective consistency

`eda.ipynb` loads `revenue_end_of_quarter` separately and evaluates the fixed heuristic. Nothing is calibrated against this outcome.

Top-50 review within each suggested action:

| Action | Assigned by heuristic | Evaluated top N | Outcome precision | Outcome recall | Outcome dollars captured |
| --- | ---: | ---: | ---: | ---: | ---: |
| Protect | 903 | 50 | 16.0% | 7.3% | 58.4% of loss dollars |
| Grow | 97 | 50 | 74.0% | 12.4% | 32.4% of growth dollars |

Absolute revenue-change capture across review budgets:

| Top K | Priority value | Current revenue | Renewal date | Random mean |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 6.4% | 2.4% | 1.3% | 1.0% |
| 25 | 27.3% | 18.7% | 3.3% | 2.6% |
| 50 | 41.3% | 34.0% | 4.3% | 5.0% |
| 100 | 55.1% | 64.9% | 11.3% | 10.1% |
| 200 | 86.2% | 87.2% | 29.2% | 20.3% |

The notebook also reports bootstrap 95% intervals and repeated-random ranges. These figures show retrospective consistency on one synthetic portfolio only. They are not evidence of predictive performance or production calibration.

## Limitations

- The dataset is one synthetic cross-section; it cannot support temporal or out-of-sample validation.
- The values are prioritization proxies, not calibrated churn probabilities, expected losses, or committed pipeline.
- Peer seat headroom is a scenario based on current portfolio peers, not a sales forecast.
- Call summaries are context for the AE and LLM, not a deterministic scoring input.
- Real outcome modeling requires historical snapshots and time-based validation.
- Local Ollama must be running with the configured model installed.