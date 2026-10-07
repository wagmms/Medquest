#!/usr/bin/env python3
"""
MedQuest - Script de Correção de Alternativas Corretas Trocadas (Gabaritos).
Corrige as questões identificadas com gabarito trocado tanto no SQLite local
(app/backend/medquest.db) quanto no Turso Cloud via HTTP Pipeline v2.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BACKEND_DIR.parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from scripts.extract_medway import (
    clean_html_to_markdown,
    format_medway_golden_explanation,
    normalize_text,
)

DB_PATH = BACKEND_DIR / "medquest.db"
EXAMS_DIR = BACKEND_DIR / "data" / "medway_extracted" / "exams"
SCRATCH_DIR = Path("/home/wagmoraes/.gemini/antigravity/brain/0336619c-87df-4bb7-9f80-e253d7caf709/scratch")
CANDIDATES_FILE = SCRATCH_DIR / "to_fix_final.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("repair_swapped_answers")


def load_env() -> None:
    env_paths = [ROOT_DIR / ".env", BACKEND_DIR / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))


def get_turso_config() -> Tuple[Optional[str], Optional[str]]:
    load_env()
    raw_url = os.environ.get("TURSO_DATABASE_URL", "")
    token = os.environ.get("TURSO_AUTH_TOKEN", "")
    if not raw_url or not token:
        return None, None
    url = raw_url.replace("libsql://", "https://").replace("wss://", "https://") + "/v2/pipeline"
    return url, token


def execute_turso_pipeline(
    url: str, token: str, requests_list: list, timeout: int = 60, retries: int = 4
) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = json.dumps({"requests": requests_list}).encode("utf-8")
    last_err = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(attempt * 2)
            else:
                raise last_err
    return {}


def rebuild_fallback_explanation(old_exp: str, new_let: str, old_let: str) -> str:
    """Reorganiza o markdown da explicação existente quando o pacote JSON original não está disponível."""
    pulo_m = re.search(r"(\*\*Pulo do Gato\*\*:[\s\S]*?)(?=\n\n\*\*Raciocínio Clínico\*\*|\n\n\*\*Por que a Letra|\Z)", old_exp)
    rac_m = re.search(r"(\*\*Raciocínio Clínico\*\*:[\s\S]*?)(?=\n\n\*\*Por que a Letra|\n\n\*\*Análise dos Distratores|\Z)", old_exp)
    por_m = re.search(r"\*\*Por que a Letra\s*([A-E])\s*é a Correta\?\*\*:\s*([\s\S]*?)(?=\n\n\*\*Análise dos Distratores|\Z)", old_exp)
    dist_m = re.search(r"\*\*Análise dos Distratores\*\*:\s*([\s\S]*?)(?=\n\n\*\*Referências Bibliográficas|\Z)", old_exp)

    pulo_text = pulo_m.group(1).strip() if pulo_m else "**Pulo do Gato**:\nAtenção aos conceitos clínicos essenciais."
    rac_text = rac_m.group(1).strip() if rac_m else ""

    option_texts: Dict[str, str] = {}
    if por_m:
        option_texts[por_m.group(1).upper()] = por_m.group(2).strip()
    if dist_m:
        dist_body = dist_m.group(1)
        for line in dist_body.split("\n- "):
            lm = re.match(r"(?:- )?\*\*Letra\s*([A-E])\*\*:\s*([\s\S]*)", line.strip())
            if lm:
                option_texts[lm.group(1).upper()] = lm.group(2).strip()

    target_correct_text = option_texts.get(new_let, "Alternativa correta conforme as diretrizes clínicas.")
    dist_lines = []
    for l in sorted(option_texts.keys()):
        if l != new_let:
            dist_lines.append(f"- **Letra {l}**: {option_texts[l]}")

    parts = [
        f"**Gabarito**: Letra {new_let}",
        pulo_text,
    ]
    if rac_text:
        parts.append(rac_text)
    parts.append(f"**Por que a Letra {new_let} é a Correta?**:\n{target_correct_text}")
    if dist_lines:
        parts.append("**Análise dos Distratores**:\n" + "\n".join(dist_lines))

    return "\n\n".join(parts)


def run_repair(sync_turso: bool = True) -> None:
    if not CANDIDATES_FILE.exists():
        logger.error("Arquivo de candidatos %s não encontrado. Execute consolidate_swapped_questions.py primeiro.", CANDIDATES_FILE)
        return

    with open(CANDIDATES_FILE, "r", encoding="utf-8") as f:
        candidates = json.load(f)

    logger.info("Carregadas %d questões candidatas para correção.", len(candidates))

    # 1. Backup do banco SQLite
    backup_path = DB_PATH.with_suffix(f".db.bak_gabaritos_{int(time.time())}")
    logger.info("Criando backup do banco local em %s...", backup_path)
    shutil.copy2(DB_PATH, backup_path)

    # 2. Conexão SQLite local
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Cache de arquivos de prova
    track_cache: Dict[str, Any] = {}
    re_track_id = re.compile(r"\[(\d+)\]")

    def get_track_data(tid: str) -> Optional[Dict[str, Any]]:
        if tid in track_cache:
            return track_cache[tid]
        tf = EXAMS_DIR / f"track_{tid}.json"
        if not tf.exists():
            track_cache[tid] = None
            return None
        try:
            with open(tf, "r", encoding="utf-8") as fp:
                tdata = json.load(fp)
            track_cache[tid] = tdata
            return tdata
        except Exception:
            track_cache[tid] = None
            return None

    now_iso = datetime.now(timezone.utc).isoformat()
    total_corrected = 0
    turso_stmts: List[Dict[str, Any]] = []

    logger.info("Iniciando atualização no banco local SQLite...")

    for idx, c in enumerate(candidates, start=1):
        qid = c["id"]
        old_let = c["old_letter"]
        new_let = c["new_letter"]
        sf = c.get("source_file", "")
        sn = c.get("source_number")

        # 1. Gerar nova explicação
        new_exp_text = None
        m_tid = re_track_id.search(sf)
        if m_tid:
            tid = m_tid.group(1)
            tdata = get_track_data(tid)
            if tdata and isinstance(tdata, dict):
                questions = tdata.get("questions", [])
                matched_item = None
                if sn and 1 <= sn <= len(questions):
                    cand_item = questions[sn - 1]
                    if isinstance(cand_item, dict):
                        matched_item = cand_item

                if matched_item:
                    det = matched_item.get("detail", {})
                    exp_det = matched_item.get("explanation", {})
                    opts = det.get("options", [])
                    new_exp_text = format_medway_golden_explanation(
                        exp_det, opts, new_let, is_discursive=False
                    )

        # Fallback de explicação
        if not new_exp_text:
            cursor.execute("SELECT explanation_text FROM explanations WHERE question_id = ?", (qid,))
            cur_exp = cursor.fetchone()
            old_exp_str = cur_exp["explanation_text"] if cur_exp else ""
            new_exp_text = rebuild_fallback_explanation(old_exp_str, new_let, old_let)

        # 2. Executar updates no SQLite local
        cursor.execute("UPDATE questions SET correct_letter = ? WHERE id = ?", (new_let, qid))
        cursor.execute("UPDATE alternatives SET is_correct = 1 WHERE question_id = ? AND letter = ?", (qid, new_let))
        cursor.execute("UPDATE alternatives SET is_correct = 0 WHERE question_id = ? AND letter != ?", (qid, new_let))
        cursor.execute(
            "UPDATE explanations SET explanation_text = ?, reviewed_at = ? WHERE question_id = ?",
            (new_exp_text, now_iso, qid)
        )

        total_corrected += 1

        # 3. Preparar statements para Turso Cloud
        turso_stmts.extend([
            {
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE questions SET correct_letter = ? WHERE id = ?",
                    "args": [{"type": "text", "value": new_let}, {"type": "integer", "value": str(qid)}]
                }
            },
            {
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE alternatives SET is_correct = 1 WHERE question_id = ? AND letter = ?",
                    "args": [{"type": "integer", "value": str(qid)}, {"type": "text", "value": new_let}]
                }
            },
            {
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE alternatives SET is_correct = 0 WHERE question_id = ? AND letter != ?",
                    "args": [{"type": "integer", "value": str(qid)}, {"type": "text", "value": new_let}]
                }
            },
            {
                "type": "execute",
                "stmt": {
                    "sql": "UPDATE explanations SET explanation_text = ?, reviewed_at = ? WHERE question_id = ?",
                    "args": [
                        {"type": "text", "value": new_exp_text},
                        {"type": "text", "value": now_iso},
                        {"type": "integer", "value": str(qid)}
                    ]
                }
            }
        ])

        if idx % 500 == 0 or idx == len(candidates):
            conn.commit()
            logger.info("Processadas %d/%d questões locais...", idx, len(candidates))

    conn.commit()
    conn.close()
    logger.info("Sucesso local! %d questões corrigidas no SQLite local.", total_corrected)

    # 4. Sincronização remota com Turso Cloud
    if sync_turso:
        url, token = get_turso_config()
        if not url or not token:
            logger.warning("Credenciais do Turso Cloud não configuradas. Sincronização remota pulada.")
            return

        logger.info("Iniciando sincronização remota com Turso Cloud (%d operações)...", len(turso_stmts))
        batch_size = 200  # 50 questões por lote (4 statements por questão)
        total_batches = (len(turso_stmts) + batch_size - 1) // batch_size

        for b_idx in range(total_batches):
            chunk = turso_stmts[b_idx * batch_size : (b_idx + 1) * batch_size]
            reqs = [{"type": "execute", "stmt": {"sql": "BEGIN"}}]
            reqs.extend(chunk)
            reqs.append({"type": "execute", "stmt": {"sql": "COMMIT"}})
            execute_turso_pipeline(url, token, reqs)
            if (b_idx + 1) % 10 == 0 or (b_idx + 1) == total_batches:
                logger.info("Turso Pipeline: lote %d/%d enviado com sucesso.", b_idx + 1, total_batches)

        logger.info("Sincronização remota com Turso Cloud concluída com 100% de sucesso!")


if __name__ == "__main__":
    sync = "--no-turso" not in sys.argv
    run_repair(sync_turso=sync)
