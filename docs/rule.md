# 📜 SYSTEM STANDARDS & ENGINEERING SPECIFICATIONS (rule.md)

This document establishes the mandatory architectural rules, data integrity standards, formatting protocols, and algorithmic constraints governing all source code, AI assistant components (Gemini Flash), Discord notification pipelines, and Streamlit user interfaces across the **Stock-AI** platform.

---

## 1. Output Language & Encoding Standard (Strict Vietnamese Localization)

### 1.1. 100% Standard Unicode Vietnamese Requirement
- All end-user facing artifacts — including market analysis reports, executive summaries, stock recommendations, and risk alerts — must be generated in **100% standard Unicode Vietnamese**.
- **STRICT PROHIBITION:** Under no circumstances may raw Chinese / CJK characters (`[\u4e00-\u9fff]`) appear in published outputs (common artifacts from LLM tokenizer bleed: `证券公司`, `股票`, `银行`, `风险`, `变动`...).

### 1.2. Ticker Symbol & Brokerage Nomenclature Standardization
- **SSI Securities Corporation:** Must always render as **`SSI`**, **`Mã SSI`**, or **`Công ty Chứng khoán SSI`** (or `CTCK SSI`).
- **PROHIBITED:** Hybrid strings such as `证券公司 SSI`.
- **Other Securities Firms:** Explicitly write `VND (VNDirect)`, `VCI (Vietcap)`, `HCM (HSC)`, etc.

---

## 2. Two-Tier Anti-Hallucination Defense Architecture

To eliminate CJK character artifacts and tokenizer leakage, the system implements an independent two-layer defense barrier:

```
                  ┌──────────────────────────────────────────────┐
                  │              Input Prompt / Query            │
                  └──────────────────────┬───────────────────────┘
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ TIER 1: SYSTEM LANGUAGE DIRECTIVE (PROMPT-LEVEL INJECTION)                     │
│ • Enforce strict role and language constraints at head and tail of prompt.    │
│ • Restrict persona exclusively to Vietnam Equities Financial Analyst.          │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         ▼
                               [ Google Gemini Flash ]
                                         ▼
┌────────────────────────────────────────────────────────────────────────────────┐
│ TIER 2: DETERMINISTIC CODE SANITIZER (PYTHON RUNTIME SAFETY NET)               │
│ • `sanitize_ai_text()` intercepts text before dispatch.                        │
│ • Translates known CJK financial tokens to standard Vietnamese equivalents.    │
│ • Deterministic Regex strips any remaining CJK Unicode span `[\u4e00-\u9fff]`. │
└────────────────────────────────────────┬───────────────────────────────────────┘
                                         ▼
              ┌──────────────────────────────────────────────────────┐
              │ Clean 100% Vietnamese Output for Discord & Web UI     │
              └──────────────────────────────────────────────────────┘
```

### 2.1. Tier 1: Prompt Constraint Injection (`ai_analyst.py`)
Every query dispatched to the Gemini API is automatically wrapped with `SYSTEM_LANGUAGE_RULE` through the centralized `call_gemini(client, prompt)` handler:

```python
SYSTEM_LANGUAGE_RULE = """
[MANDATORY - ABSOLUTE LANGUAGE RULE]:
- MUST use 100% STANDARD UNICODE VIETNAMESE.
- STRICTLY PROHIBITED from using any Chinese / CJK characters (e.g., 证券公司, 股票, 银行, 风险, 变动...).
- For SSI or other brokers: explicitly write 'Công ty Chứng khoán SSI', 'Chứng khoán SSI', or 'Mã SSI'. NEVER write '证券公司 SSI'.
"""
```

### 2.2. Tier 2: Deterministic Python Sanitizer (`sanitize_ai_text`)
Even if probabilistic LLM sampling exhibits variance, `sanitize_ai_text()` guarantees safety at the Python execution layer:
1. **Financial Token Translation Dictionary:**
   - `证券公司` ➔ `Công ty Chứng khoán` *(Securities Corporation)*
   - `证券` ➔ `Chứng khoán` *(Securities)*
   - `股票` ➔ `Cổ phiếu` *(Stock / Shares)*
   - `银行` ➔ `Ngân hàng` *(Bank)*
   - `变动` ➔ `Biến động` *(Price Fluctuation)*
   - `风险` ➔ `Rủi ro` *(Risk)*
   - `投资` ➔ `Đầu tư` *(Investment)*
   - `买入` ➔ `Mua` *(Buy)*
   - `卖出` ➔ `Bán` *(Sell)*
2. **CJK Regex Elimination Gate:** `re.sub(r'[\u4e00-\u9fff]+', '', text)` removes any remaining glyphs.

---

## 3. Quantamental 2-Pass Pipeline Architecture

To resolve the two primary failure modes of financial AI (**numerical hallucinations** and **cyclical earnings peak traps**), the system enforces the core design philosophy:

> **"Python executes 100% of deterministic arithmetic — the LLM is restricted to qualitative synthesis, market catalyst analysis, and scenario attribution."**

```
                       Stock Analysis Request: {symbol}
                                      │
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ STEP 1: PRE-FLIGHT DATA GATE                     │
             │ • Liquidity Check (ADV20 ≥ 3 - 5 billion VND)    │
             │ • Financial Statement Freshness (Last 2 quarters) │
             └────────────────────────┬─────────────────────────┘
                   [PASS]             │          [FAIL]
                                      │             │
                                      │             ▼
                                      │   "REJECT RECOMMENDATION:
                                      │    INSUFFICIENT DATA QUALITY"
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ STEP 2: DETERMINISTIC PYTHON QUANT ENGINE        │
             │ • Piotroski F-Score (0-9 Scale)                  │
             │ • Altman Z-Score (Safe / Grey / Distress Zones)   │
             │ • ATR(14) Volatility Stop & HOSE Ceiling Limits  │
             │ • Valuation Triangle (Multiples + Historical)    │
             └────────────────────────┬─────────────────────────┘
                                      │ (Feed verified data to Pass 1 Prompt)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ STEP 3: PASS 1 (LLM SCENARIO PROBABILITY)        │
             │ • Evaluates macro catalysts & management outlook │
             │ • Returns JSON: {P_bull, P_base, P_bear}         │
             └────────────────────────┬─────────────────────────┘
                                      │ (Return scenario weights to Python)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ STEP 4: PYTHON DETERMINISTIC HARD GATES          │
             │ • Expected Value: EV = Σ(P_i × Price_i)          │
             │ • Margin of Safety: MoS % = (EV - Price) / Price │
             │ • Risk / Reward Ratio: R = Upside / Downside     │
             │ • Kelly Criterion: f* = p - (1-p) / R            │
             │ • Hard Gates: MoS ≥ 15%, R ≥ 1.5, Kelly > 0      │
             └────────────────────────┬─────────────────────────┘
                                      │ (Pass verified decisions to Pass 2 Prompt)
                                      ▼
             ┌──────────────────────────────────────────────────┐
             │ STEP 5: PASS 2 (LLM INSTITUTIONAL REPORT)        │
             │ • Synthesizes 8 CFA-aligned pillars              │
             │ • Strictly cites Python-computed figures only    │
             │ • Dispatches to Web Dashboard & Discord Alerts   │
             └──────────────────────────────────────────────────┘
```

### 3.1. Mathematical Hard Decision Gates
The pipeline **STRICTLY REJECTS BUY RECOMMENDATIONS** if any of the following constraints are violated:
1. **Margin of Safety (MoS):** Must achieve $\ge 8\%$ for Large Caps or $\ge 15\%$ for Mid/Small Caps. If MoS is negative $\to$ Forced downgrade to `🔴 SELL / REDUCE EXPOSURE`.
2. **Risk / Reward Ratio ($R$):** Must satisfy $R \ge 1.5$ (for short-term swing trading) or $R \ge 2.0$ (for medium-term positioning).
3. **Kelly Criterion ($f^*$):** If $f^* \le 0$, the optimal mathematical capital allocation is zero $\to$ Opening new long positions is prohibited.

---

## 4. Quantitative Integration with 24/7 Trading Bot

For real-time market supervision (`trading_bot.py`):
1. **Dynamic ATR(14) Stop-Loss Execution:**
   - Rather than relying solely on static $-5\%$ or $-7\%$ levels, the bot computes market volatility-adjusted stops:
     $$StopLoss_{ATR} = \max(\text{Entry Price} \times 0.93, \text{Current Price} - 2 \times ATR(14))$$
   - Prevents premature stop-outs during temporary noise while honoring the HOSE statutory $-7\%$ limit.
2. **Pre-Signal Safety Gates:**
   - Evaluates `Data Gate` and `Piotroski F-Score`: If accounting manipulation or severe illiquidity is detected, the buy alert is canceled immediately.

---

## 5. Visual Formatting Standards (Discord & Web UI)

### 5.1. Mandatory Ticker Symbol Bolding
- All stock ticker symbols (e.g., **SSI**, **BSR**, **MSB**, **HPG**, **MWG**, **FPT**, **VHM**) **MUST BE BOLDED** (`**TICKER**`) across all titles, narrative paragraphs, and bullet points.
- Enables rapid mobile scanning for active traders on Discord notifications.

### 5.2. Standardized Action Badges
Every formal outlook or recommendation must include an official visual badge:
- 🟢 **`[BUY / MUA MỚI]`** / 🟢 **`[ACCUMULATE / MUA GOM]`**: Capital confluence + technical breakout confirmed.
- 🔵 **`[HOLD / NẮM GIỮ]`** / 🔵 **`[RIDE PROFIT / GỒNG LÃI]`**: Trading above MA20, strong institutional accumulation.
- 🟡 **`[WATCH / THEO DÕI]`** / 🟡 **`[AWAIT PULLBACK / CHỜ ĐIỀU CHỈNH]`**: Healthy base formation, awaiting confirmation.
- 🟠 **`[TAKE PROFIT / CHỐT LỜI]`** / 🟠 **`[TRIM / HẠ TỶ TRỌNG]`**: Target reached, RSI overbought, taking partial profit.
- 🔴 **`[STOP LOSS / CẮT LỖ]`** / 🔴 **`[EXIT / BÁN DỨT KHOÁT]`**: Stop-loss breached (-5%, -7%, or heavy-volume breakdown).
- ⛔ **`[STAND ASIDE / ĐỨNG NGOÀI]`**: Deceptive positive news with broken technicals — strictly avoid catching falling knives.

### 5.3. Hierarchy & Anti-Numbering Protocol
- **PROHIBITED:** Continuous sequential numbering like `1. Stock A`, `2. Catalyst`, `3. Entry Zone`, `4. Target`, `5. Stop Loss`, `6. Technicals`... which breaks visual hierarchy.
- **MANDATORY TWO-LEVEL INDENTATION:**
  - **Level 1 (Ticker Header):** Bullet `• ` with bold ticker and badge:
    `• Stock **SSI** (Securities) — 🟢 **[BUY / MUA GOM]**`
  - **Level 2 (Attributes):** Two-space indent with hyphen `- `:
    `  - **Catalyst / Xúc tác:** Inflow momentum riding liquidity expansion wave.`  
    `  - **Accumulation Zone / Vùng gom:** 20.1 - 20.5k (Current: **20.3k**)`  
    `  - **Target / Mục tiêu:** 22.33k | **Stop-loss / Dừng lỗ:** 19.55k | **R:R:** 2.7`  
    `  - **Technicals / Kỹ thuật:** Base consolidation above MA20, RSI at 60.2.`  

### 5.4. Bifurcated Trading Styles (T+ Breakout vs. Position Accumulation)
To ensure clarity and prevent mathematical distortion of the Risk/Reward ($R:R$) ratio, signals must explicitly declare one of two operational styles:

1. ⚡ **Style 1: T+ SWING / BREAKOUT SNIPER**
   - **Focus:** Momentum breakouts backed by institutional volume spikes.
   - **Badges:** ⚡ **`[T+ SWING / LƯỚT SÓNG T+]`** or 🚀 **`[NEW BREAKOUT / BREAKOUT MUA MỚI]`**.
   - **Entry Tolerance:** Tight entry band $\le 3$ price ticks (max $\pm 0.3\% - 0.5\%$). Single lump-sum execution. Chasing prices above the ceiling is strictly blocked.
   - **R:R Calculation:** Must use the upper bound of the entry range to reflect worst-case entry risk.

2. 💎 **Style 2: POSITION ACCUMULATION / VALUE MEDIUM-TERM**
   - **Focus:** High-quality fundamental bluechips (**FPT**, **HPG**, **MWG**, **VHM**...).
   - **Badges:** 💎 **`[POSITION ENTRY / GOM HÀNG VỊ THẾ]`** or 🟢 **`[ACCUMULATE / MUA GOM TÍCH LŨY]`**.
   - **Accumulation Zone:** Allowed spread of $1.5\% - 2.5\%$.
   - **Mandatory 3-Step Tranche Execution:**
     - *Tranche 1 (30% Scout):* Entry at upper edge of accumulation band.
     - *Tranche 2 (40% Expansion):* Entry upon pullback test of MA20.
     - *Tranche 3 (30% Completion):* Entry at major support floor.
   - **Target Average Cost:** Mandatory calculation of expected blended cost basis.
   - **R:R Calculation:** Must be anchored to the **Target Average Cost**, preventing artificial inflation of expected returns.

### 5.5. Discord Embed & UI Responsive Constraints
1. **Discord Embed Payload Limits:**
   - Markdown tables (`|---|`) are prohibited in AI-generated message bodies as Discord embeds cannot render them natively on mobile screens.
   - Summaries exceeding Discord's 1024-character field limit are automatically split via `split_ai_summary_into_fields()`.
   - Continued fields must use clean sequential labels like `(Part 2)`, `(Part 3)` rather than redundant chained strings.
2. **Streamlit UI Layout:**
   - Render structured KPI cards with color-coded badges matching status definitions (Emerald Green: Buy, Amber: Watch/Hold, Crimson: Sell/Stop).

---

## 6. Legal Compliance Firewall & Security Integrity

To ensure full compliance with the Vietnamese legal framework and protect user assets:

### 6.1. Vietnamese Securities Law Compliance (Articles 10 & 82)
- All public Discord notifications and private direct messages (DMs) must append the mandatory statutory disclaimer (`SIGNAL_DISCLAIMER`):
  > *"Tuyên bố miễn trừ trách nhiệm: Hệ thống cung cấp thông tin phân tích định lượng và nghiên cứu thị trường, không phải là lời mời chào hay khuyến nghị đầu tư tài chính ủy thác. Nhà đầu tư tự chịu trách nhiệm về quyết định phân bổ vốn theo Điều 10 & 82 Luật Chứng khoán 2019."*
- Prohibits automated execution of real-money broker orders without human-in-the-loop (HITL) authorization.

### 6.2. News Vector Sanitization Against Prompt Injection (`sanitize_news_for_llm`)
- Raw text ingested from CafeF, Google News, or social RSS feeds must never be passed directly into LLM prompts.
- All titles are capped at 120 characters and summaries at 400 characters.
- A deterministic regex blocklist strips prompt injection triggers (e.g., `ignore previous instructions`, `system prompt`, `you are now`, `drop table`, `admin override`).

### 6.3. Daily Pre-ATO Heartbeat
- The background daemon dispatches an automated system heartbeat at **08:30 UTC+7** daily, verifying database connectivity, feed latencies, and alerting operators if market data pipelines are degraded prior to the ATO open.

---

## 7. Quantitative Portfolio Risk Constraints & Allocation Rules

To prevent catastrophic drawdown and fat-tail risk exposure:

### 7.1. Strict Sector Concentration Guard (`check_sector_concentration`)
- **Max Sector Exposure:** No more than **3 active positions** or **$\le 25\%$ total portfolio NAV** may be allocated to any single economic sector (e.g., Banking, Real Estate, Steel, Securities).
- If a proposed trade breaches this limit, the system triggers a hard stop veto: `recommendation_allowed = False`.

### 7.2. Position Sizing via Half-Kelly & Liquidity Tiering
- Full Kelly criterion ($f^*$) is strictly banned to prevent over-allocation. The engine caps position sizing at **Half-Kelly** ($f^* / 2$).
- **ADV20 Liquidity Tiering:** Order size must not exceed $2\%$ of the 20-day Average Daily Volume (ADV20) to prevent market impact.

### 7.3. Risk Parity / Equal Risk Contribution Allocation (`optimize_portfolio_risk_parity`)
- Capital is allocated inversely proportional to asset volatility:
  $$w_i \propto \frac{1}{\sigma_i}$$
- **Single-Stock Ceiling:** Capped at a hard maximum of **$25\%$** of total capital.
- **Budget Redistribution:** Excess capital from capped high-conviction assets is iteratively redistributed across uncapped holdings according to their inverse volatility weight.

---

## 8. Execution Microstructure & Dynamic Slippage Simulation

### 8.1. Dynamic Slippage Bounds (`calculate_dynamic_slippage_bps`)
Backtests and simulations must abandon static slippage assumptions in favor of market-regime-sensitive dynamic slippage ranging from **15 bps to 200 bps**:
- **Baseline Friction:** 15 bps (0.15% fee + 0.10% tax).
- **Ceiling Limit Buy (+6.85% to +7.0%):** $4.0\times$ penalty ($60\text{ bps}$) reflecting queue congestion.
- **Floor Limit Sell (-6.85% to -7.0%):** $5.0\times$ penalty ($75\text{ bps}$) reflecting illiquid bid vacuums.
- **Volume Ratio Penalty:** Multiplier scales up when intraday volume is thin (`vol_ratio < 0.5`).
- **Hard Ceiling:** Strictly capped at $200\text{ bps}$.

### 8.2. Partial Profit Lock & Breakeven Stop Protocol (`evaluate_partial_profit_lock`)
- **Stage 1 (Target 1 Hit at $+12\%$):**
  - Lock in **$50\%$ position profits** immediately.
  - Automatically ratchet the Stop-Loss of the remaining $50\%$ position to **Breakeven $+ 0.3\%$** (covering transaction fees and taxes). The trade is mathematically immune to loss.
- **Stage 2 (Trend Continuation $> +15\%$):**
  - Shift remaining position to an automated **$5\%$ Trailing Stop** anchored to the highest recorded price.

---

## 9. Scientific Model Validation & Overfitting Prevention

### 9.1. Walk-Forward Partitioning & Parameter Freeze
- Full-sample backtesting without out-of-sample partitioning is strictly forbidden.
- The backtest suite must segment history into 3 chronological blocks:
  1. *Training Stage (2018–2020):* Feature extraction.
  2. *Validation Stage (2020–2022):* Hyperparameter selection.
  3. *Out-of-Sample OOS (2022–2024):* Blind execution with parameters locked by **ADR-0001**.

### 9.2. Crisis Stress Matrix Testing (`run_crisis_stress_matrix`)
Every strategy must run through 11 benchmark historical crisis stress windows:
1. *Trade War 2018* (03/2018 – 12/2018)
2. *Trump Tariff Escalation 2019* (05/2019 – 08/2019)
3. *COVID-19 Panic 2020* (01/2020 – 03/2020)
4. *Delta Lockdown 2021* (07/2021 – 08/2021)
5. *Post-COVID Bull Run 2021* (01/2021 – 11/2021)
6. *FLC & Tan Hoang Minh Bond Scandals 2022* (04/2022 – 05/2022)
7. *SBV Rate Hikes 2022* (09/2022 – 10/2022)
8. *Van Thinh Phat Crisis 2022* (10/2022 – 11/2022)
9. *SBV Treasury Bill Absorption 2023* (09/2023 – 10/2023)
10. *DXY Pressure & FX Intervention 2024* (04/2024 – 05/2024)
11. *Liquidity Dry-Up 2024* (07/2024 – 08/2024)

### 9.3. Bootstrap Sharpe Confidence Intervals (`bootstrap_sharpe_ci`)
- Point-estimate Sharpe ratios with small sample sizes ($N < 30$) are invalid for decision-making.
- The engine computes **10,000 bootstrap resamples** to derive:
  - 95% Confidence Interval bounds (`ci_lower`, `ci_upper`);
  - Empirical $p$-value for $H_0: \text{Sharpe} \le 0$;
  - Effective Sample Size (ESS) adjusted for first-order autocorrelation ($\rho_1$).
- If `ci_lower <= 0`, the strategy emits an explicit warning regarding statistical insignificance.

---

## 10. AI Governance, Reliability Calibration & Rate Limiting

### 10.1. Gemini API Rate Limiting Circuit Breaker (`check_and_track_gemini_call`)
- Enforces a 60-second sliding-window tracker with a conservative **12/15 RPM buffer** on Google Gemini API.
- If request count $\ge 12$, subsequent batch calls are deferred with automated cooldown to prevent HTTP 429 quota exhaustion.

### 10.2. Dual-Arm A/B Validation Engine (`compare_quant_vs_ai_arms`)
- All live recommendations and backtest runs must maintain parallel tracking of:
  - **Arm A (`ARM_QUANT_ONLY`):** Pure deterministic rules (F-Score, MoS, Z-Score, TA).
  - **Arm B (`ARM_QUANT_AI`):** Deterministic gates + Gemini qualitative reasoning.
- Classifies empirical AI contribution as `POSITIVE_AI_ALPHA`, `NEUTRAL_REPORTING_ONLY`, or `NEGATIVE_AI_DRAG`.

### 10.3. AI Confidence Calibration & Safety Breaker (`check_ai_calibration`)
- AI confidence scores are binned into 5 probability intervals (`50-60%`, `60-70%`, `70-80%`, `80-90%`, `90-100%`).
- Computes empirical Calibration Gap and Brier Score against realized trade win rates.
- **Safety Circuit Breaker:** If the calibration gap exceeds **$0.15$** or high-confidence buckets yield actual win rates $< 60\%$, the system automatically severs LLM confidence from Kelly sizing, falling back to pure quantitative allocation.

