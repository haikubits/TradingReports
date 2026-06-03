---
name: trading-scanner-report
description: |
  Generate a next-session trading scanner report from live market data using Python, score the best setups, write artifacts into the TradingReports repository, and publish them under Artifacts.
  Load this skill when the user asks to build, rerun, refine, or publish the stock scanner report workflow.
tools:
  - RunInTerminal
---

# Trading Scanner Report Skill

## Purpose

Use this skill to generate a reusable evening trading scanner report for the next market session. The workflow fetches market data, computes technical indicators, builds support and resistance levels, scores setup quality, writes a self-contained HTML report plus a structured JSON payload, and publishes the run artifacts into the `TradingReports` GitHub repository.

## Repository Targets

Use this repository for both the skill files and the generated report artifacts:
- repo: `https://github.com/haikubits/TradingReports`
- local path: `codeRefs/TradingReports`
- skill path: `codeRefs/TradingReports/.github/skills/trading-scanner-report/`
- artifact root: `codeRefs/TradingReports/Artifacts/`

Do not write the final published artifacts to thread-local folders when the goal is to preserve and publish them. The canonical published output belongs in the repository under `Artifacts`.

## When This Skill Applies

Load this skill when the user wants to:
- generate the trading opportunities scanner report
- rerun the report with fresh market data
- adjust the stock universe, ranking logic, or level-generation rules
- troubleshoot report generation failures or missing output fields
- verify that each selected stock includes 3 upside and 3 downside levels
- publish the generated report artifacts to the `TradingReports` repository

Do not use this skill for Azure diagnostics or infrastructure operations.

## Standard Output Location

Write the published artifacts under a timestamped report folder in the repository:
`codeRefs/TradingReports/Artifacts/YYYY-MM-DD_HH-MM/`

The timestamp folder must be created from the report generation time and reused for every artifact from that run.

Expected files inside the timestamped folder:
- `trading_scanner_report.py`
- `report-data.json`
- `trading-report.html`

## Default Market Universe

Unless the user specifies otherwise, use:
- `SPY`
- `QQQ`
- `NVDA`
- `TSLA`
- `AAPL`
- `AMZN`
- `META`
- `MSFT`
- `AMD`
- `GOOGL`

## Core Workflow

1. Capture the report generation timestamp once at the start of the run using `YYYY-MM-DD_HH-MM` format.
2. Create or update `trading_scanner_report.py` inside that run's timestamped artifact folder.
3. Use Python to fetch raw data with `yfinance`:
   - daily candles: `1y`, `1d`
   - hourly candles: `1mo`, `60m`, with `prepost=True`
   - intraday candles: `1d`, `5m`
   - options chain: first available expiry when present
4. Compute the required derived fields:
   - 200 SMA, 50 SMA, 20 EMA, 8 EMA
   - RSI(14)
   - ATR(14)
   - VWAP
   - daily trend direction and strength
   - volume ratio vs 20-day average
   - options put/call ratio and total options volume
   - NTZ using yesterday and premarket ranges
   - clustered support and resistance levels
5. Score each ticker and select the top setups by conviction.
6. Build a self-contained HTML report with inline CSS and inline JavaScript.
7. Write both HTML and JSON outputs into the same timestamped artifact folder.
8. Verify the result before handing it back.
9. Commit the timestamped folder under `Artifacts/` and push it to `main` in the `TradingReports` repository.

## Python Execution Guidance

Use Python through terminal execution. Prefer one of these patterns:

### For a full script

Capture the timestamp once and use it for the whole run:
```bash
REPORT_TS=$(date -u +%Y-%m-%d_%H-%M)
REPO_ROOT="codeRefs/TradingReports"
OUT_DIR="$REPO_ROOT/Artifacts/$REPORT_TS"
mkdir -p "$OUT_DIR"
python3 "$OUT_DIR/trading_scanner_report.py"
```

The script itself should write `report-data.json` and `trading-report.html` into the same `OUT_DIR`.

### For targeted validation

Use a short heredoc:
```bash
REPORT_TS="YYYY-MM-DD_HH-MM"
python3 - <<'PY'
import json
import os
from pathlib import Path
report_ts = os.environ['REPORT_TS']
base = Path(f'codeRefs/TradingReports/Artifacts/{report_ts}')
report = json.loads((base / 'report-data.json').read_text())
print(report['avg_conviction'])
PY
```

Replace `YYYY-MM-DD_HH-MM` with the run folder you want to inspect.

## Required Python Packages

Check for these packages before running:
- `pandas`
- `numpy`
- `yfinance`
- `pandas_market_calendars`
- `zoneinfo`

If `yfinance` or `pandas_market_calendars` is missing, install them with Python package tooling before rerunning the script.

## Report Requirements

The generated report should include:
- market context header with session date, VIX, SPY trend, and 200 SMA state
- scanner summary stats
- top 4 to 5 picks ranked by conviction
- ticker-level chips for 200 SMA, VWAP, ORB placeholder, volume, and trend
- NTZ box and reasoning cards
- 3 upside levels and 3 downside levels for every selected stock
- level confidence, source summary, and level reasoning text
- a clean light/dark theme toggle
- a self-contained HTML file with no external dependencies

## Level Engine Rules

The level engine must try structural levels first:
- clustered 60-minute pivots
- clustered daily pivots
- moving averages
- yesterday high and low
- premarket high and low

If there are fewer than 3 valid upside or downside levels, backfill with ATR-based projection levels so that every selected stock still ends with exactly:
- 3 upside levels
- 3 downside levels

ATR projection levels should be labeled with source `ATR Projection` and should have lower confidence than structurally confirmed levels.

## Verification Checklist

Before finalizing, validate all of the following inside the selected timestamped folder:
- `report-data.json` exists and is non-empty
- `trading-report.html` exists and is non-empty
- `failures` is empty when data fetches succeed
- each selected stock has `len(levels['up']) == 3`
- each selected stock has `len(levels['down']) == 3`
- the HTML includes the average conviction summary text
- the HTML is self-contained and does not depend on external scripts or stylesheets

Example validation snippet:
```bash
REPORT_TS="YYYY-MM-DD_HH-MM"
python3 - <<'PY'
import json
import os
from pathlib import Path
report_ts = os.environ['REPORT_TS']
base = Path(f'codeRefs/TradingReports/Artifacts/{report_ts}')
report = json.loads((base / 'report-data.json').read_text())
for stock in report['top_picks']:
    assert len(stock['levels']['up']) == 3, stock['ticker']
    assert len(stock['levels']['down']) == 3, stock['ticker']
print('validation passed')
PY
```

## Publish Artifacts To GitHub

After verification, publish the run artifacts from the repository working tree itself.

Use the repository's existing git credential configuration. Do not modify authentication state manually.

Example flow:
```bash
REPORT_TS="YYYY-MM-DD_HH-MM"
cd codeRefs/TradingReports
git add "Artifacts/$REPORT_TS"
if ! git diff --cached --quiet; then
  git commit -m "TradingReports: Add scanner artifacts for $REPORT_TS"
  git commit --amend --no-edit -m "TradingReports: Add scanner artifacts for $REPORT_TS

Co-authored-by: Azure SRE Agent <noreply@microsoft.com>"
  git push origin main
fi
```

When committing, make sure the final commit message starts with `TradingReports:` and includes the required co-author trailer.

## Response Guidance

When the workflow completes, return:
- the timestamped output folder used for the run
- the output artifact locations
- confirmation that the artifacts were committed and pushed under `Artifacts/`
- the top picks
- the average conviction
- whether any tickers failed to fetch
- any noteworthy caveats such as fallback ATR-projection levels or missing macro feeds

Keep the response concise and operational.

## Notes

- Treat the report as educational and research-oriented, not financial advice.
- Keep the HTML single-file and portable.
- Prefer incremental fixes over rewriting the whole script when only one report component is broken.
- Keep all skill-related files for this workflow under `.github/skills/trading-scanner-report/` in the `TradingReports` repository.
- If the user asks for a PR workflow instead of direct push to `main`, switch to a branch-based GitHub flow.