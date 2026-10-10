#!/usr/bin/env bash
# ==============================================================================
# MedQuest - Atalho para o Autoloop Blindado e Seguro
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

if command -v autoloop-medquest &> /dev/null; then
    exec autoloop-medquest "$@"
else
    exec python3 "/home/wagmoraes/.local/bin/autoloop-medquest" "$@"
fi
