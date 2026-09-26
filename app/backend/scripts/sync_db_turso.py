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
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries:
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

    # 1. Obter contagens e IDs remotos
    check_reqs = [
        {"type": "execute", "stmt": {"sql": "SELECT id FROM questions"}},
        {"type": "execute", "stmt": {"sql": "SELECT id FROM alternatives"}},
        {"type": "execute", "stmt": {"sql": "SELECT question_id, length(explanation_text) FROM explanations WHERE explanation_text IS NOT NULL"}},
        {"type": "execute", "stmt": {"sql": "SELECT id FROM question_images"}},
    ]

    try:
        remote_data = execute_turso_pipeline(url, token, check_reqs, timeout=60)
        res_q = remote_data["results"][0]["response"]["result"]["rows"]
        res_a = remote_data["results"][1]["response"]["result"]["rows"]
        res_e = remote_data["results"][2]["response"]["result"]["rows"]
        res_i = remote_data["results"][3]["response"]["result"]["rows"]

        remote_q_ids = {int(r[0]["value"]) for r in res_q if r}
        remote_a_ids = {int(r[0]["value"]) for r in res_a if r}
        remote_e_map = {int(r[0]["value"]): int(r[1]["value"]) for r in res_e if r and r[1]["value"] is not None}
        remote_i_ids = {int(r[0]["value"]) for r in res_i if r}
    except Exception as e:
        print(f"  [ERRO] Falha ao consultar estado do banco remoto Turso: {e}")
        return False

    # 2. Sincronizar Questions faltantes
    cur.execute("SELECT * FROM questions")
    local_questions = cur.fetchall()
    q_cols = [c[1] for c in cur.execute("PRAGMA table_info(questions)").fetchall()]
    missing_q = [q for q in local_questions if q["id"] not in remote_q_ids]

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

    # 4. Sincronizar Question Images faltantes
    cur.execute("SELECT * FROM question_images")
    local_images = cur.fetchall()
    img_cols = [c[1] for c in cur.execute("PRAGMA table_info(question_images)").fetchall()]
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
