# Account Intelligence - AE Support Tool

A small Streamlit app that helps an Account Executive answer two questions:

1. Which accounts should I focus on today?
2. What should I know before my next meeting?

The account ranking is deterministic and outcome-free. A local Ollama model is used only to turn a small whitelist of account facts into a meeting brief.

## Quick start

After cloning the repository:
**Add the csv file with the name `account_data.csv` to the root of the repository**

```bash
python -m venv .venv

# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Open the URL Streamlit prints, usually <http://localhost:8501>.


## Ollama

Install Ollama, start it locally, and pull the configured model:

```bash
ollama serve
ollama pull gemma4:12b
```

Any model can be used I used  `gemma4:12b` that is about a 7.6 GB download, and I have the resources to run it seamlessly from my local setup. A different locally installed model can be selected with environment variables:

```powershell
# Windows
$env:OLLAMA_MODEL = "gemma4:12b"
$env:OLLAMA_HOST = "http://localhost:11434"
```

```bash
# macOS/Linux
export OLLAMA_MODEL="gemma4:12b"
export OLLAMA_HOST="http://localhost:11434"
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

`eda.ipynb` loads `revenue_end_of_quarter` separately and evaluates the fixed heuristic on the same 244 accounts the product can surface: renewals within the 90-day operating horizon. Nothing is calibrated against this outcome.

Top-50 review within each suggested action:

| Action | Assigned by heuristic | Evaluated top N | Outcome precision | Outcome recall | Outcome dollars captured |
| --- | ---: | ---: | ---: | ---: | ---: |
| Protect | 229 | 50 | 16.0% | 19.5% | 86.5% of loss dollars |
| Grow | 15 | 15 | 66.7% | 16.7% | 30.3% of growth dollars |

Absolute revenue-change capture across operational review budgets:

| Top K | Full priority | Current revenue | Renewal date | Random mean |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 21.0% | 30.2% | 4.4% | 4.2% |
| 25 | 68.1% | 69.1% | 10.9% | 10.8% |
| 50 | 83.3% | 85.1% | 16.1% | 20.5% |
| 100 | 94.9% | 95.6% | 37.1% | 41.0% |
| 200 | 99.3% | 99.2% | 95.7% | 82.0% |

A progressive ablation shows what each layer adds to the ranking:

| Top K | Current revenue | Revenue x urgency | Protection only | Full priority |
| ---: | ---: | ---: | ---: | ---: |
| 10 | 30.2% | 37.1% | 29.2% | 21.0% |
| 25 | 69.1% | 63.8% | 68.0% | 68.1% |
| 50 | 85.1% | 85.1% | 83.3% | 83.3% |

Leave-one-protection-signal-out results show that component effects depend on the review budget:

| Top K | Full priority | No idle seats | No AI adoption | No support pressure | No contact gap |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | 21.0% | 21.0% | 21.0% | 21.0% | 37.5% |
| 25 | 68.1% | 65.0% | 61.8% | 65.0% | 68.1% |
| 50 | 83.3% | 79.6% | 83.3% | 83.3% | 83.3% |

Current revenue is a competitive baseline on this synthetic cohort, and revenue times urgency performs best at the top-10 budget. Revenue alone remains operationally naive: it cannot distinguish Protect from Grow or explain which account signal needs attention. The heuristic is retained for those actionable motions and explanations, not because this retrospective proves better generalization. Better performance on future data remains a hypothesis that requires historical snapshots and time-based validation.

The notebook also reports bootstrap 95% intervals and repeated-random ranges. These figures describe retrospective consistency on one synthetic cohort only. They are not evidence of predictive performance or production calibration.

## Limitations

- The dataset is one synthetic cross-section; it cannot support temporal or out-of-sample validation.
- The values are prioritization proxies, not calibrated churn probabilities, expected losses, or committed pipeline.
- Peer seat headroom is a scenario based on current portfolio peers, not a sales forecast.
- Call summaries are context for the AE and LLM, not a deterministic scoring input.
- Real outcome modeling requires historical snapshots and time-based validation.
- Local Ollama must be running with the configured model installed.