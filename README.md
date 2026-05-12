# ua-smart-alerts

Real-time UA campaign monitoring bot that checks campaign data every 30 minutes and sends Slack alerts when anomalies are detected.

## What it does

- Pulls the last 24 hours of campaign data (installs, spend, impressions, ROAS)
- Runs a set of pluggable **detectors** — each one looks for a specific type of anomaly
- Sends a Slack message for each alert, with AI-written context via Claude
- Suppresses duplicate alerts (same issue won't ping you every 30 minutes)

## How it works — plugin architecture

Every detector lives in `src/detectors/` as a standalone file. To add a new detector:

1. Create `src/detectors/my_new_check.py`
2. Subclass `Detector` from `src/detectors/base.py`
3. Implement the `check(df)` method — return a list of `Alert` objects
4. Add it to the detector list in `src/main.py`

That's it. No shared state, no registration system. Each detector is self-contained.

### Detectors shipped

| Detector | Severity | What it catches |
|---|---|---|
| `CpiSpikeDetector` | warning | CPI rose >25% in last 6h vs prior 6h |
| `BudgetOverrunDetector` | critical | Daily spend exceeded budget by >20% |
| `RoasDropDetector` | warning | ROAS D1 dropped >40% vs 7-day baseline |
| `ZeroImpressionsDetector` | critical | Campaign had spend but zero impressions for 2+ hours |

## Setup

```bash
# 1. Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — fill in your Slack bot token, channel ID, Anthropic API key

# 4. Run
python -m src.main

# 5. Run tests
pytest tests/ -v
```

## Project structure

```
src/
  detectors/
    base.py          # Alert dataclass + abstract Detector
    cpi_spike.py
    budget_overrun.py
    roas_drop.py
    zero_impressions.py
  data_loader.py     # CSV loading + timestamp handling
  deduplicator.py    # Suppress repeated alerts
  main.py            # Entry point
data/
  sample_hourly_data.csv   # Test data with planted anomalies
tests/
  test_detectors.py
  test_deduplicator.py
prompts/
  system_prompt.example.md
```
