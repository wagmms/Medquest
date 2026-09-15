"""
Script de Reescrita de Explicações MedQuest — Padrão Residência R1-USP (Template Ouro)
Suporta múltiplos provedores (Yunqiao/Claude, Google Gemini, DeepSeek).
Garante atomicidade, backup automático, retomada por checkpoint e modo dry-run.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import itertools
import json
import os
import re
import shutil
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

# Forçar stdout em UTF-8 no Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "medquest.db")
ENV_PATH = os.path.join(BACKEND_DIR, ".env")
BACKUPS_DIR = os.path.join(BACKEND_DIR, "backups")


def load_env():
    """Carrega variáveis de ambiente do .env sem dependências externas."""
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip("'\""))


load_env()

# Configurações padrão dos provedores
YUNQIAO_URL = "https://yunqiaoapi.com/v1/chat/completions"
DEFAULT_YUNQIAO_KEYS = [
    os.environ.get("YUNQIAO_API_KEY", "sk-2pqLEozeRTA1kaORC1dHNv3u5R8RkgukcVXByDgQOQrBr3iT")
]
DEFAULT_YUNQIAO_MODEL = "claude-haiku-4-5"

SOMAAPI_URL = "https://somaapi.com/v1/chat/completions"
DEFAULT_SOMA_KEYS = [
    os.environ.get("SOMAAPI_KEY", "sk-f9CuFhW85HXOW3Z7TObNSi0pYFCH69euabKFQkF9EnVQov00")
]
DEFAULT_SOMA_MODEL = "claude-haiku-4-5-20251001"

GEMINI_KEYS_RAW = os.environ.get("GEMINI_API_KEYS", "") or os.environ.get("GEMINI_API_KEY", "")
GEMINI_KEYS = [k.strip() for k in GEMINI_KEYS_RAW.split(",") if k.strip()]
gemini_key_cycle = itertools.cycle(GEMINI_KEYS) if GEMINI_KEYS else None

DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")


class KeyManager:
    """Gerencia rotação automática e thread-safe de múltiplas chaves de API quando o saldo acaba."""
    def __init__(self, keys: list[str]):
        self.keys = [k.strip() for k in keys if k.strip()]
        self.current_idx = 0
        self.lock = threading.Lock()
        self.exhausted = len(self.keys) == 0

    def get_current_key(self) -> str | None:
        with self.lock:
            if self.exhausted or self.current_idx >= len(self.keys):
                return None
            return self.keys[self.current_idx]

    def report_failure(self, failed_key: str, reason: str):
        with self.lock:
            if self.current_idx < len(self.keys) and self.keys[self.current_idx] == failed_key:
                print(f"\n⚠️ [CHAVE {self.current_idx + 1} ESGOTADA / FALHOU] ({failed_key[:10]}...{failed_key[-4:]}): {reason}", flush=True)
                self.current_idx += 1
                if self.current_idx < len(self.keys):
                    next_k = self.keys[self.current_idx]
                    print(f"🔄 [ROTAÇÃO AUTOMÁTICA] Alternando imediatamente para Chave {self.current_idx + 1} ({next_k[:10]}...{next_k[-4:]})!\n", flush=True)
                else:
                    self.exhausted = True
                    print(f"\n🛑 [TODAS AS CHAVES FORAM ESGOTADAS] Saldo indisponível em todas as chaves fornecidas.\n", flush=True)

    def is_exhausted(self) -> bool:
        with self.lock:
            return self.exhausted or self.current_idx >= len(self.keys)


# Template Ouro (5 Pilares) - Padrão Residência Médica R1-USP (Otimizado para Alta Densidade e Baixo Consumo de Tokens)
SYSTEM_PROMPT = """Você é um preceptor médico de elite para provas de residência (padrão R1-USP, ENARE, SUS-SP).
Reescreva a explicação no 'Template Ouro (5 Pilares)'. Seja DENSO, DIRETO e CIRÚRGICO, sem enrolação teórica ou ciclo básico.

ESTRUTURA OBRIGATÓRIA (inicie diretamente com **Gabarito**):

**Gabarito**: Letra [X]

**Pulo do Gato**: [1 a 2 frases com o gatilho mental, critério formal (Tokyo, Hinchey, Atlanta, Alvarado) ou pegadinha de prova].

**Raciocínio Clínico**: [1 parágrafo integrando os dados clínicos, topografia e fisiopatologia essencial].

**Por que a Letra [X] é a Correta?**: [1 a 2 parágrafos objetivos com a conduta indicada segundo diretrizes brasileiras (SBC, SBPT, SBP, Febrasgo, CBC) ou Ministério da Saúde].

**Análise dos Distratores**:
- **Letra [A]**: [1 frase explicando o erro específico e em que contexto estaria certa].
- **Letra [B]**: [1 frase explicando o erro específico e em que contexto estaria certa].
- **Letra [C]**: [1 frase explicando o erro específico e em que contexto estaria certa].
- **Letra [D]**: [1 frase explicando o erro específico e em que contexto estaria certa].
(Se houver Letra E, inclua no mesmo padrão).

REGRAS:
1. Questão "EXCETO/INCORRETA": adapte o cabeçalho para "**Por que a Letra [X] é a Incorreta (Gabarito)?**" e analise as opções sob "**Análise das Alternativas Verdadeiras**".
2. Português médico brasileiro padrão (CIVD, plaquetopenia, etc.).
3. Sem metatextos ou mensagens de despedida ao final.
"""


def backup_database():
    """Realiza backup seguro com timestamp antes de iniciar gravações em lote."""
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUPS_DIR, f"medquest_backup_before_rewrite_{ts}.db")
    print(f"📦 Criando backup do banco de dados em: {backup_file} ...", flush=True)
    shutil.copy2(DB_PATH, backup_file)
    print("✅ Backup concluído com sucesso.", flush=True)
    return backup_file


def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def clean_explanation_text(text: str) -> str:
    """Remove eventuais marcadores indesejados ou blocos markdown de fechamento."""
    if not text:
        return ""
    clean = text.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```[a-zA-Z]*\n?", "", clean)
        clean = re.sub(r"\n?```$", "", clean)
    clean = clean.strip()
    return clean


def get_model_pricing(model: str) -> tuple[float, float]:
    """Retorna (preço_entrada_por_token, preço_saida_por_token)."""
    m = model.lower()
    if "gemini" in m:
        return 0.000000075, 0.0000003  # $0.075/M in, $0.30/M out
    elif "haiku" in m:
        return 0.000001, 0.000005  # $1/M in, $5/M out
    elif "deepseek" in m:
        return 0.00000027, 0.0000011  # $0.27/M in, $1.1/M out
    elif "opus" in m:
        return 0.000005, 0.000025  # $5/M in, $25/M out
    else:  # sonnet padrão
        return 0.000003, 0.000015  # $3/M in, $15/M out


def call_openai_compatible(
    question_prompt: str,
    endpoint_url: str,
    model: str,
    key_manager: KeyManager | str,
    timeout: int = 45
) -> tuple[str | None, int, int]:
    """Chama endpoints compatíveis com OpenAI (Yunqiao, SomaAPI) com limite de tokens e User-Agent."""
    if "somaapi" in endpoint_url and model == "claude-haiku-4-5":
        model = "claude-haiku-4-5-20251001"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 550
    }
    data = json.dumps(payload).encode("utf-8")

    while True:
        if isinstance(key_manager, KeyManager):
            if key_manager.is_exhausted():
                return None, 0, 0
            api_key = key_manager.get_current_key()
            if not api_key:
                return None, 0, 0
        else:
            api_key = str(key_manager)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = urllib.request.Request(endpoint_url, data=data, headers=headers, method="POST")

        for attempt in range(2):
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    choice = result["choices"][0]["message"]["content"]
                    usage = result.get("usage", {})
                    inp_tokens = usage.get("prompt_tokens", len(question_prompt) // 3)
                    out_tokens = usage.get("completion_tokens", len(choice) // 3)
                    return clean_explanation_text(choice), inp_tokens, out_tokens
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass
                is_auth_or_quota = e.code in (401, 402, 403) or any(
                    term in err_body.lower() for term in ["quota", "balance", "insufficient", "arrears", "invalid token", "out of credits", "exceeded"]
                )
                if is_auth_or_quota:
                    if isinstance(key_manager, KeyManager):
                        key_manager.report_failure(api_key, f"HTTP {e.code}: {err_body[:80]}")
                        break
                    else:
                        print(f"⚠️ [API ERROR] HTTP {e.code}: {err_body[:80]}")
                        return None, 0, 0
                if attempt < 1:
                    time.sleep(2)
            except Exception as e:
                if attempt < 1:
                    time.sleep(2)
                else:
                    return None, 0, 0

        if not isinstance(key_manager, KeyManager):
            break

    return None, 0, 0


def call_yunqiao(question_prompt: str, model: str, key_manager: KeyManager | str, timeout: int = 45) -> tuple[str | None, int, int]:
    return call_openai_compatible(question_prompt, YUNQIAO_URL, model, key_manager, timeout=timeout)


def call_somaapi(question_prompt: str, model: str, key_manager: KeyManager | str, timeout: int = 45) -> tuple[str | None, int, int]:
    return call_openai_compatible(question_prompt, SOMAAPI_URL, model, key_manager, timeout=timeout)


def call_gemini(question_prompt: str, model: str = "gemini-3.5-flash-lite", timeout: int = 45) -> tuple[str | None, int, int]:
    """Chama a API oficial do Google Gemini com rotação de chaves e x-goog-api-key."""
    if not gemini_key_cycle:
        raise ValueError("Nenhuma chave Gemini disponível.")

    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [{"parts": [{"text": question_prompt}]}],
        "generationConfig": {"temperature": 0.2}
    }
    data = json.dumps(payload).encode("utf-8")

    for attempt in range(len(GEMINI_KEYS) * 2):
        key = next(gemini_key_cycle)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": key
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                cand = result["candidates"][0]["content"]["parts"][0]["text"]
                usage = result.get("usageMetadata", {})
                inp_tokens = usage.get("promptTokenCount", 0)
                out_tokens = usage.get("candidatesTokenCount", 0)
                return clean_explanation_text(cand), inp_tokens, out_tokens
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(1.5)
            elif attempt < 2:
                time.sleep(1)
        except Exception:
            time.sleep(1)

    return None, 0, 0


def build_question_payload(q: dict[str, Any], alts: list[dict[str, str]]) -> str:
    """Constrói o texto conciso da questão com enunciado, alternativas e gabarito."""
    alts_str = "\n".join([f"Letra {a['letter']}: {a['text']}" for a in alts])
    return (
        f"ID: {q['id']} | {q.get('institution_label', 'SP')} ({q.get('year', '')}) | {q.get('area', '')} - {q.get('subtema', '')}\n\n"
        f"ENUNCIADO:\n{q['stem'].strip()}\n\n"
        f"ALTERNATIVAS:\n{alts_str}\n\n"
        f"GABARITO OFICIAL: Letra {q['correct_letter']}\n\n"
        f"INSTRUÇÃO: Inicie diretamente com '**Gabarito**: Letra {q['correct_letter']}' e siga estritamente os 5 blocos: "
        f"'**Pulo do Gato**:', '**Raciocínio Clínico**:', '**Por que a Letra {q['correct_letter']} é a Correta?**:' e '**Análise dos Distratores**:'. "
        f"Não adicione títulos (#) ou introduções."
    )


def fetch_questions(
    mode: str = "missing_raciocinio",
    area: str | None = None,
    subtema: str | None = None,
    question_id: int | None = None,
    limit: int | None = None
) -> list[dict[str, Any]]:
    """Carrega questões do banco de dados aplicando os filtros informados."""
    conn = get_db()
    c = conn.cursor()

    filters = []
    params: list[Any] = []

    if question_id is not None:
        filters.append("q.id = ?")
        params.append(question_id)
    else:
        if area:
            filters.append("q.area = ?")
            params.append(area)
        if subtema:
            filters.append("q.subtema LIKE ?")
            params.append(f"%{subtema}%")

        if mode == "older" or mode == "pending_upgrade":
            filters.append("(DATE(e.reviewed_at) < '2026-09-15' OR e.reviewed_at IS NULL)")
        elif mode == "missing_raciocinio":
            filters.append("(e.explanation_text IS NULL OR e.explanation_text NOT LIKE '%Raciocínio Clínico%')")
        elif mode == "missing_distractors":
            filters.append("(e.explanation_text IS NULL OR (e.explanation_text NOT LIKE '%Análise dos Distratores%' AND e.explanation_text NOT LIKE '%Distratores%'))")
        elif mode == "critical":
            filters.append("""(e.explanation_text IS NULL 
                OR LENGTH(e.explanation_text) < 100 
                OR e.explanation_text NOT LIKE '%Pulo do Gato%'
                OR e.explanation_text NOT LIKE '%Raciocínio Clínico%')""")
        elif mode == "all":
            pass

    where_clause = " WHERE " + " AND ".join(filters) if filters else ""
    query = f"""
        SELECT q.id, q.area, q.subtema, q.institution_label, q.year, q.stem, q.correct_letter, e.explanation_text
        FROM questions q
        LEFT JOIN explanations e ON e.question_id = q.id
        {where_clause}
        ORDER BY q.id ASC
    """
    if limit:
        query += f" LIMIT {limit}"

    rows = c.execute(query, params).fetchall()
    results = []

    for r in rows:
        qid = r["id"]
        c_alts = c.execute("SELECT letter, text FROM alternatives WHERE question_id = ? ORDER BY letter", (qid,)).fetchall()
        alts = [{"letter": a["letter"], "text": a["text"]} for a in c_alts]
        results.append({
            "id": qid,
            "area": r["area"],
            "subtema": r["subtema"],
            "institution_label": r["institution_label"],
            "year": r["year"],
            "stem": r["stem"],
            "correct_letter": r["correct_letter"],
            "current_explanation": r["explanation_text"],
            "alternatives": alts
        })

    conn.close()
    return results


def process_question(
    q: dict[str, Any],
    provider: str,
    model: str,
    key_manager: KeyManager | str
) -> tuple[int, str | None, int, int]:
    """Processa uma única questão com o provedor selecionado."""
    prompt = build_question_payload(q, q["alternatives"])
    if provider == "yunqiao":
        res, inp_tok, out_tok = call_yunqiao(prompt, model=model, key_manager=key_manager)
    elif provider == "somaapi":
        res, inp_tok, out_tok = call_somaapi(prompt, model=model, key_manager=key_manager)
    elif provider == "gemini":
        res, inp_tok, out_tok = call_gemini(prompt, model=model)
    else:
        raise ValueError(f"Provedor {provider} não suportado.")
    return q["id"], res, inp_tok, out_tok


def main():
    parser = argparse.ArgumentParser(description="Reescrita de Comentários MedQuest — Padrão Residência R1-USP")
    parser.add_argument("--id", type=int, help="ID de uma questão específica para teste")
    parser.add_argument("--area", type=str, help="Filtrar por Grande Área (ex: Pediatria, Cirurgia, Clínica Médica)")
    parser.add_argument("--subtema", type=str, help="Filtrar por Subtema (ex: Apendicite, Asma)")
    parser.add_argument("--mode", choices=["older", "missing_raciocinio", "missing_distractors", "critical", "all"], default="older", help="Modo de seleção de questões")
    parser.add_argument("--limit", type=int, default=None, help="Limite de questões a processar")
    parser.add_argument("--dry-run", action="store_true", help="Executa e mostra no terminal sem gravar no banco de dados")
    parser.add_argument("--provider", choices=["yunqiao", "somaapi", "gemini"], default="somaapi", help="Provedor LLM")
    parser.add_argument("--model", type=str, help="Nome do modelo")
    parser.add_argument("--workers", type=int, default=3, help="Número de chamadas simultâneas (padrão: 3)")
    parser.add_argument("--keys", nargs="+", help="Lista de chaves de API com failover automático")

    args = parser.parse_args()

    if not args.model:
        if args.provider == "somaapi":
            args.model = DEFAULT_SOMA_MODEL
        elif args.provider == "yunqiao":
            args.model = DEFAULT_YUNQIAO_MODEL
        else:
            args.model = "gemini-3.5-flash-lite"

    if args.keys:
        active_keys = args.keys
    else:
        if args.provider == "somaapi":
            active_keys = DEFAULT_SOMA_KEYS
        elif args.provider == "gemini":
            active_keys = GEMINI_KEYS
        else:
            active_keys = DEFAULT_YUNQIAO_KEYS

    key_manager = KeyManager(active_keys)

    if args.provider in ("yunqiao", "somaapi") and key_manager.is_exhausted():
        print(f"❌ Erro: Nenhuma chave disponível para {args.provider.upper()}.", file=sys.stderr)
        sys.exit(1)

    print("=" * 70)
    print("🏥 MEDQUEST — REESCRITA DE EXPLICAÇÕES NO TEMPLATE OURO (USP R1)")
    print("=" * 70)
    print(f"• Provedor: {args.provider.upper()} | Modelo: {args.model}")
    print(f"• Chaves configuradas: {len(active_keys)} chave(s) com rotação automática")
    print(f"• Modo de seleção: {args.mode} | Limite: {args.limit or 'Sem limite'}")
    if args.area:
        print(f"• Filtro Área: {args.area}")
    if args.subtema:
        print(f"• Filtro Subtema: {args.subtema}")
    if args.id:
        print(f"• Questão Única: ID {args.id}")
    print(f"• Dry-Run (Sem gravação): {'SIM' if args.dry_run else 'NÃO'}")
    print("-" * 70)

    questions = fetch_questions(
        mode=args.mode,
        area=args.area,
        subtema=args.subtema,
        question_id=args.id,
        limit=args.limit
    )

    if not questions:
        print("ℹ️ Nenhuma questão encontrada com os filtros selecionados.")
        return

    print(f"🎯 Total de questões a processar: {len(questions)}")

    if args.dry_run:
        q = questions[0]
        print(f"\n--- [DRY-RUN] Testando QID {q['id']} ({q['area']} - {q['subtema']}) ---")
        qid, res, in_t, out_t = process_question(q, args.provider, args.model, key_manager)
        if res:
            print("\n" + "=" * 50 + " COMENTÁRIO GERADO " + "=" * 50)
            print(res)
            print("=" * 120)
            print(f"Tokens de Entrada: ~{in_t} | Tokens de Saída: ~{out_t}")
            p_in, p_out = get_model_pricing(args.model)
            cost = (in_t * p_in) + (out_t * p_out)
            print(f"Custo estimado desta questão: US$ {cost:.5f} (~R$ {cost * 5.6:.3f})")
            print("=" * 120)
        else:
            print("❌ Falha na geração.")
        return

    backup_database()

    conn = get_db()
    cursor = conn.cursor()

    total = len(questions)
    sucesso = 0
    total_in_tokens = 0
    total_out_tokens = 0
    inicio = time.time()

    print(f"\n🚀 Iniciando processamento de {total} questões com {args.workers} workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        question_iter = iter(questions)
        future_map = {}

        # Preenche os workers iniciais
        for _ in range(args.workers * 2):
            try:
                q = next(question_iter)
                f = executor.submit(process_question, q, args.provider, args.model, key_manager)
                future_map[f] = q
                time.sleep(0.2)
            except StopIteration:
                break

        idx = 0
        while future_map:
            done, _ = concurrent.futures.wait(future_map.keys(), return_when=concurrent.futures.FIRST_COMPLETED)
            for future in done:
                idx += 1
                q = future_map.pop(future)
                qid = q["id"]
                try:
                    _, explanation, in_t, out_t = future.result()
                    if explanation and len(explanation) > 150:
                        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
                        cursor.execute("""
                            INSERT INTO explanations (question_id, explanation_text, generated_at, reviewed_at)
                            VALUES (?, ?, ?, ?)
                            ON CONFLICT(question_id) DO UPDATE SET
                                explanation_text = excluded.explanation_text,
                                reviewed_at = excluded.reviewed_at
                        """, (qid, explanation, now, now))
                        conn.commit()

                        sucesso += 1
                        total_in_tokens += in_t
                        total_out_tokens += out_t
                        tempo_passado = time.time() - inicio
                        print(f"[{idx}/{total}] ✅ QID {qid} ({q['area']} | {q['subtema'][:25]}) | In: {in_t} Out: {out_t} ({tempo_passado:.1f}s)", flush=True)
                    else:
                        print(f"[{idx}/{total}] ⚠️ QID {qid}: Falha ao gerar comentário válido.", flush=True)
                except Exception as e:
                    print(f"[{idx}/{total}] ❌ QID {qid}: Erro: {e}", flush=True)

                if key_manager.is_exhausted():
                    print("\n🛑 Todas as chaves foram esgotadas. Finalizando tarefas pendentes...", flush=True)
                    question_iter = iter([])
                    break

                if not key_manager.is_exhausted():
                    try:
                        next_q = next(question_iter)
                        time.sleep(0.1)
                        new_f = executor.submit(process_question, next_q, args.provider, args.model, key_manager)
                        future_map[new_f] = next_q
                    except StopIteration:
                        pass

    conn.close()
    duracao = time.time() - inicio
    p_in, p_out = get_model_pricing(args.model)
    custo_total = (total_in_tokens * p_in) + (total_out_tokens * p_out)

    print("\n" + "=" * 70)
    print("🎉 PROCESSAMENTO CONCLUÍDO!")
    print(f"• Questões atualizadas com sucesso: {sucesso}/{total}")
    print(f"• Duração total: {duracao:.1f} segundos (Média: {duracao / max(1, sucesso):.1f}s/questão)")
    print(f"• Total de tokens: {total_in_tokens:,} entrada | {total_out_tokens:,} saída")
    print(f"• Custo estimado total: US$ {custo_total:.4f} (~R$ {custo_total * 5.6:.2f})")
    print("=" * 70)


if __name__ == "__main__":
    main()
