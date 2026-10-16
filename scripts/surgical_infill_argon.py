#!/usr/bin/env python3
"""
Motor de Enriquecimento Cirúrgico de Distratores via Gemini 4 Argon.
Alvo: Questões com distratores boilerplate ('Letra X: Incorreta.').
Garante paridade absoluta de imagens médicas e ancoragem clínica de excelência para residência.
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
CHECKPOINT_PATH = os.path.join(BACKEND_DIR, "data", "infill_checkpoint.json")

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

def call_argon_infill(stem: str, alts: list, correct_letter: str, topic: str, subtema: str, existing_reasoning: str) -> dict:
    api_key = get_api_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-4-argon:generateContent?key={api_key}"
    
    alts_text = "\n".join([f"- Letra {a[0]}: {a[1]}" for a in alts])
    context_reasoning = f"\nRACIOCÍNIO CLÍNICO DO PROFESSOR:\n{existing_reasoning[:1200]}" if existing_reasoning else ""

    prompt = f"""Você é um Preceptor Chefe de Residência Médica (R1 USP, ENARE, UNICAMP).
A questão a seguir possui distratores preenchidos apenas com 'Incorreta.'.
Gere a análise técnica individual de cada distrator incorreto, explicando a fisiopatologia, o motivo do erro e a pegadinha da banca examinadora.
Também gere um 'Pulo do Gato' de alto rendimento focado na regra prática decisória de prova.

DADOS DA QUESTÃO:
Tema: {subtema} ({topic})
Enunciado: {stem}
Gabarito: Letra {correct_letter}
Alternativas:
{alts_text}
{context_reasoning}

Responda ESTRITAMENTE em formato JSON com o seguinte schema:
{{
  "pulo_do_gato": "texto com o gatilho decisório de prova e a pegadinha do distrator",
  "por_que_correta": "justificativa sucinta e cirúrgica da correta",
  "distratores": [
    {{"letter": "LETRA", "text": "Incorreta. Explicação clínica do erro e do distrator..."}}
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

def process_question(qid: int, original_text: str, stem: str, alts: list, correct_letter: str, topic: str, subtema: str) -> tuple[int, str, bool]:
    orig_urls = extract_image_urls(original_text)
    
    # Extrai o raciocínio clínico já existente no comentário do professor se houver
    rac_match = re.search(r'\*\*Raciocínio Clínico\*\*:(.*?)(?=\*\*Por que a Letra|\*\*Análise dos Distratores|$)', original_text, re.DOTALL)
    existing_rac = rac_match.group(1).strip() if rac_match else ""
    
    # Chama o Argon
    infill_data = call_argon_infill(stem, alts, correct_letter, topic, subtema, existing_rac)
    
    pulo_novo = infill_data.get("pulo_do_gato", "").strip()
    correta_nova = infill_data.get("por_que_correta", "").strip()
    distratores_novos = infill_data.get("distratores", [])
    
    # Formata bloco de distratores
    dist_lines = []
    for d in distratores_novos:
        letra = d.get("letter", "").strip().upper()
        texto = d.get("text", "").strip()
        if texto.startswith("Incorreta."):
            texto = texto[len("Incorreta."):].strip()
        dist_lines.append(f"- **Letra {letra}**: {texto}")
        
    dist_bloco = "\n".join(dist_lines)
    
    # Preserva o início do comentário e imagens
    new_text = original_text
    
    # 1. Substitui Pulo do Gato se o original era genérico
    if "Atenção aos conceitos centrais e critérios diagnósticos explorados" in original_text and pulo_novo:
        new_text = re.sub(
            r'\*\*Pulo do Gato\*\*:\s*Atenção aos conceitos centrais[^\n]+',
            f'**Pulo do Gato**:\n{pulo_novo}',
            new_text
        )
        
    # 2. Substitui Correta se o original era genérico
    if "Alternativa correta conforme as diretrizes e raciocínio clínico apresentados" in original_text and correta_nova:
        new_text = re.sub(
            r'\*\*Por que a Letra [A-E] é a Correta\?\*\*:\s*Alternativa correta conforme as diretrizes[^\n]+',
            f'**Por que a Letra {correct_letter} é a Correta?**:\n{correta_nova}',
            new_text
        )
        
    # 3. Substitui a Análise dos Distratores
    # Remove qualquer bloco anterior de distratores boilerplate
    new_text = re.sub(r'\*\*Análise dos Distratores\*\*:\s*(\n\s*[-•*]\s*\*\*Letra\s+[A-E]\*\*:\s*Incorreta\.?)+', f'**Análise dos Distratores**:\n{dist_bloco}', new_text, flags=re.MULTILINE)
    # Remove linhas residuais de 'Letra X: Incorreta' no final do texto
    new_text = re.sub(r'(?:\n\s*[-•*]\s*\*\*Letra\s+[A-E]\*\*:\s*Incorreta\.?)+$', '', new_text.strip()) + '\n'
        
    # Validação estrita de Paridade de Imagens (Zero-Drop)
    new_urls = extract_image_urls(new_text)
    if orig_urls != new_urls:
        # Se houve divergência acidental, reanexa as imagens originais
        for u in orig_urls:
            if u not in new_urls:
                new_text += f"\n\n![imagem]({u})"
                
    final_urls = extract_image_urls(new_text)
    assert set(orig_urls) == set(final_urls), f"Quebra de paridade de imagens no QID {qid}"
    
    return qid, new_text, (new_text != original_text)

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(f"🚀 Iniciando Enriquecimento Cirúrgico de Distratores com Gemini 4 Argon (Limite: {limit or 'TOTAL'})...")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT e.question_id, e.explanation_text, q.stem, q.correct_letter, q.topic, q.subtema
        FROM explanations e
        JOIN questions q ON e.question_id = q.id
        WHERE (e.explanation_text LIKE '%- **Letra B**: Incorreta.%'
           OR e.explanation_text LIKE '%- **Letra C**: Incorreta.%'
           OR e.explanation_text LIKE '%- **Letra D**: Incorreta.%')
        ORDER BY e.question_id
    """
    if limit:
        query += f" LIMIT {limit}"
        
    targets = cursor.execute(query).fetchall()
    print(f"🎯 Total de questões a processar neste ciclo: {len(targets)}")
    
    if not targets:
        print("✅ Nenhuma questão pendente de enriquecimento encontrada!")
        return

    # Pré-carrega alternativas
    q_ids = [t[0] for t in targets]
    placeholders = ",".join("?" * len(q_ids))
    alts_rows = cursor.execute(f"SELECT question_id, letter, text FROM alternatives WHERE question_id IN ({placeholders}) ORDER BY letter", q_ids).fetchall()
    alts_by_q = {}
    for qid, let, txt in alts_rows:
        alts_by_q.setdefault(qid, []).append((let, txt))
        
    completed = 0
    updated = 0
    t0 = time.time()
    
    # Processamento concorrente com 10 workers (seguro para cota GCP Nível 1)
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {}
        for row in targets:
            qid, exp_text, stem, c_let, topic, subtema = row
            alts = alts_by_q.get(qid, [])
            fut = executor.submit(process_question, qid, exp_text, stem, alts, c_let, topic, subtema)
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
                    print(f"[{completed}/{len(targets)}] QID {qid} processada | Atualizadas: {updated} | Velocidade: {rate:.1f} q/s")
            except Exception as e:
                print(f"⚠️ Erro ao processar QID {qid}: {e}")
                
    conn.close()
    print(f"\n🎉 Ciclo concluído! Total processado: {completed} | Atualizadas no banco: {updated} em {(time.time() - t0):.1f}s")

if __name__ == "__main__":
    main()
