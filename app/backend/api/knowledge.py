"""Módulo de Data Store e Recuperação Médica (Grounding RAG).

Gerencia a base de conhecimento médico indexada (Fichas Resumo, Revisões Rápidas e Diretrizes)
utilizando SQLite FTS5 (BM25) de alta performance e latência ultrabaixa (< 5ms).
"""

import logging
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_KNOWLEDGE_DB = os.environ.get(
    "MEDKNOWLEDGE_DB",
    str(BACKEND_DIR / "medknowledge.db")
)


def get_knowledge_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Retorna conexão SQLite configurada para o Data Store de conhecimento."""
    path = db_path or DEFAULT_KNOWLEDGE_DB
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_knowledge_schema(conn: sqlite3.Connection) -> None:
    """Inicializa as tabelas de chunks e o índice FTS5 para busca textual ultra-rápida."""
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_file TEXT NOT NULL,
                source_type TEXT NOT NULL,
                specialty TEXT NOT NULL DEFAULT '',
                topic TEXT NOT NULL DEFAULT '',
                subtopic TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                word_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_kc_specialty_topic
            ON knowledge_chunks(specialty, topic)
        """)

        # Tabela virtual FTS5 para busca em linguagem natural e termos clínicos
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                title,
                content,
                specialty UNINDEXED,
                topic UNINDEXED,
                subtopic UNINDEXED,
                content='knowledge_chunks',
                content_rowid='id',
                tokenize='unicode61 remove_diacritics 2'
            )
        """)

        # Triggers de sincronização automática entre a tabela física e o índice FTS5
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_kc_ai AFTER INSERT ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(rowid, title, content, specialty, topic, subtopic)
                VALUES (new.id, new.title, new.content, new.specialty, new.topic, new.subtopic);
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_kc_ad AFTER DELETE ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, specialty, topic, subtopic)
                VALUES('delete', old.id, old.title, old.content, old.specialty, old.topic, old.subtopic);
            END;
        """)
        conn.execute("""
            CREATE TRIGGER IF NOT EXISTS trg_kc_au AFTER UPDATE ON knowledge_chunks BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, title, content, specialty, topic, subtopic)
                VALUES('delete', old.id, old.title, old.content, old.specialty, old.topic, old.subtopic);
                INSERT INTO knowledge_fts(rowid, title, content, specialty, topic, subtopic)
                VALUES (new.id, new.title, new.content, new.specialty, new.topic, new.subtopic);
            END;
        """)


def _sanitize_fts_query(raw_query: str) -> str:
    """Sanitiza strings de busca para operadores válidos do SQLite FTS5."""
    cleaned = re.sub(r'[^\w\s]', ' ', raw_query, flags=re.UNICODE)
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) >= 3]
    if not tokens:
        return ""
    # Junta com OR para cobrir combinações de termos médicos relevantes
    # Prioriza os primeiros 8 termos para não sobrecarregar a árvore de busca
    return " OR ".join(tokens[:8])


def retrieve_medical_context(
    area: str = "",
    subtema: str = "",
    stem: str = "",
    user_question: str = "",
    top_k: int = 3,
    db_path: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Recupera os blocos de conhecimento médico mais relevantes com base na área, subtema e termos da dúvida.
    Retorna lista de dicionários contendo título, conteúdo e metadados das fontes.
    """
    db_file = db_path or DEFAULT_KNOWLEDGE_DB
    if not os.path.exists(db_file):
        logger.debug("[Grounding] Arquivo do knowledge store não existe ainda: %s", db_file)
        return []

    # Combina a dúvida do usuário com trechos do enunciado e subtema para extrair termos-chave
    search_seed = f"{user_question} {subtema} {stem[:200]}".strip()
    fts_query = _sanitize_fts_query(search_seed)

    if not fts_query:
        return []

    try:
        conn = get_knowledge_connection(db_file)
        results = []

        # Tentativa 1: Busca FTS5 filtrando por especialidade/área quando informada
        norm_area = area.strip()
        norm_subtema = subtema.strip()

        with conn:
            cursor = conn.cursor()
            if norm_area:
                cursor.execute(
                    """
                    SELECT kc.id, kc.source_file, kc.source_type, kc.specialty,
                           kc.topic, kc.subtopic, kc.title, kc.content, fts.rank
                    FROM knowledge_fts fts
                    JOIN knowledge_chunks kc ON fts.rowid = kc.id
                    WHERE knowledge_fts MATCH ?
                      AND (kc.specialty LIKE ? OR kc.topic LIKE ? OR kc.subtopic LIKE ?)
                    ORDER BY fts.rank
                    LIMIT ?
                    """,
                    (fts_query, f"%{norm_area}%", f"%{norm_area}%", f"%{norm_subtema}%", top_k)
                )
                results = [dict(row) for row in cursor.fetchall()]

            # Tentativa 2: Fallback para busca global por ranking BM25 se filtragem for muito restritiva
            if not results:
                cursor.execute(
                    """
                    SELECT kc.id, kc.source_file, kc.source_type, kc.specialty,
                           kc.topic, kc.subtopic, kc.title, kc.content, fts.rank
                    FROM knowledge_fts fts
                    JOIN knowledge_chunks kc ON fts.rowid = kc.id
                    WHERE knowledge_fts MATCH ?
                    ORDER BY fts.rank
                    LIMIT ?
                    """,
                    (fts_query, top_k)
                )
                results = [dict(row) for row in cursor.fetchall()]

        return results

    except Exception as exc:
        logger.warning("[Grounding] Erro na recuperação de contexto médico: %s", exc)
        return []


def format_grounding_block(chunks: List[Dict[str, Any]]) -> str:
    """Formata os chunks recuperados em um bloco Markdown claro para ancorar o prompt da IA."""
    if not chunks:
        return ""

    blocks = []
    for c in chunks:
        src = c.get("source_file", "Diretriz Médica")
        topic = c.get("topic") or c.get("specialty") or "Clínica"
        sub = c.get("subtopic") or c.get("title") or ""
        header = f"[Fonte: {src} - {topic}"
        if sub and sub != topic:
            header += f" | {sub}"
        header += "]"

        content = c.get("content", "").strip()
        blocks.append(f"{header}\n{content}")

    joined = "\n\n---\n\n".join(blocks)
    return f"""### CONTEXTO CLÍNICO OFICIAL ANCORADO (DATA STORE):
As informações abaixo foram extraídas diretamente das fontes médicas e diretrizes de estudo oficiais.
Priorize estritamente estas referências para fundamentar a sua resposta e utilize citações explícitas [Fonte: ...].

{joined}
"""
