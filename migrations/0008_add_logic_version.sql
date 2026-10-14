-- Migration 0008: Add logic_version column to decision_records and decision_lifecycle_events
-- Implements explicit audit tracking for logic freeze governance (Phase 28 / OOS Governance).

ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS logic_version TEXT;
ALTER TABLE decision_lifecycle_events ADD COLUMN IF NOT EXISTS logic_version TEXT;

CREATE INDEX IF NOT EXISTS idx_decision_records_logic_version ON decision_records(logic_version);
CREATE INDEX IF NOT EXISTS idx_lifecycle_events_logic_version ON decision_lifecycle_events(logic_version);
