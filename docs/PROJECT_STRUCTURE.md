# 🏛️ PROJECT ARCHITECTURE & CODEBASE STRUCTURE (PROJECT_STRUCTURE.md)

This document provides a comprehensive technical breakdown of the source code architecture, directory taxonomy, module responsibilities, and data flows of the **Stock-AI** quantitative analysis copilot. It serves as the primary technical specification for code reviewers, Test Leads, and system maintainers deploying to Production (Render.com, Linux VPS, or Cloud Containers).

---

## 1. 📂 Repository Taxonomy & Module Roles

```text
Stock - learning/
│
├── app.py                      # 🚀 MAIN ENTRYPOINT (Streamlit Application)
│                               # - Page configuration, responsive layout, custom CSS (Dark/Light)
│                               # - Top navigation bar orchestrating 5 functional feature tabs
│
├── components/                 # 📊 VISUALIZATION ENGINE (Embedded Native Components)
│   ├── __init__.py             # Component exports
│   ├── tradingview_chart.py    # Native 60 FPS TradingView Lightweight Charts integration:
│   │                           # - Multi-timeframe support: 1m, 5m, 15m, 30m, 1h, 1D, 1W, 1M
│   │                           # - Independent subpanels: Volume, MACD, RSI with drag resizers
│   │                           # - Synchronized crosshair (#v-crosshair-line) & fixed price-axis width
│   └── echarts_valuation.py    # Apache ECharts Multiples Valuation Bands:
│                               # - Dual-axis: VN-Index (left) vs P/E or P/B bands (right)
│                               # - Historical Mean Valuation overlay & interactive DataZoom slider
│
├── tabs/                       # 📑 FEATURE TABS (Business Domain Logic)
│   ├── __init__.py             # Tab exports
│   ├── tab_overview.py         # Tab 1: Market & Portfolio Overview (NAV KPIs, Heatmap, 24h News)
│   ├── tab_market.py           # Tab 2: Market Breadth & Historical Multiples (P/E, P/B bands)
│   ├── tab_charts.py           # Tab 3: Deep Technical Inspection (TradingView 60 FPS charts)
│   ├── tab_portfolio.py        # Tab 4: Portfolio Allocation & In-place Editable Data Table
│   ├── tab_ai.py               # Tab 5: AI Strategy Analysis (2-Pass Quantamental + CFA Narrative)
│   └── tab_alpha_tracker.py    # Tab 6: Signal Audit, Regime Backtest & Paper Trading Platform:
│                               # - Subtab 1: Alpha Ledger (Post-Market Audit, MFE/MAE, Loss Attribution)
│                               # - Subtab 2: Regime Backtest Engine (Multi-Strategy, VN-Index Benchmark, Multi-line Equity)
│                               # - Subtab 3: Forward Testing Paper Trading (Live Supabase Signals, Implementation Shortfall)
│
├── backtest_engine.py          # 🚀 DETERMINISTIC HOSE BACKTEST ENGINE
│                               # - Simulates HOSE microstructure: ±7% ceiling/floor, T+2.5 lag, fees/taxes, 15 bps slippage
│                               # - Multi-strategy signal generator: Quant Core (FA+MoS+Z-Score+TA), MA Crossover, RSI Reversion
│                               # - Dynamic Jensen's Alpha & Beta calculation against VN-Index benchmark
│                               # - Sub-equity curve decomposition across 4 market regimes (Full, Uptrend, Downtrend, Sideways)
│                               # - Capital & comparative helpers: `calculate_buy_and_hold_equity`, `calculate_normalized_benchmark_equity`
│
├── regime_classifier.py        # 🧭 OBJECTIVE MARKET REGIME CLASSIFIER
│                               # - Classifies market environment: UPTREND, DOWNTREND, SIDEWAYS
│                               # - Methodologies: MA200 Slope & Momentum-Volatility with adaptive windows
│                               # - Operates strictly on VN-Index to eliminate Regime Tautology
│
├── paper_trading.py            # 📝 FORWARD TESTING & SHORTFALL FRAMEWORK
│                               # - Measures execution drag via Implementation Shortfall (bps)
│                               # - Enforces daily signal budgets, holding cooldowns, and virtual position tracking
│                               # - Supports ablation testing: Quant Only vs Quant + LLM
│
├── db_manager.py               # 🗄️ PERSISTENCE & AUDIT (Supabase PostgreSQL REST Client)
│                               # - Immutable snapshot logging (`signals`) and lifecycle tracking (`signal_tracking`)
│                               # - Post-market audit engine (15:15 UTC+7) computing MFE, MAE, T+ marks
│                               # - Quantitative performance metrics query (Hit Rate, Profit Factor, Alpha)
│                               # - Cross-day cooldown verification (`check_symbol_recent_signal`)
│
├── quant_engine.py             # 📐 DETERMINISTIC QUANTITATIVE CORE (Python Engine)
│                               # - Data Gate: Recency validation & minimum liquidity filter (ADV20)
│                               # - Piotroski F-Score (0-9): Fundamental financial health scoring
│                               # - Altman Z-Score: Bankruptcy probability classification (Safe / Grey / Distress)
│                               # - ATR(14) Volatility Stop-Loss: Dynamic volatility-based risk thresholds
│                               # - Hard Gates: Expected Value, Margin of Safety (MoS), Kelly Criterion
│
├── quant_valuation.py          # 🎯 4-ARCHETYPE VALUATION ENGINE
│                               # - Sector archetype classification (Bank, Cyclical, Real Estate, Growth)
│                               # - Valuation models: P/B regression, Historical Median, SOTP, DCF/Graham
│                               # - Deterministic Margin of Safety (MoS %) calculation
│
├── quant_sanity_check.py       # 🛡️ MATHEMATICAL CONSISTENCY & SANITY GUARD
│                               # - Enforces 6 invariant financial rules (e.g., Profitable != Cut Loss)
│                               # - Dynamic Trailing Stop clamping: Clamped strictly < Current Price
│
├── data_engine.py              # ⚙️ DATA INGESTION & RISK ENGINE
│                               # - Market data feeds: Vnstock (VCI source), Google News, CafeF RSS
│                               # - Historical index feeds: `fetch_index_historical("VNINDEX")` for benchmark tracking
│                               # - Technical indicators: MA20, MA50, RSI14, Vol/SMA20, Smart Money Flow
│                               # - 4-Pillar Conviction Scoring Matrix (0-100 points)
│                               # - 5-Day Cross-Day Cooldown deduplication (Supabase-first + local JSON fallback)
│                               # - Daily Signal Budget (Max 2 BUYs/day) & Portfolio Guard (Max 8 positions)
│
├── ai_analyst.py               # 🧠 AI STRATEGY LAYER (Gemini Flash LLM)
│                               # - 2-Pass Quantamental pipeline: Python calculates -> Gemini interprets
│                               # - Web-to-Discord hook: Automatically dispatches BUY signals to Client Discord DM
│                               # - Anti-Hallucination Guard: Deterministic regex sanitizer eliminating CJK tokens
│                               # - CFA-grade institutional report generation
│
├── discord_alerts.py           # 🔔 NOTIFICATION ENGINE (Discord Webhooks & Bot)
│                               # - Formatted Rich Embeds with color-coded conviction tiers
│                               # - Direct Message (DM) private alerts for urgent risk triggers & Web BUY signals
│                               # - Watchlist pruning notification dispatched once daily before ATO (08:45)
│                               # - Smart Regex message chunker preserving Discord 4096-char limits
│
├── trading_bot.py              # 🤖 24/7 BACKGROUND WORKER (Automated Trading Bot)
│                               # - Autonomous loop aligned with Vietnam Trading Sessions (UTC+7)
│                               # - Real-time risk audit (< 1s latency): Stop loss, Trailing stop, Ceiling check
│                               # - Scheduled strategy dispatches: 08:45 (ATO), 11:30 (Lunch), 14:45 (ATC)
│                               # - Once-per-day Watchlist pruning guard before ATO (08:45)
│                               # - Post-market audit trigger at 15:15 UTC+7
│
├── run_cloud.py                # ☁️ CLOUD DUAL-PROCESS RUNNER
│                               # - Concurrently runs Trading Bot Daemon (Thread 1) + Streamlit UI (Thread 2)
│                               # - Tailored for single-container cloud hosting (Render.com, Koyeb, Docker)
│
├── tests/                      # 🧪 COMPREHENSIVE TEST SUITE (151 tests, 100% Pass)
│   ├── conftest.py             # Pytest configuration and 100% offline mock fixtures (Zero Discord Leak)
│   ├── test_backtest_engine.py # HOSE ceiling, T+2.5, slippage, Alpha/Beta vs VN-Index, Quant Core, Stop-Loss
│   ├── test_regime_classifier.py # MA200 slope, momentum-volatility, adaptive windowing
│   ├── test_paper_trading.py   # Implementation Shortfall, execution lag, order management
│   ├── test_sanity_checks.py   # Invariant rules, R:R calculation, trailing stop clamping
│   ├── test_v2_system.py       # Archetype valuation, holding evaluation, market regime
│   ├── test_alpha_and_lifecycle.py # GDKHQ dividend shield, anti-chasing, Supabase lifecycle
│   ├── test_task_0004_ui_and_web_hook.py # Streamlit tab rendering and Web-to-Discord hook verification
│   └── test_signal_budget.py   # 4-pillar conviction, 5-day cooldown, budget cap, portfolio guard
│
├── data/                       # 💾 DATA ARTIFACTS & LOCAL PERSISTENCE
│   ├── portfolio.json          # Portfolio holdings state
│   ├── watchlist.json          # Monitored watchlist state
│   └── .signal_cooldown.json   # Local fallback cache for 5-day signal cooldown
│
└── docs/                       # 📚 DOCUMENTATION & WORKFLOW
    ├── AI-workflow/            # Multi-Agent Workflow governance (Client.md, GLOBAL/, ROLES/, TASK/)
    ├── PRODUCT_CASE_STUDY.md   # Architectural decisions, RCA deep dives (v1.0 to v4.0)
    ├── PROJECT_STRUCTURE.md    # Codebase architecture specification (This file)
    └── rule.md                 # System operational rules and quant constraints
```

---

## 2. 🔄 End-to-End Data Flow Architecture

```mermaid
flowchart TD
    subgraph DataSources ["1. Data Ingestion Layer"]
        Vnstock["Vnstock API / VCI"] -->|OHLCV, Financial Ratios| DataEngine["data_engine.py"]
        GoogleNews["CafeF & Google News RSS"] -->|24h Macro & Sector RSS| DataEngine
        PortfolioJSON[("data/portfolio.json")] <-->|Read / Write Holdings| DataEngine
    end

    subgraph QuantCore ["2. Deterministic Quantitative Core"]
        DataEngine -->|OHLCV & Financials| QuantEngine["quant_engine.py"]
        DataEngine -->|Sector Classification| QuantVal["quant_valuation.py"]
        QuantVal -->|MoS %, Fair Value| QuantEngine
        QuantEngine -->|Data Gate, F-Score, Z-Score, ATR| AIAnalyst["ai_analyst.py"]
        QuantEngine -->|Mathematical Invariants| SanityCheck["quant_sanity_check.py"]
    end

    subgraph CredibilityEngine ["3. Signal Credibility & Risk Layer"]
        DataEngine --> Conviction[4-Pillar Conviction Scoring 0-100]
        Conviction --> CooldownCheck{In 5-Day Cooldown?}
        CooldownCheck -->|Yes| CooldownDowngrade[WATCH_CONFIRMATION]
        CooldownCheck -->|No| PortGuard{Open Positions < 8?}
        PortGuard -->|Full| PortDowngrade[WATCH_CONFIRMATION]
        PortGuard -->|Available| BudgetCap{Daily Budget: Max 2 BUYs}
        BudgetCap -->|Rank 1-2| ApprovedBUY[RECOMMEND_BUY]
        BudgetCap -->|Rank 3+| OverflowWatch[WATCH_CONFIRMATION]
    end

    subgraph Storage ["4. Audit Trail & Cloud Persistence"]
        ApprovedBUY -->|Immutable Snapshot| DBManager["db_manager.py"]
        TradingBot["trading_bot.py"] -->|15:15 Post-Market Audit| DBManager
        DBManager <-->|PostgreSQL REST API| Supabase[("Supabase Cloud DB")]
    end

    subgraph UI ["5. Streamlit User Interface"]
        AppCore["app.py"] --> Tab1["Tab 1: Overview & Portfolio"]
        AppCore --> Tab2["Tab 2: Market & ECharts Multiples"]
        AppCore --> Tab3["Tab 3: TradingView 60 FPS Charts"]
        AppCore --> Tab4["Tab 4: Portfolio Allocation Table"]
        AppCore --> Tab5["Tab 5: 2-Pass AI Strategy Report"]
        AppCore --> Tab6["Tab 6: Signal Audit & Backtest / Paper Trading"]
        Tab6 --> Subtab1["Subtab 1: Alpha Ledger & Attribution"]
        Tab6 --> Subtab2["Subtab 2: Regime Backtest Engine"]
        Tab6 --> Subtab3["Subtab 3: Forward Paper Trading"]
        Subtab1 -->|Audit Query| DBManager
        Subtab2 --> BacktestEng["backtest_engine.py"]
        Subtab2 --> RegimeClf["regime_classifier.py"]
        Subtab3 --> PaperTrade["paper_trading.py"]
        Subtab3 -->|Live Forward Signals| DBManager
    end

    subgraph Alerts ["6. Notification Delivery"]
        TradingBot -->|Emergency Alerts & Scheduled Reports| Discord["discord_alerts.py"]
        Tab5 -->|Web-to-Discord Hook: BUY Signal| Discord
        Discord --> DiscordChannel["Discord Channel #stock-alerts"]
        Discord --> DiscordDM["Discord Private DM (Secure)"]
    end
```

---

## 3. 🛡️ Institutional Signal Credibility & Quantitative Backtest Specifications

The system implements strict anti-dilution risk controls and realistic exchange friction simulation:

| Mechanism | Configuration | Implementation File | Rationale |
|---|:---:|---|---|
| **Conviction Matrix** | $\ge 70$ pts for BUY | `data_engine.py` | Requires confluence across Valuation (40), Technicals (25), Catalyst (20), Flow (15). |
| **5-Day Cooldown** | 5 Trading Days | `data_engine.py` + `db_manager.py` | Prevents firing duplicate BUY recommendations for the same symbol across consecutive sessions. |
| **Daily Signal Budget** | Max 2 BUYs / Day | `data_engine.py` | Forces capital concentration into the top 2 highest-conviction ideas; ranks by score, vol, and R:R. |
| **Portfolio Guard** | Max 8 Positions | `data_engine.py` + `db_manager.py` | Limits total concurrent active positions to prevent liquidity risk and excessive portfolio fragmentation. |
| **GDKHQ Shield** | Ex-dividend Gap Filter | `data_engine.py` + `tests/test_alpha_and_lifecycle.py` | Prevents artificial ex-rights price drops from triggering false stop-loss alerts. |
| **Anti-Chasing Filter** | Ceiling Check (+6.85%) | `data_engine.py` + `backtest_engine.py` | Automatically vetoes buy orders when price is pinned at HOSE upper trading limit. |
| **HOSE Settlement Lag** | Strict T+2.5 Rule | `backtest_engine.py` | Stock bought at day T can only be liquidated starting from the afternoon session of T+2. |
| **Exchange Frictions** | 0.25% Fee/Tax + 15 bps Slippage | `backtest_engine.py` | Incorporates two-way transaction fees (0.15%), sell tax (0.10%), and adverse slippage. |
| **VN-Index Benchmark** | Dynamic Jensen's Alpha & Beta | `backtest_engine.py` + `data_engine.py` | Calibrates relative performance against VN-Index; computes true systematic beta (e.g., VIC $\beta=1.78$). |
| **Adaptive Regime Partition** | MA200 Slope & Momentum-Vol | `regime_classifier.py` | Evaluates strategy CAGR, MDD, and Sharpe across Full, Uptrend, Downtrend, and Sideways cycles. |
| **Quant Core Strategy** | FA + MoS + Z-Score + TA | `backtest_engine.py` | Tests Piotroski F-Score $\ge 6$, MoS $\ge 15\%$, Z-Score $> 1.8$, RSI $< 70$, and ATR Stop-Loss. |
| **Implementation Shortfall** | Basis Points (bps) Drag | `paper_trading.py` | Audits price degradation between algorithmic decision price and real post-market fill price. |

---

## 4. 🚀 Deployment Architecture (Production on Render.com)

1. **Dual-Process Orchestration (`run_cloud.py`)**:
   - Cloud PaaS services (e.g., Render free tier) allow only one exposed Web service port.
   - `run_cloud.py` starts the `TradingBot` daemon as a background worker thread (`start_bot_thread()`) while simultaneously running `streamlit run app.py` on the HTTP port bound by the container (`$PORT`).
2. **Persistence Resilience**:
   - Cooldown and signal audit states persist primarily in **Supabase PostgreSQL**.
   - If network degradation occurs, `data_engine.py` gracefully falls back to local storage (`data/.signal_cooldown.json`).
3. **Automated CI/CD (`.github/workflows/ci.yml`)**:
   - Lints all Python files using `ruff`.
   - Executes offline test suites (`pytest tests/ -m offline`) on every push to `main` and Pull Request.
