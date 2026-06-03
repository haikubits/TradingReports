# TradingReports

Repository for the trading scanner skill and its published report artifacts.

## Contents

- `.github/skills/trading-scanner-report/` - skill definition and canonical Python generator
- `Artifacts/YYYY-MM-DD_HH-MM/` - timestamped published report runs

## Trading scanner workflow

The scanner builds a next-session report from market data, scores setups, and writes:

- `trading_scanner_report.py`
- `report-data.json`
- `trading-report.html`

The committed skill file documents how to generate a new run, validate the output, and publish the timestamped artifact folder.
