"""
Script resiliente de extração da resposta curta esperada pela banca para questões discursivas.
Utiliza pool multi-chave Round-Robin, modelo gemini-3.1-flash-lite-preview com fallback entre chaves,
tratamento robusto de erros transitórios (503/429) e salvamento incremental contínuo.
"""

import os
import sys
import json
import time
import sqlite3
import re
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "medquest.db"
OUTPUT_PATH = ROOT / "data" / "discursive_short_answers.json"

SYSTEM_PROMPT = """Você é um preceptor médico especialista em provas práticas e discursivas de residência médica (como UNICAMP, USP, etc.).
Sua missão é extrair estritamente a RESPOSTA CURTA ESPERADA PELA BANCA examinadora para uma questão discursiva/dissertativa.

Regras estritas:
1. Resposta ultra-concisa: retorne APENAS o termo, diagnóstico nosológico, conduta, fármaco, agente etiológico, valor de referência ou procedimento que pontua na folha de resposta da banca.
2. Tamanho ideal: de 1 a 8 palavras (ex: "Aciclovir", "Angioplastia primária", "Doença de Wilson", "Dexametasona", "Streptococcus pneumoniae", "Conduta expectante / Sintomáticos").
3. Se a questão tiver múltiplos sub-itens explícitos no enunciado (ex: A e B, ou conduta e diagnóstico), use o formato conciso em uma linha: "A: [resposta] | B: [resposta]".
4. NÃO inclua explicações, NÃO inclua justificativas teóricas, NÃO adicione introduções como "A resposta é" ou "Gabarito:".
5. Não termine com ponto final desnecessário. Retorne apenas o padrão objetivo da banca.
"""

MODEL = "gemini-3.1-flash-lite-preview"


def clean_extracted_answer(raw: str) -> str:
    if not raw:
        return ""
    t = raw.strip()
    t = re.sub(r"^[`'\"]+|[`'\"]+$", "", t).strip()
    t = re.sub(r"^(?:\*\*)?(?:Gabarito|Resposta|Padrão de Resposta)(?:\s+Oficial)?(?:\*\*)?:\s*", "", t, flags=re.IGNORECASE).strip()
    if t.startswith("**") and t.endswith("**") and len(t) > 4:
        t = t[2:-2].strip()
    if "\n" not in t and t.endswith("."):
        t = t[:-1].strip()
    bad_phrases = ["user safety", "i cannot", "desculpe", "não foi possível", "como modelo de ia", "como uma ia", "sou um modelo"]
    if any(bad in t.lower() for bad in bad_phrases):
        return ""
    return t


def get_discursive_questions(conn: sqlite3.Connection):
    cursor = conn.cursor()
    rows = cursor.execute("""
        SELECT q.id, q.source_file, q.source_number, q.year, q.institution_code, q.stem, e.explanation_text
        FROM questions q
        JOIN alternatives a ON a.question_id = q.id
        LEFT JOIN explanations e ON e.question_id = q.id
        GROUP BY q.id
        HAVING COUNT(a.id) <= 1 
           OR GROUP_CONCAT(a.text) LIKE '%anote sua%' 
           OR GROUP_CONCAT(a.text) LIKE '%dissertat%' 
           OR GROUP_CONCAT(a.text) LIKE '%discursiv%'
        ORDER BY q.id
    """).fetchall()
    return rows


def save_progress(cache: dict):
    temp_path = OUTPUT_PATH.with_suffix(".tmp")
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    temp_path.replace(OUTPUT_PATH)


def main():
    if not DB_PATH.exists():
        print(f"Erro: banco não encontrado em {DB_PATH}")
        sys.exit(1)

    raw_keys = os.environ.get("GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEY", "")
    keys = [k.strip() for k in raw_keys.split(",") if len(k.strip()) > 10 and not k.strip().lower().startswith("dummy")]
    if not keys:
        print("Erro: Nenhuma chave Gemini configurada no .env!")
        sys.exit(1)

    print(f"Pool de chaves iniciado com {len(keys)} chaves Google AI.")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    cache = {}
    if OUTPUT_PATH.exists():
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                raw_cache = json.load(f)
            cache = {
                k: v for k, v in raw_cache.items() 
                if v.get("short_answer") and "user safety" not in v.get("short_answer", "").lower()
            }
            print(f"Cache existente carregado: {len(cache)} respostas válidas salvas.")
        except Exception as e:
            print(f"Aviso ao carregar cache: {e}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    questions = get_discursive_questions(conn)
    conn.close()

    total = len(questions)
    print(f"Total de questões discursivas identificadas: {total}")

    pending_qs = [dict(q) for q in questions if str(q["id"]) not in cache or not cache[str(q["id"])].get("short_answer")]
    print(f"Questões pendentes na fila: {len(pending_qs)}")

    if not pending_qs:
        print("Todas as 735 questões já foram extraídas e salvas no cache!")
        return

    current_key_idx = 0
    key_cooldowns = {k: 0.0 for k in keys}
    last_save_time = time.time()
    completed_count = len(cache)

    print(f"\nIniciando extração contínua de {len(pending_qs)} questões...")

    for q_idx, q in enumerate(pending_qs, 1):
        qid = q["id"]
        stem = (q["stem"] or "").strip()
        exp = (q["explanation_text"] or "").strip()[:4500]

        prompt = f"""Enunciado da Questão:
{stem}

Comentário / Resolução da Questão:
{exp}

Com base no enunciado (especialmente a pergunta final direta) e na resolução comentada, qual é a RESPOSTA CURTA ESPERADA PELA BANCA? Retorne APENAS essa resposta concisa.
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {"temperature": 0.1}
        }
        body = json.dumps(payload).encode("utf-8")

        extracted_answer = ""
        max_attempts = 12

        for attempt in range(max_attempts):
            now = time.time()

            # Escolher chave que não esteja em cooldown
            chosen_key = None
            chosen_key_num = 0
            for _ in range(len(keys)):
                k = keys[current_key_idx]
                k_num = current_key_idx + 1
                current_key_idx = (current_key_idx + 1) % len(keys)
                if key_cooldowns[k] <= now:
                    chosen_key = k
                    chosen_key_num = k_num
                    break

            if not chosen_key:
                min_cd = min(key_cooldowns.values())
                wait_sec = max(1.0, min_cd - now + 0.5)
                print(f"[PAUSA] Todas as chaves em cooldown. Aguardando {wait_sec:.1f}s...")
                time.sleep(wait_sec)
                continue

            url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json", "x-goog-api-key": chosen_key}
            )

            try:
                with urllib.request.urlopen(req, timeout=16) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        text = parts[0].get("text", "") if parts else ""
                        cleaned = clean_extracted_answer(text)
                        if cleaned:
                            extracted_answer = cleaned
                            break
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8", errors="ignore")
                except Exception:
                    pass

                if e.code == 429 or "RESOURCE_EXHAUSTED" in err_body:
                    m = re.search(r'"retryDelay":\s*"([0-9.]+)s"', err_body)
                    delay = float(m.group(1)) if m else 30.0
                    key_cooldowns[chosen_key] = time.time() + max(delay, 20.0)
                    print(f"[RATE LIMIT] Chave #{chosen_key_num} em cooldown por {max(delay, 20.0):.0f}s. Alternando chave...")
                elif e.code in (500, 502, 503, 504):
                    key_cooldowns[chosen_key] = time.time() + 15.0
                    print(f"[HTTP {e.code}] Chave #{chosen_key_num} temporariamente indisponível. Alternando chave...")
                else:
                    print(f"[HTTP {e.code}] Chave #{chosen_key_num}: {err_body[:80]}. Alternando...")
                time.sleep(0.5)
            except Exception as e:
                # Timeout ou erro de conexão
                key_cooldowns[chosen_key] = time.time() + 10.0
                print(f"[TIMEOUT] Chave #{chosen_key_num}: {e}. Alternando chave...")
                time.sleep(0.5)

        if extracted_answer:
            cache[str(qid)] = {
                "question_id": qid,
                "source_file": q["source_file"],
                "year": q["year"],
                "short_answer": extracted_answer,
                "status": "success"
            }
            completed_count += 1
            print(f"[{completed_count}/{total}] ID {qid} ({q['year']}): {extracted_answer[:55]}", flush=True)

            if time.time() - last_save_time > 5:
                save_progress(cache)
                last_save_time = time.time()
        else:
            print(f"[FALHA DEFINITIVA] Questão ID {qid} não pôde ser extraída após {max_attempts} tentativas.", flush=True)

        # Intervalo seguro para manter a taxa bem abaixo dos limites da Google AI
        time.sleep(0.25)

    save_progress(cache)
    success = sum(1 for v in cache.values() if v.get("short_answer"))
    print(f"\nExtração concluída com sucesso: {success}/{total}")


if __name__ == "__main__":
    main()
