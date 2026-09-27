#!/usr/bin/env python3
"""
MedQuest - Auto-Heal Flashcards (Google Gemini AI)
===================================================
Script autônomo conectado às APIs Google (Gemini Pool) para monitorar, detectar,
corrigir e restaurar flashcards reportados por alunos ("na internet" / Turso Cloud e local).

Quando um usuário reporta um card na aplicação web, o campo `report_status` é preenchido
com o motivo (ex: "Mal formatado", "Erro médico", "Gabarito errado"). O card fica
automaticamente oculto das sessões de estudo.

Este script:
1. Detecta cards reportados na nuvem (Turso Cloud) ou localmente.
2. Recupera o contexto médico completo da questão de residência vinculada.
3. Utiliza o pool multi-chave do Google Gemini com fallback automático de modelos.
4. Gera uma correção clínica, sintática (Cloze {{c1::...}}) e de formatação impecável.
5. Salva um log de auditoria detalhado em `flashcard_repair_logs`.
6. Remove o `report_status` (NULL), recolocando o card ONLINE instantaneamente.

Modos de uso:
-------------
- Execução única (One-shot, processa todos os reportados e encerra):
    python scripts/auto_heal_cards.py

- Modo Sentinela / Daemon (Monitora continuamente a cada 30 segundos):
    python scripts/auto_heal_cards.py --watch --interval 30

- Simulação sem alterar o banco (Dry-Run):
    python scripts/auto_heal_cards.py --dry-run

- Corrigir um card específico:
    python scripts/auto_heal_cards.py --card-id 245

- Definir alvo (turso [padrão], local, both):
    python scripts/auto_heal_cards.py --target both
"""

import argparse
import json
import logging
import os
import re
import signal
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Configuração de Caminhos e Ambiente
# -----------------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = ROOT_DIR / "app" / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Carrega variáveis de ambiente (.env da raiz e do backend)
from dotenv import load_dotenv

env_candidates = [ROOT_DIR / ".env", BACKEND_DIR / ".env"]
for env_path in env_candidates:
    if env_path.exists():
        load_dotenv(env_path)

from api.db import _connect_turso, _reconnect_turso, TursoConnection
from api.gemini_pool import gemini_pool

# -----------------------------------------------------------------------------
# Configuração de Logging com Cores ANSI
# -----------------------------------------------------------------------------
class ColoredFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[36m",     # Ciano
        logging.INFO: "\033[32m",      # Verde
        logging.WARNING: "\033[33m",   # Amarelo
        logging.ERROR: "\033[31m",     # Vermelho
        logging.CRITICAL: "\033[41m",  # Fundo Vermelho
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def format(self, record):
        color = self.COLORS.get(record.levelno, self.RESET)
        time_str = datetime.now().strftime("%H:%M:%S")
        prefix = f"{self.BOLD}[{time_str} AutoHeal]{self.RESET} {color}[{record.levelname}]{self.RESET}"
        return f"{prefix} {record.getMessage()}"


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter())
logger = logging.getLogger("AutoHeal")
logger.setLevel(logging.INFO)
logger.addHandler(handler)


# -----------------------------------------------------------------------------
# Gerenciador de Banco de Dados (Turso Cloud & SQLite Local)
# -----------------------------------------------------------------------------
class DatabaseManager:
    """Gerencia conexões seguras com Turso Cloud e/ou SQLite local."""

    def __init__(self, target: str = "turso"):
        self.target = target.lower()
        self.turso_url = os.environ.get("TURSO_DATABASE_URL")
        self.turso_token = os.environ.get("TURSO_AUTH_TOKEN")
        self.local_db_path = Path(os.environ.get("MEDQUEST_DB", BACKEND_DIR / "medquest.db"))

        self.turso_conn: Optional[TursoConnection] = None
        self.local_conn: Optional[sqlite3.Connection] = None

        self._init_connections()
        self.ensure_repair_tables()

    def _init_connections(self):
        if self.target in ("turso", "both"):
            if not self.turso_url or not self.turso_token:
                if self.target == "turso":
                    raise ValueError(
                        "TURSO_DATABASE_URL e TURSO_AUTH_TOKEN são obrigatórios para --target turso. "
                        "Verifique seu arquivo .env."
                    )
                logger.warning("Credenciais Turso não encontradas; operando apenas em modo local.")
            else:
                client = _connect_turso(self.turso_url, self.turso_token)
                self.turso_conn = TursoConnection(
                    client,
                    persistent=True,
                    reconnect=lambda fc: _reconnect_turso(self.turso_url, self.turso_token, fc),
                )
                logger.info(f"Conexão com Turso Cloud estabelecida: {self.turso_url}")

        if self.target in ("local", "both"):
            if not self.local_db_path.exists():
                logger.warning(f"Banco local SQLite não encontrado em {self.local_db_path}")
            else:
                self.local_conn = sqlite3.connect(str(self.local_db_path), timeout=15)
                self.local_conn.row_factory = sqlite3.Row
                self.local_conn.execute("PRAGMA foreign_keys = ON")
                self.local_conn.execute("PRAGMA busy_timeout = 10000")
                try:
                    self.local_conn.execute("PRAGMA journal_mode = WAL")
                    self.local_conn.execute("PRAGMA synchronous = NORMAL")
                except Exception:
                    pass
                logger.info(f"Conexão com SQLite Local estabelecida: {self.local_db_path.name}")

    def ensure_repair_tables(self):
        """Cria a tabela de histórico de auditoria de reparos caso não exista."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS flashcard_repair_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            flashcard_id INTEGER NOT NULL,
            report_reason TEXT,
            original_front TEXT,
            original_back TEXT,
            repaired_front TEXT,
            repaired_back TEXT,
            fix_summary TEXT,
            changes_json TEXT,
            model_used TEXT,
            target_db TEXT,
            repaired_at TEXT NOT NULL
        )
        """
        create_idx_sql = "CREATE INDEX IF NOT EXISTS idx_repair_logs_fid ON flashcard_repair_logs(flashcard_id)"

        if self.turso_conn:
            try:
                self.turso_conn.execute(create_sql)
                self.turso_conn.execute(create_idx_sql)
                self.turso_conn.commit()
            except Exception as e:
                logger.error(f"Erro ao verificar tabela de logs no Turso: {e}")

        if self.local_conn:
            try:
                self.local_conn.execute(create_sql)
                self.local_conn.execute(create_idx_sql)
                self.local_conn.commit()
            except Exception as e:
                logger.error(f"Erro ao verificar tabela de logs local: {e}")

    def get_primary_connection(self):
        """Retorna a conexão principal para consulta dos cards reportados."""
        if self.turso_conn:
            return self.turso_conn
        if self.local_conn:
            return self.local_conn
        raise RuntimeError("Nenhuma conexão de banco ativa (Turso ou Local).")

    def fetch_reported_cards(self, specific_card_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Busca flashcards com report_status ativo."""
        conn = self.get_primary_connection()
        if specific_card_id:
            sql = """
                SELECT id, question_id, front, back, report_status, source_context,
                       deck_name, tags, user_id, is_ai_generated
                FROM flashcards
                WHERE id = ? AND report_status IS NOT NULL AND TRIM(report_status) != ''
            """
            rows = conn.execute(sql, (specific_card_id,)).fetchall()
        else:
            sql = """
                SELECT id, question_id, front, back, report_status, source_context,
                       deck_name, tags, user_id, is_ai_generated
                FROM flashcards
                WHERE report_status IS NOT NULL AND TRIM(report_status) != ''
                ORDER BY id ASC
            """
            rows = conn.execute(sql).fetchall()

        cards = []
        for r in rows:
            cards.append({
                "id": r["id"],
                "question_id": r["question_id"],
                "front": r["front"] or "",
                "back": r["back"] or "",
                "report_status": r["report_status"] or "",
                "source_context": r["source_context"] or "",
                "deck_name": r["deck_name"] or "Geral",
                "tags": r["tags"] or "",
                "user_id": r["user_id"] or "1",
                "is_ai_generated": r["is_ai_generated"] or 0,
            })
        return cards

    def fetch_question_context(self, question_id: Optional[int]) -> Optional[Dict[str, Any]]:
        """Busca o contexto completo da questão médica vinculada."""
        if not question_id:
            return None

        conn = self.get_primary_connection()
        try:
            q_row = conn.execute(
                "SELECT stem, correct_letter, area, subtema, topic FROM questions WHERE id = ?",
                (question_id,)
            ).fetchone()
            if not q_row:
                return None

            alts = conn.execute(
                "SELECT letter, text, is_correct FROM alternatives WHERE question_id = ? ORDER BY letter",
                (question_id,)
            ).fetchall()

            exp_row = conn.execute(
                "SELECT explanation_text FROM explanations WHERE question_id = ?",
                (question_id,)
            ).fetchone()

            return {
                "question_id": question_id,
                "stem": q_row["stem"],
                "correct_letter": q_row["correct_letter"],
                "area": q_row["area"] or "",
                "subtema": q_row["subtema"] or "",
                "topic": q_row["topic"] or "",
                "alternatives": [
                    {
                        "letter": a["letter"],
                        "text": a["text"],
                        "is_correct": bool(a["is_correct"])
                    }
                    for a in alts
                ],
                "explanation": exp_row["explanation_text"] if exp_row else "",
            }
        except Exception as e:
            logger.warning(f"Não foi possível obter contexto da questão {question_id}: {e}")
            return None

    def apply_repair(
        self,
        card_id: int,
        fixed_front: str,
        fixed_back: str,
        report_reason: str,
        original_front: str,
        original_back: str,
        fix_summary: str,
        changes_made: List[str],
        model_used: str,
    ) -> bool:
        """
        Aplica a correção no banco de dados:
        - Atualiza front e back com a versão corrigida
        - Reseta report_status para NULL (colocando o card online de imediato)
        - Insere registro detalhado de auditoria em flashcard_repair_logs
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        changes_json = json.dumps(changes_made, ensure_ascii=False)
        success = True

        # Atualização no Turso Cloud
        if self.turso_conn:
            try:
                self.turso_conn.execute(
                    """
                    UPDATE flashcards
                    SET front = ?, back = ?, report_status = NULL
                    WHERE id = ?
                    """,
                    (fixed_front, fixed_back, card_id)
                )
                self.turso_conn.execute(
                    """
                    INSERT INTO flashcard_repair_logs (
                        flashcard_id, report_reason, original_front, original_back,
                        repaired_front, repaired_back, fix_summary, changes_json,
                        model_used, target_db, repaired_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'turso', ?)
                    """,
                    (
                        card_id, report_reason, original_front, original_back,
                        fixed_front, fixed_back, fix_summary, changes_json,
                        model_used, now_iso
                    )
                )
                self.turso_conn.commit()
                logger.info(f"✅ Card #{card_id} atualizado no Turso Cloud e recolocado ONLINE.")
            except Exception as e:
                logger.error(f"❌ Falha ao aplicar reparo do card #{card_id} no Turso: {e}")
                success = False

        # Atualização no SQLite Local
        if self.local_conn and self.target in ("local", "both"):
            try:
                # Verifica se o card existe localmente
                row = self.local_conn.execute("SELECT id FROM flashcards WHERE id = ?", (card_id,)).fetchone()
                if row:
                    self.local_conn.execute(
                        """
                        UPDATE flashcards
                        SET front = ?, back = ?, report_status = NULL
                        WHERE id = ?
                        """,
                        (fixed_front, fixed_back, card_id)
                    )
                    self.local_conn.execute(
                        """
                        INSERT INTO flashcard_repair_logs (
                            flashcard_id, report_reason, original_front, original_back,
                            repaired_front, repaired_back, fix_summary, changes_json,
                            model_used, target_db, repaired_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'local', ?)
                        """,
                        (
                            card_id, report_reason, original_front, original_back,
                            fixed_front, fixed_back, fix_summary, changes_json,
                            model_used, now_iso
                        )
                    )
                    self.local_conn.commit()
                    logger.info(f"✅ Card #{card_id} atualizado no SQLite local e sincronizado.")
                else:
                    logger.debug(f"Card #{card_id} não existe no banco SQLite local (apenas no Turso).")
            except Exception as e:
                logger.error(f"❌ Falha ao aplicar reparo do card #{card_id} no SQLite local: {e}")
                if self.target == "local":
                    success = False

        return success


# -----------------------------------------------------------------------------
# Mecanismo de Reparo por Inteligência Artificial (Google Gemini)
# -----------------------------------------------------------------------------
class CardHealer:
    """Motor de diagnóstico e restauração de cards utilizando Google Gemini."""

    SYSTEM_INSTRUCTION = """
Você é um preceptor médico especialista e designer pedagógico sênior da plataforma MedQuest, especializado em flashcards médicos de alta performance (formato Cloze / repetição espaçada FSRS) para provas de Residência Médica (USP, UNICAMP, SUS-SP, ENARE).

Sua missão é analisar um flashcard que foi reportado por um aluno, identificar com precisão o problema relatado (erro médico, má formatação, ambiguidade, cloze mal posicionado, texto cortado, distrator inadequado ou desatualização), corrigi-lo com máxima precisão médica e devolvê-lo perfeito, didático e pronto para estudo online.

DIRETRIZES FUNDAMENTAIS DE QUALIDADE (PADRÃO MEDQUEST):
1. ESTRUTURA DO FRONT:
   - Deve iniciar com a tag do tema entre colchetes, ex: [Tema / Subtema].
   - Em seguida, traga o caso clínico essencial em 1 a 2 frases concisas com os achados clínicos relevantes.
   - Finalize com uma pergunta clínica clara e direcionada contendo a omissão cloze:
     👉 Conduta / Diagnóstico / Conceito: {{c1::Resposta Correta}}
   - A resposta omitida no cloze {{c1::...}} deve ser o conceito-chave, sem pontuação solta ou erros de sintaxe.
   - NUNCA mencione letras de alternativas (ex: "Alternativa C", "opção B") no front ou back do card.

2. ESTRUTURA DO BACK:
   - Inicie com "💡 **Pulo do Gato:**" trazendo a regra de ouro médica, conduta padrão-ouro ou fisiopatologia direta.
   - Se houver distrator relevante ou pegadinha clássica, adicione "⚠️ **Por que não '...'?**" explicando por que a conduta alternativa é incorreta e qual o erro conceitual.
   - Utilize markdown limpo (negrito para termos-chave, listas se necessário).
   - NUNCA inclua tags HTML residuais (<p>, <br>, <span>).

3. TRATAMENTO ESPECÍFICO DO MOTIVO DO REPORT:
   - "Mal formatado": ajuste quebras de linha (\\n\\n), sintaxe do cloze {{c1::...}}, pontuação e negritos.
   - "Erro médico" ou "Gabarito errado": ajuste a conduta médica conforme diretrizes e Ministério da Saúde.
   - "Texto cortado" ou "Incompleto": recupere o raciocínio completo com base no caso clínico original.

Responda ESTRITAMENTE em formato JSON com a seguinte estrutura:
{
  "fixed_front": "[Subtema] Resumo do caso clínico...\\n\\n👉 Pergunta clínica: {{c1::Resposta}}",
  "fixed_back": "💡 **Pulo do Gato:**\\n...\\n\\n⚠️ **Por que não '...'?**\\n...",
  "fix_summary": "Resumo técnico sucinto do que foi consertado (1 frase)",
  "changes_made": [
    "Alteração específica 1",
    "Alteração específica 2"
  ]
}
"""

    def __init__(self, model_override: Optional[str] = None):
        self.model_override = model_override

    def heal_card(
        self,
        card: Dict[str, Any],
        question_ctx: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """Executa a análise e reparo do flashcard via Google Gemini."""
        prompt = self._build_prompt(card, question_ctx)
        try:
            response = gemini_pool.generate_content(
                prompt=prompt,
                system_instruction=self.SYSTEM_INSTRUCTION,
                json_mode=True,
                model=self.model_override,
                temperature=0.15,
                timeout=30,
            )

            raw_text = response.get("text", "").strip()
            parsed = self._parse_and_validate_response(raw_text, card)
            if parsed:
                parsed["model_used"] = response.get("model", "gemini")
                return parsed

            logger.warning(f"Resposta da IA para o card #{card['id']} falhou na validação de formato.")
            return None

        except Exception as e:
            logger.error(f"Erro ao chamar Gemini API para o card #{card['id']}: {e}")
            return None

    def _build_prompt(self, card: Dict[str, Any], q_ctx: Optional[Dict[str, Any]]) -> str:
        prompt_parts = [
            "POR FAVOR, ANALISE E CONSERTE ESTE FLASHCARD REPORTADO NO MEDQUEST:",
            f"ID DO CARD: {card['id']}",
            f"MOTIVO DO REPORT DO ALUNO: {card['report_status']}",
            f"DECK / CONTEXTO: {card.get('source_context') or card.get('deck_name') or 'Geral'}",
            "",
            "FRONT ATUAL (FRENTE):",
            card["front"],
            "",
            "BACK ATUAL (VERSO):",
            card["back"] if card["back"] else "(Verso vazio)",
        ]

        if q_ctx:
            prompt_parts.extend([
                "",
                "---",
                "CONTEXTO DA QUESTÃO ORIGINAL DE RESIDÊNCIA MÉDICA:",
                f"ÁREA / SUBTEMA: {q_ctx.get('area')} > {q_ctx.get('subtema') or q_ctx.get('topic')}",
                f"ENUNCIADO (CASO CLÍNICO):\n{q_ctx.get('stem')}",
                "",
                f"GABARITO OFICIAL: Letra {q_ctx.get('correct_letter')}",
                "ALTERNATIVAS DA QUESTÃO:"
            ])
            for alt in q_ctx.get("alternatives", []):
                mark = " [CORRETA - GABARITO]" if alt["is_correct"] else ""
                prompt_parts.append(f"  {alt['letter']}) {alt['text']}{mark}")

            if q_ctx.get("explanation"):
                prompt_parts.extend([
                    "",
                    "COMENTÁRIO DO PROFESSOR / EXPLICAÇÃO OFICIAL:",
                    q_ctx["explanation"]
                ])

        prompt_parts.extend([
            "",
            "---",
            "AÇÃO ESPERADA:",
            f"Conserte o card atendendo à reclamação do aluno ('{card['report_status']}').",
            "Mantenha ou aperfeiçoe a formatação Cloze ({{c1::...}}) e os padrões do MedQuest.",
            "Responda estritamente em JSON."
        ])

        return "\n".join(prompt_parts)

    def _parse_and_validate_response(
        self, raw_text: str, original_card: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Extrai e valida o JSON retornado pelo Gemini."""
        if not raw_text:
            return None

        # Remove possíveis blocos markdown ```json ... ``` se existirem
        cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            # Fallback para regex caso venha com texto extra ao redor
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if match:
                try:
                    data = json.loads(match.group(0))
                except Exception:
                    return None
            else:
                return None

        fixed_front = data.get("fixed_front", "").strip()
        fixed_back = data.get("fixed_back", "").strip()
        fix_summary = data.get("fix_summary", "").strip()
        changes_made = data.get("changes_made", [])

        if not fixed_front or not fixed_back:
            return None

        # Validação da sintaxe Cloze: deve conter {{c1::...}}
        if not re.search(r"\{\{c\d+::.*?\}\}", fixed_front):
            logger.warning("Front corrigido não contém sintaxe Cloze válida {{c1::...}}.")
            # Se o original tinha cloze, não aceitamos perder o cloze
            if "{{c" in original_card.get("front", ""):
                return None

        # Garante lista em changes_made
        if not isinstance(changes_made, list):
            changes_made = [str(changes_made)]

        return {
            "fixed_front": fixed_front,
            "fixed_back": fixed_back,
            "fix_summary": fix_summary or "Card corrigido e reformatado com sucesso.",
            "changes_made": changes_made,
        }


# -----------------------------------------------------------------------------
# Orquestrador de Processamento e Sentinela (Watch Mode)
# -----------------------------------------------------------------------------
def process_single_card(
    card: Dict[str, Any],
    db_mgr: DatabaseManager,
    healer: CardHealer,
    dry_run: bool = False
) -> bool:
    """Processa a recuperação de um único flashcard."""
    card_id = card["id"]
    reason = card["report_status"]
    logger.info(f"🔍 Diagnosticando Card #{card_id} | Motivo do report: '{reason}'")

    q_ctx = db_mgr.fetch_question_context(card.get("question_id"))
    if q_ctx:
        logger.debug(f"Contexto médico recuperado para o card #{card_id} (Questão #{card['question_id']})")

    start_ai = time.time()
    repair = healer.heal_card(card, q_ctx)
    elapsed_ai = time.time() - start_ai

    if not repair:
        logger.error(f"❌ Não foi possível gerar uma correção válida para o card #{card_id}.")
        return False

    model_used = repair.get("model_used", "gemini")
    logger.info(f"🤖 IA ({model_used}, {elapsed_ai:.1f}s) propôs correção para o card #{card_id}:")
    logger.info(f"   💡 Resumo do reparo: {repair['fix_summary']}")
    for change in repair.get("changes_made", []):
        logger.info(f"   - {change}")

    if dry_run:
        print("\n" + "=" * 65)
        print(f"🔬 [SIMULAÇÃO / DRY-RUN] CARD #{card_id}")
        print("=" * 65)
        print("--- FRONT ORIGINAL ---")
        print(card["front"])
        print("\n--- FRONT CORRIGIDO ---")
        print(repair["fixed_front"])
        print("\n--- BACK ORIGINAL ---")
        print(card["back"])
        print("\n--- BACK CORRIGIDO ---")
        print(repair["fixed_back"])
        print("=" * 65 + "\n")
        logger.info(f"Card #{card_id} [DRY-RUN]: nenhuma alteração gravada no banco.")
        return True

    # Aplicação no Banco de Dados
    applied = db_mgr.apply_repair(
        card_id=card_id,
        fixed_front=repair["fixed_front"],
        fixed_back=repair["fixed_back"],
        report_reason=reason,
        original_front=card["front"],
        original_back=card["back"],
        fix_summary=repair["fix_summary"],
        changes_made=repair["changes_made"],
        model_used=model_used,
    )
    return applied


def run_pipeline(
    db_mgr: DatabaseManager,
    healer: CardHealer,
    card_id: Optional[int] = None,
    dry_run: bool = False
) -> Tuple[int, int, int]:
    """Executa uma varredura sobre os flashcards reportados."""
    cards = db_mgr.fetch_reported_cards(specific_card_id=card_id)
    if not cards:
        if card_id:
            logger.info(f"Nenhum card reportado com ID #{card_id} encontrado.")
        else:
            logger.debug("Nenhum card reportado pendente no momento.")
        return 0, 0, 0

    logger.info(f"🚨 Detectado(s) {len(cards)} card(s) reportado(s) para tratamento.")
    success_count = 0
    fail_count = 0

    for card in cards:
        ok = process_single_card(card, db_mgr, healer, dry_run=dry_run)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    return len(cards), success_count, fail_count


def start_watch_loop(
    db_mgr: DatabaseManager,
    healer: CardHealer,
    interval: int = 30,
    dry_run: bool = False
):
    """Executa o Sentinela em loop contínuo (Watch Mode)."""
    running = True

    def _sig_handler(sig, frame):
        nonlocal running
        logger.info("Sinal de interrupção recebido. Encerrando Sentinela com segurança...")
        running = False

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    logger.info(f"👀 Sentinela ativado! Monitorando banco '{db_mgr.target}' a cada {interval}s.")
    logger.info("Pressione Ctrl+C para encerrar.")

    while running:
        try:
            total, ok, fail = run_pipeline(db_mgr, healer, dry_run=dry_run)
            if total > 0:
                logger.info(f"Varredura concluída: {ok} corrigido(s), {fail} falha(s).")
        except Exception as e:
            logger.error(f"Erro inesperado durante ciclo de monitoramento: {e}", exc_info=True)

        # Espera fracionada para responder imediatamente a sinais de interrupção
        for _ in range(interval):
            if not running:
                break
            time.sleep(1)

    logger.info("Sentinela finalizado com sucesso.")


# -----------------------------------------------------------------------------
# CLI Entrypoint
# -----------------------------------------------------------------------------
def parse_arguments():
    parser = argparse.ArgumentParser(
        description="Auto-Heal Flashcards (Google Gemini AI) - Detecção e restauração automática de cards reportados."
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Executar em modo contínuo (Sentinela / Daemon), verificando periodicamente novos reports."
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=30,
        help="Intervalo em segundos entre verificações no modo --watch (padrão: 30)."
    )
    parser.add_argument(
        "--target", "-t",
        choices=["turso", "local", "both"],
        default="turso",
        help="Banco de dados de destino: 'turso' (nuvem online, padrão), 'local' (SQLite) ou 'both' (ambos sincronizados)."
    )
    parser.add_argument(
        "--card-id", "-c",
        type=int,
        default=None,
        help="Corrigir exclusivamente um ID de flashcard específico."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Executar em modo de simulação (diagnostica e propõe as correções sem alterar o banco de dados)."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Forçar um modelo específico do Gemini (ex: 'gemini-3.5-flash-lite', 'gemini-3.6-flash')."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Ativar logging detalhado (DEBUG)."
    )
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=======================================================")
    logger.info("MedQuest - Auto-Heal Flashcards (Google Gemini Engine)")
    logger.info("=======================================================")
    logger.info(f"Alvo do Banco: {args.target.upper()} | Modo: {'SENTINELA (Watch)' if args.watch else 'ONE-SHOT'}")
    logger.info(f"Total de chaves Google AI registradas: {gemini_pool.total_keys}")

    try:
        db_mgr = DatabaseManager(target=args.target)
    except Exception as e:
        logger.critical(f"Falha fatal ao inicializar banco de dados: {e}")
        sys.exit(1)

    healer = CardHealer(model_override=args.model)

    if args.watch:
        start_watch_loop(db_mgr, healer, interval=args.interval, dry_run=args.dry_run)
    else:
        total, ok, fail = run_pipeline(db_mgr, healer, card_id=args.card_id, dry_run=args.dry_run)
        if total == 0:
            logger.info("✨ Nenhum card reportado precisando de reparos no momento.")
        else:
            logger.info(f"🏁 Processamento finalizado: {ok}/{total} corrigido(s) com sucesso. ({fail} falha(s))")


if __name__ == "__main__":
    main()
