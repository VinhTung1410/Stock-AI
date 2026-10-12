-- Migration 0007: Enforce UNIQUE constraint on decision_forward_returns(decision_id)
-- Enables native upsert with ON CONFLICT (decision_id) in PostgreSQL / Supabase.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint WHERE conname = 'uq_decision_forward_returns_decision_id'
  ) THEN
    ALTER TABLE decision_forward_returns
    ADD CONSTRAINT uq_decision_forward_returns_decision_id UNIQUE (decision_id);
  END IF;
END $$;
