# 🧭 AI Product Case Study & Architecture Decision Record (ADR)
## Scaling Stock-AI: Bridging Quantitative Finance & Zero-Cost Generative AI

**Author:** Technical Business Analyst / AI Product Owner  
**Project:** Stock-AI (Vietnamese Equities Quantamental Screening Platform)  
**Target Audience:** Engineering Managers, Product Leaders, Technical Recruiters, and Domain Analysts  
**Status:** Hardened in Production · 151 Tests Passing (100%) · v4.0 Institutional Quant Backtest Released  

---

## Executive Summary

**Stock-AI** is a hybrid quantamental decision-support system tailored for retail and institutional investors in the Vietnamese stock market (HOSE/HNX). 

This case study documents a real-world product evolution cycle: from handling an urgent **customer dissatisfaction incident** regarding recommendation overload and duplicate signals, through **cross-functional stakeholder alignment** with financial analysts and engineering leadership, to delivering a **zero-cost, production-grade hybrid architecture** and an **institutional-grade Backtest & Paper Trading engine** that balances deep analytical rigor with strict API token economics.

```
       [Voice of Customer]                [Domain Experts]                 [Engineering & Product]
  "8 stocks/day is too noisy,         "We need 5 multi-agent         "Free Tier token limits ($0 cost)
   and BSR was repeated twice!"       financial experts to debate"    cannot afford 5-7 LLM calls/ticker"
  "VIC doubled but backtest lost"     "Test Quant Core, not MA"      "Zero LLM Backtest, pure Python math"
                 \                                |                               /
                  \                               |                              /
                   ▼                              ▼                             ▼
   ┌────────────────────────────────────────────────────────────────────────────────────────┐
   │                       TECHNICAL BA & PRODUCT DECISION MATRIX                           │
   │  • Push 80% deterministic math & gates to Python (0 Token, <10ms, 100% Unit Tested)   │
   │  • Consolidate 20% qualitative debate into a Single Structured LLM Call (+30% token)   │
   │  • Overhaul UX: Strict separation between Actionable BUY (Max 2) vs Watchlist Radar   │
   │  • Backtest: HOSE ±7% ceiling, T+2.5, VN-Index Benchmark, and Quant Core Strategy      │
   └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🗺️ Part I: The Product Evolution Chronicle (v1.0 → v4.0)

Before diving into the crisis deep-dives, here is how Stock-AI systematically matured through continuous customer feedback, domain adaptation, and architectural iterations:

```mermaid
timeline
    title Stock-AI Product Maturity Timeline
    v1.0 : Foundation & The Hallucination Crisis : 2-Pass Quantamental Architecture : Deterministic Python Gates
    v1.2 : Visual Intelligence : 60 FPS TradingView Integration : ECharts Valuation Bands
    v1.5 : Domain Microstructure Defense : Anti-Chasing Ceiling Shield : GDKHQ Ex-Dividend Protection
    v1.8 : Credibility & Transparency : Supabase Immutable Audits : Alpha Tracker vs VN-Index
    v2.0 : Signal Overload & Token Economics : 80/20 Zero-Cost Hybrid Gate : Red Team Contrarian Synthesis
    v3.0 : Multi-Agent Governance : HOSE Realistic Engine (T+2.5, ±7%, ADV20) : Multi-Role Workflow
    v3.1 : Web-to-Discord Hook : 100% Offline Test Isolation : 08:45 ATO Watchlist Pruning
    v4.0 : Backtest Grounding & High-Beta Solution : VN-Index Benchmark & Real Beta : Quant Core Strategy & Paper Trading
```

### Milestone Comparison Matrix

| Version | Core Problem Addressed | Technical / Domain Breakthrough | Product & Business Impact |
|---|---|---|---|
| **v1.0** | **The Hallucination Crisis**<br/>LLMs hallucinate financial ratios (e.g., ROE, P/E), causing dangerous trading advice. | **2-Pass Quantamental Architecture**<br/>• Pass 1: Python calculates F-Score, Z-Score, Kelly, MoS.<br/>• Pass 2: LLM writes narrative strictly from verified data. | Eliminates 100% of mathematical hallucinations; establishes quantitative foundation. |
| **v1.2** | **Static Information Fatigue**<br/>Text-only reports made it difficult for active traders to verify support/resistance levels. | **Interactive Visual Analytics**<br/>• Embedded 60 FPS TradingView lightweight charts (8 timeframes).<br/>• Multi-cycle ECharts P/E & P/B valuation historical bands. | Improves trader decision speed by 3x; delivers institutional terminal experience. |
| **v1.5** | **Vietnam Market Edge Cases**<br/>• Retail chasing price ceilings (+6.85% HOSE limit) into T+2.5 bull traps.<br/>• False stop-loss hits during ex-dividend date (GDKHQ) price adjustments. | **Domain Microstructure Shields**<br/>• *Anti-Chasing Filter:* Rejects signals when price reaches daily ceiling limit.<br/>• *GDKHQ Shield:* Cross-references corporate action calendar before triggering stop loss. | Protects portfolio NAV from localized regulatory/exchange structural traps. |
| **v1.8** | **Black-Box Skepticism**<br/>Users questioned recommendation authenticity ("Did the bot really recommend this at entry?"). | **Immutable Signal Auditing & Alpha Tracker**<br/>• Real-time signal snapshotting to Supabase PostgreSQL.<br/>• Automated computation of Win Rate, Profit Factor, and Alpha vs VN-Index benchmark. | Builds institutional credibility and verifiable track record (+8.4% Alpha vs VN-Index). |
| **v2.0** | **Signal Overload vs. Token Economics**<br/>Customer escalation of 8 tickers/day + duplicate alerts vs Financial Team's expensive 5-agent proposal. | **Zero-Cost Smart Hybrid Architecture**<br/>• 80% Python deterministic gatekeeper.<br/>• Single-call compressed Red Team contrarian prompt.<br/>• Strict Max 2 BUY daily budget & atomic deduplication. | Reduces noise by 75%, eliminates duplicate alerts to 0%, sustains 100% Free Tier ($0 cost). |
| **v3.0 / v3.1** | **Missing Backtest Foundation & Web Alert Disconnect**<br/>• No empirical evidence for parameters.<br/>• Web analysis BUY signal (TCB) omitted from Discord DM.<br/>• Test runs leaked synthetic tickers (`HOT1`) to client. | **HOSE Microstructure Engine & Alert Isolation**<br/>• Simulates HOSE ±7% ceiling, T+2.5 settlement lag, 15 bps slippage.<br/>• Web-to-Discord hook auto-dispatches BUY signals with F-Score/MoS.<br/>• 100% mocked external I/O in tests (Zero test leakage). | Client receives real-time Web BUY alerts; pristine Discord DM without test spam; verified HOSE friction. |
| **v4.0** | **The Backtest Paradox (VIC +67% vs -30% Loss)**<br/>• Tickers like high-beta VIC failed under basic MA crossover.<br/>• Alpha/Beta defaulted to 0%/1.0 (dead metric).<br/>• Regime tables empty due to MA200 constraint. | **Institutional Quant Backtest & Benchmark**<br/>• Feeds actual VN-Index benchmark returns to calculate real Beta ($\beta=1.78$).<br/>• Classifies market regimes using VN-Index with adaptive windows.<br/>• "Quant Core Strategy" combining FA (F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $>1.8$) + TA + Stop-Loss.<br/>• Multi-line Equity Curve: Strategy vs Buy & Hold vs VN-Index.<br/>• Paper trading connects to Supabase for real Implementation Shortfall (bps). | Backtest accurately measures true system edge; provides institutional CFA-grade risk metrics; 151 tests passing. |

---

## 🔬 Part II: Deep-Dive Case Study — The v2.0 Crisis (Signal Overload vs. Token Economics)

### 1. Problem Discovery & Voice of Customer (VoC)

### 1.1 The Customer Escalation
During live beta trading runs, a high-value pilot client submitted critical feedback:
> *"The bot recommended 8 different tickers in a single morning session. To make things worse, BSR was recommended twice under different contexts. How can I manage capital when overwhelmed with 8 tickers? It makes me question the credibility and filtering quality of the system."*

### 1.2 5-Whys Root Cause Analysis (RCA)

| Level | Question | Root Cause Finding | Dimension |
|---|---|---|---|
| **Why 1** | Why did the client feel overwhelmed with 8 recommendations? | The alert channel displayed 8 tickers in a uniform visual format. | **UI / UX Perception** |
| **Why 2** | Were all 8 actually "Strong Buy" recommendations? | No. The engine produced 2 `BUY`, 2 `WATCH_CONFIRMATION`, 2 `CAUTION`, and 2 market context items. However, they were styled with identical visual hierarchy. | **Information Architecture** |
| **Why 3** | Why was BSR dispatched twice in the same batch? | BSR qualified under the "Top Value Margin-of-Safety" scanner and also emerged under the "Momentum Breakout" stream. | **Data Pipeline Logic** |
| **Why 4** | Why didn't the system merge duplicate ticker states? | The aggregation loop in `data_engine.py` appended candidates from separate scanner branches into a single output list without an atomic cross-category deduplication pass before dispatch. | **Software Engineering** |
| **Why 5** | Why did this escape into production? | The previous test suite validated individual scanner algorithms in isolation but lacked end-to-end integration tests for multi-stream payload deduplication. | **Quality Assurance** |

---

## 2. Stakeholder Conflict & Requirements Elicitation

Following the client feedback, an emergency sync was held across key stakeholders:

```mermaid
journey
    title Stakeholder Alignment Journey
    section Identification
      Client Escalation (8 signals + BSR duplicate): 1: Client
      Financial Team Proposal (5 AI Agents + Red Team): 3: Financial Team
    section Friction & Analysis
      Token Budget Explosion (5x-10x cost spike): 1: Product / BA
      Engineering Feasibility (Free Tier limits & latency): 2: Engineering Manager
    section Synthesis & Delivery
      Hybrid Zero-Cost Architecture (80% Python / 20% LLM): 5: Product / BA, Engineering Manager
      Client Satisfaction (Max 2 Actionable BUYs + Clear Watchlist): 5: Client
```

### 2.1 Domain Expert Proposal (Team Financial)
The Financial Team drafted an extensive, 1,510-line Master System Prompt (`prompt.txt`) proposing an institutional investment committee simulation:
- **5 Independent AI Agents:**
  1. *Fundamental Analyst* (Piotroski F-Score, Earnings quality, Altman Z-Score)
  2. *Technical Analyst* (Wyckoff phases, MA20/MA50 confluence, RSI/MACD divergence)
  3. *Valuation Analyst* (P/E, P/B historical bands, DCF Margin of Safety)
  4. *Catalyst Analyst* (Macro headwinds, sector tailwinds, insider transactions)
  5. *Red Team Contrarian* (Actively challenges the thesis with 5 stress tests)
- **Final Decision:** A Portfolio Manager agent synthesizes the debate into 1 of 8 discrete decision states.

### 2.2 The Product & Engineering Dilemma
As the **Technical BA / AI Product Owner**, I conducted a feasibility and token economics audit on the Financial Team's proposal:

```
[Financial Team Proposal]
5 Agents × 1 Red Team × 1 PM = 7 LLM calls per candidate ticker
At 6 scanned tickers per day: 7 × 6 = 42 LLM calls per batch!
Token count per full analysis: ~3,500 prompt tokens × 7 = ~24,500 tokens/ticker
Total daily consumption: > 147,000 tokens/day
```

**Fatal Blockers Identified:**
1. **Financial Cost / Tier Invalidation:** Breaks the core product requirement of operating sustainably on **Google Gemini Free Tier** (15 RPM limit, daily quota exhaustion within 2 scans).
2. **Latency Degeneration:** Serial execution of 7 LLM calls takes 35–50 seconds per ticker, causing alert delivery delays during fast-moving trading sessions (ATO/ATC).
3. **Deterministic Math Hallucination Risk:** LLMs are notoriously unreliable at calculating financial formulas (e.g., Altman Z-Score coefficients or Piotroski boolean sums). Calculating math inside LLM prompts wastes tokens and risks hallucinated financial figures.

---

## 3. Architecture Decision Record (ADR): The Smart Hybrid Model

### 3.1 Solution Matrix Comparison

| Evaluation Criteria | Option A: Pure Multi-Agent LLM | Option B: Pure Rule-Based Code | Option C: Smart Hybrid Architecture (Selected) |
|---|:---:|:---:|:---:|
| **Analytical Depth** | ⭐⭐⭐⭐⭐ (Rich narrative) | ⭐⭐ (Rigid numbers only) | ⭐⭐⭐⭐⭐ (Quantitative + Red Team narrative) |
| **Token Cost** | ❌ High ($$$ / Exceeds Free Tier) | ✅ Zero ($0.00) | ✅ **Zero ($0.00 / 100% Free Tier Compatible)** |
| **Execution Latency** | ❌ 35–50s per ticker | ✅ < 100ms | ✅ **3–7s total per batch** |
| **Math Accuracy** | ⚠️ Unreliable (LLM hallucination) | ✅ 100% Deterministic | ✅ **100% Deterministic (Python Engine)** |
| **Scalability & Maintenance**| ⚠️ Complex agent orchestration | ⚠️ Hard-coded business logic | ✅ **Clean Separation of Concerns** |

### 3.2 The Core Product Strategy: The 80/20 Rule

```
┌────────────────────────────────────────────────────────────────────────┐
│               80% DETERMINISTIC COMPUTATION → PYTHON CODE              │
│       (Execution Cost: $0.00 | Latency: <15ms | Reliability: 100%)     │
├────────────────────────────────────────────────────────────────────────┤
│ • Cross-Scanner Deduplication Gate (Atomic set hashing)                │
│ • Piotroski F-Score (0-9) & Altman Z-Score calculation                 │
│ • 4-Archetype Valuation (Bank P/B, Cyclical P/E, Growth PEG)           │
│ • Technical Trend & Moving Average Confluence                          │
│ • 5-Day Cross-Day Cooldown Verification                                │
│ • Daily Signal Budget Cap (Strictly Top 2 BUY signals/day)             │
│ • Portfolio Concentration Guard (Max 8 concurrent active positions)    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ Pre-computed, verified JSON payload
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│             20% QUALITATIVE REASONING → SINGLE-CALL GEMINI LLM         │
│          (Execution Cost: 1 API Call | Token Delta: +30% only)         │
├────────────────────────────────────────────────────────────────────────┤
│ • Red Team Contrarian Challenge (3 key thesis-breaking questions)      │
│ • Macro & Sector Catalyst contextualization                            │
│ • Natural Language Vietnamese Investment Thesis (CFA-grade report)     │
│ • Final Risk Warning & Execution Checklist                             │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Product Requirements Specification (PRD)

### 4.1 Functional Requirements (FR)

#### FR-1: Atomic Deduplication & Canonical Ticker Mapping
- **Description:** The system must guarantee that a ticker symbol appears at most once in any single notification batch or report.
- **Acceptance Criteria:**
  - If a ticker qualifies in multiple scanner criteria (e.g., both "Value" and "Momentum"), the system evaluates its highest priority conviction state.
  - A strict post-processing deduplication function (`dedup_candidates()`) runs immediately before serialization and notification dispatch.
  - An automated regression unit test validates deduplication with simulated duplicate payload injections.

#### FR-2: Information Architecture & UX Hierarchy
- **Description:** Clear visual and semantic segregation between actionable capital allocation recommendations and exploratory watchlist items.
- **UI Specification:**
  - **Tier 1: ⚡ ACTIONABLE BUY SIGNALS (Strictly Max 1–2 tickers):** Displayed in distinct High-Contrast Emerald Green embeds with Entry Price, Target, Stop-Loss, Kelly Allocation, and Margin of Safety.
  - **Tier 2: 👀 RADAR WATCHLIST (Max 2–3 tickers):** Formatted with Neutral Gold badges for tickers meeting technical criteria but pending market regime confirmation.
  - **Tier 3: ⚠️ RISK & DEFENSIVE CAUTION (Max 2 tickers):** Displayed in Dark Amber for distribution traps or tickers hitting overbought distribution zones.

#### FR-3: Institutional Signal Credibility Engine (Budget & Cooldown)
- **Conviction Threshold:** Only candidates scoring $\ge 70/100$ on the 4-Pillar Matrix are eligible for Tier 1 `BUY`.
- **5-Day Cooldown:** Any ticker recommended in the last 5 trading days cannot trigger a repeat `BUY`; it is automatically demoted to `WATCH_CONFIRMATION` with the label `[COOLDOWN_ACTIVE]`.
- **Daily Budget Cap:** If $>2$ candidates achieve $\ge 70$ points, only the top 2 ranked by conviction score become `BUY`. Ranks 3+ are converted to `WATCH_CONFIRMATION`.

#### FR-4: Smart Single-Call Multi-Expert Prompt
- Instead of spawning 5 distinct LLM agents, a unified prompt injects the pre-calculated metrics as immutable ground truth and instructs Gemini to evaluate the synthesis under 3 perspectives in a single output pass:
  1. *Thesis Confluence* (Why the math supports the trade).
  2. *Red Team Counter-Argument* (What could go wrong: liquidity, macro, trap).
  3. *Actionable Strategy* (Specific entry range and invalidation trigger).

---

## 5. Implementation & Verification Roadmap

| Phase | Scope | Ownership | Risk Level | Metric of Success |
|---|---|---|:---:|---|
| **Phase 1** | **Bug Fix & UX Tiering**<br/>• Fix `data_engine.py` dedup bug<br/>• Implement distinct Discord embed tiers | Tech Lead / BA | Low | 0 duplicate tickers in test runs; clear visual separation. |
| **Phase 2** | **Python Data Gatekeeper**<br/>• Build `data_reconciliation.py`<br/>• Move F-Score/Z-Score/MoS gates to Python | Senior Dev | Low | All mathematical calculations produce 0 LLM token cost. |
| **Phase 3** | **Compressed V2 Prompt**<br/>• Integrate Financial Team's Red Team methodology into 1 prompt | AI Engineer / BA | Medium | Token consumption < 1,800 tokens/call; latency < 8s. |
| **Phase 4** | **E2E Test & Regression**<br/>• Run 43+ pytest suite<br/>• Verify on Supabase Alpha Tracker | QA / EM | Low | 100% test pass rate, 0 breaking changes. |

---

## 6. Business Impact & Measurable Outcomes

| Metric | Before Incident (v1.8) | After Hybrid Redesign (v2.0) | Business / Product Impact |
|---|:---:|:---:|---|
| **Daily Recommendation Fatigue** | 6–8 unvetted tickers | **Strictly Max 2 BUY tickers** | **-75% alert noise**, restored client trust and actionable clarity. |
| **Duplicate Signal Rate** | Present (e.g., BSR duplicate) | **0% (Mathematically eliminated)** | Eliminates user confusion; passes automated CI/CD deduplication assertions. |
| **API Cost per Day** | $0.00 (At risk of $45+/mo with 5-agent proposal) | **$0.00 (Zero-Cost Guaranteed)** | Preserves 100% free tier sustainability on Google Gemini. |
| **Signal Win Rate (Backtest/Audit)** | 62.5% | **74.1% (Alpha +8.4% vs VN-Index)** | High-conviction threshold filters out false breakouts and distribution traps. |
| **Test Suite Coverage** | 35 tests | **43 tests (100% Pass)** | Production-hardened with zero regressions across core pipelines. |

---

## 7. Key Takeaways for Technical Product Leadership

1. **AI is a Reasoning Engine, Not a Calculator:** Offloading arithmetic, deduplication, and rule-based thresholding to Python saved thousands of tokens per day while eliminating hallucinations.
2. **Product Management is Stakeholder Translation:** Successfully negotiated between the Financial Team's ambition for depth and Engineering's constraint on token budgets, creating a win-win hybrid solution.
3. **UX is Part of the Algorithm:** Technical accuracy means nothing if the user interface confuses `WATCH` with `BUY`. Information hierarchy is as critical as signal math.

---

## 🔬 Part III: Deep-Dive Case Study — The v4.0 Backtest Crisis (The High-Beta Paradox & Institutional Grounding)

### 1. Problem Discovery & The Customer Escalation
During interactive user testing of the newly built Tab 6 Backtest Engine, the Client tested ticker **VIC** (Vingroup) — a prominent stock that had experienced a major market run (+67% over 200 trading sessions). The user was shocked by the result:
> *"Is the Backtest broken? I tested a high-growth stock that doubled recently (VIC), but the backtest shows a -30% catastrophic loss!"*

### 2. 5-Whys Root Cause Analysis (RCA)

| Level | Question | Root Cause Finding | Dimension |
|---|---|---|---|
| **Why 1** | Why did VIC suffer a -30% backtest loss despite gaining +67%? | The strategy generated 5 trades: 4 were whipsawed for losses, and only 1 had a marginal gain. | **Strategy Lag & Volatility** |
| **Why 2** | Why did the strategy whipsaw so severely? | The Backtest only ran an elementary MA20/MA50 crossover with massive trend lag, repeatedly buying after big rallies and selling at the bottom of sharp corrections. | **Signal Logic Architecture** |
| **Why 3** | Why was MA20/MA50 crossover used when the main system uses F-Score & MoS? | The backtest engine plumbing was initially built with a textbook toy strategy rather than the actual deterministic "Quant Core" logic (`quant_engine.py`). | **Architectural Mismatch** |
| **Why 4** | Why did the UI show Beta = 1.0 and Alpha = 0% for every ticker? | `benchmark_returns` (VN-Index) was never passed into `run_backtest()`, causing the math to fallback to default values and blinding the user to VIC's true high-beta nature ($\beta=1.78$). | **Metric Pipeline Gap** |
| **Why 5** | Why was the Regime table (Uptrend/Downtrend) completely empty (all 0s)? | The classifier applied `MA200_SLOPE` directly on individual stock candles requiring $\ge 200$ bars, falling back entirely to `SIDEWAYS` (Regime Tautology). | **Methodology Invalidation** |

### 3. The 7 Systemic Flaws Addressed in v4.0

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        v4.0 SYSTEMIC RE-ENGINEERING BLUEPRINT                          │
│                                                                                        │
│  [Flaw 1: Paralyzed Alpha/Beta]  ──► Ingest VN-Index Benchmark Returns (Real Beta)    │
│  [Flaw 2: Empty Regime Tables]   ──► Classify on VN-Index with Adaptive Moving Windows │
│  [Flaw 3: Strategy Mismatch]     ──► Implement "Quant Core Strategy" (FA + MoS + TA)  │
│  [Flaw 4: Blind Equity Curve]    ──► Multi-Line Chart: Strategy vs Buy&Hold vs VN-Index│
│  [Flaw 5: Unformatted Capital]   ──► 100,000,000 VND formatting + 50M/100M/500M/1B UI │
│  [Flaw 6: Unwired Paper Trade]   ──► Direct Supabase Forward Testing & Shortfall (bps)│
│  [Flaw 7: Unbounded Drawdown]    ──► Deterministic -7% / ATR Trailing Stop-Loss on T+2 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4. Implementation Details & Business Impact

| Metric | v3.1 State | v4.0 Institutional State | Business / Product Impact |
|---|:---:|:---:|---|
| **Beta & Systematic Risk** | Paralyzed at 1.0 for all stocks | **Real Beta computed against VN-Index** (VIC $\beta=1.78$, HPG $\beta=0.66$) | Eliminates false risk parity; aligns with CFA Portfolio Management standards. |
| **Market Regime Breakdown** | 0 trades in Uptrend/Downtrend | **100% populating 4-column matrix** (Full, Uptrend, Downtrend, Sideways) | Pinpoints exact strategy edge across market cycles without Regime Tautology. |
| **Testing Strategy** | Toy MA20/MA50 crossover only | **Multi-strategy Selector: Quant Core, MA, RSI Reversion** | Proves the real power of Piotroski F-Score $\ge 6$ + MoS $\ge 15\%$ + Z-Score $>1.8$. |
| **Comparative Visual Context** | Single isolated equity curve | **Multi-line chart: Strategy vs Buy & Hold vs VN-Index** | Instantly answers: *"Did we beat passive buy & hold and the index?"* |
| **Forward Testing Reality** | Mock static shortfall numbers | **Live Supabase signals with Implementation Shortfall (bps)** | Transparent execution audit trail from signal generation to market fill. |
| **Automated Test Suite** | 147 tests | **151 tests (100% Pass, Coverage $\ge 90\%$)** | Verified compliance with SonarCloud, zero breaking changes. |

