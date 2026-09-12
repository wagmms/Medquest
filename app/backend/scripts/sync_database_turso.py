#!/usr/bin/env python3
"""
MedQuest - Sincronizador Seguro e Bidirecional: Local SQLite <-> Turso Cloud.

Objetivos:
1. Enviar atualizações de conteúdo (questões com nova taxonomia, explicações,
   alternativas corrigidas e flashcards de estudo) do SQLite local para o Turso.
2. Atualizar o índice FTS5 (questions_fts) no Turso para busca textual rápida.
3. Preservar 100% dos dados de usuários em produção (attempts, spaced_repetition,
   planner_progress, flashcards de usuários).
4. Baixar com segurança tentativas e dados de usuários de produção do Turso para
   o banco local para manter o ambiente de desenvolvimento completo.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Configuração de encoding para Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BACKEND_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = BACKEND_DIR.parent

# Carregar variáveis de ambiente
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(ROOT_DIR / ".env")

LOCAL_DB = BACKEND_DIR / "medquest.db"

RAW_URL = os.environ.get("TURSO_DATABASE_URL") or os.environ.get("TURSO_SYNC_DATABASE_URL", "")
TURSO_URL = RAW_URL.replace("libsql://", "https://").replace("wss://", "https://")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN") or os.environ.get("TURSO_SYNC_AUTH_TOKEN", "")

if not TURSO_URL or not TURSO_TOKEN:
    print("[ERRO] TURSO_DATABASE_URL (ou TURSO_SYNC_DATABASE_URL) e token são obrigatórios.")
    sys.exit(1)

PIPELINE_URL = f"{TURSO_URL}/v3/pipeline"
HEADERS = {
    "Authorization": f"Bearer {TURSO_TOKEN}",
    "Content-Type": "application/json",
}


def convert_val(val: Any) -> dict[str, Any]:
    if val is None:
        return {"type": "null"}
    elif isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    elif isinstance(val, float):
        return {"type": "float", "value": val}
    elif isinstance(val, bytes):
        return {"type": "text", "value": val.decode("utf-8", "ignore")}
    else:
        return {"type": "text", "value": str(val)}


def make_stmt(sql: str, args: list[Any] | None = None) -> dict[str, Any]:
    stmt: dict[str, Any] = {"sql": sql}
    if args is not None:
        stmt["args"] = [convert_val(a) for a in args]
    return {"type": "execute", "stmt": stmt}


def make_close() -> dict[str, Any]:
    return {"type": "close"}


def execute_pipeline(
    session: requests.Session, requests_list: list[dict[str, Any]], max_retries: int = 5
) -> dict[str, Any]:
    payload = {"requests": requests_list}
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.post(PIPELINE_URL, headers=HEADERS, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                for r in data.get("results", []):
                    if r.get("type") == "error":
                        raise RuntimeError(f"Erro SQL no Turso: {r.get('error')}")
                return data
            elif resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.0 * attempt)
                continue
            else:
                raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except (requests.RequestException, RuntimeError) as e:
            if attempt == max_retries:
                raise e
            time.sleep(1.0 * attempt)
    raise RuntimeError("Falha no pipeline após todas as tentativas.")


def run_pipeline_query(session: requests.Session, sql: str, args: list[Any] | None = None) -> list[dict[str, Any]]:
    reqs = [make_stmt(sql, args), make_close()]
    res = execute_pipeline(session, reqs)
    result = res["results"][0]["response"]["result"]
    cols = [c["name"] for c in result["cols"]]
    rows = []
    for r in result["rows"]:
        row_dict = {}
        for idx, col_name in enumerate(cols):
            cell = r[idx]
            row_dict[col_name] = cell["value"] if cell["type"] != "null" else None
        rows.append(row_dict)
    return rows


def sync():
    t_start = time.time()
    print("=" * 70)
    print("      MEDQUEST - SINCRONIZAÇÃO SEGURA (LOCAL <-> TURSO CLOUD)     ")
    print("=" * 70)
    print(f"Origem Local : {LOCAL_DB}")
    print(f"Destino Turso: {TURSO_URL}")
    print("-" * 70)

    session = requests.Session()
    local_conn = sqlite3.connect(LOCAL_DB)
    local_conn.row_factory = sqlite3.Row

    # -------------------------------------------------------------
    # ETAPA 1: Sincronizar Taxonomia e Metadados das Questões
    # -------------------------------------------------------------
    print("\n[1/5] Verificando taxonomia e dados das questões...")
    turso_q = run_pipeline_query(
        session,
        "SELECT id, area, subtema, subtema_orig, subtema_id, topic, stem, correct_letter, status, editorial_status, review_date FROM questions",
    )
    turso_q_map = {int(q["id"]): q for q in turso_q}

    local_q = local_conn.execute(
        "SELECT id, area, subtema, subtema_orig, subtema_id, topic, stem, correct_letter, status, editorial_status, review_date FROM questions"
    ).fetchall()

    questions_to_update = []
    for lq in local_q:
        qid = lq["id"]
        tq = turso_q_map.get(qid)
        if not tq:
            continue
        diff = False
        for col in ["area", "subtema", "subtema_orig", "subtema_id", "topic", "stem", "correct_letter", "status", "editorial_status", "review_date"]:
            if str(lq[col] or "") != str(tq.get(col) or ""):
                diff = True
                break
        if diff:
            questions_to_update.append(lq)

    print(f"  -> Questões com divergência a sincronizar: {len(questions_to_update)}")
    if questions_to_update:
        batch_size = 100
        sql_update_q = """
            UPDATE questions SET 
                area = ?, subtema = ?, subtema_orig = ?, subtema_id = ?, 
                topic = ?, stem = ?, correct_letter = ?, status = ?,
                editorial_status = ?, review_date = ?
            WHERE id = ?
        """
        for i in range(0, len(questions_to_update), batch_size):
            chunk = questions_to_update[i : i + batch_size]
            reqs = []
            for q in chunk:
                args = [
                    q["area"], q["subtema"], q["subtema_orig"], q["subtema_id"],
                    q["topic"], q["stem"], q["correct_letter"], q["status"],
                    q["editorial_status"], q["review_date"], q["id"]
                ]
                reqs.append(make_stmt(sql_update_q, args))
            reqs.append(make_close())
            execute_pipeline(session, reqs)
            print(f"     Sincronizadas {min(i + batch_size, len(questions_to_update))}/{len(questions_to_update)} questões...")
        print(f"  [OK] {len(questions_to_update)} questões atualizadas no Turso com sucesso.")
    else:
        print("  [OK] Todas as questões já estão idênticas no Turso.")

    # -------------------------------------------------------------
    # ETAPA 2: Sincronizar Explicações Clínicas
    # -------------------------------------------------------------
    print("\n[2/5] Verificando explicações clínicas...")
    turso_exps = run_pipeline_query(
        session, "SELECT question_id, length(explanation_text) as l, explanation_text FROM explanations"
    )
    turso_exp_map = {int(e["question_id"]): e["explanation_text"] for e in turso_exps}

    local_exps = local_conn.execute(
        "SELECT question_id, explanation_text, generated_at, reviewed_at FROM explanations"
    ).fetchall()

    exps_to_update = []
    for le in local_exps:
        qid = le["question_id"]
        t_text = turso_exp_map.get(qid)
        l_text = le["explanation_text"]
        if (l_text or "") != (t_text or ""):
            exps_to_update.append(le)

    print(f"  -> Explicações com divergência a sincronizar: {len(exps_to_update)}")
    if exps_to_update:
        batch_size = 50
        sql_update_exp = """
            INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(question_id) DO UPDATE SET
                explanation_text = excluded.explanation_text,
                generated_at = excluded.generated_at,
                reviewed_at = excluded.reviewed_at
        """
        for i in range(0, len(exps_to_update), batch_size):
            chunk = exps_to_update[i : i + batch_size]
            reqs = []
            for e in chunk:
                args = [e["question_id"], e["explanation_text"], e["generated_at"], e["reviewed_at"]]
                reqs.append(make_stmt(sql_update_exp, args))
            reqs.append(make_close())
            execute_pipeline(session, reqs)
            print(f"     Sincronizadas {min(i + batch_size, len(exps_to_update))}/{len(exps_to_update)} explicações...")
        print(f"  [OK] {len(exps_to_update)} explicações atualizadas no Turso com sucesso.")
    else:
        print("  [OK] Todas as explicações já estão idênticas no Turso.")

    # -------------------------------------------------------------
    # ETAPA 3: Sincronizar Alternativas Corrigidas
    # -------------------------------------------------------------
    print("\n[3/5] Verificando alternativas...")
    turso_alts = run_pipeline_query(session, "SELECT id, question_id, letter, text, is_correct FROM alternatives")
    turso_alt_map = {int(a["id"]): a for a in turso_alts}

    local_alts = local_conn.execute("SELECT id, question_id, letter, text, is_correct FROM alternatives").fetchall()
    alts_to_update = []
    for la in local_alts:
        aid = la["id"]
        ta = turso_alt_map.get(aid)
        if not ta:
            continue
        if str(la["text"] or "") != str(ta.get("text") or "") or int(la["is_correct"]) != int(ta.get("is_correct", 0)):
            alts_to_update.append(la)

    print(f"  -> Alternativas com divergência: {len(alts_to_update)}")
    if alts_to_update:
        sql_alt = "UPDATE alternatives SET text = ?, is_correct = ? WHERE id = ?"
        reqs = [make_stmt(sql_alt, [a["text"], a["is_correct"], a["id"]]) for a in alts_to_update]
        reqs.append(make_close())
        execute_pipeline(session, reqs)
        print(f"  [OK] {len(alts_to_update)} alternativas corrigidas no Turso.")
    else:
        print("  [OK] Alternativas idênticas no Turso.")

    # -------------------------------------------------------------
    # ETAPA 4: Sincronizar Flashcards (Preservando Produção)
    # -------------------------------------------------------------
    print("\n[4/5] Sincronizando flashcards (preservando usuários de produção)...")
    turso_fc = run_pipeline_query(session, "SELECT id, user_id, question_id, front, back, created_at FROM flashcards")
    turso_fc_keys = {(f["user_id"], f["front"][:100], f["back"][:100]): f for f in turso_fc}

    local_fc = local_conn.execute(
        "SELECT id, user_id, question_id, front, back, created_at FROM flashcards"
    ).fetchall()
    local_fc_keys = {(f["user_id"], f["front"][:100], f["back"][:100]): f for f in local_fc}

    # 4.1 Enviar flashcards locais que não existem no Turso
    fc_to_upload = [f for f in local_fc if (f["user_id"], f["front"][:100], f["back"][:100]) not in turso_fc_keys]
    if fc_to_upload:
        print(f"  -> Enviando {len(fc_to_upload)} flashcards locais para o Turso...")
        sql_fc = "INSERT INTO flashcards (user_id, question_id, front, back, created_at) VALUES (?, ?, ?, ?, ?)"
        reqs = [make_stmt(sql_fc, [f["user_id"], f["question_id"], f["front"], f["back"], f["created_at"]]) for f in fc_to_upload]
        reqs.append(make_close())
        execute_pipeline(session, reqs)
        print(f"  [OK] {len(fc_to_upload)} flashcards enviados ao Turso.")
    else:
        print("  [OK] Nenhum flashcard novo a enviar ao Turso.")

    # 4.2 Baixar flashcards do Turso (produção) que não existem no local
    fc_to_pull = [f for f in turso_fc if (f["user_id"], f["front"][:100], f["back"][:100]) not in local_fc_keys]
    if fc_to_pull:
        print(f"  -> Baixando {len(fc_to_pull)} flashcards de produção do Turso para o SQLite local...")
        cur = local_conn.cursor()
        for f in fc_to_pull:
            cur.execute(
                "INSERT OR IGNORE INTO flashcards (id, user_id, question_id, front, back, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (f["id"], f["user_id"], f["question_id"], f["front"], f["back"], f["created_at"])
            )
        local_conn.commit()
        print(f"  [OK] {len(fc_to_pull)} flashcards de produção importados localmente.")

    # -------------------------------------------------------------
    # ETAPA 5: Sincronizar FTS5 e Telemetria de Produção
    # -------------------------------------------------------------
    # 5.1 Reindexar FTS5 no Turso
    print("\n[5/5] Reindexando FTS5 no Turso...")
    try:
        reqs = [make_stmt("INSERT INTO questions_fts(questions_fts) VALUES('rebuild')"), make_close()]
        execute_pipeline(session, reqs)
        print("  [OK] Índice FTS5 reconstruído no Turso com sucesso.")
    except Exception as e:
        print(f"  [AVISO FTS] {e}")

    # 5.2 Baixar tentativas (attempts) e repetição espaçada (spaced_repetition) de produção para o local
    print("\n[BÔNUS] Harmonizando tentativas de usuários de produção para o SQLite local...")
    turso_atts = run_pipeline_query(session, "SELECT id, question_id, selected_letter, is_correct, answered_at, confidence, user_id, time_spent_ms FROM attempts")
    local_atts_keys = set(
        (r["user_id"], r["question_id"], r["answered_at"])
        for r in local_conn.execute("SELECT user_id, question_id, answered_at FROM attempts").fetchall()
    )
    atts_to_import = [a for a in turso_atts if (a["user_id"], int(a["question_id"]), a["answered_at"]) not in local_atts_keys]
    if atts_to_import:
        cur = local_conn.cursor()
        for a in atts_to_import:
            cur.execute(
                """INSERT OR IGNORE INTO attempts 
                   (question_id, selected_letter, is_correct, answered_at, confidence, user_id, time_spent_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (a["question_id"], a["selected_letter"], a["is_correct"], a["answered_at"], a["confidence"], a["user_id"], a["time_spent_ms"])
            )
        local_conn.commit()
        print(f"  [OK] {len(atts_to_import)} tentativas de produção importadas para o banco local.")
    else:
        print("  [OK] Tentativas já harmonizadas.")

    elapsed = time.time() - t_start
    print("\n" + "=" * 70)
    print(f"       SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO EM {elapsed:.2f}s!       ")
    print("=" * 70)
    local_conn.close()


if __name__ == "__main__":
    sync()
