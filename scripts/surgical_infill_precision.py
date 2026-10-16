#!/usr/bin/env python3
"""
Motor de Infill Cirúrgico de Precisão com Gemini 4 Argon.
Preenche ESTRITAMENTE as letras de distratores que estão vazias ('- **Letra X**: Incorreta.'),
preservando 100% das explicações já escritas pelos professores e todas as imagens.
"""

import sqlite3
import json
import os
import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "backend")
DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")

def get_api_key():
    cfg_path = os.path.expanduser("~/.gemini/config/argon.json")
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            return json.load(f)["apiKey"]
    raise RuntimeError("Chave GEMINI_API_KEY não encontrada em ~/.gemini/config/argon.json")

def extract_image_urls(text: str) -> list[str]:
    if not text:
        return []
    return re.findall(r'https?://[^\s\)\"\'>]+', text)

def find_empty_distractor_letters(text: str) -> list[str]:
    """Identifica exatamente quais letras estão puramente como 'Incorreta.' sem explicação."""
    lines = text.split("\n")
    empty_letters = []
    for i, line in enumerate(lines):
        m = re.match(r'^\s*[-•*]\s*\*\*Letra\s+([A-E])\*\*:\s*Incorreta\.?\s*$', line, re.I)
        if m:
            letra = m.group(1).upper()
            # Verifica se a próxima linha não é uma continuação explicativa do professor
            has_continuation = False
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                if next_line and not re.match(r'^\s*[-•*]\s*\*\*Letra', next_line) and not next_line.startswith("#") and not next_line.startswith("!"):
                    has_continuation = True
            if not has_continuation:
                empty_letters.append(letra)
    return empty_letters

def call_argon_for_specific_letters(stem: str, alts_dict: dict, empty_letters: list[str], correct_letter: str, subtema: str, existing_reasoning: str) -> dict:
    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent?key={api_key}"
    
    needed_alts = "\n".join([f"- Letra {let}: {alts_dict.get(let, '')}" for let in empty_letters])
    correct_alt = f"- Letra {correct_letter} (CORRETA): {alts_dict.get(correct_letter, '')}"
    
    prompt = f"""Você é um Preceptor Chefe de Residência Médica (R1 USP, ENARE, UNICAMP).
A questão a seguir já possui comentários do professor, mas faltam as justificativas das alternativas listadas abaixo.
Gere a análise técnica para cada uma das alternativas solicitadas, explicando a fisiopatologia, o motivo do erro e a pegadinha da banca.

DADOS DA QUESTÃO:
Tema: {subtema}
Enunciado: {stem}
Gabarito Oficial: Letra {correct_letter}
Alternativa Correta:
{correct_alt}

ALTERNATIVAS INCORRETAS QUE PRECISAM DE JUSTIFICATIVA:
{needed_alts}

Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{{
  "distratores": [
    {{"letter": "LETRA", "text": "Explicação clínica e pegadinha da banca..."}}
  ]
}}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json"
        }
    }
    
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_res = data["candidates"][0]["content"]["parts"][0]["text"]
                return json.loads(text_res)
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(2 * (attempt + 1))

def process_single_question(qid: int, original_text: str, stem: str, alts_dict: dict, correct_letter: str, subtema: str) -> tuple[int, str, bool]:
    orig_urls = extract_image_urls(original_text)
    empty_letters = find_empty_distractor_letters(original_text)
    
    if not empty_letters:
        return qid, original_text, False
        
    infill_res = call_argon_for_specific_letters(stem, alts_dict, empty_letters, correct_letter, subtema, original_text)
    dist_map = {}
    for item in infill_res.get("distratores", []):
        let = item.get("letter", "").strip().upper()
        txt = item.get("text", "").strip()
        if txt.startswith("Incorreta."):
            txt = txt[len("Incorreta."):].strip()
        dist_map[let] = txt
        
    lines = original_text.split("\n")
    new_lines = []
    modified = False
    
    for line in lines:
        m = re.match(r'^\s*[-•*]\s*\*\*Letra\s+([A-E])\*\*:\s*Incorreta\.?\s*$', line, re.I)
        if m and m.group(1).upper() in dist_map:
            letra = m.group(1).upper()
            new_lines.append(f"- **Letra {letra}**: {dist_map[letra]}")
            modified = True
        else:
            new_lines.append(line)
            
    new_text = "\n".join(new_lines)
    
    # Validação de paridade de imagens (Zero-Drop)
    new_urls = extract_image_urls(new_text)
    assert orig_urls == new_urls, f"Quebra de imagem no QID {qid}"
    
    return qid, new_text, modified

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"🚀 Iniciando Infill Cirúrgico de Precisão (Gemini 4 Argon)...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    rows = cursor.execute("""
        SELECT e.question_id, e.explanation_text, q.stem, q.correct_letter, q.subtema
        FROM explanations e
        JOIN questions q ON e.question_id = q.id
        WHERE e.explanation_text LIKE '%Incorreta%'
        ORDER BY e.question_id
    """).fetchall()
    
    targets = []
    for r in rows:
        qid, exp, stem, c_let, subtema = r
        empty = find_empty_distractor_letters(exp)
        if empty:
            targets.append((qid, exp, stem, c_let, subtema, empty))
            if limit and len(targets) >= limit:
                break
                
    print(f"🎯 Total de questões com distratores estritamente vazios: {len(targets)}")
    if not targets:
        print("✅ Nenhuma questão com distrator vazio encontrada!")
        return

    # Pré-carrega alternativas
    q_ids = [t[0] for t in targets]
    placeholders = ",".join("?" * len(q_ids))
    alts_rows = cursor.execute(f"SELECT question_id, letter, text FROM alternatives WHERE question_id IN ({placeholders})", q_ids).fetchall()
    alts_by_q = {}
    for qid, let, txt in alts_rows:
        alts_by_q.setdefault(qid, {})[let.strip().upper()] = txt
        
    completed = 0
    updated = 0
    t0 = time.time()
    
    # Escala para 25 workers paralelos (aproveitando a cota alta do GCP Nível 1)
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = {}
        for item in targets:
            qid, exp, stem, c_let, subtema, empty = item
            alts_dict = alts_by_q.get(qid, {})
            fut = executor.submit(process_single_question, qid, exp, stem, alts_dict, c_let, subtema)
            futures[fut] = qid
            
        for fut in as_completed(futures):
            qid = futures[fut]
            try:
                res_qid, new_exp, modified = fut.result()
                if modified:
                    cursor.execute("UPDATE explanations SET explanation_text = ? WHERE question_id = ?", (new_exp, res_qid))
                    conn.commit()
                    updated += 1
                completed += 1
                if completed % 10 == 0 or completed == len(targets):
                    rate = completed / (time.time() - t0)
                    print(f"[{completed}/{len(targets)}] QID {qid} cirurgicamente enriquecida | Atualizadas: {updated} | Velocidade: {rate:.1f} q/s")
            except Exception as e:
                print(f"⚠️ Erro no QID {qid}: {e}")
                
    conn.close()
    print(f"\n🎉 Enriquecimento de precisão concluído! Processadas: {completed} | Atualizadas no banco: {updated} em {(time.time() - t0):.1f}s")

if __name__ == "__main__":
    main()
