-- Migration 0009: Raw Input Snapshots and WORM (Append-Only) Protection
-- Implements point-in-time raw data preservation and blocks DELETE/UPDATE on decision tables.

-- 1. Table for Point-in-time Raw Provider Snapshots (Durable Storage)
CREATE TABLE IF NOT EXISTS raw_input_snapshots (
    id BIGSERIAL PRIMARY KEY,
    session_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    raw_bctc JSONB,
    raw_price JSONB,
    raw_consensus JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_snapshots_date_symbol ON raw_input_snapshots(session_date, symbol);
CREATE INDEX IF NOT EXISTS idx_raw_snapshots_decision_id ON raw_input_snapshots(decision_id);

-- 2. WORM (Write Once, Read Many) Trigger to prevent DELETE / UPDATE on audit tables
CREATE OR REPLACE FUNCTION enforce_append_only_audit_log()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'WORM Violation: % operation is prohibited on table % (Append-Only Governance Rule)', TG_OP, TG_TABLE_NAME;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply WORM to decision_records
DROP TRIGGER IF EXISTS trg_worm_decision_records ON decision_records;
CREATE TRIGGER trg_worm_decision_records
BEFORE UPDATE OR DELETE ON decision_records
FOR EACH ROW
EXECUTE FUNCTION enforce_append_only_audit_log();

-- Apply WORM to decision_lifecycle_events
DROP TRIGGER IF EXISTS trg_worm_lifecycle_events ON decision_lifecycle_events;
CREATE TRIGGER trg_worm_lifecycle_events
BEFORE UPDATE OR DELETE ON decision_lifecycle_events
FOR EACH ROW
EXECUTE FUNCTION enforce_append_only_audit_log();

-- Apply WORM to raw_input_snapshots
DROP TRIGGER IF EXISTS trg_worm_raw_snapshots ON raw_input_snapshots;
CREATE TRIGGER trg_worm_raw_snapshots
BEFORE UPDATE OR DELETE ON raw_input_snapshots
FOR EACH ROW
EXECUTE FUNCTION enforce_append_only_audit_log();
