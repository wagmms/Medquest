CREATE TABLE IF NOT EXISTS osce_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    area TEXT NOT NULL,
    subtema TEXT NOT NULL,
    institution TEXT NOT NULL,
    year INTEGER NOT NULL,
    difficulty TEXT NOT NULL DEFAULT 'hard',
    duration_seconds INTEGER NOT NULL DEFAULT 480,
    scenario_door_markdown TEXT NOT NULL,
    patient_persona_json TEXT NOT NULL,
    physical_exam_json TEXT NOT NULL,
    lab_imaging_json TEXT NOT NULL,
    checklist_barema_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS osce_sessions (
    id TEXT PRIMARY KEY,
    station_id INTEGER NOT NULL REFERENCES osce_stations(id),
    user_id TEXT NOT NULL,
    circuit_session_id TEXT,
    status TEXT NOT NULL DEFAULT 'in_progress',
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    elapsed_seconds INTEGER DEFAULT 0,
    transcript_json TEXT NOT NULL DEFAULT '[]',
    actions_taken_json TEXT NOT NULL DEFAULT '[]',
    final_score REAL DEFAULT 0.0,
    checklist_evaluation_json TEXT DEFAULT '{}',
    preceptor_feedback_json TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_osce_stations_area_inst ON osce_stations(area, institution);
CREATE INDEX IF NOT EXISTS idx_osce_sessions_user ON osce_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_osce_sessions_station ON osce_sessions(station_id);
