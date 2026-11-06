#!/usr/bin/env python3
"""
Script de correção de distratores e alternativas deslocadas dentro do Raciocínio Clínico.

Identifica e repara explicações onde as alternativas (A - Correta, B - Incorreta, etc.)
e/ou a "Visão do aprovado" foram inadvertidamente incorporadas dentro do bloco de
Raciocínio Clínico, preenchendo as seções canônicas do Template Ouro:
  1. Gabarito
  2. Pulo do Gato (com a Visão do aprovado real)
  3. Raciocínio Clínico (limpo, focado na discussão do caso)
  4. Por que a Letra [X] é a Correta? (com o texto real da alternativa)
  5. Análise dos Distratores (com o texto real de cada distrator)
"""

import os
import sys
import re
import sqlite3
import argparse
from typing import Dict, List, Tuple, Optional

# Garantir path raiz do backend para imports de db se necessário
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

DEFAULT_DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")

STATUS_WORDS = r'(?:Corret[ao]s?|Incorret[ao]s?|Cert[ao]s?|Errad[ao]s?|Fals[ao]s?|Verdadeir[ao]s?)'

# Regex para identificar marcadores de alternativas dentro do Raciocínio Clínico
ALT_MARKER_REGEX = re.compile(
    r'(?:^|\n|\.\s{1,2}|\*\*\s+)'
    r'\s*'
    r'(?:\*{1,2})?'
    r'(?:[-*•]\s*)?'
    r'(?:'
    r'([A-E])\s*(?:[–—\-:]|(?:\.\s*)|\)\s*)\s*(?:\*{1,2})?\s*(?:alternativa\s+)?' + STATUS_WORDS +
    r'|'
    r'(?:Alternativa|Letra)\s+([A-E])\s*(?:\*{1,2})?\s*(?:[–—\-:]|(?:\.\s*)|\)\s*)\s*(?:\*{1,2})?\s*(?:(?:alternativa\s+)?' + STATUS_WORDS + r')?'
    r'|'
    r'(?:Alternativa|Letra)\s+([A-E])\s*(?:\*{1,2})?\s*:'
    r')'
    r'(?:\*{1,2})?'
    r'(?:\.|\s*[-–—:]|\s*\([^)]*\))?',
    re.IGNORECASE
)

# Frases de transição pré-alternativas
INTRO_TRANSITION_REGEX = re.compile(
    r'(?:\n\s*)*'
    r'(?:'
    r'(?:(?:E\s+)?(?:vamos|vejamos|veja|analisando|analisemos|vamos\s+avaliar|vamos\s+analisar|avaliando)\s+(?:às|as|nossas|cada)\s+(?:alternativas|opções)[^:\n]*:?)'
    r'|'
    r'(?:Análise\s+(?:das\s+)?(?:alternativas|opções)[^:\n]*:?)'
    r'|'
    r'(?:Vamos\s+às\s+alternativas[^:\n]*:?)'
    r')\s*$',
    re.IGNORECASE
)

VISA_DO_APROVADO_REGEX = re.compile(
    r'(?:^|\n)\s*(?:\*{1,2})?(?:Visão\s+do\s+[Aa]provado|Dica\s+do\s+[Aa]provado|Pulo\s+do\s+[Gg]ato)(?:\*{1,2})?\s*:?\s*(?:\*{1,2})?\s*',
    re.IGNORECASE
)

GENERIC_PULO_PHRASES = [
    'Atenção aos conceitos centrais e critérios diagnósticos explorados pela banca examinadora.',
    'Atenção aos conceitos centrais e critérios diagnósticos explorados pela banca.',
    'Atenção aos critérios diagnósticos e conceitos centrais explorados pela banca.',
    'Atenção aos conceitos centrais',
]

def is_generic_pulo(pulo_text: str) -> bool:
    if not pulo_text:
        return True
    cleaned = pulo_text.strip()
    return any(cleaned == p or cleaned.startswith(p) for p in GENERIC_PULO_PHRASES)

def is_placeholder_distractor(text: str) -> bool:
    if not text:
        return True
    t = text.strip()
    lines = [l.strip() for l in t.split('\n') if l.strip()]
    if not lines:
        return True
    return all(
        re.match(r'^-\s*\*\*Letra\s+[A-E]\*\*:\s*(?:Incorret[ao]\.?|Alternativa avaliada conforme o raciocínio[^\n]*)$', l, re.I)
        for l in lines
    )

def is_placeholder_correta(text: str) -> bool:
    if not text:
        return True
    t = text.strip()
    return (
        'Alternativa correta conforme as diretrizes e raciocínio clínico apresentados.' in t
        or 'Alternativa avaliada conforme o raciocínio clínico apresentado.' in t
        or t == 'Correta.'
        or t == 'Incorreta.'
    )

def clean_alternative_body(text: str) -> str:
    cleaned = text.strip()
    # Remove pontuação inicial, bullets ou asteriscos
    cleaned = re.sub(r'^[\s*.:–—\-!•]+', '', cleaned)
    # Remove prefixos de status como Correta. / Incorreta. / Correta!
    cleaned = re.sub(r'^(?:Corret[ao]s?|Incorret[ao]s?|Cert[ao]s?|Errad[ao]s?|Fals[ao]s?|Verdadeir[ao]s?)(?:\s*\([^)]*\))?[\s*.:–—\-!•]*\s*', '', cleaned, flags=re.I)
    # Limpa pontuação residual após o status
    cleaned = re.sub(r'^[\s*.:–—\-!•]+', '', cleaned)
    # Remove asteriscos e espaços finais
    cleaned = re.sub(r'[\s*]+$', '', cleaned).strip()
    return cleaned

def parse_and_fix_explanation(
    qid: int, 
    correct_letter: str, 
    explanation_text: str,
    available_letters: List[str]
) -> Tuple[bool, str, Dict]:
    """
    Analisa explanation_text, extrai alternativas/distratores deslocados de Raciocínio Clínico
    e retorna (changed: bool, new_explanation: str, debug_info: dict).
    """
    if not explanation_text:
        return False, explanation_text, {}

    # 1. Separar seções existentes
    sections = {}
    current_sec = "header"
    sec_content = []
    
    header_regex = re.compile(
        r'^(?:\*{1,2})?(Gabarito|Pulo do Gato|Raciocínio Clínico|Por que a Letra [^\n*:]+ é a Correta\?|Análise dos Distratores|Referências Bibliográficas)(?:\*{1,2})?:\s*(.*)$',
        re.IGNORECASE
    )

    lines = explanation_text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        m = header_regex.match(line)
        if m:
            if current_sec:
                sections[current_sec] = '\n'.join(sec_content).strip()
            sec_name_raw = m.group(1).lower()
            if 'gabarito' in sec_name_raw:
                current_sec = 'gabarito'
            elif 'pulo do gato' in sec_name_raw:
                current_sec = 'pulo'
            elif 'raciocínio clínico' in sec_name_raw:
                current_sec = 'raciocinio'
            elif 'por que a letra' in sec_name_raw:
                current_sec = 'correta'
            elif 'distratores' in sec_name_raw:
                current_sec = 'distratores'
            elif 'referências' in sec_name_raw:
                current_sec = 'referencias'
            else:
                current_sec = sec_name_raw
            
            rest = m.group(2).strip()
            sec_content = [rest] if rest else []
        else:
            sec_content.append(line)
        i += 1
    if current_sec:
        sections[current_sec] = '\n'.join(sec_content).strip()

    rac_text = sections.get('raciocinio', '')
    if not rac_text:
        return False, explanation_text, {}

    # 2. Localizar marcadores de alternativas em raciocinio
    matches = list(ALT_MARKER_REGEX.finditer(rac_text))
    if len(matches) < 2:
        return False, explanation_text, {}

    matched_items = []
    for m in matches:
        let = (m.group(1) or m.group(2) or m.group(3) or '').upper()
        if let and let in 'ABCDE':
            matched_items.append((let, m.start(), m.end()))

    if len(matched_items) < 2:
        return False, explanation_text, {}

    letters_seen = [item[0] for item in matched_items]
    if len(set(letters_seen)) < 2:
        return False, explanation_text, {}

    first_alt_pos = matched_items[0][1]
    
    # 3. Limpar o Raciocínio Clínico até antes da primeira alternativa
    new_raciocinio = rac_text[:first_alt_pos].rstrip()
    new_raciocinio = INTRO_TRANSITION_REGEX.sub('', new_raciocinio).rstrip()

    # 4. Extrair texto de cada alternativa e "Visão do aprovado" trailing
    alt_texts = {}
    visao_aprovado_text = ""

    last_alt_text_end = len(rac_text)
    last_item_pos = matched_items[-1][2]
    after_last = rac_text[last_item_pos:]
    visao_m = VISA_DO_APROVADO_REGEX.search(after_last)
    if visao_m:
        visao_start = last_item_pos + visao_m.start()
        visao_content_start = last_item_pos + visao_m.end()
        visao_aprovado_text = rac_text[visao_content_start:].strip()
        last_alt_text_end = visao_start

    for idx in range(len(matched_items)):
        let, start_pos, end_pos = matched_items[idx]
        next_pos = matched_items[idx + 1][1] if idx + 1 < len(matched_items) else last_alt_text_end
        raw_body = rac_text[end_pos:next_pos]
        cleaned_body = clean_alternative_body(raw_body)
        alt_texts[let] = cleaned_body

    # 5. Pulo do Gato
    current_pulo = sections.get('pulo', '')
    new_pulo = current_pulo
    if visao_aprovado_text and is_generic_pulo(current_pulo):
        new_pulo = visao_aprovado_text
    elif not current_pulo and visao_aprovado_text:
        new_pulo = visao_aprovado_text

    # 6. Por que a Letra {correct_letter} é a Correta
    correct_letters_list = [l.upper() for l in re.findall(r'[A-E]', correct_letter or '')]
    if not correct_letters_list:
        correct_letters_list = ['A']

    current_correta = sections.get('correta', '')
    
    if len(correct_letters_list) > 1:
        corr_lines = []
        for c_let in correct_letters_list:
            b = alt_texts.get(c_let, '').strip()
            if b:
                corr_lines.append(f"- **Letra {c_let}**: {b}")
            else:
                corr_lines.append(f"- **Letra {c_let}**: Alternativa correta conforme as diretrizes e raciocínio clínico apresentados.")
        new_correta = '\n'.join(corr_lines)
    else:
        single_corr = correct_letters_list[0]
        extracted_correta_body = alt_texts.get(single_corr, '').strip()
        if extracted_correta_body:
            new_correta = extracted_correta_body
        elif current_correta and not is_placeholder_correta(current_correta):
            new_correta = current_correta
        else:
            new_correta = "Alternativa correta conforme as diretrizes e raciocínio clínico apresentados."

    # 7. Análise dos Distratores
    current_dist = sections.get('distratores', '')
    dist_is_placeholder = is_placeholder_distractor(current_dist)

    all_options = sorted(list(set(available_letters or ['A', 'B', 'C', 'D'])))
    distractor_letters = [l for l in all_options if l not in correct_letters_list]

    dist_lines = []
    existing_dist_map = {}
    if not dist_is_placeholder and current_dist:
        for line in current_dist.split('\n'):
            line_m = re.match(r'^-\s*\*\*Letra\s+([A-E])\*\*:\s*(.*)$', line.strip(), re.I)
            if line_m:
                existing_dist_map[line_m.group(1).upper()] = line_m.group(2).strip()

    for d_let in distractor_letters:
        if d_let in existing_dist_map and existing_dist_map[d_let] and not is_placeholder_correta(existing_dist_map[d_let]):
            dist_lines.append(f"- **Letra {d_let}**: {existing_dist_map[d_let]}")
        elif d_let in alt_texts and alt_texts[d_let]:
            dist_lines.append(f"- **Letra {d_let}**: {alt_texts[d_let]}")
        else:
            dist_lines.append(f"- **Letra {d_let}**: Incorreta.")

    new_distratores = '\n'.join(dist_lines)

    # 8. Montar explicação no padrão oficial
    gabarito_val = sections.get('gabarito', f"Letra {correct_letter}")
    if not gabarito_val:
        gabarito_val = f"Letra {correct_letter}"

    parts = [f"**Gabarito**: {gabarito_val}"]
    if new_pulo:
        parts.append(f"**Pulo do Gato**:\n{new_pulo}")
    if new_raciocinio:
        parts.append(f"**Raciocínio Clínico**:\n{new_raciocinio}")
    if new_correta:
        parts.append(f"**Por que a Letra {correct_letter} é a Correta?**:\n{new_correta}")
    if new_distratores:
        parts.append(f"**Análise dos Distratores**:\n{new_distratores}")
    if 'referencias' in sections and sections['referencias']:
        parts.append(f"**Referências Bibliográficas**:\n{sections['referencias']}")

    new_explanation = "\n\n".join(parts)
    return True, new_explanation, {
        "extracted_letters": list(alt_texts.keys()),
        "has_visao_aprovado": bool(visao_aprovado_text),
        "updated_pulo": new_pulo != current_pulo,
        "updated_correta": new_correta != current_correta,
        "updated_dist": new_distratores != current_dist
    }


def main():
    parser = argparse.ArgumentParser(description="Corrige distratores dentro do raciocínio clínico no MedQuest.")
    parser.add_argument("--commit", action="store_true", help="Efetiva as alterações no banco de dados.")
    parser.add_argument("--db-path", default=DEFAULT_DB_PATH, help="Caminho para o medquest.db")
    parser.add_argument("--limit", type=int, default=0, help="Limita o número de questões processadas (0 = sem limite)")
    args = parser.parse_args()

    if not os.path.exists(args.db_path):
        print(f"Erro: banco de dados não encontrado em {args.db_path}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(args.db_path)
    c = conn.cursor()

    c.execute("""
        SELECT q.id, q.source_file, q.correct_letter, e.explanation_text
        FROM questions q
        JOIN explanations e ON q.id = e.question_id
        WHERE e.explanation_text IS NOT NULL
    """)
    rows = c.fetchall()
    print(f"Total de questões com explicações carregadas: {len(rows)}")

    # Carregar alternativas de cada questão
    c.execute("SELECT question_id, letter FROM alternatives ORDER BY question_id, letter")
    alt_map = {}
    for qid, let in c.fetchall():
        alt_map.setdefault(qid, []).append(let)

    to_update = []
    pulo_promoted = 0

    for qid, src, corr, exp in rows:
        alts = alt_map.get(qid, ['A', 'B', 'C', 'D'])
        changed, new_exp, dbg = parse_and_fix_explanation(qid, corr, exp, alts)
        if changed:
            to_update.append((new_exp, qid))
            if dbg.get("updated_pulo"):
                pulo_promoted += 1
            if args.limit > 0 and len(to_update) >= args.limit:
                break

    print(f"Questões identificadas para correção: {len(to_update)}")
    print(f"Pulos do Gato enriquecidos com 'Visão do aprovado': {pulo_promoted}")

    if args.commit:
        print("Aplicando correções no banco de dados...")
        c.executemany("UPDATE explanations SET explanation_text = ? WHERE question_id = ?", to_update)
        conn.commit()
        print(f"Sucesso! {len(to_update)} explicações atualizadas com sucesso no banco de dados.")
    else:
        print("\nModo DRY-RUN (simulação). Nenhuma alteração foi persistida no banco.")
        print("Execute com --commit para gravar as alterações.")

    conn.close()


if __name__ == '__main__':
    main()
