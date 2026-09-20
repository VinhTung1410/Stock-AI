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
   - `证券公司` ➔ `Công ty Chứng khoán`
   - `证券` ➔ `Chứng khoán`
   - `股票` ➔ `Cổ phiếu`
   - `银行` ➔ `Ngân hàng`
   - `变动` ➔ `Biến động`
   - `风险` ➔ `Rủi ro`
   - `投资` ➔ `Đầu tư`
   - `买入` ➔ `Mua`
   - `卖出` ➔ `Bán`
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
- 🟢 **`[MUA MỚI]`** / 🟢 **`[MUA GOM]`**: Capital confluence + technical breakout confirmed.
- 🔵 **`[NẮM GIỮ]`** / 🔵 **`[GỒNG LÃI]`**: Trading above MA20, strong institutional accumulation.
- 🟡 **`[THEO DÕI]`** / 🟡 **`[CHỜ ĐIỀU CHỈNH]`**: Healthy base formation, awaiting confirmation.
- 🟠 **`[CHỐT LỜI]`** / 🟠 **`[HẠ TỶ TRỌNG]`**: Target reached, RSI overbought, taking partial profit.
- 🔴 **`[CẮT LỖ]`** / 🔴 **`[BÁN DỨT KHOÁT]`**: Stop-loss breached (-5%, -7%, or heavy-volume breakdown).
- ⛔ **`[ĐỨNG NGOÀI / TRÁNH BẪY]`**: Deceptive positive news with broken technicals — strictly avoid catching falling knives.

### 5.3. Hierarchy & Anti-Numbering Protocol
- **PROHIBITED:** Continuous sequential numbering like `1. Stock A`, `2. Catalyst`, `3. Entry Zone`, `4. Target`, `5. Stop Loss`, `6. Technicals`... which breaks visual hierarchy.
- **MANDATORY TWO-LEVEL INDENTATION:**
  - **Level 1 (Ticker Header):** Bullet `• ` with bold ticker and badge:
    `• Cổ phiếu **SSI** (Chứng khoán) — 🟢 **[MUA GOM]**`
  - **Level 2 (Attributes):** Two-space indent with hyphen `- `:
    `  - **Xúc tác:** Thu hút dòng tiền đón sóng thanh khoản.`  
    `  - **Vùng gom:** 20.1 - 20.5k (Hiện tại: **20.3k**)`  
    `  - **Mục tiêu:** 22.33k | **Dừng lỗ:** 19.55k | **R:R:** 2.7`  
    `  - **Kỹ thuật:** Vận động tích lũy trên MA20, RSI đạt 60.2.`  

### 5.4. Bifurcated Trading Styles (T+ Breakout vs. Position Accumulation)
To ensure clarity and prevent mathematical distortion of the Risk/Reward ($R:R$) ratio, signals must explicitly declare one of two operational styles:

1. ⚡ **Style 1: T+ SWING / BREAKOUT SNIPER**
   - **Focus:** Momentum breakouts backed by institutional volume spikes.
   - **Badges:** ⚡ **`[LƯỚT SÓNG T+]`** or 🚀 **`[BREAKOUT MUA MỚI]`**.
   - **Entry Tolerance:** Tight entry band $\le 3$ price ticks (max $\pm 0.3\% - 0.5\%$). Single lump-sum execution. Chasing prices above the ceiling is strictly blocked.
   - **R:R Calculation:** Must use the upper bound of the entry range to reflect worst-case entry risk.

2. 💎 **Style 2: POSITION ACCUMULATION / VALUE MEDIUM-TERM**
   - **Focus:** High-quality fundamental bluechips (**FPT**, **HPG**, **MWG**, **VHM**...).
   - **Badges:** 💎 **`[GOM HÀNG VỊ THẾ]`** or 🟢 **`[MUA GOM TÍCH LŨY]`**.
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
