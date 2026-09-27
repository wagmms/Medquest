import json
import logging
import os
import re
import time

from api.gemini_pool import gemini_pool
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


def ask_preceptor_ai(
    stem: str,
    alternatives: list,
    correct_letter: str,
    correct_text: str,
    user_letter: str = "",
    user_question: str = "",
    explanation: str = "",
    area: str = "",
    subtema: str = ""
) -> dict:
    """
    Atua como um Preceptor Médico Socrático especialista em provas de residência (USP, ENARE, SUS-SP).
    Gera comentários e explicações clínicas inéditas por IA com alto rigor científico, fisiopatologia e foco em pegadinhas.
    """
    alts_formatted = "\n".join([
        f"{a.get('letter', '')}) {a.get('text', '')}"
        for a in alternatives
        if isinstance(a, dict)
    ])
    
    prompt = f"""Você é o Preceptor Clínico Virtual do MedQuest, especialista em preparação para residência médica de alto nível (USP, ENARE, SUS-SP, Unifesp, Unicamp).

ÁREA / TEMA: {area or 'Medicina'} - {subtema or 'Raciocínio Clínico'}
ENUNCIADO DA QUESTÃO:
{stem}

ALTERNATIVAS:
{alts_formatted}

GABARITO OFICIAL: Letra {correct_letter} ({correct_text})
RESPOSTA DO ALUNO: {f'Marcou Letra {user_letter}' if user_letter else 'Ainda não respondeu ou acertou'}

DÚVIDA / FOCO SOLICITADO:
{user_question or 'Explique o raciocínio fisiopatológico da questão, por que a correta é o padrão-ouro e onde está a armadilha do distrator.'}

INSTRUÇÕES PEDAGÓGICAS DO PRECEPTOR:
1. Responda em tom encorajador, clínico, didático e de alta relevância para provas de residência.
2. Forneça uma explicação clínica ORIGINAL e APROFUNDADA:
   - Seção 🩺 **Raciocínio Fisiopatológico & Diagnóstico**: Explique o mecanismo fisiopatológico subjacente, os achados clínicos e os critérios diagnósticos.
   - Seção 🎯 **Conduta Padrão-Ouro**: Justifique a abordagem terapêutica recomendada pelas diretrizes e consensos médicos atuais (SBP, SBC, MS, FEBRASGO, etc.).
   - Seção ⚠️ **Análise dos Distratores & Pegadinhas**: Se o aluno errou ou pediu distratores, detalhe o porquê das alternativas incorretas serem armadilhas clássicas de banca.
   - Seção 💡 **Regra de Ouro**: Finalize com uma 'take-home message' mnemônica ou regra de decisão indispensável para a prova.
3. Formate a resposta em Markdown limpo, com tópicos bem estruturados e ênfase visual.
"""

    try:
        preceptor_order = [
            p.strip().lower()
            for p in os.environ.get("AI_PRECEPTOR_PROVIDER_ORDER", "gemini").split(",")
            if p.strip()
        ]
        resp = generate_content_with_fallback(
            prompt=prompt,
            system_instruction="Você é um preceptor médico de elite que ensina raciocínio clínico para residência médica. Gere comentários originais, aprofundados e didáticos.",
            timeout=25,
            # Uma resposta curta/refusal nao deve encerrar a cadeia: o pool
            # continua no proximo provedor ate obter uma explicacao substancial.
            response_validator=lambda value: len(value.strip()) >= 80,
            provider_order=preceptor_order,
        )
        text = resp.get("text", "").strip()
        if text:
            return {
                "answer": text,
                "model": resp.get("model", "universal"),
                "source": resp.get("source", "universal")
            }
    except Exception as e:
        logger.error(f"Erro no preceptor IA Universal: {e}")

    # Fallback estruturado caso todos os provedores de IA estejam fora do ar
    clean_pulo = _extract_pulo_do_gato(explanation)
    fallback_response = f"**Raciocínio Clínico Resumido**:\nO gabarito oficial é a Letra **{correct_letter}** ({correct_text}).\n\n"
    if clean_pulo:
        fallback_response += f"💡 **Pulo do Gato**:\n{clean_pulo}\n\n"
    elif explanation:
        fallback_response += f"📚 **Fundamentação Clínica**:\n{explanation}\n\n"
    fallback_response += f"💡 **Regra de Ouro**: Em {subtema or area or 'questões clínicas de residência'}, priorize sempre a identificação da âncora clínica no enunciado e correlacione com a conduta padrão-ouro das diretrizes vigentes."
    
    return {
        "answer": fallback_response,
        "model": "deterministic_fallback",
        "source": "fallback"
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
