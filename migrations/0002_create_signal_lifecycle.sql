-- Migration 0002: Create signal_lifecycle table for v5.1 Institutional Evidence Framework
-- Immutable quant & AI snapshot at signal time, separate initial_stop_price for exact R-Multiple.

CREATE TABLE IF NOT EXISTS signal_lifecycle (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_id TEXT UNIQUE NOT NULL,  -- e.g. "FPT_20260926_143022"
  symbol TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),

  -- Quant inputs (đóng băng khi phát tín hiệu)
  entry_price NUMERIC(10,2),
  entry_regime TEXT,                  -- UPTREND / SIDEWAYS / DOWNTREND
  entry_sector TEXT,
  f_score INT,
  z_score NUMERIC(6,3),
  mos_pct NUMERIC(6,2),
  kelly_f NUMERIC(6,4),
  rsi14 NUMERIC(5,1),
  conviction_score NUMERIC(5,1),
  adv20_billion NUMERIC(8,2),

  -- AI metadata (đóng băng khi phát tín hiệu)
  ai_confidence NUMERIC(5,1),
  ai_recommendation TEXT,
  prompt_version TEXT,               -- e.g. "quant_2pass_v3.2"
  model_version TEXT,                -- e.g. "gemini-2.5-flash"

  -- Position & Risk boundaries
  initial_stop_price NUMERIC(10,2),  -- CỐ ĐỊNH: Dùng để tính R-Multiple chuẩn xác
  stop_loss_price NUMERIC(10,2),     -- ĐỘNG: Có thể điều chỉnh theo trailing stop
  target_price NUMERIC(10,2),

  -- Exit & Realized results
  exit_timestamp TIMESTAMPTZ,
  exit_price NUMERIC(10,2),
  exit_reason TEXT,                  -- STOP / TARGET / TRAILING / MANUAL / REGIME
  pnl_pct NUMERIC(7,3),
  r_multiple NUMERIC(6,3),          -- pnl / initial_risk

  -- Path metrics (cron T+1, T+5, T+20)
  mfe_pct NUMERIC(7,3),
  mae_pct NUMERIC(7,3),
  t1_pct NUMERIC(7,3),
  t5_pct NUMERIC(7,3),
  t20_pct NUMERIC(7,3),

  -- Benchmark comparisons
  vnindex_pct_same_period NUMERIC(7,3),
  vn30_pct_same_period NUMERIC(7,3),

  -- Experiment arm & Lifecycle status
  arm TEXT DEFAULT 'QUANT_AI',        -- QUANT_ONLY / QUANT_AI
  status TEXT DEFAULT 'OPEN'          -- OPEN / CLOSED / CANCELLED
);

CREATE INDEX IF NOT EXISTS idx_signal_lifecycle_symbol ON signal_lifecycle(symbol);
CREATE INDEX IF NOT EXISTS idx_signal_lifecycle_status ON signal_lifecycle(status);
CREATE INDEX IF NOT EXISTS idx_signal_lifecycle_created_at ON signal_lifecycle(created_at);
