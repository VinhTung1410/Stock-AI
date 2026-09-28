-- Migration 0003: Create decision_records & decision_forward_returns for v6.1 Institutional Evidence Framework
-- Implements append-only decision audit trail (BUY, WATCH, REJECT) with immutable trigger and forward returns.

-- 1. Extend signal_lifecycle with T+3, T+10, decision_id, and T+2 lock flag
ALTER TABLE signal_lifecycle ADD COLUMN IF NOT EXISTS t3_pct NUMERIC(7,3);
ALTER TABLE signal_lifecycle ADD COLUMN IF NOT EXISTS t10_pct NUMERIC(7,3);
ALTER TABLE signal_lifecycle ADD COLUMN IF NOT EXISTS decision_id TEXT;
ALTER TABLE signal_lifecycle ADD COLUMN IF NOT EXISTS t_plus_2_locked BOOLEAN DEFAULT FALSE;

-- 2. Create decision_records table (Universe Panel Log)
CREATE TABLE IF NOT EXISTS decision_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id TEXT UNIQUE NOT NULL,      -- e.g. "DEC_HPG_20260928_143000"
  symbol TEXT NOT NULL,
  decision_time TIMESTAMPTZ DEFAULT NOW(),
  session TEXT DEFAULT 'NOON',           -- ATO / NOON / ATC
  decision TEXT NOT NULL,                -- BUY / WATCH / REJECT
  primary_rejection_gate TEXT,          -- DATA_GATE / MACRO_REGIME / ANTI_CHASING / LIQUIDITY / VALUATION / AI_VETO / COOLDOWN
  rejection_reasons JSONB DEFAULT '[]'::jsonb,

  -- 4 Data Tiers
  facts JSONB NOT NULL DEFAULT '{}'::jsonb,        -- Price, asof, fin_period, adv20_shares
  inferences JSONB NOT NULL DEFAULT '{}'::jsonb,   -- MoS, mos_is_informative, F-Score, Z-Score, RSI, conviction
  opinions JSONB NOT NULL DEFAULT '{}'::jsonb,     -- LLM recommendation, prompt_hash, model_id, temperature
  counterfactual JSONB NOT NULL DEFAULT '{}'::jsonb, -- Gate ROI tracking metrics

  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_records_symbol ON decision_records(symbol);
CREATE INDEX IF NOT EXISTS idx_decision_records_decision ON decision_records(decision);
CREATE INDEX IF NOT EXISTS idx_decision_records_time ON decision_records(decision_time);
CREATE INDEX IF NOT EXISTS idx_decision_records_gate ON decision_records(primary_rejection_gate);

-- 3. Create decision_forward_returns table
CREATE TABLE IF NOT EXISTS decision_forward_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  decision_id TEXT NOT NULL REFERENCES decision_records(decision_id) ON DELETE RESTRICT,
  symbol TEXT NOT NULL,
  snapshot_price NUMERIC(10,2) NOT NULL,
  t1_return_pct NUMERIC(7,3),
  t3_return_pct NUMERIC(7,3),
  t5_return_pct NUMERIC(7,3),
  t10_return_pct NUMERIC(7,3),
  t20_return_pct NUMERIC(7,3),
  vnindex_t5_pct NUMERIC(7,3),
  vnindex_t20_pct NUMERIC(7,3),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_forward_returns_decision_id ON decision_forward_returns(decision_id);
CREATE INDEX IF NOT EXISTS idx_decision_forward_returns_symbol ON decision_forward_returns(symbol);

-- 4. Immutable Trigger: Forbid UPDATE and DELETE on decision_records
CREATE OR REPLACE FUNCTION forbid_decision_mutation()
RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'decision_records is an immutable audit table. UPDATE and DELETE operations are forbidden.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_immutable_decision_records ON decision_records;
CREATE TRIGGER trg_immutable_decision_records
BEFORE UPDATE OR DELETE ON decision_records
FOR EACH ROW
EXECUTE FUNCTION forbid_decision_mutation();
