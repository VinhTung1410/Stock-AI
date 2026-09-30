-- Migration 0004: Add analyst context tracking fields to decision_records (Phase 8 / v6.3)
-- Enables auditing the impact of external institutional analyst reports (TCBS) on AI decisions.

ALTER TABLE decision_records
  ADD COLUMN IF NOT EXISTS analyst_context_used  BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS regime_conflict        BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS context_source_file    TEXT,
  ADD COLUMN IF NOT EXISTS context_date           DATE;

-- Indices for rapid querying and audit slicing
CREATE INDEX IF NOT EXISTS idx_decision_records_context_used ON decision_records(analyst_context_used);
CREATE INDEX IF NOT EXISTS idx_decision_records_regime_conflict ON decision_records(regime_conflict);
CREATE INDEX IF NOT EXISTS idx_decision_records_context_date ON decision_records(context_date);
