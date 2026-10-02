-- Migration 013: Índices de performance críticos para alternativas e imagens de questões
CREATE TABLE IF NOT EXISTS alternatives (
    id INTEGER PRIMARY KEY,
    question_id INTEGER,
    letter TEXT,
    text TEXT,
    is_correct INTEGER
);

CREATE TABLE IF NOT EXISTS question_images (
    id INTEGER PRIMARY KEY,
    question_id INTEGER,
    file_path TEXT,
    order_index INTEGER
);

CREATE INDEX IF NOT EXISTS idx_alternatives_question_id ON alternatives (question_id);
CREATE INDEX IF NOT EXISTS idx_question_images_question_id ON question_images (question_id);
