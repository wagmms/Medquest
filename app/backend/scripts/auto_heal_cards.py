#!/usr/bin/env python3
"""
MedQuest - Auto-Heal Flashcards (Google Gemini AI)
Wrapper para execução a partir de app/backend/scripts/.
"""
import os
import sys
from pathlib import Path

# Redireciona para o script canônico em scripts/auto_heal_cards.py
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
CANONICAL_SCRIPT = ROOT_DIR / "scripts" / "auto_heal_cards.py"

if not CANONICAL_SCRIPT.exists():
    raise FileNotFoundError(f"Script canônico não encontrado em {CANONICAL_SCRIPT}")

# Executa o script canônico preservando sys.argv
with open(CANONICAL_SCRIPT, "r", encoding="utf-8") as f:
    code = compile(f.read(), str(CANONICAL_SCRIPT), "exec")
    exec(code, {"__name__": "__main__", "__file__": str(CANONICAL_SCRIPT)})
