# TradingReports

Repository for reusable trading skills and published report artifacts.

## Contents

- `.github/skills/trading-scanner-report/` - scanner skill definition and canonical Python generator
- `.github/skills/stock-analysis-framework/` - reusable large-cap stock analysis skill
- `Artifacts/YYYY-MM-DD_HH-MM/` - timestamped published report runs

## Trading scanner workflow

The scanner builds a next-session report from market data, scores setups, and writes:

- `trading_scanner_report.py`
- `report-data.json`
- `trading-report.html`

The committed scanner skill documents how to generate a new run, validate the output, and publish the timestamped artifact folder.

## Stock analysis workflow

The stock analysis skill provides a structured seven-phase framework for evaluating mid- and large-cap equities before making a buy, wait, or avoid decision.
