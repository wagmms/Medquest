CREATE TABLE IF NOT EXISTS theme_progress (
    user_id TEXT NOT NULL,
    subtema TEXT NOT NULL,
    theory_completed INTEGER NOT NULL DEFAULT 0 CHECK (theory_completed IN (0, 1)),
    study_path TEXT NOT NULL DEFAULT 'essential' CHECK (study_path IN ('essential', 'complete')),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, subtema)
);
