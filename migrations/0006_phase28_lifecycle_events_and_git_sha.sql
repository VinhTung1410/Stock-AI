-- Migration 0006: Decision Lifecycle Events and Git SHA Tracking (Phase 28 / TASK-0085)
-- Establishes immutable event sourcing for trading signals and git_sha provenance tracking.

-- 1. Create decision_lifecycle_events table
CREATE TABLE IF NOT EXISTS decision_lifecycle_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id TEXT UNIQUE NOT NULL,
  correlation_id TEXT NOT NULL,
  symbol TEXT NOT NULL,
  event_type TEXT NOT NULL,
  event_data JSONB DEFAULT '{}'::jsonb,
  market_regime TEXT DEFAULT 'UNKNOWN',
  model_version TEXT DEFAULT 'v15.0_phase28',
  git_sha TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_lifecycle_events_correlation ON decision_lifecycle_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_lifecycle_events_symbol ON decision_lifecycle_events(symbol);
CREATE INDEX IF NOT EXISTS idx_lifecycle_events_type ON decision_lifecycle_events(event_type);
CREATE INDEX IF NOT EXISTS idx_lifecycle_events_created ON decision_lifecycle_events(created_at);

-- 2. Add git_sha to decision_records to differentiate pre- and post-fix runs
ALTER TABLE decision_records ADD COLUMN IF NOT EXISTS git_sha TEXT;
