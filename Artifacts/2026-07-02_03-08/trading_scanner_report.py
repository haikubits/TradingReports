from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Any

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf
from zoneinfo import ZoneInfo


OUTPUT_DIR = Path(__file__).resolve().parent
DEFAULT_UNIVERSE = [
    "SPY",
    "QQQ",
    "NVDA",
    "TSLA",
    "AAPL",
    "AMZN",
    "META",
    "MSFT",
    "AMD",
    "GOOGL",
]
COMPANY_NAMES = {
    "SPY": "SPDR S&P 500 ETF Trust",
    "QQQ": "Invesco QQQ Trust",
    "NVDA": "NVIDIA Corporation",
    "TSLA": "Tesla, Inc.",
    "AAPL": "Apple Inc.",
    "AMZN": "Amazon.com, Inc.",
    "META": "Meta Platforms, Inc.",
    "MSFT": "Microsoft Corporation",
    "AMD": "Advanced Micro Devices, Inc.",
    "GOOGL": "Alphabet Inc. Class A",
}
CONFIGURED_EVENTS: list[str] = []
CONFIGURED_FED_SPEAKERS: list[str] = []
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def round_price(value: float) -> float:
    if value >= 100:
        return round(value * 2) / 2
    return round(value * 4) / 4


def safe_number(value: Any, default: float = float("nan")) -> float:
    try:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            return default
        return float(value)
    except Exception:
        return default


def ensure_timezone(index: pd.Index, tz: str = "America/New_York") -> pd.Index:
    if not hasattr(index, "tz"):
        return index
    if index.tz is None:
        return index.tz_localize(tz)
    return index.tz_convert(tz)


def next_trading_day(now_et: datetime) -> datetime:
    nyse = mcal.get_calendar("NYSE")
    start = now_et.date()
    end = (now_et + timedelta(days=10)).date()
    schedule = nyse.schedule(start_date=start, end_date=end)
    if schedule.empty:
        candidate = now_et + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate

    for market_open in schedule["market_open"]:
        market_open_et = market_open.tz_convert(ET)
        if market_open_et.date() > now_et.date():
            return market_open_et

    fallback = now_et + timedelta(days=1)
    while fallback.weekday() >= 5:
        fallback += timedelta(days=1)
    return fallback


def fetch_raw_data(ticker_str: str) -> dict[str, Any]:
    tk = yf.Ticker(ticker_str)
    daily = tk.history(period="1y", interval="1d", auto_adjust=False, actions=False)
    hourly = tk.history(period="1mo", interval="60m", prepost=True, auto_adjust=False, actions=False)
    intraday = tk.history(period="1d", interval="5m", auto_adjust=False, actions=False)

    if daily.empty:
        raise ValueError(f"No daily data returned for {ticker_str}")

    options = None
    try:
        expiries = list(tk.options)
        if expiries:
            options = tk.option_chain(expiries[0])
    except Exception:
        options = None

    last_price = safe_number(daily["Close"].iloc[-1])
    prev_close = safe_number(daily["Close"].iloc[-2]) if len(daily) > 1 else last_price

    return {
        "ticker": ticker_str,
        "company_name": COMPANY_NAMES.get(ticker_str, ticker_str),
        "daily": daily,
        "hourly": hourly,
        "intraday": intraday,
        "options": options,
        "last_price": last_price,
        "prev_close": prev_close,
    }


def fetch_vix() -> float:
    vix = yf.Ticker("^VIX")
    history = vix.history(period="5d", auto_adjust=False, actions=False)
    return safe_number(history["Close"].iloc[-1], 0.0)


def compute_moving_averages(daily: pd.DataFrame) -> dict[str, float]:
    close = daily["Close"]
    return {
        "sma200": safe_number(close.rolling(200).mean().iloc[-1]),
        "sma50": safe_number(close.rolling(50).mean().iloc[-1]),
        "ema20": safe_number(close.ewm(span=20, adjust=False).mean().iloc[-1]),
        "ema8": safe_number(close.ewm(span=8, adjust=False).mean().iloc[-1]),
    }


def compute_rsi(daily: pd.DataFrame, period: int = 14) -> float:
    close = daily["Close"]
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return safe_number(rsi.iloc[-1], 50.0)


def compute_atr(daily: pd.DataFrame, period: int = 14) -> float:
    high = daily["High"]
    low = daily["Low"]
    close = daily["Close"]
    tr = pd.concat([high - low, (high - close.shift(1)).abs(), (low - close.shift(1)).abs()], axis=1).max(axis=1)
    return safe_number(tr.rolling(period).mean().iloc[-1], 0.0)


def compute_vwap(intraday: pd.DataFrame) -> float:
    if intraday.empty:
        return float("nan")
    tp = (intraday["High"] + intraday["Low"] + intraday["Close"]) / 3
    volume = intraday["Volume"].replace(0, np.nan)
    vwap = (tp * volume).cumsum() / volume.cumsum()
    return safe_number(vwap.iloc[-1])


def detect_trend(daily: pd.DataFrame, lookback: int = 10) -> dict[str, Any]:
    recent = daily.tail(lookback)
    highs = recent["High"].values
    lows = recent["Low"].values
    n = max(len(highs) - 1, 1)
    hh = sum(1 for i in range(1, len(highs)) if highs[i] > highs[i - 1]) / n
    hl = sum(1 for i in range(1, len(lows)) if lows[i] > lows[i - 1]) / n
    lh = sum(1 for i in range(1, len(highs)) if highs[i] < highs[i - 1]) / n
    ll = sum(1 for i in range(1, len(lows)) if lows[i] < lows[i - 1]) / n

    if hh >= 0.55 and hl >= 0.55:
        return {"direction": "Uptrend", "strength": round((hh + hl) / 2, 2)}
    if lh >= 0.55 and ll >= 0.55:
        return {"direction": "Downtrend", "strength": round((lh + ll) / 2, 2)}
    return {"direction": "Range", "strength": round(max(hh + hl, lh + ll) / 2, 2)}


def compute_volume_status(daily: pd.DataFrame) -> dict[str, Any]:
    avg_vol = safe_number(daily["Volume"].tail(20).mean(), 0.0)
    today_vol = safe_number(daily["Volume"].iloc[-1], 0.0)
    ratio = today_vol / avg_vol if avg_vol > 0 else 0.0
    if ratio >= 2.0:
        label = "2x Avg"
    elif ratio >= 1.0:
        label = "Above Avg"
    else:
        label = "Below Avg"
    return {"ratio": round(ratio, 2), "label": label, "today": int(today_vol), "avg20": int(avg_vol)}


def compute_ntz(daily: pd.DataFrame, hourly: pd.DataFrame) -> dict[str, float]:
    yd = daily.iloc[-2] if len(daily) > 1 else daily.iloc[-1]
    yd_high = safe_number(yd["High"], 0.0)
    yd_low = safe_number(yd["Low"], 0.0)

    if hourly.empty:
        pm_high = yd_high
        pm_low = yd_low
    else:
        hourly_local = hourly.copy()
        hourly_local.index = ensure_timezone(hourly_local.index)
        session_date = hourly_local.index[-1].date()
        today_ext = hourly_local[hourly_local.index.date == session_date]
        pre_mkt = today_ext[(today_ext.index.hour < 9) | ((today_ext.index.hour == 9) & (today_ext.index.minute < 30))]
        if pre_mkt.empty:
            pre_mkt = today_ext.iloc[:3]
        pm_high = safe_number(pre_mkt["High"].max(), yd_high)
        pm_low = safe_number(pre_mkt["Low"].min(), yd_low)

    return {
        "pm_high": round(pm_high, 2),
        "pm_low": round(pm_low, 2),
        "yd_high": round(yd_high, 2),
        "yd_low": round(yd_low, 2),
        "ntz_upper": round(max(pm_high, yd_high), 2),
        "ntz_lower": round(min(pm_low, yd_low), 2),
    }


def compute_options_data(options: Any) -> dict[str, Any]:
    if options is None:
        return {"pc_ratio_vol": 0.0, "pc_ratio_oi": 0.0, "total_volume": 0, "call_vol": 0, "put_vol": 0}

    call_vol = int(pd.to_numeric(options.calls.get("volume", 0), errors="coerce").fillna(0).sum())
    put_vol = int(pd.to_numeric(options.puts.get("volume", 0), errors="coerce").fillna(0).sum())
    call_oi = int(pd.to_numeric(options.calls.get("openInterest", 0), errors="coerce").fillna(0).sum())
    put_oi = int(pd.to_numeric(options.puts.get("openInterest", 0), errors="coerce").fillna(0).sum())

    return {
        "pc_ratio_vol": round(put_vol / call_vol, 2) if call_vol > 0 else 0.0,
        "pc_ratio_oi": round(put_oi / call_oi, 2) if call_oi > 0 else 0.0,
        "total_volume": call_vol + put_vol,
        "call_vol": call_vol,
        "put_vol": put_vol,
    }


def find_pivots(data: np.ndarray, window: int = 5) -> tuple[list[float], list[float]]:
    highs: list[float] = []
    lows: list[float] = []
    for i in range(window, len(data) - window):
        segment = data[i - window : i + window + 1]
        if data[i] == max(segment):
            highs.append(float(data[i]))
        if data[i] == min(segment):
            lows.append(float(data[i]))
    return highs, lows


def cluster_levels(levels: list[float], threshold_pct: float = 0.003) -> list[dict[str, Any]]:
    if not levels:
        return []
    levels = sorted(levels)
    avg_price = float(np.mean(levels))
    threshold = avg_price * threshold_pct
    clusters = [[levels[0]]]
    for level in levels[1:]:
        if level - float(np.mean(clusters[-1])) <= threshold:
            clusters[-1].append(level)
        else:
            clusters.append([level])

    result = []
    for cluster in clusters:
        mean_val = float(np.mean(cluster))
        result.append({"price": round_price(mean_val), "touches": len(cluster)})
    return result


def compute_levels(hourly: pd.DataFrame, daily: pd.DataFrame, current_price: float, ntz: dict[str, float]) -> dict[str, Any]:
    closes_60 = hourly["Close"].dropna().values if not hourly.empty else np.array([])
    closes_d = daily["Close"].dropna().values

    pivot_h_60, pivot_l_60 = find_pivots(closes_60, window=5) if len(closes_60) >= 11 else ([], [])
    pivot_h_d, pivot_l_d = find_pivots(closes_d, window=3) if len(closes_d) >= 7 else ([], [])
    clustered_60 = cluster_levels(pivot_h_60 + pivot_l_60)
    clustered_d = cluster_levels(pivot_h_d + pivot_l_d)

    mas = compute_moving_averages(daily)
    ma_entries = []
    for val, label in [
        (mas["sma200"], "200 SMA (Daily)"),
        (mas["sma50"], "50 SMA (Daily)"),
        (mas["ema20"], "20 EMA (Daily)"),
        (mas["ema8"], "8 EMA (Daily)"),
    ]:
        if not math.isnan(val):
            ma_entries.append({"price": round_price(val), "source": label})

    yd = daily.iloc[-2] if len(daily) > 1 else daily.iloc[-1]
    fixed_entries = [
        {"price": round_price(safe_number(yd["High"], current_price)), "source": "Yesterday High"},
        {"price": round_price(safe_number(yd["Low"], current_price)), "source": "Yesterday Low"},
        {"price": round_price(ntz["pm_high"]), "source": "Pre-market High"},
        {"price": round_price(ntz["pm_low"]), "source": "Pre-market Low"},
    ]

    level_map: dict[float, dict[str, Any]] = {}
    merge_threshold = current_price * 0.002

    def add_to_map(price: float, source_label: str, touches: int = 1) -> None:
        closest = None
        if level_map:
            candidate = min(level_map.keys(), key=lambda key: abs(key - price))
            if abs(candidate - price) <= merge_threshold:
                closest = candidate
        key = closest if closest is not None else price
        if key not in level_map:
            level_map[key] = {"price": key, "sources": [], "touches": 0}
        level_map[key]["sources"].append(source_label)
        level_map[key]["touches"] += touches

    for item in clustered_60:
        add_to_map(item["price"], f"60-min S/R ({item['touches']} touches)", item["touches"])
    for item in clustered_d:
        add_to_map(item["price"], f"Daily S/R ({item['touches']} touches)", item["touches"])
    for item in ma_entries:
        add_to_map(item["price"], item["source"], 1)
    for item in fixed_entries:
        add_to_map(item["price"], item["source"], 1)

    for level in level_map.values():
        source_score = min(len(set(level["sources"])) * 20, 60)
        touch_score = min(level["touches"] * 5, 30)
        dist = abs(level["price"] - current_price) / current_price if current_price else 0.0
        proximity_penalty = min(dist * 200, 10)
        confidence = max(min(int(source_score + touch_score - proximity_penalty), 95), 35)
        level["confidence"] = confidence
        level["price"] = round(level["price"], 2)
        level["sources"] = list(dict.fromkeys(level["sources"]))
        level["source_summary"] = " + ".join(level["sources"][:2])

    above = sorted([v for v in level_map.values() if v["price"] > current_price], key=lambda item: item["price"])[:3]
    below = sorted([v for v in level_map.values() if v["price"] < current_price], key=lambda item: item["price"], reverse=True)[:3]

    atr = compute_atr(daily)
    base_step = max(atr, current_price * 0.004, 0.5 if current_price >= 100 else 0.25)

    def fill_missing(levels: list[dict[str, Any]], direction: int) -> list[dict[str, Any]]:
        attempts = 1
        while len(levels) < 3 and attempts <= 12:
            candidate = round(round_price(current_price + (direction * base_step * attempts)), 2)
            if direction > 0:
                valid_side = candidate > current_price
                too_close = any(abs(candidate - item["price"]) <= merge_threshold for item in levels)
            else:
                valid_side = candidate < current_price
                too_close = any(abs(candidate - item["price"]) <= merge_threshold for item in levels)
            if valid_side and not too_close:
                levels.append(
                    {
                        "price": candidate,
                        "sources": ["ATR Projection"],
                        "touches": 1,
                        "confidence": max(36, 46 - (len(levels) * 4)),
                        "source_summary": "ATR Projection",
                    }
                )
            attempts += 1
        return levels

    above = fill_missing(above, 1)
    below = fill_missing(below, -1)
    above = sorted(above, key=lambda item: item["price"])[:3]
    below = sorted(below, key=lambda item: item["price"], reverse=True)[:3]

    return {"up": above, "down": below}


def score_stock(raw: dict[str, Any]) -> dict[str, Any]:
    daily = raw["daily"]
    current = raw["last_price"]
    score = 0
    reasons: list[str] = []

    trend = detect_trend(daily)
    trend_pts = int(trend["strength"] * 25)
    score += trend_pts
    reasons.append(f"Trend: {trend['direction']} ({trend_pts}/25)")

    mas = compute_moving_averages(daily)
    sma200 = mas["sma200"]
    aligned = False
    if not math.isnan(sma200):
        if trend["direction"] == "Uptrend" and current > sma200:
            aligned = True
        elif trend["direction"] == "Downtrend" and current < sma200:
            aligned = True
    sma_pts = 15 if aligned else 5
    score += sma_pts
    pos = "Above" if current > sma200 else "Below"
    reasons.append(f"200 SMA: {pos} ({'aligned' if aligned else 'counter-trend'}) ({sma_pts}/15)")

    vol = compute_volume_status(daily)
    if vol["ratio"] >= 1.5:
        vol_pts = 15
    elif vol["ratio"] >= 1.0:
        vol_pts = 10
    else:
        vol_pts = 5
    score += vol_pts
    reasons.append(f"Volume: {vol['ratio']}x avg ({vol_pts}/15)")

    rsi = compute_rsi(daily)
    if 30 <= rsi <= 70:
        rsi_pts = 15
    elif 20 <= rsi <= 80:
        rsi_pts = 10
    else:
        rsi_pts = 0
    score += rsi_pts
    reasons.append(f"RSI: {rsi:.0f} ({rsi_pts}/15)")

    atr = compute_atr(daily)
    atr_pct = atr / current * 100 if current else 0.0
    if 0.5 <= atr_pct <= 3.0:
        atr_pts = 15
    elif atr_pct < 0.5:
        atr_pts = 5
    else:
        atr_pts = 8
    score += atr_pts
    reasons.append(f"ATR: {atr_pct:.1f}% ({atr_pts}/15)")

    opts = compute_options_data(raw["options"])
    if opts["total_volume"] > 100000:
        opt_pts = 15
    elif opts["total_volume"] > 10000:
        opt_pts = 10
    else:
        opt_pts = 5
    score += opt_pts
    reasons.append(f"Options vol: {opts['total_volume']:,} ({opt_pts}/15)")

    if trend["direction"] == "Uptrend" and current > sma200:
        bias = "Bullish"
    elif trend["direction"] == "Downtrend" and current < sma200:
        bias = "Bearish"
    elif trend["direction"] == "Uptrend":
        bias = "Neutral-Bullish"
    elif trend["direction"] == "Downtrend":
        bias = "Neutral-Bearish"
    else:
        bias = "Neutral"

    return {
        "ticker": raw["ticker"],
        "company_name": raw["company_name"],
        "conviction": min(score, 100),
        "trend": trend["direction"],
        "trend_strength": trend["strength"],
        "bias": bias,
        "reasons": reasons,
        "price": round(current, 2),
        "change": round(current - raw["prev_close"], 2),
        "change_pct": round(((current - raw["prev_close"]) / raw["prev_close"] * 100) if raw["prev_close"] else 0.0, 2),
        "rsi": round(rsi, 1),
        "atr_pct": round(atr_pct, 1),
        "vol_ratio": vol["ratio"],
        "vol_label": vol["label"],
        "sma200_pos": pos,
        "vwap_pos": "Unknown",
        "pc_ratio": opts["pc_ratio_vol"],
        "options_total_volume": opts["total_volume"],
        "trend_breakdown": trend,
        "mas": {k: round(v, 2) if not math.isnan(v) else None for k, v in mas.items()},
        "volume": vol,
    }


def conviction_color(score: int) -> str:
    if score >= 80:
        return "success"
    if score >= 65:
        return "warning"
    return "danger"


def bias_color(bias: str) -> str:
    if "Bullish" in bias:
        return "success"
    if "Bearish" in bias:
        return "danger"
    return "warning"


def chip_tone(label: str, value: str) -> str:
    if label == "ORB":
        return "warning"
    if value in {"Above", "Uptrend", "2x Avg", "Above Avg", "Bullish"}:
        return "success"
    if value in {"Below", "Downtrend", "Range", "Bearish", "Below Avg"}:
        return "danger"
    return "warning"


def format_currency(value: float) -> str:
    return f"${value:,.2f}"


def trend_reasoning(stock: dict[str, Any]) -> str:
    mas = stock["mas"]
    ema8 = mas.get("ema8")
    ema20 = mas.get("ema20")
    sma200 = mas.get("sma200")
    momentum = "confirming momentum" if (ema8 is not None and ema20 is not None and ema8 > ema20) else "showing softer momentum"
    rsi = stock["rsi"]
    if rsi > 70:
        rsi_phrase = "approaching overbought conditions"
    elif rsi < 30:
        rsi_phrase = "oversold and vulnerable to rebounds"
    else:
        rsi_phrase = "still in a healthy operating range"
    return (
        f"The daily chart is in {stock['trend'].lower()} mode with {stock['trend_strength']:.2f} strength. "
        f"Price is {stock['sma200_pos'].lower()} the 200 SMA at {format_currency(sma200 or stock['price'])}, and the 8 EMA at {format_currency(ema8 or stock['price'])} is "
        f"{'above' if (ema8 or 0) >= (ema20 or 0) else 'below'} the 20 EMA at {format_currency(ema20 or stock['price'])}, {momentum}. "
        f"RSI is {rsi:.1f}, which is {rsi_phrase}."
    )


def level_confluence_reasoning(stock: dict[str, Any]) -> str:
    up = stock["levels"]["up"]
    down = stock["levels"]["down"]
    all_levels = up + down
    best = max(all_levels, key=lambda item: item["confidence"]) if all_levels else None
    ordered_prices = sorted([level["price"] for level in all_levels])
    gaps = [ordered_prices[i + 1] - ordered_prices[i] for i in range(len(ordered_prices) - 1)]
    avg_gap = mean(gaps) if gaps else 0.0
    if avg_gap < stock["price"] * 0.004:
        spacing = "tight"
        rr = "quicker scalp-style"
    elif avg_gap < stock["price"] * 0.012:
        spacing = "balanced"
        rr = "workable intraday"
    else:
        spacing = "wide"
        rr = "swing-style"
    if best:
        source_list = ", ".join(best["sources"])
        highlight = f"The best-defined level is {format_currency(best['price'])} at {best['confidence']}% confidence from {source_list}."
    else:
        highlight = "Level density is lighter than usual, so treat the map as approximate rather than precise."
    return (
        f"Found {len(up)} clustered levels above and {len(down)} below the current price. {highlight} "
        f"Average spacing is {format_currency(avg_gap)} which gives {spacing} room for {rr} risk-to-reward planning."
    )


def catalyst_reasoning(stock: dict[str, Any], macro_events: list[str], fed_speakers: list[str]) -> str:
    notes: list[str] = []
    if stock["atr_pct"] > 3.0:
        notes.append(f"⚠ ATR is {stock['atr_pct']:.1f}% which signals a wider-than-normal range; trim size if you trade it.")
    else:
        notes.append(f"ATR is {stock['atr_pct']:.1f}%, supportive of normal next-session expansion without being disorderly.")

    if stock["rsi"] > 70 or stock["rsi"] < 30:
        notes.append(f"⚠ RSI at {stock['rsi']:.1f} is in an extreme zone, so continuation trades need tighter invalidation.")

    if stock["pc_ratio"] > 1.5:
        notes.append(f"Put/call volume ratio is {stock['pc_ratio']:.2f}, showing bearish options positioning.")
    elif 0 < stock["pc_ratio"] < 0.5:
        notes.append(f"Put/call volume ratio is {stock['pc_ratio']:.2f}, showing bullish options positioning.")
    else:
        notes.append(f"Put/call volume ratio is {stock['pc_ratio']:.2f}, which is fairly balanced for sentiment context.")

    if stock["vol_ratio"] < 1.0:
        notes.append(f"⚠ Relative volume is only {stock['vol_ratio']:.2f}x the 20-day average, so follow-through may need confirmation after the open.")
    else:
        notes.append(f"Relative volume is {stock['vol_ratio']:.2f}x the 20-day average, showing tradable participation.")

    if macro_events:
        notes.append(f"Macro calendar risk tomorrow includes {'; '.join(macro_events)}.")
    elif fed_speakers:
        notes.append(f"Fed speakers on deck: {'; '.join(fed_speakers)}.")
    else:
        notes.append("No external macro calendar feed is configured in this run, so event risk should be checked separately before the bell.")
    return " ".join(notes)


def ntz_comment(stock: dict[str, Any]) -> str:
    ntz = stock["ntz"]
    width_pct = ((ntz["ntz_upper"] - ntz["ntz_lower"]) / stock["price"] * 100) if stock["price"] else 0.0
    if width_pct > 1.5:
        return f"Wide NTZ at {width_pct:.2f}% of price. Wait for a clean breakout beyond the box before forcing entries."
    if width_pct < 0.5:
        return f"Tight NTZ at {width_pct:.2f}% of price. A fast early break can matter if volume confirms."
    return f"Balanced NTZ at {width_pct:.2f}% of price. Respect the box until one side clearly gives way."


def confidence_text(confidence: int) -> str:
    if confidence >= 80:
        return "High confluence - multiple independent sources confirm this level"
    if confidence >= 65:
        return "Moderate confluence - valid but may not hold on heavy volume"
    return "Lower confluence - treat it as an approximate zone rather than an exact line"


def level_market_mechanic(sources: list[str]) -> str:
    if any("Yesterday" in source for source in sources):
        return "Previous session extremes often mark the boundary of yesterday's buyer and seller battle."
    if any("SMA" in source or "EMA" in source for source in sources):
        return "Moving averages act as dynamic support and resistance watched by systematic participants."
    if any("Pre-market" in source for source in sources):
        return "Pre-market extremes can attract opening auction liquidity and gap-fill reactions."
    if any("ATR Projection" in source for source in sources):
        return "ATR-based projections estimate measured-move continuation when nearby structure is thin beyond the immediate range."
    return "Repeated support and resistance touches make this a proven supply-demand zone."


def level_reasoning(level: dict[str, Any], side: str, next_target: float | None) -> str:
    sources = ", ".join(level["sources"])
    flip = "support" if side == "up" else "resistance"
    target_text = f" If it breaks cleanly, the next target is {format_currency(next_target)} and the broken level can flip into {flip}." if next_target else " If it breaks cleanly, expect a move toward the next visible pocket of liquidity."
    return (
        f"Created by {sources}. {level_market_mechanic(level['sources'])} "
        f"{confidence_text(level['confidence'])}.{target_text}"
    )


def build_report_data(universe: list[str] | None = None, top_n: int = 5) -> dict[str, Any]:
    if universe is None:
        universe = DEFAULT_UNIVERSE

    now_utc = datetime.now(tz=UTC)
    now_et = now_utc.astimezone(ET)
    next_session = next_trading_day(now_et)
    vix = fetch_vix()
    vix_regime = "low" if vix < 15 else "moderate" if vix < 20 else "elevated" if vix < 30 else "high"

    all_scores: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for ticker in universe:
        try:
            raw = fetch_raw_data(ticker)
            scored = score_stock(raw)
            scored["_raw"] = raw
            all_scores.append(scored)
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})

    all_scores.sort(key=lambda item: item["conviction"], reverse=True)
    top_picks = all_scores[:top_n]

    picks: list[dict[str, Any]] = []
    for stock in top_picks:
        raw = stock.pop("_raw")
        vwap = compute_vwap(raw["intraday"])
        if math.isnan(vwap):
            vwap_pos = "At VWAP"
        else:
            if abs(stock["price"] - vwap) / stock["price"] <= 0.001:
                vwap_pos = "At VWAP"
            else:
                vwap_pos = "Above" if stock["price"] > vwap else "Below"
        stock["vwap"] = round(vwap, 2) if not math.isnan(vwap) else None
        stock["vwap_pos"] = vwap_pos
        stock["ntz"] = compute_ntz(raw["daily"], raw["hourly"])
        stock["levels"] = compute_levels(raw["hourly"], raw["daily"], stock["price"], stock["ntz"])
        stock["indicator_chips"] = [
            {"label": "200 SMA", "value": stock["sma200_pos"]},
            {"label": "VWAP", "value": stock["vwap_pos"]},
            {"label": "ORB", "value": "Pending"},
            {"label": "Volume", "value": stock["vol_label"]},
            {"label": "Trend", "value": stock["trend"]},
        ]
        stock["reasoning_cards"] = [
            {"title": "Trend Structure", "body": trend_reasoning(stock)},
            {"title": "Level Confluence", "body": level_confluence_reasoning(stock)},
            {"title": "Catalyst / Risk", "body": catalyst_reasoning(stock, CONFIGURED_EVENTS, CONFIGURED_FED_SPEAKERS)},
        ]
        stock["ntz_comment"] = ntz_comment(stock)

        up_levels = stock["levels"]["up"]
        down_levels = stock["levels"]["down"]
        for index, level in enumerate(up_levels):
            next_target = up_levels[index + 1]["price"] if index + 1 < len(up_levels) else None
            level["reasoning"] = level_reasoning(level, "up", next_target)
        for index, level in enumerate(down_levels):
            next_target = down_levels[index + 1]["price"] if index + 1 < len(down_levels) else None
            level["reasoning"] = level_reasoning(level, "down", next_target)
        picks.append(stock)

    spy_entry = next((item for item in all_scores if item["ticker"] == "SPY"), None)

    return {
        "generated_at": now_et.strftime("%A %I:%M %p ET"),
        "generated_at_iso": now_utc.isoformat(),
        "session_date": next_session.strftime("%A, %B %d, %Y"),
        "vix": round(vix, 1),
        "vix_regime": vix_regime,
        "spy_trend": spy_entry["trend"] if spy_entry else "Unknown",
        "spy_sma_pos": spy_entry["sma200_pos"] if spy_entry else "Unknown",
        "fed_speakers": CONFIGURED_FED_SPEAKERS,
        "economic_events": CONFIGURED_EVENTS,
        "scanned_count": len(universe),
        "passed_count": sum(1 for item in all_scores if item["conviction"] >= 60),
        "avg_conviction": round(sum(item["conviction"] for item in picks) / len(picks)) if picks else 0,
        "top_picks": picks,
        "failures": failures,
    }


def esc(text: Any) -> str:
    value = str(text)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_context_chip(label: str, value: str, tone: str) -> str:
    return (
        f'<div class="context-chip">'
        f'<span class="dot dot-{tone}"></span>'
        f'<span><strong>{esc(label)}:</strong> {esc(value)}</span>'
        f'</div>'
    )


def render_stat_card(label: str, value: str, sublabel: str, accent: bool = False) -> str:
    value_class = "stat-value accent" if accent else "stat-value"
    return (
        '<div class="stat-card">'
        f'<div class="stat-label">{esc(label)}</div>'
        f'<div class="{value_class}">{esc(value)}</div>'
        f'<div class="stat-sublabel">{esc(sublabel)}</div>'
        '</div>'
    )


def render_chip(chip: dict[str, str]) -> str:
    tone = chip_tone(chip["label"], chip["value"])
    return (
        '<div class="indicator-chip">'
        f'<span class="dot dot-{tone}"></span>'
        f'<span>{esc(chip["label"])}: {esc(chip["value"])}</span>'
        '</div>'
    )


def render_reason_card(card: dict[str, str]) -> str:
    return (
        '<div class="reason-card">'
        f'<div class="reason-tag">{esc(card["title"])}</div>'
        f'<div class="reason-body">{esc(card["body"])}</div>'
        '</div>'
    )


def render_ntz(stock: dict[str, Any]) -> str:
    ntz = stock["ntz"]
    items = [
        ("PM High", format_currency(ntz["pm_high"])),
        ("PM Low", format_currency(ntz["pm_low"])),
        ("YD High", format_currency(ntz["yd_high"])),
        ("YD Low", format_currency(ntz["yd_low"])),
    ]
    rows = "".join(
        f'<div class="ntz-item"><div class="ntz-label">{label}</div><div class="price">{value}</div></div>'
        for label, value in items
    )
    return (
        '<div class="ntz-box">'
        '<div class="ntz-title">No Trading Zone</div>'
        f'<div class="ntz-note">{esc(stock["ntz_comment"])}</div>'
        f'<div class="ntz-grid">{rows}</div>'
        '</div>'
    )


def render_level_row(level: dict[str, Any], label: str, side: str, index: int) -> str:
    arrow = "▲" if side == "up" else "▼"
    tone = "success" if side == "up" else "danger"
    tooltip_id = f"tooltip-{side}-{index}-{int(level['price'] * 100)}"
    source_tags = "".join(f'<span class="source-tag">{esc(source)}</span>' for source in level["sources"])
    return (
        f'<div class="level-block" style="--delay:{0.1 * index:.2f}s">'
        f'<button class="level-row" type="button" data-tooltip-target="{tooltip_id}">'
        f'<span class="level-tag text-{tone}">{esc(label)}</span>'
        f'<span class="level-price price text-{tone}">{esc(format_currency(level["price"]))}</span>'
        '<span class="confidence-track">'
        f'<span class="confidence-fill fill-{tone}" style="width:{level["confidence"]}%"></span>'
        '</span>'
        f'<span class="confidence-label text-{tone}">{level["confidence"]}%</span>'
        f'<span class="source-summary">{esc(level["source_summary"])}</span>'
        '</button>'
        f'<div class="level-tooltip" id="{tooltip_id}">'
        f'<div class="tooltip-title text-{tone}">{arrow} {esc(label)} {"Upside" if side == "up" else "Downside"} - {esc(format_currency(level["price"]))} ({level["confidence"]}% confidence)</div>'
        f'<div class="tooltip-body">{esc(level["reasoning"])}</div>'
        f'<div class="source-tags">{source_tags}</div>'
        '</div>'
        '</div>'
    )


def render_stock_card(stock: dict[str, Any], index: int) -> str:
    conviction_tone = conviction_color(stock["conviction"])
    bias_tone = bias_color(stock["bias"])
    change_tone = "success" if stock["change"] >= 0 else "danger"
    indicator_html = "".join(render_chip(chip) for chip in stock["indicator_chips"])
    reason_html = "".join(render_reason_card(card) for card in stock["reasoning_cards"])

    up_levels = list(reversed(stock["levels"]["up"]))
    down_levels = stock["levels"]["down"]
    up_html = "".join(render_level_row(level, f"L{len(up_levels) - i}", "up", i) for i, level in enumerate(up_levels))
    down_html = "".join(render_level_row(level, f"L{i + 1}", "down", i + len(up_levels)) for i, level in enumerate(down_levels))

    expanded_class = " expanded" if index == 0 else ""
    detail_style = "" if index == 0 else " hidden"
    return (
        f'<section class="stock-card{expanded_class}" style="--delay:{0.06 * index:.2f}s">'
        '<button class="stock-header" type="button">'
        f'<div class="ticker-box">{esc(stock["ticker"])}</div>'
        '<div class="stock-identity">'
        f'<div class="stock-ticker">{esc(stock["ticker"])}</div>'
        f'<div class="stock-name">{esc(stock["company_name"])}</div>'
        '</div>'
        '<div class="stock-meta-grid">'
        '<div class="meta-block"><div class="meta-label">Last Close</div>'
        f'<div class="meta-value price">{esc(format_currency(stock["price"]))}</div></div>'
        '<div class="meta-block"><div class="meta-label">Change</div>'
        f'<div class="meta-value text-{change_tone}">{stock["change"]:+.2f} ({stock["change_pct"]:+.2f}%)</div></div>'
        '<div class="meta-block"><div class="meta-label">Bias</div>'
        f'<div class="meta-value text-{bias_tone}">{esc(stock["bias"])}</div></div>'
        '</div>'
        '<div class="conviction-wrap">'
        f'<div class="conviction-label">{stock["conviction"]}% conviction</div>'
        '<div class="conviction-track">'
        f'<div class="conviction-fill fill-{conviction_tone}" style="width:{stock["conviction"]}%"></div>'
        '</div>'
        '</div>'
        '<div class="expand-arrow">▼</div>'
        '</button>'
        f'<div class="stock-detail{detail_style}">'
        '<div class="detail-grid">'
        '<div class="detail-panel">'
        '<div class="section-kicker">Why this stock was selected</div>'
        f'<div class="indicator-chip-row">{indicator_html}</div>'
        f'{reason_html}'
        f'{render_ntz(stock)}'
        '</div>'
        '<div class="detail-panel detail-panel-levels">'
        '<div class="section-kicker">Trading Levels</div>'
        f'{up_html}'
        '<div class="now-marker"><span>NOW</span>'
        f'<span class="price">{esc(format_currency(stock["price"]))}</span></div>'
        f'{down_html}'
        '</div>'
        '</div>'
        '</div>'
        '</section>'
    )


def generate_html(report_data: dict[str, Any]) -> str:
    macro_events = report_data["economic_events"] if report_data["economic_events"] else ["No external calendar configured"]
    fed_speakers = report_data["fed_speakers"] if report_data["fed_speakers"] else ["No Fed speaker feed configured"]
    vix_tone = "success" if report_data["vix_regime"] == "low" else "warning" if report_data["vix_regime"] == "moderate" else "danger"
    spy_tone = "success" if report_data["spy_trend"] == "Uptrend" else "danger" if report_data["spy_trend"] == "Downtrend" else "warning"
    sma_tone = "success" if report_data["spy_sma_pos"] == "Above" else "danger"
    avg_tone = "success" if report_data["avg_conviction"] >= 85 else "warning" if report_data["avg_conviction"] >= 70 else "danger"
    avg_summary = (
        "very strong setups today"
        if report_data["avg_conviction"] >= 85
        else "good setups, standard day"
        if report_data["avg_conviction"] >= 70
        else "below average, be selective"
    )

    context_chips = "".join([
        render_context_chip("SPY", report_data["spy_trend"], spy_tone),
        render_context_chip("200 SMA", f"SPY {report_data['spy_sma_pos']} 200 SMA", sma_tone),
        render_context_chip("VIX", f"{report_data['vix']:.1f}", vix_tone),
        render_context_chip("Regime", report_data["vix_regime"].title(), vix_tone),
        render_context_chip("Fed", "; ".join(fed_speakers), "warning"),
        render_context_chip("Events", "; ".join(macro_events), "warning"),
    ])

    stats_html = "".join([
        render_stat_card("Scanned", f"{report_data['scanned_count']:,}", "default liquid universe"),
        render_stat_card("Passed", f"{report_data['passed_count']:,}", "conviction >= 60"),
        render_stat_card("Top Picks", f"{len(report_data['top_picks'])}", "highest ranked setups", accent=True),
        render_stat_card("Avg Conv.", f"{report_data['avg_conviction']}%", avg_summary),
    ])

    cards_html = "".join(render_stock_card(stock, index) for index, stock in enumerate(report_data["top_picks"]))
    failures_html = ""
    if report_data["failures"]:
        rows = "".join(
            f'<li><strong>{esc(item["ticker"])}:</strong> {esc(item["error"])}</li>' for item in report_data["failures"]
        )
        failures_html = f'<div class="failures"><div class="section-kicker">Skipped tickers</div><ul>{rows}</ul></div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<script>
(() => {{
  const param = new URLSearchParams(window.location.search).get("clawpilotTheme");
  const theme = param || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.setAttribute("data-theme", theme);
}})();
</script>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Trading Opportunities Report</title>
<style>
:root {{
  --cp-bg: #f7f4ef;
  --cp-surface: #ffffff;
  --cp-surface-soft: #f2ece4;
  --cp-text: #242424;
  --cp-text-muted: #5c5c5c;
  --cp-text-soft: #444444;
  --cp-accent: #b11f4b;
  --cp-accent-soft: #f8dce4;
  --cp-success: #16a34a;
  --cp-danger: #dc2626;
  --cp-warning: #f59e0b;
  --cp-border: #dedede;
  --cp-border-strong: #b4aba0;
  --cp-highlight: #fff5ec;
  --cp-shadow: 0 0 2px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.14);
}}
html[data-theme="dark"] {{
  --cp-bg: #3d3b3a;
  --cp-surface: #292929;
  --cp-surface-soft: #333333;
  --cp-text: #dedede;
  --cp-text-muted: #b8b8b8;
  --cp-text-soft: #cfcfcf;
  --cp-accent: #fd8ea1;
  --cp-accent-soft: #55323a;
  --cp-success: #4ade80;
  --cp-danger: #f87171;
  --cp-warning: #fbbf24;
  --cp-border: #505050;
  --cp-border-strong: #767676;
  --cp-highlight: #403731;
  --cp-shadow: 0 0 2px rgba(0,0,0,0.32), 0 1px 2px rgba(0,0,0,0.36);
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0;
  background: var(--cp-bg);
  color: var(--cp-text);
  font-family: "Segoe UI", Aptos, Calibri, -apple-system, BlinkMacSystemFont, sans-serif;
}}
button {{ font: inherit; }}
.price {{ font-family: Consolas, "Courier New", Courier, monospace; }}
.page {{ max-width: 1200px; margin: 0 auto; padding: 28px 20px 48px; }}
.theme-toggle {{
  position: fixed;
  top: 16px;
  right: 16px;
  width: 36px;
  height: 36px;
  border-radius: 999px;
  border: 1px solid var(--cp-border);
  background: var(--cp-surface);
  color: var(--cp-text);
  box-shadow: var(--cp-shadow);
  cursor: pointer;
  z-index: 20;
}}
.card, .stock-card, .stat-card, .header-card {{
  background: var(--cp-surface);
  border: 1px solid var(--cp-border);
  border-radius: 16px;
  box-shadow: var(--cp-shadow);
}}
.header-card {{ padding: 24px; margin-bottom: 16px; }}
.header-top {{ display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; flex-wrap: wrap; }}
.title-wrap h1 {{ margin: 0; font-size: 1.6rem; font-weight: 700; letter-spacing: -0.02em; }}
.title-wrap h1 span {{ color: var(--cp-accent); }}
.header-date {{ margin-top: 6px; font-size: 0.85rem; color: var(--cp-text-muted); }}
.auto-badge {{
  padding: 6px 14px;
  border-radius: 0.625rem;
  background: var(--cp-accent-soft);
  color: var(--cp-accent);
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
}}
.context-row {{ display: flex; gap: 12px; flex-wrap: wrap; margin-top: 18px; }}
.context-chip {{
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 14px;
  border-radius: 0.625rem;
  background: var(--cp-surface-soft);
  border: 1px solid var(--cp-border);
  font-size: 0.78rem;
  color: var(--cp-text-muted);
}}
.dot {{ width: 7px; height: 7px; border-radius: 999px; flex: 0 0 auto; }}
.dot-success {{ background: var(--cp-success); }}
.dot-danger {{ background: var(--cp-danger); }}
.dot-warning {{ background: var(--cp-warning); }}
.stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 18px; }}
.stat-card {{ padding: 18px 20px; }}
.stat-label {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; color: var(--cp-text-muted); }}
.stat-value {{ font-size: 1.5rem; font-weight: 700; margin-top: 4px; }}
.stat-value.accent {{ color: var(--cp-accent); }}
.stat-sublabel {{ font-size: 0.75rem; color: var(--cp-text-muted); margin-top: 2px; }}
.stock-list {{ display: grid; gap: 16px; }}
.stock-card {{ overflow: hidden; animation: fadeIn 0.3s ease both; animation-delay: var(--delay); }}
.stock-card.expanded {{ border-color: var(--cp-accent); }}
.stock-header {{
  width: 100%;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px 24px;
  background: transparent;
  border: 0;
  text-align: left;
  cursor: pointer;
  color: inherit;
}}
.stock-header:hover, .level-row:hover {{ background: var(--cp-accent-soft); }}
.ticker-box {{
  width: 44px;
  height: 44px;
  border-radius: 0.625rem;
  background: var(--cp-accent-soft);
  color: var(--cp-accent);
  font-weight: 800;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
}}
.stock-identity {{ min-width: 180px; }}
.stock-ticker {{ font-size: 1rem; font-weight: 700; }}
.stock-name {{ font-size: 0.82rem; color: var(--cp-text-muted); margin-top: 2px; }}
.stock-meta-grid {{ display: flex; flex: 1 1 auto; gap: 16px; flex-wrap: wrap; }}
.meta-block {{ min-width: 100px; }}
.meta-label {{ font-size: 0.68rem; text-transform: uppercase; color: var(--cp-text-muted); letter-spacing: 0.06em; }}
.meta-value {{ font-size: 0.95rem; font-weight: 600; margin-top: 4px; }}
.text-success {{ color: var(--cp-success); }}
.text-danger {{ color: var(--cp-danger); }}
.text-warning {{ color: var(--cp-warning); }}
.conviction-wrap {{ margin-left: auto; min-width: 140px; }}
.conviction-label {{ font-size: 0.72rem; color: var(--cp-text-muted); text-align: right; margin-bottom: 6px; }}
.conviction-track {{ height: 8px; border-radius: 4px; border: 1px solid var(--cp-border); background: var(--cp-surface-soft); overflow: hidden; }}
.conviction-fill, .confidence-fill {{ display: block; height: 100%; transition: width 0.4s ease; }}
.fill-success {{ background: var(--cp-success); }}
.fill-warning {{ background: var(--cp-warning); }}
.fill-danger {{ background: var(--cp-danger); }}
.expand-arrow {{ color: var(--cp-text-muted); transition: transform 0.25s ease; margin-left: 8px; }}
.stock-card.expanded .expand-arrow {{ transform: rotate(180deg); }}
.stock-detail {{ padding: 0 24px 24px; }}
.stock-detail.hidden {{ display: none; }}
.detail-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
.detail-panel {{ padding: 4px 0 0; }}
.section-kicker {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.08em; color: var(--cp-text-muted); font-weight: 700; margin-bottom: 12px; }}
.indicator-chip-row {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }}
.indicator-chip {{
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.72rem;
  font-weight: 600;
  border: 1px solid var(--cp-border);
  background: var(--cp-surface);
}}
.reason-card {{ background: var(--cp-surface-soft); border: 1px solid var(--cp-border); border-radius: 0.625rem; padding: 14px 16px; margin-bottom: 12px; }}
.reason-tag {{ font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--cp-accent); margin-bottom: 4px; }}
.reason-body, .ntz-note, .tooltip-body, .footer-note, .failures li {{ font-size: 0.85rem; color: var(--cp-text-soft); line-height: 1.55; }}
.ntz-box {{ background: var(--cp-surface-soft); border: 1px dashed var(--cp-warning); border-radius: 0.625rem; padding: 12px 16px; }}
.ntz-title {{ font-size: 0.72rem; font-weight: 700; color: var(--cp-warning); text-transform: uppercase; margin-bottom: 6px; }}
.ntz-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-top: 10px; }}
.ntz-label {{ color: var(--cp-text-muted); font-size: 0.75rem; margin-bottom: 2px; }}
.detail-panel-levels {{ padding: 0; }}
.level-block {{ animation: fadeIn 0.3s ease both; animation-delay: var(--delay); }}
.level-row {{
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 0.625rem;
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  text-align: left;
}}
.level-tag {{ font-size: 0.7rem; font-weight: 800; text-transform: uppercase; width: 28px; flex: 0 0 auto; }}
.level-price {{ font-size: 0.95rem; font-weight: 700; width: 88px; flex: 0 0 auto; }}
.confidence-track {{ flex: 1; height: 20px; background: var(--cp-surface-soft); border: 1px solid var(--cp-border); border-radius: 4px; overflow: hidden; min-width: 80px; }}
.confidence-label {{ font-size: 0.72rem; font-weight: 700; width: 40px; text-align: right; flex: 0 0 auto; }}
.source-summary {{ font-size: 0.72rem; color: var(--cp-text-muted); width: 160px; text-align: right; flex: 0 0 auto; }}
.now-marker {{ display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1.5px dashed var(--cp-border-strong); border-radius: 0.625rem; background: var(--cp-highlight); color: var(--cp-accent); font-weight: 700; margin: 12px 0; }}
.level-tooltip {{ display: none; margin: 8px 10px 12px; background: var(--cp-surface); border: 1px solid var(--cp-border-strong); border-radius: 0.625rem; padding: 12px 16px; box-shadow: var(--cp-shadow); }}
.level-tooltip.open {{ display: block; }}
.tooltip-title {{ font-size: 0.78rem; font-weight: 700; margin-bottom: 6px; }}
.source-tags {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
.source-tag {{ font-size: 0.66rem; padding: 2px 8px; border-radius: 4px; background: var(--cp-accent-soft); color: var(--cp-accent); font-weight: 600; }}
.failures {{ margin-top: 18px; padding: 16px 18px; background: var(--cp-surface); border: 1px solid var(--cp-border); border-radius: 16px; box-shadow: var(--cp-shadow); }}
.footer-note {{ margin-top: 24px; text-align: center; color: var(--cp-text-muted); }}
@keyframes fadeIn {{
  from {{ opacity: 0; transform: translateY(8px); }}
  to {{ opacity: 1; transform: translateY(0); }}
}}
@media (max-width: 900px) {{
  .stock-header {{ flex-wrap: wrap; }}
  .conviction-wrap {{ width: 100%; margin-left: 0; }}
  .conviction-label {{ text-align: left; }}
  .detail-grid {{ grid-template-columns: 1fr; }}
  .source-summary {{ width: 120px; }}
}}
@media (max-width: 768px) {{
  .page {{ padding: 20px 14px 36px; }}
  .stock-header {{ padding: 18px; }}
  .stock-detail {{ padding: 0 18px 18px; }}
  .stock-meta-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }}
  .level-row {{ flex-wrap: wrap; }}
  .source-summary {{ width: 100%; text-align: left; }}
  .ntz-grid {{ grid-template-columns: 1fr 1fr; }}
}}
</style>
</head>
<body>
<button class="theme-toggle" type="button" aria-label="Toggle theme">◐</button>
<div class="page">
  <section class="header-card header-card-main">
    <div class="header-top">
      <div class="title-wrap">
        <h1>Trading Opportunities <span>Report</span></h1>
        <div class="header-date">Session: {esc(report_data['session_date'])} - Generated {esc(report_data['generated_at'])}</div>
      </div>
      <div class="auto-badge">Auto-generated scanner report</div>
    </div>
    <div class="context-row">{context_chips}</div>
  </section>
  <section class="stats-grid">{stats_html}</section>
  <section class="stock-list">{cards_html}</section>
  {failures_html}
  <div class="footer-note">This report is for educational/research purposes only. Not financial advice. All levels are generated from technical analysis. Past performance does not guarantee future results.</div>
</div>
<script>
const root = document.documentElement;
document.querySelector('.theme-toggle').addEventListener('click', () => {{
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
}});

document.querySelectorAll('.stock-card .stock-header').forEach((header) => {{
  header.addEventListener('click', () => {{
    const card = header.closest('.stock-card');
    card.classList.toggle('expanded');
    const detail = card.querySelector('.stock-detail');
    detail.classList.toggle('hidden');
  }});
}});

document.querySelectorAll('.level-row').forEach((row) => {{
  row.addEventListener('click', (event) => {{
    event.stopPropagation();
    const targetId = row.getAttribute('data-tooltip-target');
    const tooltip = document.getElementById(targetId);
    const parent = row.closest('.detail-panel-levels');
    parent.querySelectorAll('.level-tooltip.open').forEach((node) => {{
      if (node !== tooltip) node.classList.remove('open');
    }});
    tooltip.classList.toggle('open');
  }});
}});
</script>
</body>
</html>'''



def write_outputs(report_data: dict[str, Any]) -> None:
    json_path = OUTPUT_DIR / "report-data.json"
    html_path = OUTPUT_DIR / "trading-report.html"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(report_data, handle, indent=2)
    with html_path.open("w", encoding="utf-8") as handle:
        handle.write(generate_html(report_data))


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = build_report_data()
    write_outputs(report)
    print(json.dumps({
        "json": str(OUTPUT_DIR / "report-data.json"),
        "html": str(OUTPUT_DIR / "trading-report.html"),
        "top_picks": [item["ticker"] for item in report["top_picks"]],
        "avg_conviction": report["avg_conviction"],
        "failures": report["failures"],
    }, indent=2))
