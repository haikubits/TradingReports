---
name: stock-analysis-framework
description: |
  Analyze a mid- or large-cap equity using a seven-phase framework that covers business context,
  earnings quality, guidance, valuation, competitive position, sentiment, and disciplined buy timing.
  Load this skill when the user wants a structured stock write-up, scorecard, or investment-decision framework.
---

# Stock Analysis Framework Skill

## Purpose

Use this skill to evaluate a mid- or large-cap equity with market cap above $10B using a consistent, narrative-aware process. The framework is designed to prevent shallow valuation work by forcing context, earnings quality, guidance interpretation, competitive analysis, sentiment checks, and buy-decision discipline before reaching a conclusion.

Core principle:
- The market prices narratives, not just numbers.
- A stock can beat published estimates and still fall if it misses the narrative or whisper bar.
- Do not jump straight to valuation. Complete the earlier phases first.

## Repository Targets

Use this repository for the skill definition:
- repo: `https://github.com/haikubits/TradingReports`
- local path: `codeRefs/TradingReports`
- skill path: `codeRefs/TradingReports/.github/skills/stock-analysis-framework/`

## When This Skill Applies

Load this skill when the user wants to:
- analyze a specific mid- or large-cap stock end-to-end
- compare multiple large-cap stocks using a shared framework
- understand whether an earnings selloff is narrative-driven or fundamentally justified
- produce a structured investment memo, checklist, or scorecard
- assess valuation together with guidance quality and catalyst timing

Do not use this skill as the only framework for small caps or micro caps. Those require additional liquidity, management, and balance sheet risk work.

## Required Scope

This framework applies to equities with:
- market cap above $10B
- enough reporting history to evaluate multi-quarter growth, margins, guidance behavior, and valuation context

If the company does not fit that profile, explicitly call out that the framework only partially applies.

## Standard Workflow

Work through these seven phases in order.

### Phase 1 - Context and Orientation

Answer these first:
- What does the company do in one sentence?
- What are the primary revenue drivers?
- Is the model hardware, software, recurring SaaS, transactional, licensing, or mixed?
- What two or three things must go right for growth to continue?
- Is the business cyclical or a secular growth compounder?
- What is the current market narrative?
- What is the stock's recent price-action context relative to the market and peers?

Rules:
- If you cannot explain the business clearly in one sentence, stop and gather more context.
- Separate cyclical mean-reversion setups from secular compounding setups.
- Check whether the stock has already run hard into an event; the expectation bar rises with the run-up.

### Phase 2 - Earnings and Fundamentals

Evaluate the quality of the recent results, not just the headline beat.

Check:
- revenue growth rate and whether it is accelerating or decelerating versus the prior 2 to 4 quarters
- gross, operating, EBITDA, and free-cash-flow margins
- GAAP versus non-GAAP EPS and the size of recurring exclusions
- beat magnitude and whether management likely sandbagged
- whether guidance was raised, held, or cut after the beat
- segment-level contribution to growth or weakness
- balance-sheet quality, debt trajectory, buybacks, and dividends

Key interpretation rules:
- accelerating growth is more valuable than merely high growth
- margin expansion is a strong compounding signal
- stock-based compensation is a real cost
- a headline beat with weak segments or weak guidance is not a clean bullish result

### Phase 3 - Guidance and Forward View

Treat guidance as the most important near-term input.

Compare guidance against:
- published consensus
- the likely whisper or optimistic buy-side expectation
- the company's own historical guidance conservatism

Check:
- next-quarter revenue guidance
- full-year guidance change: raise, hold, or cut
- historical pattern of conservative versus aggressive guidance
- qualitative demand signals from the call: backlog, customer adds, pipeline, design wins, pricing power, contract duration

Rules:
- a consensus beat can still fail if it misses the whisper bar
- a strong quarter with flat guidance may imply pull-forward rather than true outperformance
- known conservative guiders should be judged against their own history, not at face value alone

### Phase 4 - Valuation

Use valuation only after business quality and forward view are understood.

Primary tools:
- forward P/E versus the company's own 3 to 5 year history
- forward P/E versus peers and the S&P 500
- PEG ratio for growth-adjusted context
- EV/EBITDA and EV/FCF for capital-structure-aware comparisons
- DCF as the intrinsic-value anchor
- price-to-sales only when earnings are not yet useful

DCF inputs:
- current annual free cash flow
- years 1 to 5 growth rate
- years 6 to 10 growth rate
- terminal growth rate, usually 2 to 4%
- WACC, usually 8 to 12% for large-cap tech unless risk demands more
- net debt
- shares outstanding

Always run:
- bear case
- base case
- bull case

Margin-of-safety guide:
- 15 to 20% discount can be acceptable for high-quality large-cap compounders
- 30 to 50% discount is more appropriate for lower-moat or cyclical names

### Phase 5 - Competitive and Macro Context

Check whether the company can protect returns and whether macro conditions support or hurt the thesis.

Assess:
- moat type: switching costs, network effects, cost advantages, intangible assets, or efficient scale
- moat strength: wide, narrow, or none
- growth and margin position relative to competitors
- market-share direction
- relevant macro drivers such as rates, FX, hyperscaler capex, or regulation
- customer concentration risk from filings

Rules:
- lower-moat businesses require a better price
- customer concentration is risk first and moat second
- a company can execute well and still face multiple compression from macro headwinds

### Phase 6 - Sentiment and Positioning

Use this phase to separate long-term value from short-term market psychology.

Check:
- short interest and whether it is rising or falling
- options-implied move into earnings
- institutional ownership and recent fund-flow direction
- analyst rating changes and price-target trajectory

Rules:
- high short interest is both warning and squeeze fuel
- buying calls into earnings requires beating the implied move, not just being directionally right
- direction of analyst sentiment matters more than the current rating mix alone

### Phase 7 - Buy Decision and Timing

Answer the four gating questions in order:
1. Is the business fundamentally sound and growing?
2. Is there a meaningful margin of safety?
3. What is the catalyst for re-rating?
4. What is the bear case, and is it tolerable?

If the answer is no to an early question, stop rather than forcing a buy thesis.

Timing rules:
- post-earnings selloffs can be attractive if fundamentals remain intact and the miss is mainly narrative-driven
- distinguish sentiment-driven selloffs from genuine business deterioration
- avoid buying immediately into a large gap down; let price and volume stabilize first

Position sizing:
- enter in thirds rather than all at once
- first third on initial conviction
- second third when the thesis is confirmed
- final third when the catalyst materializes
- scale total size by conviction, margin of safety, and portfolio context

## Decision Scorecard

Use this final check before presenting a buy or watchlist conclusion.

Positive signals:
- revenue growth is accelerating
- margins are stable or expanding
- guidance beat the whisper bar or full-year guidance was raised
- shares trade at or below base-case intrinsic value
- forward P/E is below the company's own history
- PEG is below 1.5
- a clear re-rating catalyst exists
- any recent selloff appears sentiment-driven rather than fundamentally driven

Scoring guide:
- 6 to 8 checks: strong buy thesis; scaling in is reasonable
- 4 to 5 checks: starter position or watchlist candidate
- below 4: wait for more clarity or a better price

## Output Format

When using this skill, structure the response with these sections:
1. Business snapshot
2. Current narrative and price context
3. Earnings and guidance quality
4. Valuation view
5. Competitive and macro context
6. Sentiment and positioning
7. Buy decision using the four gating questions
8. Scorecard summary
9. Risks, bear case, and timing notes

Keep the conclusion explicit:
- buy now
- starter only
- watchlist / wait
- avoid for now

Always state why.

## Guardrails

- Treat the framework as research support, not financial advice.
- Do not present valuation outputs as certainty; show assumption sensitivity.
- Explicitly separate narrative disappointment from true fundamental deterioration.
- Do not skip earlier phases just because valuation appears cheap.
- For small-cap, micro-cap, or thinly traded names, state that this framework is incomplete without extra risk work.

## Source

Derived from the attached stock-analysis framework provided on 2026-06-04 and translated into reusable skill instructions for the TradingReports repository.
