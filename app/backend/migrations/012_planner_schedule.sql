CREATE TABLE IF NOT EXISTS planner_schedule (
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'standard' CHECK (mode IN ('standard', 'intensive')),
    week INTEGER NOT NULL,
    subtema TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, mode, week, subtema)
);
CREATE INDEX IF NOT EXISTS idx_planner_schedule_lookup 
ON planner_schedule(user_id, mode, week, display_order);
