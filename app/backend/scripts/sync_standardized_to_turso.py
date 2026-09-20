#!/usr/bin/env python3
"""
Sincroniza as explicações padronizadas do banco local SQLite para o banco remoto Turso (online).
Usa a API HTTP Pipeline v2 do Turso com queries parametrizadas para máxima segurança e velocidade.
"""

import os
import sys
import json
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

load_env()

TURSO_RAW_URL = os.environ.get("TURSO_DATABASE_URL", "")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

if not TURSO_RAW_URL or not TURSO_TOKEN:
    print("[ERRO] TURSO_DATABASE_URL ou TURSO_AUTH_TOKEN não configurados no ambiente/.env.")
    sys.exit(1)

TURSO_URL = TURSO_RAW_URL.replace("libsql://", "https://").replace("wss://", "https://") + "/v2/pipeline"

def sync_to_turso(chunk_size: int = 50):
    print(f"Conectando ao banco local: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT question_id, explanation_text FROM explanations WHERE explanation_text IS NOT NULL")
    local_rows = c.fetchall()
    print(f"Total de explicações locais: {len(local_rows)}")

    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }

    # Passo 1: Descobrir no Turso quais questões ainda possuem formatação antiga com dois-pontos dentro
    print("Identificando questões no Turso online com formatação antiga...")
    find_req = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": "SELECT question_id FROM explanations WHERE explanation_text LIKE '%**Pulo do Gato:%' OR explanation_text LIKE '%**Raciocínio Clínico:%'"
                }
            }
        ]
    }
    req = urllib.request.Request(TURSO_URL, data=json.dumps(find_req).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        rows = data["results"][0]["response"]["result"]["rows"]
        turso_outdated_ids = {int(r[0]["value"]) for r in rows}

    print(f"Questões no Turso precisando de atualização: {len(turso_outdated_ids)}")

    if not turso_outdated_ids:
        print("[OK] O banco remoto Turso já está 100% padronizado!")
        return

    # Filtra do banco local as explicações para atualizar no Turso
    to_update = [(qid, text) for qid, text in local_rows if qid in turso_outdated_ids]
    print(f"Total a sincronizar com Turso: {len(to_update)}")

    total_chunks = (len(to_update) + chunk_size - 1) // chunk_size

    for idx, i in enumerate(range(0, len(to_update), chunk_size)):
        chunk = to_update[i:i + chunk_size]
        requests_list = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]

        for qid, text in chunk:
            requests_list.append({
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE explanations SET explanation_text = ? WHERE question_id = ?",
                    "args": [
                        {"type": "text", "value": text},
                        {"type": "integer", "value": str(qid)}
                    ]
                }
            })

        requests_list.append({"type": "execute", "stmt": {"sql": "COMMIT"}})

        chunk_req = urllib.request.Request(
            TURSO_URL,
            data=json.dumps({"requests": requests_list}).encode("utf-8"),
            headers=headers,
            method="POST"
        )

        try:
            with urllib.request.urlopen(chunk_req, timeout=60) as cresp:
                if cresp.status == 200:
                    print(f"  -> Chunk {idx + 1}/{total_chunks} ({len(chunk)} itens) sincronizado com sucesso.")
        except Exception as e:
            print(f"  -> [ERRO] Falha no chunk {idx + 1}: {e}")
            sys.exit(1)

    print("\n[SUCESSO] Sincronização com o Turso finalizada com sucesso!")

    # Verificação pós-sync
    print("\nVerificando integridade no Turso pós-sincronização...")
    check_req = {
        "requests": [
            {
                "type": "execute",
                "stmt": {
                    "sql": "SELECT count(*) FROM explanations WHERE explanation_text LIKE '%**Pulo do Gato:%'"
                }
            },
            {
                "type": "execute",
                "stmt": {
                    "sql": "SELECT explanation_text FROM explanations WHERE question_id = 11604"
                }
            }
        ]
    }
    req2 = urllib.request.Request(TURSO_URL, data=json.dumps(check_req).encode("utf-8"), headers=headers, method="POST")
    with urllib.request.urlopen(req2, timeout=30) as resp2:
        res_data = json.loads(resp2.read().decode("utf-8"))
        rem_outdated = res_data["results"][0]["response"]["result"]["rows"][0][0]["value"]
        sample_text = res_data["results"][1]["response"]["result"]["rows"][0][0]["value"]

        print(f"Questões despadronizadas restantes no Turso: {rem_outdated}")
        print("Trecho Questão 11604 no Turso pós-sync:")
        print(repr(sample_text[:250]))


if __name__ == "__main__":
    sync_to_turso()
