#!/usr/bin/env python3
"""
MedQuest - Sincronizador Unificado de Banco de Dados (SQLite Local -> Turso Cloud Online)
Sincroniza tabelas críticas (questions, alternatives, explanations) de forma incremental,
rápida e segura através da API HTTP Pipeline v2 do Turso.
"""

import os
import sys
import json
import time
import sqlite3
import urllib.request
import urllib.error

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DB_PATH = os.path.join(ROOT_DIR, "app", "backend", "medquest.db")
ENV_PATHS = [
    os.path.join(ROOT_DIR, ".env"),
    os.path.join(ROOT_DIR, "app", "backend", ".env")
]


def load_env():
    for env_path in ENV_PATHS:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def get_turso_config():
    load_env()
    raw_url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not raw_url or not token:
        return None, None
    url = raw_url.replace("libsql://", "https://").replace("wss://", "https://") + "/v2/pipeline"
    return url, token


def execute_turso_pipeline(url: str, token: str, requests_list: list, timeout: int = 60, retries: int = 4) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"requests": requests_list}).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                if not isinstance(resp_data, dict):
                    raise RuntimeError("Resposta do Turso Pipeline não é um objeto JSON válido.")
                if "error" in resp_data:
                    raise RuntimeError(f"Erro global no Turso Pipeline: {resp_data['error']}")
                results = resp_data.get("results")
                if not isinstance(results, list):
                    raise RuntimeError("Campo 'results' ausente ou inválido na resposta do Turso Pipeline.")
                if requests_list and len(results) != len(requests_list):
                    raise RuntimeError(f"Resposta incompleta do Turso Pipeline: esperados {len(requests_list)} resultados, mas recebidos {len(results)}.")
                for idx, r in enumerate(results):
                    if not isinstance(r, dict) or not r:
                        raise RuntimeError(f"Resultado {idx+1}/{len(results)} da resposta do Turso está vazio ou não é um objeto válido.")
                    if r.get("type") == "error" or "error" in r:
                        err_detail = r.get("error", "Erro SQL desconhecido")
                        raise RuntimeError(f"Erro em statement SQL {idx+1}/{len(results)} retornado pelo Turso: {err_detail}")
                    tem_confirmacao = (r.get("type") in ("ok", "execute")) or ("response" in r and isinstance(r["response"], dict))
                    if not tem_confirmacao:
                        raise RuntimeError(f"Resultado {idx+1}/{len(results)} do Turso não contém confirmação válida de sucesso: {r}")
                return resp_data
        except Exception as e:
            last_err = e
            if attempt < retries and not isinstance(e, RuntimeError):
                time.sleep(attempt * 2)
            else:
                raise last_err


def sync_database(verbose: bool = True) -> bool:
    start_time = time.time()
    url, token = get_turso_config()

    if not url or not token:
        print("  [AVISO] TURSO_DATABASE_URL ou TURSO_AUTH_TOKEN não encontrados no .env.")
        print("          A sincronização com o banco online foi ignorada.")
        return False

    if not os.path.exists(DB_PATH):
        print(f"  [ERRO] Banco local SQLite não encontrado em: {DB_PATH}")
        return False

    if verbose:
        print("  [i] Conectando ao banco local SQLite e ao Turso Cloud...")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 0. Assegurar índices críticos de alta performance no Turso Cloud
    try:
        execute_turso_pipeline(url, token, [
            {"type": "execute", "stmt": {"sql": "CREATE INDEX IF NOT EXISTS idx_alternatives_question_id ON alternatives (question_id)"}},
            {"type": "execute", "stmt": {"sql": "CREATE INDEX IF NOT EXISTS idx_question_images_question_id ON question_images (question_id)"}},
        ], timeout=30)
    except Exception:
        pass

    # 1. Obter contagens, IDs remotos e sincronizar tabela de exclusões (tombstones)
    check_reqs = [
        {"type": "execute", "stmt": {"sql": "CREATE TABLE IF NOT EXISTS deleted_questions (question_id INTEGER PRIMARY KEY, deleted_at TEXT, deleted_by TEXT)"}},
        {"type": "execute", "stmt": {"sql": "SELECT question_id FROM deleted_questions"}},
        {"type": "execute", "stmt": {"sql": "SELECT id FROM questions"}},
        {"type": "execute", "stmt": {"sql": "SELECT id FROM alternatives"}},
        {"type": "execute", "stmt": {"sql": "SELECT question_id, length(explanation_text) FROM explanations WHERE explanation_text IS NOT NULL"}},
        {"type": "execute", "stmt": {"sql": "SELECT id FROM question_images"}},
    ]

    try:
        remote_data = execute_turso_pipeline(url, token, check_reqs, timeout=60)
        res_del = remote_data["results"][1]["response"]["result"]["rows"]
        res_q = remote_data["results"][2]["response"]["result"]["rows"]
        res_a = remote_data["results"][3]["response"]["result"]["rows"]
        res_e = remote_data["results"][4]["response"]["result"]["rows"]
        res_i = remote_data["results"][5]["response"]["result"]["rows"]

        remote_deleted_ids = {int(r[0]["value"]) for r in res_del if r}
        remote_q_ids = {int(r[0]["value"]) for r in res_q if r}
        remote_a_ids = {int(r[0]["value"]) for r in res_a if r}
        remote_e_map = {int(r[0]["value"]): int(r[1]["value"]) for r in res_e if r and r[1]["value"] is not None}
        remote_i_ids = {int(r[0]["value"]) for r in res_i if r}
    except Exception as e:
        print(f"  [ERRO] Falha ao consultar estado do banco remoto Turso: {e}")
        return False

    # 1b. Sincronizar exclusões bidirecionais (evita reenvio de questões deletadas online)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS deleted_questions (
            question_id INTEGER PRIMARY KEY,
            deleted_at TEXT,
            deleted_by TEXT
        )
    """)
    local_deleted_ids = {r[0] for r in cur.execute("SELECT question_id FROM deleted_questions").fetchall()}

    # Aplicar exclusões remotas no banco local
    to_delete_locally = [
        qid for qid in remote_deleted_ids
        if qid not in local_deleted_ids or cur.execute("SELECT 1 FROM questions WHERE id = ?", (qid,)).fetchone()
    ]
    if to_delete_locally:
        if verbose:
            print(f"  [-] Sincronizando {len(to_delete_locally)} exclusões realizadas online para o banco local SQLite...")
        for qid in to_delete_locally:
            cur.execute("DELETE FROM alternatives WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM explanations WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM question_images WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM attempts WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM favorites WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM spaced_repetition WHERE question_id = ?", (qid,))
            cur.execute("UPDATE flashcards SET question_id = NULL WHERE question_id = ?", (qid,))
            cur.execute("DELETE FROM questions WHERE id = ?", (qid,))
            cur.execute(
                "INSERT OR REPLACE INTO deleted_questions (question_id, deleted_at, deleted_by) VALUES (?, datetime('now'), 'turso_sync')",
                (qid,)
            )
        conn.commit()
        local_deleted_ids.update(to_delete_locally)

    # Propagar exclusões locais para o Turso Cloud se houver
    to_delete_remotely = [qid for qid in local_deleted_ids if qid in remote_q_ids or qid not in remote_deleted_ids]
    if to_delete_remotely:
        if verbose:
            print(f"  [-] Propagando {len(to_delete_remotely)} exclusões locais para o Turso Cloud...")
        del_batch_size = 100
        for i in range(0, len(to_delete_remotely), del_batch_size):
            chunk = to_delete_remotely[i:i + del_batch_size]
            ph = ",".join("?" * len(chunk))
            del_args = [{"type": "integer", "value": str(qid)} for qid in chunk]
            del_reqs = [
                {"type": "execute", "stmt": {"sql": "BEGIN"}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM alternatives WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM explanations WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM question_images WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM attempts WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM favorites WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM spaced_repetition WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"UPDATE flashcards SET question_id = NULL WHERE question_id IN ({ph})", "args": del_args}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM questions WHERE id IN ({ph})", "args": del_args}},
            ]
            for qid in chunk:
                del_reqs.append({
                    "type": "execute",
                    "stmt": {
                        "sql": "INSERT OR REPLACE INTO deleted_questions (question_id, deleted_at, deleted_by) VALUES (?, datetime('now'), 'local_sync')",
                        "args": [{"type": "integer", "value": str(qid)}]
                    }
                })
            del_reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, del_reqs)
        remote_deleted_ids.update(to_delete_remotely)
        remote_q_ids.difference_update(to_delete_remotely)

    all_deleted_ids = local_deleted_ids | remote_deleted_ids

    # 2. Sincronizar Questions faltantes (ignorando questões que foram excluídas)
    cur.execute("SELECT * FROM questions")
    local_questions = cur.fetchall()
    q_cols = [c[1] for c in cur.execute("PRAGMA table_info(questions)").fetchall()]
    missing_q = [q for q in local_questions if q["id"] not in remote_q_ids and q["id"] not in all_deleted_ids]

    if missing_q:
        if verbose:
            print(f"  [+] Enviando {len(missing_q)} novas questões para o Turso...")
        batch_size = 100
        insert_sql = f"INSERT INTO questions ({', '.join(q_cols)}) VALUES ({', '.join(['?' for _ in q_cols])})"
        total_batches = (len(missing_q) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(missing_q), batch_size), start=1):
            chunk = missing_q[i:i + batch_size]
            reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
            for q in chunk:
                args = []
                for c in q_cols:
                    val = q[c]
                    if val is None:
                        args.append({"type": "null"})
                    elif isinstance(val, int):
                        args.append({"type": "integer", "value": str(val)})
                    elif isinstance(val, float):
                        args.append({"type": "float", "value": val})
                    else:
                        args.append({"type": "text", "value": str(val)})
                reqs.append({"type": "execute", "stmt": {"sql": insert_sql, "args": args}})
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, reqs)
            if verbose and (batch_idx % 25 == 0 or batch_idx == total_batches):
                print(f"      ... [Questões] {min(i + batch_size, len(missing_q))}/{len(missing_q)} ({batch_idx}/{total_batches} lotes)")

    # Sincronizar alteração específica no stem de Q10218
    cur.execute("SELECT stem FROM questions WHERE id = 10218")
    row_10218 = cur.fetchone()
    if row_10218:
        execute_turso_pipeline(url, token, [{
            "type": "execute",
            "stmt": {
                "sql": "UPDATE questions SET stem = ? WHERE id = 10218",
                "args": [{"type": "text", "value": row_10218["stem"]}]
            }
        }])

    # 2b. Sincronizar metadados atualizados de Questions (subtema canônico, topic, subtema_orig)
    cur.execute("SELECT id, subtema, topic, subtema_orig FROM questions")
    local_q_meta = {r["id"]: (r["subtema"], r["topic"], r["subtema_orig"]) for r in cur.fetchall()}

    try:
        res_q_meta = execute_turso_pipeline(url, token, [{
            "type": "execute",
            "stmt": {"sql": "SELECT id, subtema, topic, subtema_orig FROM questions"}
        }], timeout=60)
        remote_q_meta = res_q_meta["results"][0]["response"]["result"]["rows"]

        questions_to_update = []
        for r in remote_q_meta:
            qid = int(r[0]["value"])
            if qid in local_q_meta:
                l_sub, l_top, l_orig = local_q_meta[qid]
                r_sub = r[1].get("value") if len(r) > 1 and isinstance(r[1], dict) else None
                r_top = r[2].get("value") if len(r) > 2 and isinstance(r[2], dict) else None
                r_orig = r[3].get("value") if len(r) > 3 and isinstance(r[3], dict) else None
                if l_sub != r_sub or l_top != r_top or l_orig != r_orig:
                    questions_to_update.append((qid, l_sub, l_top, l_orig))

        if questions_to_update:
            if verbose:
                print(f"  [+] Atualizando taxonomia de {len(questions_to_update)} questões no Turso...")
            batch_size = 200
            total_batches = (len(questions_to_update) + batch_size - 1) // batch_size
            for batch_idx, i in enumerate(range(0, len(questions_to_update), batch_size), start=1):
                chunk = questions_to_update[i:i + batch_size]
                reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
                for qid, sub, top, orig in chunk:
                    args = [
                        {"type": "text", "value": sub or ""},
                        {"type": "text", "value": top or ""},
                        {"type": "text", "value": orig} if orig else {"type": "null"},
                        {"type": "integer", "value": str(qid)}
                    ]
                    reqs.append({
                        "type": "execute",
                        "stmt": {
                            "sql": "UPDATE questions SET subtema = ?, topic = ?, subtema_orig = ? WHERE id = ?",
                            "args": args
                        }
                    })
                reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
                execute_turso_pipeline(url, token, reqs, timeout=60)
                if verbose and (batch_idx % 20 == 0 or batch_idx == total_batches):
                    print(f"      ... [Taxonomia Questões] {min(i + batch_size, len(questions_to_update))}/{len(questions_to_update)} ({batch_idx}/{total_batches} lotes)")
    except Exception as e:
        print(f"  [AVISO] Não foi possível verificar atualização de taxonomia no Turso: {e}")

    # 3. Sincronizar Alternatives faltantes
    cur.execute("SELECT * FROM alternatives")
    local_alts = cur.fetchall()
    a_cols = [c[1] for c in cur.execute("PRAGMA table_info(alternatives)").fetchall()]
    missing_a = [a for a in local_alts if a["id"] not in remote_a_ids]

    if missing_a:
        if verbose:
            print(f"  [+] Enviando {len(missing_a)} novas alternativas para o Turso...")
        batch_size = 200
        insert_alt_sql = f"INSERT INTO alternatives ({', '.join(a_cols)}) VALUES ({', '.join(['?' for _ in a_cols])})"
        total_batches = (len(missing_a) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(missing_a), batch_size), start=1):
            chunk = missing_a[i:i + batch_size]
            reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
            for a in chunk:
                args = []
                for c in a_cols:
                    val = a[c]
                    if val is None:
                        args.append({"type": "null"})
                    elif isinstance(val, int):
                        args.append({"type": "integer", "value": str(val)})
                    elif isinstance(val, float):
                        args.append({"type": "float", "value": val})
                    else:
                        args.append({"type": "text", "value": str(val)})
                reqs.append({"type": "execute", "stmt": {"sql": insert_alt_sql, "args": args}})
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, reqs)
            if verbose and (batch_idx % 50 == 0 or batch_idx == total_batches):
                print(f"      ... [Alternativas] {min(i + batch_size, len(missing_a))}/{len(missing_a)} ({batch_idx}/{total_batches} lotes)")

    # 4. Sincronizar Question Images
    cur.execute("SELECT * FROM question_images")
    local_images = cur.fetchall()
    local_i_ids = {img["id"] for img in local_images}
    img_cols = [c[1] for c in cur.execute("PRAGMA table_info(question_images)").fetchall()]

    # 4a. Remover imagens obsoletas ou expurgadas do Turso
    obsolete_i_ids = [rid for rid in remote_i_ids if rid not in local_i_ids]
    if obsolete_i_ids:
        if verbose:
            print(f"  [-] Removendo {len(obsolete_i_ids)} imagens obsoletas/expurgadas do Turso...")
        batch_size = 500
        total_batches = (len(obsolete_i_ids) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(obsolete_i_ids), batch_size), start=1):
            chunk = obsolete_i_ids[i:i + batch_size]
            ph = ",".join("?" * len(chunk))
            args = [{"type": "integer", "value": str(cid)} for cid in chunk]
            reqs = [
                {"type": "execute", "stmt": {"sql": "BEGIN"}},
                {"type": "execute", "stmt": {"sql": f"DELETE FROM question_images WHERE id IN ({ph})", "args": args}},
                {"type": "execute", "stmt": {"sql": "COMMIT"}}
            ]
            execute_turso_pipeline(url, token, reqs)
            if verbose and (batch_idx % 10 == 0 or batch_idx == total_batches):
                print(f"      ... [Imagens Removidas] {min(i + batch_size, len(obsolete_i_ids))}/{len(obsolete_i_ids)} ({batch_idx}/{total_batches} lotes)")

    # 4b. Sincronizar Question Images faltantes
    missing_i = [img for img in local_images if img["id"] not in remote_i_ids]

    if missing_i:
        if verbose:
            print(f"  [+] Enviando {len(missing_i)} novas imagens para o Turso...")
        batch_size = 200
        insert_img_sql = f"INSERT INTO question_images ({', '.join(img_cols)}) VALUES ({', '.join(['?' for _ in img_cols])})"
        total_batches = (len(missing_i) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(missing_i), batch_size), start=1):
            chunk = missing_i[i:i + batch_size]
            reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
            for img in chunk:
                args = []
                for c in img_cols:
                    val = img[c]
                    if val is None:
                        args.append({"type": "null"})
                    elif isinstance(val, int):
                        args.append({"type": "integer", "value": str(val)})
                    elif isinstance(val, float):
                        args.append({"type": "float", "value": val})
                    else:
                        args.append({"type": "text", "value": str(val)})
                reqs.append({"type": "execute", "stmt": {"sql": insert_img_sql, "args": args}})
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, reqs)
            if verbose and (batch_idx % 25 == 0 or batch_idx == total_batches):
                print(f"      ... [Imagens] {min(i + batch_size, len(missing_i))}/{len(missing_i)} ({batch_idx}/{total_batches} lotes)")

    # 5. Sincronizar Explanations (faltantes ou alteradas)
    cur.execute("SELECT question_id, explanation_text, generated_at, reviewed_at FROM explanations WHERE explanation_text IS NOT NULL")
    local_exps = cur.fetchall()

    exps_to_sync = []
    for e in local_exps:
        qid = e["question_id"]
        text = e["explanation_text"]
        # Se não existe no Turso ou o tamanho difere
        if qid not in remote_e_map or remote_e_map[qid] != len(text):
            exps_to_sync.append((qid, text, e["generated_at"] or "", e["reviewed_at"] or ""))

    if exps_to_sync:
        if verbose:
            print(f"  [+] Atualizando {len(exps_to_sync)} explicações no Turso...")
        batch_size = 100
        total_batches = (len(exps_to_sync) + batch_size - 1) // batch_size
        for batch_idx, i in enumerate(range(0, len(exps_to_sync), batch_size), start=1):
            chunk = exps_to_sync[i:i + batch_size]
            reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
            for qid, text, gen, rev in chunk:
                reqs.append({
                    "type": "execute",
                    "stmt": {
                        "sql": "INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at) VALUES (?, ?, ?, ?) ON CONFLICT(question_id) DO UPDATE SET explanation_text = excluded.explanation_text, reviewed_at = excluded.reviewed_at",
                        "args": [
                            {"type": "integer", "value": str(qid)},
                            {"type": "text", "value": text},
                            {"type": "text", "value": gen},
                            {"type": "text", "value": rev}
                        ]
                    }
                })
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, reqs)
            if verbose and (batch_idx % 25 == 0 or batch_idx == total_batches):
                print(f"      ... [Explicações] {min(i + batch_size, len(exps_to_sync))}/{len(exps_to_sync)} ({batch_idx}/{total_batches} lotes)")

    duration = time.time() - start_time
    total_synced = len(missing_q) + len(missing_a) + len(missing_i) + len(exps_to_sync)

    if total_synced > 0:
        print(f"  [OK] Turso Cloud sincronizado com sucesso!")
        print(f"       +{len(missing_q)} questões, +{len(missing_a)} alternativas, +{len(missing_i)} imagens, {len(exps_to_sync)} explicações atualizadas ({duration:.1f}s)")
    else:
        print(f"  [OK] Turso Cloud já está 100% atualizado e em sincronia com o banco local ({duration:.1f}s)")

    conn.close()
    return True


if __name__ == "__main__":
    success = sync_database(verbose=True)
    sys.exit(0 if success else 1)
