import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote

from api.gemini_pool import gemini_pool
from .adaptive_tools import format_student_diagnostic_block, get_student_weak_topics
from .knowledge import format_grounding_block, retrieve_medical_context
from .universal_pool import generate_content_with_fallback

logger = logging.getLogger(__name__)

# In-memory TTL cache for semantic search expansions (avoids redundant AI calls)
_search_cache = {}  # key: normalized query -> (timestamp, result)
_SEARCH_CACHE_TTL = 300  # 5 minutes
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")

def _clean_option_text(text: str) -> str:
    """Remove prefixos de alternativas como 'A) ', 'B - ', etc."""
    if not text:
        return ""
    return re.sub(r'^[A-Ea-e][\)\.\:\-]\s*', '', text).strip()


def _extract_pulo_do_gato(explanation: str) -> str:
    if not explanation:
        return ""
    # Captura a seção inteira do Pulo do Gato até o próximo cabeçalho estruturado ou fim do texto,
    # garantindo máxima relevância clínica e profundidade médica sem truncamento artificial (Guardrail 5).
    match = re.search(
        r'(?:\*\*Pulo[\s_]+do[\s_]+Gato:?\*\*|\*\*Pulo[\s_]+do[\s_]+Gato\*\*|💡\s*\*\*Pulo do Gato\*\*|Pulo[\s_]+do[\s_]+Gato):?\s*([\s\S]*?)(?=(?:\n\s*\n\s*(?:#{1,6}\s+|\*\*[A-ZÀ-Úa-zà-ú0-9#]|[-*+]\s+\*\*)|(?:\n\s*(?:#{1,6}\s+|\*\*[A-ZÀ-Úa-zà-ú0-9#]))|\Z))',
        explanation,
        re.IGNORECASE
    )
    if match:
        pulo = match.group(1).strip()
        if pulo:
            return pulo
    match_fallback = re.search(
        r'(?:\*\*Pulo[\s_]+do[\s_]+Gato:?\*\*|\*\*Pulo[\s_]+do[\s_]+Gato\*\*|💡\s*\*\*Pulo do Gato\*\*|Pulo[\s_]+do[\s_]+Gato):?\s*([^\n\r]+)',
        explanation,
        re.IGNORECASE
    )
    if match_fallback:
        return match_fallback.group(1).strip()
    return ""


def _extract_why_wrong(explanation: str, wrong_letter: str, wrong_text: str) -> str:
    if not explanation or not wrong_letter:
        return ""
    pattern = rf'(?:-\s*)?\*\*Alternativa[^\n]*\({re.escape(wrong_letter)}\)[^\n]*\*\*:\s*([\s\S]*?)(?=(?:\n\s*(?:-\s*\*\*|\*\*|###)|\Z))'
    match = re.search(pattern, explanation, re.IGNORECASE)
    if not match:
        pattern2 = rf'(?:-\s*)?\*\*Alternativa\s+{re.escape(wrong_letter)}[^\n]*\*\*:\s*([\s\S]*?)(?=(?:\n\s*(?:-\s*\*\*|\*\*|###)|\Z))'
        match = re.search(pattern2, explanation, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return ""


def _extract_clinical_scenario(stem: str) -> str:
    if not stem:
        return ""
    cleaned_stem = re.sub(r'\s+', ' ', stem.strip())
    end_patterns = [
        r'(?:Diante disso|Diante do exposto|Diante desse quadro|Nesse momento|Nesse caso|Considerando o caso|Em relação ao caso|Sobre o caso descrito|Com base no caso|A respeito do quadro|Considerando as diretrizes|Com base nessas informações|Assinale a alternativa|Qual a conduta|Qual o diagnóstico|Qual é o diagnóstico|O diagnóstico mais provável|A melhor conduta|A conduta mais adequada|O manejo inicial|O exame padrão-ouro|O próximo passo).*$',
        r'(?:é correto afirmar|assinale a opção|assinale a assertiva|indique a conduta).*$'
    ]
    scenario = cleaned_stem
    for pat in end_patterns:
        m = re.search(pat, scenario, re.IGNORECASE)
        if m and m.start() > 30:
            scenario = scenario[:m.start()].strip()
            break
    scenario = re.sub(r'[\s,;:]+$', '', scenario).strip()
    if scenario and not scenario.endswith('.'):
        scenario += '.'
    return scenario


def _determine_question_type(stem: str, correct_text: str) -> str:
    combined = (stem + " " + correct_text).lower()
    if any(w in combined for w in ["conduta", "tratamento", "manejo", "terapêutica", "terapia", "medicação", "droga", "prescrever", "cirurgia"]):
        return "Conduta / Manejo indicado"
    if any(w in combined for w in ["diagnóstico", "hipótese diagnóstica", "quadro clínico sugere", "provável diagnóstico"]):
        return "Diagnóstico mais provável"
    if any(w in combined for w in ["exame", "solicitar", "investigação", "método complementar", "padrão-ouro"]):
        return "Investigação / Exame complementar"
    if any(w in combined for w in ["fisiopatologia", "mecanismo", "etiologia", "causa"]):
        return "Mecanismo / Fisiopatologia"
    return "Conceito Chave"


def _extract_key_clinical_data(stem: str) -> str:
    """Extract key clinical findings (labs, vitals, imaging) from the stem.

    Returns a compact bullet list of salient data points so that the flashcard
    front preserves the diagnostic clues instead of losing them in a vague
    1-sentence summary.
    """
    if not stem:
        return ""
    findings = []

    # Lab values: e.g. "Hb 7,2 g/dL", "leucócitos: 18.000", "PCR 120 mg/L"
    lab_pattern = re.compile(
        r'(?:Hb|Hemoglobina|Ht|Hematócrito|Leucócitos|Plaquetas|PCR|VHS|'
        r'Creatinina|Ureia|Potássio|Sódio|Glicemia|HbA1c|TSH|T4|TGO|TGP|'
        r'Bilirrubina|Albumina|INR|TP|TTPA|Lactato|pH|pO2|pCO2|HCO3|BE|'
        r'Troponina|BNP|NT-proBNP|Amilase|Lipase|Cálcio|Magnésio|Fósforo|'
        r'Ferritina|Ferro sérico|Saturação de transferrina|DHL|LDH|FA|GGT|'
        r'Fibrinogênio|D-dímero|CEA|CA-?125|CA-?19|AFP|PSA|Beta-?HCG)'
        r'\s*[:=]?\s*[\d]+[,.]?[\d]*\s*(?:g/dL|mg/dL|mg/L|mEq/L|mmol/L|'
        r'µg/L|ng/mL|pg/mL|U/L|mm³|/mm³|cel/mm³|%|mmHg|mUI/mL|UI/L|'
        r'mil/mm³|×\s*10[³⁹])?',
        re.IGNORECASE
    )
    for m in lab_pattern.finditer(stem):
        findings.append(m.group().strip())

    # Vital signs: e.g. "PA: 80x50 mmHg", "FC: 120 bpm", "Tax: 38,5°C"
    vitals_pattern = re.compile(
        r'(?:PA|Pressão arterial|FC|Frequência cardíaca|FR|Frequência respiratória|'
        r'Tax?|Temperatura|SpO2|SatO2|Sat\.?\s*O2|Glasgow)'
        r'\s*[:=]?\s*[\d]+[,./x]?[\d]*\s*(?:mmHg|bpm|irpm|°C|%)?',
        re.IGNORECASE
    )
    for m in vitals_pattern.finditer(stem):
        val = m.group().strip()
        if val not in findings:
            findings.append(val)

    # Deduplicate preserving order, cap at 6 most relevant
    seen = set()
    unique = []
    for f in findings:
        key = f.lower()
        if key not in seen:
            seen.add(key)
            unique.append(f)
    return " | ".join(unique[:6])


def _extract_clinical_pearl(explanation: str) -> str:
    """Extract a concise clinical teaching pearl from the explanation.

    Looks for patterns like 'Lembre-se:', 'Atenção:', 'Importante:', 'Dica:',
    or bold sentences that contain a clinical rule/guideline.
    """
    if not explanation:
        return ""
    # Direct teaching patterns
    pearl_patterns = [
        r'(?:Lembre-se|Atenção|Importante|Dica|Regra|Conceito[- ]chave|Palavra[- ]chave|Macete):?\s*([^\n\r]+)',
        r'\*\*(?:Lembre-se|Atenção|Importante|Dica|Regra)\*\*:?\s*([^\n\r]+)',
    ]
    for pat in pearl_patterns:
        m = re.search(pat, explanation, re.IGNORECASE)
        if m:
            pearl = m.group(1).strip().rstrip('.')
            if 15 < len(pearl) < 200:
                return pearl + '.'
    return ""


# Mapping from question type to a short cloze hint for {{c1::answer::hint}}
_CLOZE_HINT_MAP = {
    "Conduta / Manejo indicado": "conduta",
    "Diagnóstico mais provável": "diagnóstico",
    "Investigação / Exame complementar": "exame",
    "Mecanismo / Fisiopatologia": "mecanismo",
    "Conceito Chave": "conceito",
}


def _extract_medical_cloze_fallback(
    stem: str,
    correct_text: str,
    wrong_text: str,
    explanation: str = "",
    area: str = "",
    subtema: str = "",
    topic: str = "",
    correct_letter: str = "",
    wrong_letter: str = ""
) -> dict:
    """
    Gera um Cloze Flashcard didático, clínico e de alta qualidade baseado no erro médico,
    com contexto do caso, pergunta clínica focada, Pulo do Gato e análise de distrator.
    Preserva achados clínicos-chave (labs, sinais vitais) para não perder contexto.
    """
    # O fallback também é chamado diretamente quando os provedores de IA estão
    # indisponíveis; portanto, não pode depender da normalização feita pela
    # função chamadora.
    correct_clean = _clean_option_text(correct_text)
    wrong_clean = _clean_option_text(wrong_text)
    is_dummy_text = any(phrase in correct_clean.lower() for phrase in ["anote sua", "questao dissertativa", "questão dissertativa", "padrao de resposta", "padrão de resposta"])
    pulo = _extract_pulo_do_gato(explanation)
    
    if is_dummy_text:
        # Extrai resposta alvo do pulo do gato ou explicação
        if pulo and len(pulo) < 120:
            target_cloze = pulo
        else:
            target_cloze = "Ver Padrão de Resposta / Pulo do Gato"
    else:
        target_cloze = correct_clean

    scenario = _extract_clinical_scenario(stem)
    q_type = _determine_question_type(stem, target_cloze)
    why_wrong = _extract_why_wrong(explanation, wrong_letter, wrong_clean)
    clinical_data = _extract_key_clinical_data(stem)
    pearl = _extract_clinical_pearl(explanation)
    cloze_hint = _CLOZE_HINT_MAP.get(q_type, "")
    
    # Build cloze with hint for better context retention
    if cloze_hint:
        cloze_str = f"{{{{c1::{target_cloze}::{cloze_hint}}}}}"
    else:
        cloze_str = f"{{{{c1::{target_cloze}}}}}"
    
    # Build front: scenario + key clinical data + question (no [Tema] tag — shown via UI badge)
    front_parts = []
    if scenario and len(scenario) > 20:
        front_parts.append(scenario)
    if clinical_data:
        front_parts.append(f"📊 {clinical_data}")
    
    if front_parts:
        front = front_parts[0]
        extra = front_parts[1:]
        if extra:
            front = front + "\n" + "\n".join(extra)
        front = front + f"\n\n👉 {q_type}: {cloze_str}"
    else:
        front = f"👉 {q_type}: {cloze_str}"
        
    back_sections = []
    if pulo:
        back_sections.append(f"💡 Pulo do Gato:\n{pulo}")
        
    if why_wrong:
        back_sections.append(f"⚠️ Por que não '{wrong_clean}'?\n{why_wrong}")
    elif wrong_clean and wrong_clean.lower() != correct_clean.lower():
        back_sections.append(f"⚠️ Atenção ao distrator:\nA opção '{wrong_clean}' é incorreta para este quadro clínico.")

    # Add clinical pearl if different from pulo do gato
    if pearl and pearl != pulo and pearl not in (pulo or ""):
        back_sections.append(f"🎯 Pérola Clínica:\n{pearl}")
        
    if not pulo and not why_wrong and explanation:
        clean_exp = re.sub(r'(\*\*.*?\*\*|###.*?\n|##.*?\n)', '', explanation).strip()
        sentences = [s.strip() for s in re.split(r'[\.\\n]+', clean_exp) if len(s.strip()) > 15]
        if sentences:
            back_sections.append(f"📚 Racional:\n{'. '.join(sentences[:3])}.")
            
    if not back_sections:
        back_sections.append(f"Gabarito Oficial:\n{correct_clean}")
        
    back = "\n\n".join(back_sections)
    context_str = f"{area} > {subtema}" if area and subtema else (area or subtema or "MedQuest Residência")
    
    return {
        "front": front,
        "back": back,
        "context": context_str
    }


def generate_cloze_flashcard(
    stem: str,
    correct_text: str,
    wrong_text: str,
    explanation: str = "",
    area: str = "",
    subtema: str = "",
    topic: str = "",
    correct_letter: str = "",
    wrong_letter: str = ""
) -> dict:
    """
    Gera um flashcard no formato Cloze de alta fidelidade médica.
    Se AI (Gemini) estiver disponível, sintetiza com IA; caso contrário, executa o extrator determinístico.
    """
    correct_clean = _clean_option_text(correct_text)
    wrong_clean = _clean_option_text(wrong_text)

    # Extract key clinical data to feed into the prompt for context retention
    clinical_data = _extract_key_clinical_data(stem)
    clinical_data_instruction = ""
    if clinical_data:
        clinical_data_instruction = f"""   - OBRIGATÓRIO: Inclua os achados clínicos-chave do caso na linha de dados: "📊 {clinical_data}"
"""

    prompt_wrong_section = f"""O QUE O ALUNO MARCOU (ERRADO):
{wrong_clean}

A RESPOSTA CORRETA (GABARITO):
{correct_clean}
""" if wrong_clean else f"""A RESPOSTA CORRETA (GABARITO):
{correct_clean}
"""

    prompt_back_wrong = f"""   - "⚠️ Por que não '{wrong_clean}'?": explique a armadilha clínica do distrator em 1-2 frases — o que levaria alguém a errar e por que está errado.
""" if wrong_clean else ""

    q_type = _determine_question_type(stem, correct_clean)
    cloze_hint = _CLOZE_HINT_MAP.get(q_type, "conceito")

    prompt = f"""
Você é um preceptor médico especialista em preparação para residência médica (USP, SUS-SP, ENARE).
Crie um flashcard PERFEITO no formato Cloze para repetição espaçada (FSRS).

O flashcard DEVE ser autocontido — ao ler apenas o card, sem ver a questão original, o aluno deve entender o caso clínico, os achados relevantes e o que está sendo perguntado.

ÁREA/TEMA: {area} - {subtema or topic}

ENUNCIADO DA QUESTÃO:
{stem}

{prompt_wrong_section}
COMENTÁRIO/EXPLICAÇÃO DO PROFESSOR:
{explanation or 'Nenhuma explicação fornecida.'}

DIRETRIZES OBRIGATÓRIAS PARA O CAMPO "front":
1. NÃO inclua tags de tema como "[Tema]" ou "[Subtema]" no início — o tema já é exibido na interface.
2. Comece diretamente com o cenário clínico em 2-4 frases, preservando TODOS os achados-chave:
   - Dados demográficos relevantes (idade, sexo, comorbidades)
   - Sinais e sintomas cardinais (tempo de evolução, localização, caráter)
   - Achados do exame físico (sinais positivos e negativos relevantes)
{clinical_data_instruction}3. Formule a pergunta clínica usando o cloze com hint: "👉 {q_type}: {{{{c1::{correct_clean}::{cloze_hint}}}}}"
4. NUNCA mencione letras de alternativas (A, B, C, D) no flashcard.
5. NUNCA comece o front com frases genéricas como "Neste caso clínico..." ou "A alternativa correta era...".

DIRETRIZES OBRIGATÓRIAS PARA O CAMPO "back":
1. "💡 Pulo do Gato:" — a regra de ouro médica que diferencia a resposta correta (1-3 frases objetivas e de alto rendimento).
{prompt_back_wrong}2. "🎯 Pérola Clínica:" — um ensino prático memorável (mnemônico, regra, conduta-padrão ou guideline) que o aluno pode levar para a prova. Máximo 2 frases.

CAMPO "context": "{area} > {subtema or topic}"

Responda EXCLUSIVAMENTE em JSON válido:
{{
  "front": "Cenário clínico detalhado com achados-chave...\\n📊 Dados laboratoriais/vitais relevantes\\n\\n👉 Pergunta: {{{{c1::resposta::{cloze_hint}}}}}",
  "back": "💡 Pulo do Gato:\\n...\\n\\n⚠️ Por que não 'distrator'?\\n...\\n\\n🎯 Pérola Clínica:\\n...",
  "context": "{area} > {subtema or topic}"
}}
"""

    # Padrões que indicam que a IA gerou um card de baixa qualidade (formato legado)
    _LOW_QUALITY_PATTERNS = [
        "A alternativa correta era",
        "alternativa correta era",
        "Neste caso clínico, em vez de",
        "Para este quadro clínico,",
        "Você marcou",
    ]

    def _is_low_quality(card: dict) -> bool:
        front = card.get("front", "")
        back = card.get("back", "")
        # Rejeita se o front contém padrões genéricos
        for pat in _LOW_QUALITY_PATTERNS:
            if pat in front:
                return True
        # Rejeita se o front contém letras de alternativa no cloze (ex: {{c1::A) ...}})
        cloze_match = re.search(r'{{c1::(.*?)}}', front)
        if cloze_match:
            cloze_content = cloze_match.group(1)
            if re.match(r'^[A-Ea-e][\)\.\:\-]\s', cloze_content):
                return True
        # Rejeita se o back é apenas "Você marcou..." ou "Alternativa correta:"
        if back.startswith("Você marcou") or back == f"Alternativa correta: {cloze_match.group(1) if cloze_match else ''}.":
            return True
        # Rejeita se o front tem cenário muito curto (contexto perdido)
        # Extrai a parte do cenário (tudo antes de 👉)
        scenario_part = front.split("👉")[0] if "👉" in front else front
        # Remove a tag [Tema] para medir só o cenário real
        scenario_text = re.sub(r'^\[.*?\]\s*', '', scenario_part).strip()
        if len(scenario_text) < 30:
            logger.info("IA retornou card com cenário muito curto (%d chars), rejeitando.", len(scenario_text))
            return True
        return False

    def _sanitize_ai_card(card: dict) -> dict:
        """Remove letras de alternativa do cloze e limpa artefatos da IA."""
        front = card.get("front", "")
        back = card.get("back", "")
        # Remove letras dentro do cloze: {{c1::A) Texto}} -> {{c1::Texto}}
        front = re.sub(r'{{c1::[A-Ea-e][\)\.\:\-]\s*(.*?)}}', r'{{c1::\1}}', front)
        card["front"] = front
        card["back"] = back
        return card

    # Tenta gerar via Universal AI Pool
    try:
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction="Você responde apenas em JSON válido com as chaves front, back e context. O flashcard deve ser autocontido e preservar todos os achados clínicos do caso.",
            json_mode=True,
            timeout=15
        )
        result_str = resp.get("text", "").replace("```json", "").replace("```", "").strip()
        parsed = json.loads(result_str)
        if isinstance(parsed, dict) and "front" in parsed and "{{c1::" in parsed.get("front", ""):
            if _is_low_quality(parsed):
                logger.info("IA retornou card de baixa qualidade, usando fallback determinístico.")
            else:
                return _sanitize_ai_card(parsed)
    except Exception as e:
        logger.warning(f"Falha na geração AI (todos provedores), usando fallback determinístico: {e}")

    # Fallback médico determinístico de alta qualidade
    return _extract_medical_cloze_fallback(
        stem=stem,
        correct_text=correct_text,
        wrong_text=wrong_text,
        explanation=explanation,
        area=area,
        subtema=subtema,
        topic=topic,
        correct_letter=correct_letter,
        wrong_letter=wrong_letter
    )


def expand_search_query(query: str) -> list[str]:
    """
    Usa Gemini para expandir a pesquisa em 3 a 7 sinônimos ou termos relacionados.
    Retorna uma lista de strings. Se a IA falhar ou não houver chave, retorna apenas a query original.
    Resultados são cacheados por 5 minutos para evitar chamadas redundantes à IA.
    """
    cache_key = query.strip().lower()
    now = time.time()
    if cache_key in _search_cache:
        ts, cached_result = _search_cache[cache_key]
        if now - ts < _SEARCH_CACHE_TTL:
            return cached_result
        else:
            del _search_cache[cache_key]

    if len(_search_cache) > 500:
        stale_keys = [k for k, (ts, _) in _search_cache.items() if now - ts >= _SEARCH_CACHE_TTL]
        for k in stale_keys:
            del _search_cache[k]

    def _cache_and_return(terms):
        _search_cache[cache_key] = (now, terms)
        return terms

    prompt = f"""Você é um especialista médico focado em buscas. O usuário quer pesquisar o seguinte termo: "{query}"

Retorne um JSON contendo uma lista de strings (phrases). Esta lista deve conter o termo original e de 3 a 7 sinônimos, termos técnicos ou diagnósticos diferenciais intimamente ligados à pesquisa.

Exemplo para "pressao alta": ["pressao alta", "hipertensao", "has", "crise hipertensiva", "pressao arterial"]
Exemplo para "infarto": ["infarto", "iam", "isquemia miocardica", "sindrome coronariana", "supra de st"]

Responda APENAS com o JSON. Exemplo: {{ "terms": ["...", "..."] }}
"""

    try:
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction="Você responde apenas em JSON válido.",
            json_mode=True,
            timeout=8
        )
        result_str = resp.get("text", "").replace("```json", "").replace("```", "").strip()
        data = json.loads(result_str)
        terms = data.get("terms", [])
        if terms and isinstance(terms, list):
            return _cache_and_return(terms)
    except Exception as e:
        logger.error(f"Erro na expansão via IA Universal: {e}")

    return _cache_and_return([query])



def detect_preceptor_mode(
    user_query: str,
    chat_history: Optional[List[Dict[str, str]]] = None
) -> str:
    """
    Classifica a intenção do usuário no Preceptor IA para ativar a estratégia pedagógica ideal:
    - 'foco': Diagnóstico adaptativo e planejamento de estudo (/foco, /diagnostico, etc.)
    - 'conduta': Algoritmo de conduta imediata, drogas e doses (/conduta, /protocolo, etc.)
    - 'pegadinhas': Armadilhas clássicas de bancas (/pegadinha, /pegadinhas, etc.)
    - 'round': Sabatina beira-leito com 3 perguntas afiadas (/round, /visita, etc.)
    - 'caso': Desafio clínico correlato inédito (/caso, /desafio, /simulado)
    - 'replica_desafio': Aluno respondendo a um /round ou /caso prévio
    - 'duvida_livre': Dúvida específica livre sobre a questão
    - 'discussao_geral': Explicação global da questão (padrão quando sem foco específico)
    """
    q = user_query.strip().lower()

    # 1. Comandos com barra explícitos
    if q.startswith("/foco") or q.startswith("/diagnostico"):
        return "foco"
    if q.startswith("/conduta") or q.startswith("/protocolo") or q.startswith("/manejo"):
        return "conduta"
    if q.startswith("/pegadinha") or q.startswith("/armadilha"):
        return "pegadinhas"
    if q.startswith("/round") or q.startswith("/visita") or q.startswith("/sabatina"):
        return "round"
    if q.startswith("/caso") or q.startswith("/desafio") or q.startswith("/simulado"):
        return "caso"

    # 2. Expressões em linguagem natural para foco/desempenho adaptativo
    foco_keywords = [
        "em que focar", "em que devo focar", "focar hoje", "meus pontos fracos",
        "minhas fraquezas", "onde estou errando", "meu desempenho", "o que revisar",
        "o que focar", "quais temas focar", "diagnostico adaptativo"
    ]
    if any(kw in q for kw in foco_keywords):
        return "foco"

    # 3. Réplica a um desafio anterior (/round ou /caso)
    if chat_history and len(chat_history) > 0 and q and not q.startswith("/"):
        # Localiza a última mensagem do assistente
        last_asst_msg = next(
            (m.get("content", "") for m in reversed(chat_history) if m.get("role") == "assistant"),
            ""
        ).lower()
        if last_asst_msg:
            is_prev_case = any(term in last_asst_msg for term in [
                "desafio clínico", "vinheta clínica", "qual é a sua conduta",
                "alternativas:", "alternativa a", "envie a letra", "(a)", "a)"
            ])
            is_prev_round = any(term in last_asst_msg for term in [
                "pergunta 1", "pergunta 2", "visita beira-leito", "vez do interno", "como você responde"
            ])
            if is_prev_case or is_prev_round:
                return "replica_desafio"

    # 4. Discussão geral vs dúvida livre
    if not q:
        return "discussao_geral"

    generic_starters = [
        "explique", "explicar", "comente", "comentar", "discussão", "discussao",
        "por que a correta é", "gabarito", "raciocínio", "raciocinio", "raciocínio clínico"
    ]
    if q in generic_starters or len(q) < 5:
        return "discussao_geral"

    return "duvida_livre"


def ask_preceptor_ai(
    stem: str,
    alternatives: list,
    correct_letter: str,
    correct_text: str,
    user_letter: str = "",
    user_question: str = "",
    explanation: str = "",
    area: str = "",
    subtema: str = "",
    chat_history: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[str] = None,
    db: Any = None,
) -> dict:
    """
    Atua como um Preceptor Médico Socrático especialista em provas de residência (USP, ENARE, SUS-SP).
    Suporta modos especializados (/foco, /conduta, /pegadinhas, /round, /caso, réplicas e dúvidas livres),
    grounding ancorado em fontes oficiais e Tool Calling adaptativo (get_student_weak_topics).
    """
    alts_formatted = "\n".join([
        f"{a.get('letter', '')}) {a.get('text', '')}"
        for a in alternatives
        if isinstance(a, dict)
    ])

    user_query = user_question.strip() if user_question else ""
    mode = detect_preceptor_mode(user_query, chat_history)

    # 1. Recuperação RAG de fontes oficiais (Data Store)
    grounding_chunks = retrieve_medical_context(
        area=area,
        subtema=subtema,
        stem=stem,
        user_question=user_query,
        top_k=2
    )
    grounding_block = format_grounding_block(grounding_chunks)
    grounding_sources = [
        {
            "source_file": c.get("source_file"),
            "source_type": c.get("source_type"),
            "topic": c.get("topic"),
            "subtopic": c.get("subtopic"),
            "title": c.get("title")
        }
        for c in grounding_chunks
    ]

    grounding_instruction = ""
    if grounding_block:
        grounding_instruction = f"""
{grounding_block}

REGRAS DE ANCORAGEM NAS FONTES:
- Prioridade Absoluta: Suas condutas devem ser estritamente fundamentadas nas fontes anexadas no Data Store acima.
- Rastreabilidade: Sempre indique a qual fonte e tema a conduta pertence (ex: [Fonte: {grounding_sources[0]['source_file']}]).
"""

    # 2. Tool Calling Adaptativo se mode == "foco"
    tool_call_meta = None
    diagnostic_block = ""
    if mode == "foco":
        if db is not None:
            diag_data = get_student_weak_topics(db, user_id, limit=5)
            diagnostic_block = format_student_diagnostic_block(diag_data)
            tool_call_meta = {
                "name": "get_student_weak_topics",
                "data": diag_data
            }
        else:
            diagnostic_block = format_student_diagnostic_block(None)

    # 3. Histórico de Conversação (Multi-turn), filtrando duplicidade da mensagem atual
    history_formatted = ""
    if chat_history and len(chat_history) > 0:
        history_lines = []
        effective_history = list(chat_history)
        if (
            effective_history
            and effective_history[-1].get("role") == "user"
            and effective_history[-1].get("content", "").strip() == user_query
        ):
            effective_history = effective_history[:-1]

        for msg in effective_history[-6:]:
            role_label = "ALUNO" if msg.get("role") == "user" else "PRECEPTOR"
            c = msg.get("content", "").strip()
            if c:
                history_lines.append(f"**{role_label}**: {c}")
        if history_lines:
            history_formatted = "### HISTÓRICO DA DISCUSSÃO CLÍNICA PRÉVIA:\n" + "\n\n".join(history_lines) + "\n\n"

    # 4. Construção das Diretrizes Exclusivas por Modo
    if mode == "foco":
        mode_instructions = f"""
{diagnostic_block}

### MODO ATIVADO: DIAGNÓSTICO ADAPTATIVO & DIRECIONAMENTO DE ESTUDOS (/foco)
DIRETRIZES OBRIGATÓRIAS DO MODO /FOCO:
1. ⛔ REGRA ABSOLUTA: NÃO REEXPLIQUE A QUESTÃO CLÍNICA ACIMA. O aluno acionou sua função de Mentor Pedagógico e Diretor Adaptativo para saber onde focar seus estudos.
2. Analise os dados do aluno fornecidos pela ferramenta diagnóstica acima e estruture sua resposta exatamente nestas seções:
   - 📊 **Raio-X de Desempenho**: Apresente a acurácia global do aluno, total de questões resolvidas e contextualize com a grande área ({area or 'Medicina Geral'}) e subtema ({subtema or 'Raciocínio Clínico'}).
   - 🚨 **Subtemas Vulneráveis**: Identifique com precisão os subtemas com maior taxa de erro e explique o risco de perder essas questões nas grandes bancas (USP, ENARE, SUS-SP).
   - ⏰ **Status FSRS & Revisões**: Se houver revisões pendentes (srs_due_count > 0), determine a prioridade inegociável de zerar a repetição espaçada antes de avançar para novos temas.
   - 🎯 **Plano de Ataque Prático**: Prescreva uma meta cirúrgica para a sessão de hoje (ex: 'Zere as revisões pendentes + resolva 15 questões do subtema de maior risco').
3. Caso o aluno não possua histórico suficiente ainda, instrua-o a fazer um bloco de calibração com os 3 temas de maior incidência estatística da residência médica nesta área.
"""
    elif mode == "pegadinhas":
        mode_instructions = f"""
### MODO ATIVADO: ARMADILHAS CLÁSSICAS DAS BANCAS (/pegadinhas)
TEMA: {area or 'Medicina'} - {subtema or 'Clínica Médica'}
CONCEITO DO GABARITO: Letra {correct_letter}) {correct_text}

DIRETRIZES OBRIGATÓRIAS DO MODO /PEGADINHAS:
1. ⛔ REGRA ABSOLUTA: NÃO REEXPLIQUE O CASO CLÍNICO OU A FISIOPATOLOGIA DA QUESTÃO DO ZERO. Vá direto às pegadinhas que mais derrubam candidatos!
2. Apresente de 3 a 5 pegadinhas clássicas e recorrentes das grandes bancas (USP-SP, USP-RP, ENARE, UNIFESP, UNICAMP, SUS-SP) sobre este tema específico.
3. Formate OBRIGATORIAMENTE cada pegadinha com título temático numerado e bullets limpos, sem repetir cabeçalhos:
   🪤 **Pegadinha {{N}}: {{Nome Curto do Conceito ou Ponto Crítico}}**
   • **A Armadilha no Enunciado**: Como o examinador monta a alternativa ou o detalhe sutil no texto para induzir o erro (ex: doses parecidas, inversão de prioridade cronológica, fármacos coadjuvantes disfarçados de emergência, achados que parecem contraindicação mas não são).
   • **O Erro Comum**: O raciocínio intuitivo precipitado que leva o candidato a errar.
   • **Como Gabaritar**: O gatilho mental, palavra-âncora ou regra prática de eliminação para acertar em segundos.
4. Conclua com a 💡 **Regra de Ouro Anti-Pegadinha** definitiva para memorização rápida.
"""
    elif mode == "caso":
        mode_instructions = f"""
### MODO ATIVADO: NOVO DESAFIO CLÍNICO CORRELATO (/caso)
TEMA: {area or 'Medicina'} - {subtema or 'Clínica Médica'}

DIRETRIZES OBRIGATÓRIAS DO MODO /CASO:
1. ⛔ NÃO REEXPLIQUE A QUESTÃO ANTERIOR.
2. Crie uma NOVA vinheta clínica INÉDITA, realista, desafiadora e de padrão R1-USP sobre este tema, introduzindo uma variável clínica que exija raciocínio apurado (ex: paciente gestante, idoso com comorbidades, choque refratário, complicação aguda ou apresentação atípica).
3. Formule uma pergunta de conduta imediata ou decisão diagnóstica beira-leito.
4. Apresente exatamente 4 alternativas (A, B, C, D) bem estruturadas e plausíveis:
   A) ...
   B) ...
   C) ...
   D) ...
5. ⛔ REGRA INEGOCIÁVEL: NUNCA FORNEÇA O GABARITO OU A RESPOSTA NESTA MENSAGEM.
6. Encerre desafiando o aluno: "Agora é sua vez! Envie no chat a letra da alternativa que você escolheu (A, B, C ou D) para discutirmos o raciocínio."
"""
    elif mode == "round":
        mode_instructions = f"""
### MODO ATIVADO: SIMULAÇÃO DE VISITA BEIRA-LEITO (/round)
PACIENTE EM DISCUSSÃO: {stem}

DIRETRIZES OBRIGATÓRIAS DO MODO /ROUND:
1. Assuma a postura de um Chefe de Clínica / Preceptor Sênior conduzindo a visita da enfermaria/emergência com os internos.
2. Seja incisivo, técnico, prático e socrático. Contextualize brevemente a passagem de visita deste paciente.
3. Formule exatamente 3 perguntas clínicas beira-leito afiadas que um interno precisa saber responder de pronto:
   - 🔹 **Pergunta 1**: Reconhecimento imediato, sinais de gravidade ou primeiro passo na estabilização beira-leito.
   - 🔹 **Pergunta 2**: Ajuste fino de dose, diluição, via de administração, contraindicação ou droga de 2ª linha.
   - 🔹 **Pergunta 3**: Complicação iminente, tempo de monitorização ou critério de transferência/alta.
4. ⛔ REGRA INEGOCIÁVEL: NÃO RESPONDA AS PERGUNTAS AGORA.
5. Conclua com o convite socrático: "Diga-me, interno(a): qual é a sua conduta para cada um desses 3 pontos? Aguardo suas respostas para avaliar."
"""
    elif mode == "conduta":
        mode_instructions = f"""
### MODO ATIVADO: ALGORITMO TERAPÊUTICO BEIRA-LEITO (/conduta)
TEMA: {area or 'Medicina'} - {subtema or 'Clínica Médica'}
CASO: {stem}

DIRETRIZES OBRIGATÓRIAS DO MODO /CONDUTA:
1. NÃO GASTE TEMPO COM TEORIA DE CICLO BÁSICO OU DEFINIÇÕES ELEMENTARES.
2. Apresente o protocolo de conduta imediata, objetivo e esquemático, estruturado exatamente nesta sequência:
   - 🚨 **1. Reconhecimento & Alerta**: Sinais de alarme imediato, critérios de instabilidade e escores rápidos.
   - 🛑 **2. Estabilização Imediata (ABCDE)**: Medidas de suporte beira-leito (posicionamento, oxigenioterapia, acessos venosos, monitorização).
   - 💊 **3. Terapêutica Farmacológica de Escolha**: Fármacos de 1ª linha com doses exatas (adulto e pediátrica se aplicável), via, velocidade e diluição recomendada.
   - 🔬 **4. Investigação Dirigida**: Exames prioritários beira-leito versus condutas que NUNCA devem aguardar exames.
   - 🏥 **5. Critérios de Destino & Tempo de Observação**: Critérios objetivos para alta com segurança versus indicação de UTI/CTI.
"""
    elif mode == "replica_desafio":
        mode_instructions = f"""
### MODO ATIVADO: AVALIAÇÃO SOCRÁTICA DA RESPOSTA DO ALUNO
O aluno está respondendo a um desafio anterior (pergunta de /round ou questão de /caso).
RESPOSTA DO ALUNO: "{user_query}"

DIRETRIZES OBRIGATÓRIAS:
1. Avalie diretamente a resposta do aluno com precisão e clareza:
   - Indique sem rodeios se a resposta foi CORRETA, PARCIALMENTE CORRETA ou INCORRETA.
   - Explique o fundamento fisiopatológico e beira-leito por trás do acerto ou erro.
2. Se a mensagem anterior continha um novo caso de múltipla escolha:
   - Revele o gabarito oficial com a devida fundamentação clínica.
   - Explique por que os distratores estavam incorretos.
3. Se a mensagem anterior continha as 3 perguntas de visita beira-leito (/round):
   - Avalie pontualmente cada uma das 3 perguntas, pontuando a conduta do aluno e corrigindo lacunas.
4. Feche com uma orientação prática de fixação para provas de residência.
"""
    elif mode == "duvida_livre":
        mode_instructions = f"""
### MODO ATIVADO: TIRA-DÚVIDAS PONTUAL DO ALUNO
DÚVIDA ESPECÍFICA: "{user_query}"

DIRETRIZES OBRIGATÓRIAS:
1. RESPONDA DIRETAMENTE E EXCLUSIVAMENTE À DÚVIDA DO ALUNO.
2. Não reexplique todo o caso nem repita as 4 seções gerais se o aluno perguntou algo específico (ex: por que uma alternativa está errada, dosagem, fisiopatologia específica ou diagnóstico diferencial).
3. Use analogias clínicas, evidências das diretrizes oficiais e raciocínio de residência médica para sanar a dúvida com clareza cristalina.
4. Finalize com um 💡 **Pulo do Gato** específico sobre a dúvida apresentada.
"""
    else:  # discussao_geral
        mode_instructions = f"""
### MODO ATIVADO: DISCUSSÃO CLÍNICA COMPLETA DO CASO
ENUNCIADO DA QUESTÃO: {stem}
GABARITO OFICIAL: Letra {correct_letter} ({correct_text})

FILTRO ANTI-OBVIEDADE E DIRETRIZES DE RESPOSTA:
1. Proibido gastar espaço com semiologia introdutória trivial ou definições de dicionário.
2. Estruture a resposta obrigatoriamente nestas 4 seções:
   - 🩺 **Raciocínio Fisiopatológico & Decisão Beira-Leito**: Mecanismos que definem a conduta e critérios diagnósticos formais.
   - 🎯 **Conduta Padrão-Ouro**: Justifique a abordagem terapêutica de escolha, fármacos de 1ª linha e doses essenciais. Citar a fonte consultada.
   - ⚠️ **Análise dos Distratores & Pegadinhas de Prova**: Analise detalhadamente cada alternativa incorreta e exponha as armadilhas da banca.
   - 💡 **Pulo do Gato**: Regra rápida de memorização ('take-home message').
"""

    prompt = f"""Você atua como um Preceptor Clínico Sênior do HC-FMRP-USP e Especialista em Preparação para Residência Médica (Bancas USP-SP, USP-RP, ENARE, SUS-SP).

ÁREA / TEMA: {area or 'Medicina'} - {subtema or 'Raciocínio Clínico'}
QUESTÃO DE REFERÊNCIA:
{stem}

ALTERNATIVAS:
{alts_formatted}

GABARITO OFICIAL: Letra {correct_letter} ({correct_text})
RESPOSTA DO ALUNO NO QUIZ: {f'Marcou Letra {user_letter}' if user_letter else 'Ainda não respondeu ou acertou'}

{history_formatted}{grounding_instruction}
{mode_instructions}
"""

    try:
        preceptor_order = [
            p.strip().lower()
            for p in os.environ.get("AI_PRECEPTOR_PROVIDER_ORDER", "gemini").split(",")
            if p.strip()
        ]
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction=(
                "Você é um Preceptor Clínico Sênior do HC-FMRP-USP e especialista de elite em preparação para Residência Médica (USP, ENARE, SUS-SP). "
                "Seja direto, técnico, socrático e rigoroso. "
                "REGRA CRÍTICA DE COMUNICAÇÃO: PROIBIDO usar saudações genéricas como 'Olá futuro(a) residente!', 'Excelente desempenho!', "
                "'Marcar a Letra X demonstra...', ou elogios bajuladores repetitivos no início. Vá direto ao conteúdo clínico solicitado sem enrolação."
            ),
            timeout=25,
            response_validator=lambda value: len(value.strip()) >= 50,
            provider_order=preceptor_order,
        )
        text = resp.get("text", "").strip()
        if text:
            return {
                "answer": text,
                "model": resp.get("model", "universal"),
                "source": resp.get("source", "universal"),
                "grounding_sources": grounding_sources,
                "tool_call": tool_call_meta
            }
    except Exception as e:
        logger.error(f"Erro no preceptor IA Universal: {e}")

    # Fallback estruturado caso todos os provedores de IA estejam fora do ar
    clean_pulo = _extract_pulo_do_gato(explanation)
    if mode == "pegadinhas":
        fallback_response = (
            f"⚠️ **Armadilhas Clássicas de Prova ({subtema or area or 'Medicina'})**:\n"
            f"- A principal pegadinha neste tema é a confusão entre conduta imediata e terapêuticas coadjuvantes.\n"
            f"- O gabarito oficial é a Letra **{correct_letter}** ({correct_text}).\n\n"
            f"💡 **Regra de Ouro**: Identifique a âncora de instabilidade no enunciado e aplique a droga de primeira linha sem atraso."
        )
    elif mode == "conduta":
        fallback_response = (
            f"🚨 **Algoritmo de Conduta Beira-Leito**:\n"
            f"1. **Estabilização Imediata**: Priorize suporte ventilatório e hemodinâmico beira-leito.\n"
            f"2. **Terapêutica de Escolha**: A conduta padrão-ouro é a Letra **{correct_letter}** ({correct_text}).\n\n"
            f"💡 **Take-Home Message**: Não postergue a droga de 1ª linha para aguardar exames complementares."
        )
    elif mode == "round":
        fallback_response = (
            f"🩺 **Sabatina Beira-Leito (Perguntas ao Interno)**:\n"
            f"1. Qual é o primeiro sinal de alarme que define gravidade imediata neste paciente?\n"
            f"2. Qual a justificativa para a conduta indicada na Letra **{correct_letter}** em vez das alternativas?\n"
            f"3. Quais os critérios de monitorização e destino seguro deste paciente?\n\n"
            f"Envie suas respostas para avaliarmos a conduta!"
        )
    elif mode == "caso":
        fallback_response = (
            f"📋 **Desafio Clínico Correlato**:\n"
            f"Considere o mesmo cenário deste paciente, mas agora apresentando piora hemodinâmica súbita refratária à conduta inicial.\n"
            f"Qual seria o próximo passo imediato no manejo?\n"
            f"A) Manter observação clínica\nB) Repetir a droga de primeira linha e suporte avançado\nC) Aguardar exames laboratoriais\nD) Alta precoce\n\n"
            f"Qual a sua resposta? Digite a letra para discutir!"
        )
    elif mode == "foco":
        fallback_response = (
            f"📊 **Direcionamento Adaptativo de Estudos**:\n"
            f"Para dominar **{subtema or area or 'este tema'}** nas provas de residência (USP, ENARE, SUS-SP):\n"
            f"- Foque na diferenciação rápida entre condutas de 1ª linha e medidas coadjuvantes.\n"
            f"- Mantenha a fila de repetição espaçada (FSRS) sempre em dia para reter os protocolos longos.\n\n"
            f"💡 **Meta**: Resolva um bloco de 10 questões deste subtema para consolidar o raciocínio."
        )
    else:
        fallback_response = f"**Raciocínio Clínico Resumido**:\nO gabarito oficial é a Letra **{correct_letter}** ({correct_text}).\n\n"
        if clean_pulo:
            fallback_response += f"💡 **Pulo do Gato**:\n{clean_pulo}\n\n"
        elif explanation:
            fallback_response += f"📚 **Fundamentação Clínica**:\n{explanation}\n\n"
        fallback_response += f"💡 **Regra de Ouro**: Em {subtema or area or 'questões clínicas de residência'}, priorize sempre a identificação da âncora clínica no enunciado e correlacione com a conduta padrão-ouro das diretrizes vigentes."

    return {
        "answer": fallback_response,
        "model": "deterministic_fallback",
        "source": "fallback",
        "grounding_sources": grounding_sources,
        "tool_call": tool_call_meta
    }


def _extract_json_block(text: str) -> dict | None:
    """Extrai e faz parsing resiliente de JSON mesmo com markdown ou texto envolvente."""
    if not text:
        return None
    cleaned = text.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    
    match = re.search(r'(\{[\s\S]*\})', cleaned)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
    return None


def generate_study_prescription(
    weak_topics: list | None = None,
    distractors: list | None = None,
    at_risk_topics: list | None = None,
    target_institution: str | None = None
) -> dict:
    """
    Gera uma Prescrição Clínica de Estudo personalizada de alto rendimento usando Gemini 3.7 Flash.
    Analisa os tópicos de menor acurácia, as pegadinhas em que o aluno mais cai e os cards em risco de esquecimento.
    """
    institution_context = f"Instituição Alvo: {target_institution}\n" if target_institution else "Foco: Residência Médica Geral (USP, ENARE, SUS-SP)\n"
    
    weak_str = "\n".join([
        f"- {wt.get('topic') or wt.get('subtema')}: {wt.get('correct', 0)} acertos em {wt.get('attempts', 0)} questões ({round((wt.get('accuracy', 0))*100)}% acurácia)"
        for wt in (weak_topics or [])[:6]
    ]) or "Nenhum tópico crítico identificado."

    distractors_str = "\n".join([
        f"- Subtema '{d.get('subtema')}': Costuma marcar alternativa incorreta {d.get('wrong_choices', [{}])[0].get('letter', '?')} ({d.get('wrong_choices', [{}])[0].get('count', 0)}x)"
        for d in (distractors or [])[:4]
        if d.get('wrong_choices')
    ]) or "Nenhum distrator recorrente mapeado."

    at_risk_str = "\n".join([
        f"- {r.get('subtema')}: {r.get('items_count', 1)} cartões FSRS próximos do esquecimento"
        for r in (at_risk_topics or [])[:4]
    ]) or "Memória em dia para as revisões ativas."

    prompt = f"""Você é o Diretor Pedagógico e Preceptor Médico Chefe do MedQuest.
Gere uma "Prescrição Clínica de Estudo" personalizada para este médico residente.

{institution_context}
DIAGNÓSTICO DO ALUNO:
1. Tópicos de Baixo Rendimento:
{weak_str}

2. Padrões de Armadilhas / Distratores:
{distractors_str}

3. Tópicos com Risco de Esquecimento (FSRS):
{at_risk_str}

DIRETRIZES:
1. Faça um diagnóstico clínico e encorajador em 2-3 frases.
2. Defina o "Plano Tático em 3 Passos" com conceitos de alto rendimento para reverter os tópicos fracos.
3. Aponte a "Vacina contra Distratores" alertando sobre as pegadinhas mapeadas.
4. Conclua com a "Regra de Ouro Semanal".
5. Formate a resposta em Markdown limpo com ícones e bullet points.

Responda em formato estruturado.
"""

    try:
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction="Você é o diretor pedagógico do MedQuest especialista em aprovação de residência médica.",
            timeout=25
        )
        text = resp.get("text", "").strip()
        if text:
            return {
                "prescription_markdown": text,
                "model": resp.get("model", "universal"),
                "source": resp.get("source", "universal")
            }
    except Exception as e:
        logger.error(f"Erro na prescrição de estudos via IA Universal: {e}")

    fallback_md = f"""### 🩺 Prescrição de Estudo Personalizada

**Diagnóstico Geral**:
Identificamos pontos de atenção imediatos em tópicos-chave. Com foco nos conceitos fisiopatológicos e diferenciação de condutas, sua pontuação terá um salto rápido.

**Plano Tático Imediato**:
- **Revisão Ativa**: Priorize realizar blocos de 15 questões dos seus temas com menor acurácia.
- **Atenção aos Distratores**: Redobre o cuidado com as alternativas que você mais assinala por impulso. Identifique palavras excludentes (*sempre*, *nunca*, *apenas*).
- **Consolidação FSRS**: Conclua as revisões ativas pendentes antes de iniciar questões inéditas.

💡 **Regra de Ouro**: A aprovação na residência médica é construída na correção minuciosa de cada erro. Entenda o porquê de cada distrator.
"""
    return {
        "prescription_markdown": fallback_md,
        "model": "deterministic_fallback",
        "source": "fallback"
    }


def synthesize_question_explanation(
    stem: str,
    alternatives: list,
    correct_letter: str,
    correct_text: str,
    area: str = "",
    subtema: str = ""
) -> dict:
    """
    Sintetiza um comentário médico estruturado e completo (Pulo do Gato, Raciocínio Clínico,
    Alternativa Correta e Distratores) para uma questão utilizando Gemini.
    """
    alts_formatted = "\n".join([
        f"{a.get('letter', '')}) {a.get('text', '')}"
        for a in alternatives
        if isinstance(a, dict)
    ])

    prompt = f"""Você é um professor especialista em provas de residência médica (USP, ENARE, SUS-SP).
Crie o comentário oficial perfeito para a seguinte questão de residência médica:

ÁREA: {area} | SUBTEMA: {subtema}
ENUNCIADO:
{stem}

ALTERNATIVAS:
{alts_formatted}

GABARITO: Letra {correct_letter} ({correct_text})

ESTRUTURA OBRIGATÓRIA DA RESPOSTA (JSON):
{{
  "pulo_do_gato": "Âncora diagnóstica, mnemônico, síntese prática de alta relevância ou regras de decisão essenciais para fixação imediata do conceito da questão (com o tamanho e profundidade necessários para máxima relevância).",
  "raciocinio_clinico": "Explicação clínica e fisiopatológica detalhada do quadro e critérios de diagnóstico/conduta.",
  "alternativa_correta": "Por que a alternativa {correct_letter} é a única correta de acordo com as diretrizes.",
  "distratores": [
    {{"letter": "Letra", "explanation": "Por que está errada e qual a pegadinha"}}
  ]
}}
"""

    try:
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction="Você responde exclusivamente em JSON válido.",
            json_mode=True,
            timeout=25
        )
        parsed = _extract_json_block(resp.get("text", ""))
        if parsed and "pulo_do_gato" in parsed and "raciocinio_clinico" in parsed:
            # Monta a string estruturada em markdown
            distratores_md = "\n".join([
                f"- **Alternativa ({d.get('letter')})**: {d.get('explanation')}"
                for d in parsed.get("distratores", [])
            ])
            full_explanation = f"""**Gabarito Oficial**: Letra {correct_letter}

**Pulo do Gato**: {parsed.get('pulo_do_gato')}

**Raciocínio Clínico**:
{parsed.get('raciocinio_clinico')}

**Alternativa Correta ({correct_letter})**:
{parsed.get('alternativa_correta')}

**Análise dos Distratores**:
{distratores_md}
"""
            return {
                "explanation_text": full_explanation.strip(),
                "pulo_do_gato": parsed.get("pulo_do_gato"),
                "source": resp.get("source", "universal"),
                "model": resp.get("model", "universal")
            }
    except Exception as e:
        logger.error(f"Erro na síntese de comentário via IA Universal: {e}")

    # Fallback estruturado
    fallback_text = f"""**Gabarito Oficial**: Letra {correct_letter}

**Pulo do Gato**: O padrão-ouro em {subtema or area or 'quadros semelhantes'} baseia-se na identificação precoce dos critérios clínicos e conduta conforme diretrizes vigentes.

**Alternativa Correta ({correct_letter})**:
A alternativa ({correct_letter}) apresenta a abordagem preconizada para o caso apresentado.
"""
    return {
        "explanation_text": fallback_text.strip(),
        "pulo_do_gato": f"Foco nos critérios de {subtema or area}.",
        "source": "fallback",
        "model": "deterministic_fallback"
    }


def generate_preceptor_dashboard_focus(db, user_id: Optional[str]) -> dict:
    """
    Gera o diagnóstico adaptativo e o plano de ataque diário do Preceptor IA
    para exibição direta no Dashboard (Página Inicial), sem depender de uma questão avulsa.
    Cruza histórico de tentativas, pontos cegos frente às bancas e carga do FSRS.
    """
    diag_data = get_student_weak_topics(db, user_id, limit=5)
    diag_block = format_student_diagnostic_block(diag_data)

    weak_list = diag_data.get("weak_topics", [])
    if weak_list:
        top_weak = weak_list[0]
        rec_subtema = top_weak.get("topic", "Clínica Médica")
        rec_area = top_weak.get("area", "")
        rec_url = f"/estudar?subtema={quote(rec_subtema)}&limit=15"
    else:
        rec_subtema = "Síndromes Coronarianas Agudas"
        rec_area = "Clínica Médica"
        rec_url = "/estudar?area=Clinica%20Medica&limit=15"

    prompt = f"""VOCÊ É O PRECEPTOR MÉDICO SOCRÁTICO DO MEDQUEST, ESPECIALISTA EM PREPARAÇÃO DE ALTO RENDIMENTO PARA RESIDÊNCIA MÉDICA (USP-SP, ENARE, UNIFESP, UNICAMP, SUS-SP).
Sua missão nesta consulta de cabeçalho/dashboard é traçar um diagnóstico adaptativo PROFUNDO e o PLANO DE ATAQUE DO DIA para o estudante.

{diag_block}

DIRETRIZES OBRIGATÓRIAS DO PARECER DE DASHBOARD:
1. ⛔ REGRA ABSOLUTA: NÃO use saudações prolixas repetitivas ("Olá, futuro residente!", "Tudo bem?", etc.). Vá direto ao diagnóstico clínico e estratégico.
2. ⛔ PROIBIÇÃO ESTATÍSTICA: NUNCA considere temas com 1 ou 2 questões como fraqueza principal. O foco deve ser estritamente onde o aluno acumulou perda real de pontos em temas de alta incidência de prova.
3. Formate sua resposta em 4 seções cirúrgicas e aprofundadas em Markdown:
   📊 **Raio-X de Desempenho**: Avalie o volume de questões feitas e a taxa global de acerto. Se o volume for expressivo (ex: > 100 Qs), valorize a base construída, mas aponte onde a média geral está camuflando ralos de pontos específicos.
   🚨 **Subtemas Vulneráveis & Armadilhas das Bancas**: Analise criticamente os principais gargalos estatísticos (com foco em {rec_subtema} e nos outros temas com maior número de erros). Detalhe como as grandes bancas (USP, ENARE, UNIFESP) montam pegadinhas nesses tópicos (critérios diagnósticos, controvérsias de diretrizes, doses de emergência, condutas beira-leito).
   ⏰ **Status FSRS & Curva de Esquecimento**: Indique a urgência das revisões espaçadas pendentes hoje e a importância de manter a retenção de longo prazo ativa antes de novos blocos.
   🎯 **Plano de Ataque Prático do Dia**: Prescreva uma meta imediata, estruturada e sequencial (ex: bloco cirúrgico de 15 questões focado no tema prioritário {rec_subtema} + zerar pendências do FSRS).
4. Seja incisivo, técnico, denso, sem generalidades óbvias e focado na aprovação nas bancas mais disputadas do país.
"""

    system_instruction = (
        "Você é um Preceptor Médico Socrático de residência médica de excelência absoluta. "
        "Sua análise deve ser profunda, densa, tecnicamente impecável, sem superficialidades e estritamente embasada nos dados estatísticos do aluno."
    )

    try:
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction=system_instruction,
            timeout=35
        )
        text = resp.get("text", "").strip()
        if text:
            return {
                "diagnostic_data": diag_data,
                "analysis_markdown": text,
                "recommended_topic": {
                    "subtema": rec_subtema,
                    "area": rec_area,
                    "practice_url": rec_url,
                },
                "source": resp.get("source", "universal"),
                "model": resp.get("model", "Preceptor Socrático"),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }
    except Exception as e:
        logger.error(f"Erro ao gerar foco do Preceptor no dashboard: {e}")

    # Fallback estruturado de alta fidelidade
    fallback_analysis = f"""📊 **Raio-X de Desempenho**
Volume sólido de {diag_data.get('total_attempts', 0)} questões resolvidas com acurácia média de {diag_data.get('overall_accuracy_pct', 0.0)}%. A base está formada, mas o foco agora é estancar ralos de pontos específicos.

🚨 **Subtemas Vulneráveis & Armadilhas das Bancas**
O subtema prioritário com maior volume de erros acumulados é **{rec_subtema}** ({rec_area}). 
As grandes bancas (USP, ENARE, UNIFESP e SUS-SP) cobram ativamente condutas imediatas, critérios de gravidade e decisões beira-leito neste tópico. Dominar essas pegadinhas é o que garante o salto na pontuação final.

⏰ **Status FSRS & Curva de Esquecimento**
Você possui **{diag_data.get('srs_due_count', 0)}** revisões com repetição espaçada (FSRS v6) pendentes hoje. Execute essas revisões antes de iniciar blocos inéditos para manter a retenção de longo prazo blindada.

🎯 **Plano de Ataque Prático do Dia**
1. **Zerar FSRS:** Elimine as {diag_data.get('srs_due_count', 0)} revisões pendentes.
2. **Bateria Cirúrgica:** Realize imediatamente uma bateria de 15 questões focada em **{rec_subtema}**.
3. **Retificação Ativa:** Revise detalhadamente o gabarito de cada questão errada, anotando a pegadinha da banca no seu caderno de erros.
"""
    return {
        "diagnostic_data": diag_data,
        "analysis_markdown": fallback_analysis.strip(),
        "recommended_topic": {
            "subtema": rec_subtema,
            "area": rec_area,
            "practice_url": rec_url,
        },
        "source": "fallback",
        "model": "Preceptor Socrático",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }


