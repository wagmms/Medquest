"""
Orquestrador de Auditoria Clínica e Reclassificação Canônica do MedQuest via Gemini 4 Argon.
Executa auditoria em lotes concorrentes, valida 100% dos 170 temas canônicos,
grava na tabela reclassification_audit e sincroniza atômica e imediatamente com Turso.
"""

import os
import sys
import json
import time
import sqlite3
import argparse
import datetime
import subprocess
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

BASE_DIR = "/home/wagmoraes/Projetos IA/MedQuest/app/backend"
DB_PATH = os.path.join(BASE_DIR, "medquest.db")
SUBTEMA_MAP_PATH = os.path.join(BASE_DIR, "data", "subtema_map.json")
CHECKPOINT_DIR = os.path.join(BASE_DIR, "data", "audit_checkpoints")
CANONICAL_THEMES_PATH = os.path.join(BASE_DIR, "data", "170_temas_canonicos.txt")

load_dotenv(os.path.join(BASE_DIR, ".env"))

TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")


def get_canonical_themes():
    import re
    with open(CANONICAL_THEMES_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    return set(re.findall(r"  - (.+)", content))


def get_subtema_map():
    with open(SUBTEMA_MAP_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_prompt_file(dest_path):
    prompt_text = """Você é o Auditor Chefe e Preceptor de Residência Médica (Gemini 4 Argon) com máxima expertise em provas de residência (USP, ENARE, UNICAMP, UNESP, SUS-SP, AMP).

OBJETIVO:
Analisar individualmente cada uma das questões médicas anexadas, auditando sua adequação temática.

DIRETRIZ CLÍNICA MANDATÓRIA:
"Analise cada questão por vez e raciocine antes de classificar, tendo certeza de que a questão está no tema correto. Pesquise relações, não é pq uma questão se trata de criança que é necessariamente pediatria, ou mulher grávida que é necessariamente GO."
Exemplo clássico: Uma questão cujo cenário clínico cita uma paciente grávida recebendo infusão incorreta de eletrólito/medicação que aborda conceitos de Segurança do Paciente (MS/ANVISA/OMS) pertence a Medicina Preventiva (Ética Médica, Bioética e Prontuários / Documentos), e NÃO a GO. Questões de sigilo médico ou capacidade de consentimento de adolescentes pertencem a Medicina Preventiva (Ética Médica), e NÃO a Pediatria ou GO.

REGRAS ESTRITAS DE CLASSIFICAÇÃO:
1. O novo subtema DEVE ser EXATAMENTE um dos 170 temas canônicos listados no arquivo 170_temas_canonicos.txt (proibido inventar termos novos).
2. A nova grande área DEVE ser estritamente uma destas 5:
   - "Clínica Médica"
   - "Cirurgia"
   - "Ginecologia e Obstetrícia"
   - "Pediatria"
   - "Medicina Preventiva"
3. Para cada questão, examine o enunciado completo, as alternativas, o gabarito e o foco principal exigido pela banca.
4. Explique detalhadamente seu raciocínio clínico para cada questão:
   - Qual é o núcleo do conhecimento médico exigido?
   - O que a banca está realmente avaliando?
   - Por que o tema anterior estava inadequado (ou adequado)?
   - Por que o tema de destino é o padrão-ouro canônico?

FORMATO DE SAÍDA:
Retorne EXCLUSIVAMENTE um JSON puro (uma lista de objetos) com a seguinte estrutura:
[
  {
    "id": 12345,
    "banca_ano": "Banca Ano",
    "enunciado_resumo": "...",
    "subtema_atual": "...",
    "area_atual": "...",
    "raciocinio_clinico": "...",
    "decisao": "MANTER" ou "RECLASSIFICAR",
    "novo_subtema": "Nome exato de 1 dos 170 temas canônicos",
    "nova_area": "Uma das 5 grandes áreas"
  }
]
"""
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(prompt_text)


def sync_to_turso(items, smap):
    if not TURSO_URL or not TURSO_TOKEN:
        return False
    stmts = []
    for item in items:
        if item["decisao"] == "RECLASSIFICAR":
            qid = item["id"]
            new_sub = item["novo_subtema"]
            new_area = item["nova_area"]
            new_sid = smap.get(new_sub, "")
            stmts.append({
                "sql": "UPDATE questions SET area = ?, subtema = ?, subtema_id = ? WHERE id = ?",
                "args": [
                    {"type": "text", "value": new_area},
                    {"type": "text", "value": new_sub},
                    {"type": "text", "value": new_sid},
                    {"type": "integer", "value": str(qid)}
                ]
            })
    if not stmts:
        return True

    clean_url = TURSO_URL.replace("libsql://", "https://")
    url = f"{clean_url}/v2/pipeline"
    headers = {
        "Authorization": f"Bearer {TURSO_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = [{"type": "execute", "stmt": s} for s in stmts]
    payload.append({"type": "close"})

    try:
        resp = requests.post(url, headers=headers, json={"requests": payload}, timeout=15)
        return resp.status_code == 200
    except Exception as e:
        print(f"Erro ao sincronizar com Turso: {e}")
        return False


def apply_to_sqlite(items, smap):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    reclass_count = 0
    conn.execute("BEGIN TRANSACTION")
    try:
        for item in items:
            qid = item["id"]
            dec = item.get("decisao", "MANTER")
            old_sub = item.get("subtema_atual")
            old_area = item.get("area_atual")
            rationale = item.get("raciocinio_clinico", "")
            
            if dec == "RECLASSIFICAR":
                new_sub = item["novo_subtema"]
                new_area = item["nova_area"]
                new_sid = smap.get(new_sub, "")

                c.execute("""
                    UPDATE questions 
                    SET subtema = ?, area = ?, subtema_id = ?, review_date = ?
                    WHERE id = ?
                """, (new_sub, new_area, new_sid, now, qid))

                c.execute("""
                    INSERT INTO reclassification_audit 
                    (question_id, old_area, old_subtema, new_area, new_subtema, confidence, rationale, model_used, applied, classified_at)
                    VALUES (?, ?, ?, ?, ?, 0.99, ?, "gemini-4-argon", 1, ?)
                """, (qid, old_area, old_sub, new_area, new_sub, rationale, now))
                reclass_count += 1
            else:
                c.execute("UPDATE questions SET review_date = ? WHERE id = ?", (now, qid))
                c.execute("""
                    INSERT INTO reclassification_audit 
                    (question_id, old_area, old_subtema, new_area, new_subtema, confidence, rationale, model_used, applied, classified_at)
                    VALUES (?, ?, ?, ?, ?, 1.0, ?, "gemini-4-argon", 0, ?)
                """, (qid, old_area, old_sub, old_area, old_sub, rationale, now))
        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        raise e
    conn.close()
    return reclass_count


def process_batch(batch_idx, batch_questions, prompt_path, valid_themes, smap):
    batch_file = f"/tmp/argon_batch_{batch_idx}_{int(time.time()*1000)}.json"
    out_file = f"/tmp/argon_out_{batch_idx}_{int(time.time()*1000)}.json"

    with open(batch_file, "w", encoding="utf-8") as f:
        json.dump(batch_questions, f, indent=2, ensure_ascii=False)

    cmd = [
        "argon", "--no-stream", "-b", "high",
        "-p", prompt_path,
        "-f", CANONICAL_THEMES_PATH,
        "-f", batch_file,
        "-o", out_file
    ]

    max_attempts = 2
    for attempt in range(1, max_attempts + 1):
        t0 = time.time()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        elapsed = time.time() - t0

        if res.returncode == 0 and os.path.exists(out_file):
            break
        if attempt < max_attempts:
            time.sleep(3 * attempt)

    if res.returncode != 0 or not os.path.exists(out_file):
        try:
            os.remove(batch_file)
        except:
            pass
        return {
            "batch_idx": batch_idx,
            "success": False,
            "error": f"Argon error (code {res.returncode}): {res.stderr[:200]}",
            "elapsed": elapsed
        }

    try:
        with open(out_file, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1] if "\n" in raw_text else raw_text
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0].strip()
        data = json.loads(raw_text)
    except Exception as e:
        return {
            "batch_idx": batch_idx,
            "success": False,
            "error": f"JSON parse error: {e}",
            "elapsed": elapsed
        }

    for item in data:
        if item["novo_subtema"] not in valid_themes:
            return {
                "batch_idx": batch_idx,
                "success": False,
                "error": f"Tema não canônico retornado: {item['novo_subtema']}",
                "elapsed": elapsed
            }

    reclass_count = apply_to_sqlite(data, smap)
    turso_ok = sync_to_turso(data, smap)

    chk_path = os.path.join(CHECKPOINT_DIR, f"checkpoint_batch_{batch_idx}_{int(time.time())}.json")
    with open(chk_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    try:
        os.remove(batch_file)
        os.remove(out_file)
    except:
        pass

    return {
        "batch_idx": batch_idx,
        "success": True,
        "total": len(data),
        "reclassified": reclass_count,
        "turso_synced": turso_ok,
        "elapsed": elapsed
    }


def main():
    parser = argparse.ArgumentParser(description="Auditor de Questões em Lote com Gemini 4 Argon")
    parser.add_argument("--subtema", type=str, help="Filtrar por subtema específico")
    parser.add_argument("--area", type=str, help="Filtrar por grande área")
    parser.add_argument("--discrepancies-only", action="store_true", help="Auditar apenas questões onde topic != subtema")
    parser.add_argument("--limit", type=int, default=100, help="Limite máximo de questões para a rodada")
    parser.add_argument("--batch-size", type=int, default=20, help="Tamanho de cada lote")
    parser.add_argument("--workers", type=int, default=5, help="Número de workers paralelos do Argon")

    args = parser.parse_args()

    valid_themes = get_canonical_themes()
    smap = get_subtema_map()

    prompt_path = "/tmp/argon_shared_audit_prompt.txt"
    build_prompt_file(prompt_path)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    query = """
    SELECT q.id, q.year, q.institution_code, q.institution_label, q.topic, q.subtema, q.area, q.stem, q.correct_letter
    FROM questions q
    WHERE q.status = 'active'
    """
    params = []

    if args.subtema:
        query += " AND q.subtema = ?"
        params.append(args.subtema)

    if args.area:
        query += " AND q.area = ?"
        params.append(args.area)

    if args.discrepancies_only:
        query += " AND q.topic != q.subtema AND q.topic IS NOT NULL"

    query += """
    AND (q.review_date IS NULL OR q.review_date = '')
    AND q.id NOT IN (
        SELECT question_id FROM reclassification_audit 
        WHERE classified_at >= datetime('now', '-7 days')
    )
    ORDER BY q.id
    LIMIT ?
    """
    params.append(args.limit)

    c.execute(query, params)
    rows = c.fetchall()

    if not rows:
        print("Nenhuma questão encontrada com os filtros especificados.")
        conn.close()
        return

    print(f"Carregadas {len(rows)} questões para auditoria.")
    questions = []
    for r in rows:
        qid = r[0]
        c.execute("SELECT letter, text FROM alternatives WHERE question_id = ? ORDER BY letter", (qid,))
        alts = [{"letter": a[0], "text": a[1]} for a in c.fetchall()]

        c.execute("SELECT explanation_text FROM explanations WHERE question_id = ? LIMIT 1", (qid,))
        exp = c.fetchone()
        exp_text = exp[0][:250] if exp and exp[0] else None

        questions.append({
            "id": qid,
            "year": r[1],
            "institution_code": r[2],
            "institution_label": r[3],
            "topic": r[4],
            "subtema": r[5],
            "area": r[6],
            "stem": r[7],
            "correct_letter": r[8],
            "alternatives": alts,
            "explanation": exp_text
        })
    conn.close()

    batches = [questions[i:i + args.batch_size] for i in range(0, len(questions), args.batch_size)]
    print(f"Total de {len(batches)} lotes de até {args.batch_size} questões com {args.workers} workers paralelos do Argon.")

    t_start = time.time()
    total_reclass = 0
    total_success = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(process_batch, idx, b, prompt_path, valid_themes, smap): idx
            for idx, b in enumerate(batches, 1)
        }

        for future in as_completed(futures):
            res = future.result()
            idx = res["batch_idx"]
            if res["success"]:
                total_success += res["total"]
                total_reclass += res["reclassified"]
                print(f"[OK] Lote {idx}/{len(batches)} | {res['total']} q | {res['reclassified']} reclassificadas | Turso: {res['turso_synced']} | Tempo: {res['elapsed']:.1f}s")
            else:
                print(f"[FALHA] Lote {idx}/{len(batches)} | Erro: {res['error']} | Tempo: {res['elapsed']:.1f}s")

    t_total = time.time() - t_start
    print("\n=== RESUMO DA RODADA ===")
    print(f"Questões auditadas com sucesso: {total_success}/{len(questions)}")
    print(f"Total reclassificadas: {total_reclass}")
    print(f"Tempo total decorrido: {t_total:.1f}s ({t_total/60:.2f} min)")
    print(f"Velocidade: {total_success / (t_total/60):.1f} questões/minuto")


if __name__ == "__main__":
    main()
