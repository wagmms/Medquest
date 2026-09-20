#!/usr/bin/env bash
# ==============================================================================
# MedQuest - Deploy Unificado & Sincronizacao de Banco de Dados (Linux / macOS)
# ==============================================================================
# Executa em um unico comando:
#   1. Sincronizacao incremental do banco local SQLite com Turso Cloud (Online)
#   2. Commit e Push no Git (aciona deploy automatico no Vercel e Render)
#   3. Opcional: Atualizacao de containers Docker na VPS via SSH (--vps)
#
# Exemplos de uso:
#   ./deploy.sh
#   ./deploy.sh "Atualizacao de questoes e explicacoes"
#   ./deploy.sh --db-only       # Apenas sincroniza o banco sem git/deploy
#   ./deploy.sh --skip-db      # Pula sincronizacao do banco
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

python3 deploy.py "$@"
